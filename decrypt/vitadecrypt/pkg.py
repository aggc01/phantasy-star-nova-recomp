"""Vita PKG (+ licence file) -> a NoNpDrm-style extracted folder.

A PKG is one AES-128-CTR-encrypted blob (keyed off a per-package IV wrapped
under one of a handful of retail "PKG_VITA_KEY" constants, selected by a
small field in the extended header) holding a packed file table and the raw
file contents one after another. This only undoes *that* outer layer: the
files that come out the other end (eboot.bin, sce_module/*.suprx, sce_pfs/,
sce_sys/...) are exactly the NoNpDrm-style, still-PFS-encrypted tree pfs.py
expects -- see game.py for the rest of the pipeline.

Ported from Vita3K's packages/src/pkg.cpp, which itself credits mmozeiko's
pkg2zip; field names/sizes are pkg2zip's/Vita3K's packages/include/packages/pkg.h.
Everything in a PKG is big-endian, unlike the rest of this package's little-
endian Vita formats -- pkg2zip's comments call this out too.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import struct

from Crypto.Cipher import AES
from Crypto.Util import Counter

from . import keys as K
from . import sfo as SFO
from . import rif as RIF

_HEADER = struct.Struct(
    ">IHHIIIIQQQ48s16s16s64s"
)  # magic,revision,type,info_offset,info_count,header_size,file_count,total_size,data_offset,data_size,content_id,digest,pkg_data_iv,pkg_signatures
assert _HEADER.size == 0xC0

_EXT_HEADER = struct.Struct(">6IQ4I2Q")  # ... data_type2 is the 9th word
assert _EXT_HEADER.size == 0x40

_ENTRY = struct.Struct(">IIQQII")  # name_offset,name_size,data_offset,data_size,type,padding
assert _ENTRY.size == 0x20

PKG_MAGIC = 0x7F504B47     # "\x7fPKG"
EXT_MAGIC = 0x7F657874     # "\x7fext"
ENTRY_TYPE_DIR = {4, 18}

CONTENT_TYPE_APP = 0x15
CONTENT_TYPE_DLC = 0x16
CONTENT_TYPE_THEME = 0x1F

CHUNK = 8 * 1024 * 1024        # extract_pkg streams each file through memory this much at a time (a multiple of 16)
MAX_ENTRIES = 200_000
MAX_NAME_BYTES = 1024
WINDOWS_MAX_PATH = 259
LICENSE_NAME = "sce_sys/package/work.bin"
_RESERVED_NAMES = frozenset({"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)})
_FORBIDDEN_CHARS = frozenset('<>:"|?*\\') | frozenset(chr(i) for i in range(32))


class PkgError(ValueError):
    pass


def unsafe_name_reason(name: str) -> str | None:
    """Why `name` (a '/'-separated path from a PKG's file table) must not become a file on Windows, or None if it is
    fine: an absolute or drive path, '.' or '..' parts, a character or device name Windows does not allow, a
    trailing dot or space."""
    if not name:
        return "it is empty"
    if name.startswith("/"):
        return "it is an absolute path"
    parts = name.split("/")
    if parts[-1] == "":
        parts.pop()          # (a directory entry written with a trailing slash)
    for part in parts:
        if part in ("", ".", ".."):
            return "it has an empty, '.' or '..' part"
        bad = next((c for c in part if c in _FORBIDDEN_CHARS), None)
        if bad is not None:
            return "it has the character %r, which Windows file names cannot contain (or it is a drive or stream path)" % bad
        if part.endswith((" ", ".")):
            return "a part ends with a space or a dot"
        if part.split(".")[0].rstrip(" ").upper() in _RESERVED_NAMES:
            return f"{part!r} is a reserved Windows device name"
        if len(part) > 255:
            return "a part is longer than 255 characters"
    return None


@dataclasses.dataclass
class PkgEntry:
    name: str
    offset: int      # of the contents, from the start of the encrypted data region
    size: int
    is_dir: bool


@dataclasses.dataclass
class PkgView:
    """A PKG's identity and its checked file table: what a hub or setup shows before anything is extracted."""
    info: "PkgInfo"
    entries: list
    params: tuple    # (main key, IV, data region offset, file table offset, file count)

    def entry(self, name: str):
        return next((e for e in self.entries if e.name == name and not e.is_dir), None)

    def read_entry(self, read, name: str, limit: int = 1 << 20) -> bytes | None:
        """A small member's decrypted bytes (a licence file), or None if the PKG has no such file."""
        entry = self.entry(name)
        if entry is None:
            return None
        if entry.size > limit:
            raise PkgError(f"{name} is {entry.size} bytes, more than the {limit} a PKG's licence file should be")
        main_key, iv, data_offset, _items, _count = self.params
        return _cipher_at(main_key, iv, entry.offset).decrypt(read(data_offset + entry.offset, entry.size))


@dataclasses.dataclass
class PkgInfo:
    kind: str                  # "app" | "patch" | "dlc" | "theme"
    title_id: str
    content_id: str
    title: str
    app_version: str
    sfo: dict


def _ctr_decrypt(main_key: bytes, iv: bytes, offset_blocks: int, data: bytes) -> bytes:
    """AES-128-CTR starting at block `offset_blocks` (16 bytes/block) from a
    base IV -- pkg2zip/Vita3K's ctr_init() is just big-endian (iv + n)."""
    ctr_val = (int.from_bytes(iv, "big") + offset_blocks) & ((1 << 128) - 1)
    ctr = Counter.new(128, initial_value=ctr_val)
    return AES.new(main_key, AES.MODE_CTR, counter=ctr).decrypt(data)


def _cipher_at(main_key: bytes, iv: bytes, offset: int):
    """An AES-CTR keystream positioned at byte `offset` of the encrypted region, for a stream of decrypt() calls."""
    block, lead = divmod(offset, 16)
    ctr = Counter.new(128, initial_value=(int.from_bytes(iv, "big") + block) & ((1 << 128) - 1))
    cipher = AES.new(main_key, AES.MODE_CTR, counter=ctr)
    if lead:
        cipher.decrypt(bytes(lead))
    return cipher


def _head(read, size: int) -> tuple[PkgInfo, tuple]:
    """The header, the info table and the embedded param.sfo, through read(offset, n): the PKG's identity, and what
    extract_pkg needs to walk its files (main key, IV, data offset, file table offset, file count). The outer layer's
    key is a retail constant, so this needs no licence."""
    if size < _HEADER.size + _EXT_HEADER.size:
        raise PkgError("file too short to be a PKG")
    head = read(0, _HEADER.size + _EXT_HEADER.size)

    (magic, _rev, _type, info_offset, info_count, _header_size, file_count,
     total_size, data_offset, _data_size, content_id_raw, _digest, pkg_data_iv,
     _sigs) = _HEADER.unpack_from(head, 0)
    if magic != PKG_MAGIC:
        raise PkgError(f"bad PKG magic 0x{magic:08X}")
    if size < total_size:
        raise PkgError("file is smaller than the header's own total_size -- truncated download?")

    ext_words = _EXT_HEADER.unpack_from(head, _HEADER.size)
    ext_magic, data_type2 = ext_words[0], ext_words[8]
    if ext_magic != EXT_MAGIC:
        raise PkgError(f"bad PKG ext-header magic 0x{ext_magic:08X}")

    content_id = content_id_raw.rstrip(b"\x00").decode("ascii", "replace")

    # Walk the little type/size/payload info table for content_type, the file
    # table offset, and the embedded param.sfo's location -- pkg.cpp reads a
    # fixed 16 bytes per entry but only advances by 8 + size.
    content_type = sfo_offset = sfo_size = items_offset = 0
    off = info_offset
    if info_count > 1024:
        raise PkgError(f"the header lists {info_count} info blocks -- corrupted PKG")
    for _ in range(info_count):
        block = struct.unpack_from(">4I", read(off, 16), 0)
        btype, bsize = block[0], block[1]
        if btype == 2:
            content_type = block[2]
        elif btype == 13:
            items_offset = block[2]
        elif btype == 14:
            sfo_offset, sfo_size = block[2], block[3]
        off += 8 + bsize

    if content_type == CONTENT_TYPE_APP:
        kind = "app"
    elif content_type == CONTENT_TYPE_DLC:
        kind = "dlc"
    elif content_type == CONTENT_TYPE_THEME:
        kind = "theme"
    else:
        raise PkgError(f"unsupported content type 0x{content_type:X} (only Vita app/DLC/theme PKGs are supported)")

    key_type = data_type2 & 7
    pkg_vita_key = K.PKG_VITA_KEYS.get(key_type)
    if pkg_vita_key is None:
        raise PkgError(f"unknown PKG key revision {key_type} (only 2-4 are known retail keys)")
    main_key = AES.new(pkg_vita_key, AES.MODE_ECB).encrypt(pkg_data_iv)

    sfo_bytes = read(sfo_offset, sfo_size)   # (unencrypted, at its offset from the file's start: Vita3K's pkg.cpp, pkg2zip)
    app_sfo = SFO.parse_sfo(sfo_bytes)
    app_info = SFO.get_app_info(app_sfo)

    if kind == "app" and app_info.category == "gp":
        kind = "patch"  # same content_type as a full app; Vita3K tells them apart via the SFO

    info = PkgInfo(
        kind=kind,
        title_id=app_info.title_id,
        content_id=content_id or app_info.content_id,
        title=app_info.title,
        app_version=app_info.app_version,
        sfo=app_sfo,
    )
    return info, (main_key, pkg_data_iv, data_offset, items_offset, file_count)


def peek_pkg(pkg_path: str) -> PkgInfo:
    """What a PKG is (app, patch, add-on), its title and version, without a licence and without reading the gigabytes
    after its header (the hub's folder scan)."""
    with open(pkg_path, "rb") as f:
        size = os.path.getsize(pkg_path)
        return _head(_checked_reader(f, size), size)[0]


def _checked_reader(f, size: int):
    """read(offset, n) over an open file that fails clearly, rather than returning short data, past the end."""
    def read(offset: int, n: int) -> bytes:
        if offset < 0 or offset + n > size:
            raise PkgError("the file ends before its own header says it does -- truncated download?")
        f.seek(offset)
        data = f.read(n)
        if len(data) != n:
            raise PkgError("the file ended while it was being read -- truncated or still downloading?")
        return data
    return read


def _entries(read, size: int, params: tuple) -> list:
    """The file table, decrypted and checked before any file is written: every offset inside the file, every name
    safe to create on Windows, no name twice (Windows file names ignore case), no file that is also a folder."""
    main_key, iv, data_offset, items_offset, file_count = params
    if file_count > MAX_ENTRIES:
        raise PkgError(f"the header lists {file_count} files -- corrupted PKG")
    if data_offset > size or data_offset + items_offset + file_count * _ENTRY.size > size:
        raise PkgError("the file table runs past the end of the file -- truncated or corrupted PKG")
    region = size - data_offset
    table = _cipher_at(main_key, iv, items_offset).decrypt(read(data_offset + items_offset, file_count * _ENTRY.size))
    entries, seen = [], {}
    for i in range(file_count):
        name_offset, name_size, f_offset, f_size, f_type, _pad = _ENTRY.unpack_from(table, i * _ENTRY.size)
        if not 0 < name_size <= MAX_NAME_BYTES or name_offset + name_size > region:
            raise PkgError(f"entry {i}: its name runs past the end of the file -- wrong key or corrupted PKG")
        is_dir = (f_type & 0xFF) in ENTRY_TYPE_DIR
        if not is_dir and f_offset + f_size > region:
            raise PkgError(f"entry {i}: offsets run past end of file -- wrong key or corrupted PKG")
        raw = _cipher_at(main_key, iv, name_offset).decrypt(read(data_offset + name_offset, name_size))
        try:
            name = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise PkgError(f"entry {i}: unreadable file name -- wrong key or corrupted PKG") from None
        reason = unsafe_name_reason(name)
        if reason:
            raise PkgError(f"entry {i}: unsafe name {name!r}: {reason}")
        name = name.rstrip("/")
        folded = name.lower()
        if folded in seen:
            raise PkgError(f"entry {i}: {name!r} is listed twice (as {seen[folded].name!r}); Windows would merge them")
        seen[folded] = PkgEntry(name, f_offset, f_size, is_dir)
        entries.append(seen[folded])
    for entry in entries:
        parts = entry.name.lower().split("/")
        for depth in range(1, len(parts)):
            owner = seen.get("/".join(parts[:depth]))
            if owner is not None and not owner.is_dir:
                raise PkgError(f"{entry.name!r} is inside {owner.name!r}, which is a file")
    return entries


def inspect_pkg(read, size: int) -> PkgView:
    """A PKG's identity and its checked file table, through read(offset, n); nothing is extracted. Everything it reads
    lies near the start of the file, so a stream that can only be read forward (a ZIP member) can serve `read`."""
    info, params = _head(read, size)
    return PkgView(info, _entries(read, size, params), params)


def inspect_pkg_file(pkg_path: str) -> PkgView:
    with open(pkg_path, "rb") as f:
        size = os.path.getsize(pkg_path)
        return inspect_pkg(_checked_reader(f, size), size)


def extract_pkg(pkg_path: str, out_dir: str, *, rif_path: str | None = None, progress=None) -> PkgInfo:
    """Decrypt `pkg_path` into `out_dir` (created if missing) as a flat,
    still-PFS-encrypted NoNpDrm-style tree, plus `sce_sys/package/work.bin`
    built from the given .rif licence file (optional -- without one, work.bin
    is simply not written, and pfs.py/game.py will need an explicit
    --klicensee instead).

    The file table is checked first (offsets, Windows-safe names), then each file is decrypted CHUNK bytes at a time,
    so a multi-gigabyte PKG needs only that much memory. progress(done, total) is called as bytes are written."""
    size = os.path.getsize(pkg_path)
    with open(pkg_path, "rb") as f:
        read = _checked_reader(f, size)
        view = inspect_pkg(read, size)
        info = view.info
        main_key, pkg_data_iv, data_offset, _items_offset, _count = view.params

        base = os.path.abspath(out_dir)
        if os.name == "nt":
            longest = max((e for e in view.entries), key=lambda e: len(e.name), default=None)
            if longest and len(base) + 1 + len(longest.name) > WINDOWS_MAX_PATH:
                raise PkgError(f"{longest.name!r} would be {len(base) + 1 + len(longest.name)} characters long under "
                               f"{base}, over the Windows limit of {WINDOWS_MAX_PATH}. Use a shorter folder path.")
        os.makedirs(out_dir, exist_ok=True)

        total = sum(e.size for e in view.entries if not e.is_dir)
        done = 0
        for entry in view.entries:
            dest = os.path.join(out_dir, *entry.name.split("/"))
            if entry.is_dir:
                os.makedirs(dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            cipher = _cipher_at(main_key, pkg_data_iv, entry.offset)
            f.seek(data_offset + entry.offset)
            left = entry.size
            with open(dest, "wb") as out:
                while left:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        raise PkgError(f"{entry.name}: the file ended inside this entry -- truncated PKG")
                    out.write(cipher.decrypt(chunk))
                    left -= len(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)

    rif = None
    if rif_path:
        with open(rif_path, "rb") as f:
            rif = f.read()
    if rif is not None:
        work_dir = os.path.join(out_dir, "sce_sys", "package")
        os.makedirs(work_dir, exist_ok=True)
        with open(os.path.join(work_dir, "work.bin"), "wb") as f:
            f.write(rif)

    return info


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python3 -m vitadecrypt.pkg",
        description="Extract a Vita PKG (+ .rif licence file) into a NoNpDrm-style folder (still PFS-encrypted).",
    )
    p.add_argument("pkg", nargs="?")
    p.add_argument("outdir", nargs="?")
    p.add_argument("--rif")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest or not (args.pkg and args.outdir):
        _selftest()
        return 0

    info = extract_pkg(args.pkg, args.outdir, rif_path=args.rif)
    print(f"{info.kind} {info.title_id} {info.content_id!r} {info.title!r} v{info.app_version}")
    print(f"extracted to {args.outdir}")
    return 0


def _pad16(b: bytes) -> bytes:
    return b + b"\x00" * (-len(b) % 16)


def _build_synthetic_pkg(
    tmp_sfo: bytes, files: dict[str, bytes], *, key_type: int = 2, content_type: int = CONTENT_TYPE_APP,
    content_id: str = "IP0177-PCSB00013_00-GOLFDS00000000",
) -> bytes:
    """Build a byte-exact PKG (same header/info-table/entry/AES-CTR layout as
    a real retail one) so pkg.py can be tested without a real game.
    Intentionally reimplements the *encrypt* side independently of
    extract_pkg's decrypt side (same primitives, inverse order, built up
    section by section here instead of extract_pkg's single-region read) so
    the test is not circular. Every section below is kept 16-byte aligned so
    each one's AES-CTR counter offset (byte_offset // 16) is exact.
    """
    pkg_data_iv = bytes(range(16))
    main_key = AES.new(K.PKG_VITA_KEYS[key_type], AES.MODE_ECB).encrypt(pkg_data_iv)

    def enc(offset_blocks: int, plain: bytes) -> bytes:
        ctr_val = (int.from_bytes(pkg_data_iv, "big") + offset_blocks) & ((1 << 128) - 1)
        return AES.new(main_key, AES.MODE_CTR, counter=Counter.new(128, initial_value=ctr_val)).encrypt(plain)

    names = list(files)
    blobs = [files[n] for n in names]
    name_blobs = [n.encode("utf-8") for n in names]

    # A retail PKG's layout: header, info table, the param.sfo unencrypted (the info table's type 14 gives its offset
    # from the file's start), then the encrypted data region, whose offsets are relative to the header's data_offset:
    # [entry table][names...][file data...]
    items_offset = 0
    body_offset = items_offset + len(names) * _ENTRY.size  # _ENTRY.size (32) is already 16-aligned

    name_offsets, data_offsets = [], []
    cursor = body_offset
    for nb in name_blobs:
        name_offsets.append(cursor)
        cursor += len(_pad16(nb))
    for blob in blobs:
        data_offsets.append(cursor)
        cursor += len(_pad16(blob))
    region_size = cursor

    region = bytearray(region_size)
    entries = bytearray()
    for nb, blob, noff, doff in zip(name_blobs, blobs, name_offsets, data_offsets):
        entries += _ENTRY.pack(noff, len(nb), doff, len(blob), 1, 0)
        region[noff: noff + len(nb)] = nb
        region[doff: doff + len(blob)] = blob
    region[items_offset: items_offset + len(entries)] = bytes(entries)

    region_enc = enc(0, bytes(region))

    info_offset = _HEADER.size + _EXT_HEADER.size
    sfo_offset = info_offset + 3 * 16   # (just after the three-entry info table)
    info_table = (
        struct.pack(">4I", 2, 8, content_type, 0)
        + struct.pack(">4I", 13, 8, items_offset, 0)
        + struct.pack(">4I", 14, 8, sfo_offset, len(tmp_sfo))
    )
    data_offset_abs = sfo_offset + len(_pad16(tmp_sfo))
    total_size = data_offset_abs + region_size

    header = _HEADER.pack(
        PKG_MAGIC, 1, 0, info_offset, 3, _HEADER.size, len(names),
        total_size, data_offset_abs, region_size,
        content_id.encode("ascii").ljust(48, b"\x00"), bytes(16), pkg_data_iv, bytes(64),
    )
    ext_header = _EXT_HEADER.pack(EXT_MAGIC, 0, _EXT_HEADER.size, 0, 0, 0, 0, 0, key_type, 0, 0, 0, 0)
    return header + ext_header + info_table + _pad16(tmp_sfo) + region_enc


def _selftest() -> None:
    tmp_sfo = SFO.build_sfo({
        "APP_VER": "01.00", "CATEGORY": "gd", "TITLE_ID": "PCSB00013",
        "CONTENT_ID": "IP0177-PCSB00013_00-GOLFDS00000000", "TITLE": "Self Test Golf",
    })
    files = {
        "eboot.bin": b"\x7fELF-fake-eboot-for-test\x00" * 4,
        "sce_sys/param.sfo": tmp_sfo,
        "sce_module/libc.suprx": b"SCE\x00-fake-suprx-for-test",
    }
    pkg_bytes = _build_synthetic_pkg(tmp_sfo, files, key_type=3)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pkg_path = os.path.join(tmp, "test.pkg")
        out_dir = os.path.join(tmp, "out")
        with open(pkg_path, "wb") as f:
            f.write(pkg_bytes)

        klic = bytes.fromhex("00112233445566778899aabbccddeeff")[:16]
        rif_path = os.path.join(tmp, "fake.rif")
        with open(rif_path, "wb") as f:
            f.write(RIF.build_rif("IP0177-PCSB00013_00-GOLFDS00000000", klic))

        info = extract_pkg(pkg_path, out_dir, rif_path=rif_path)
        assert info.kind == "app", info.kind
        assert info.title_id == "PCSB00013", info.title_id
        assert info.content_id == "IP0177-PCSB00013_00-GOLFDS00000000"
        assert info.title == "Self Test Golf"

        for name, blob in files.items():
            got = open(os.path.join(out_dir, *name.split("/")), "rb").read()
            assert got == blob, f"{name}: extracted content differs"

        work = open(os.path.join(out_dir, "sce_sys", "package", "work.bin"), "rb").read()
        assert RIF.parse_rif(work).klicensee == klic

        # a PATCH pkg (same content_type, CATEGORY=gp) is told apart via the SFO
        patch_sfo = SFO.build_sfo({
            "APP_VER": "01.01", "CATEGORY": "gp", "TITLE_ID": "PCSB00013",
            "CONTENT_ID": "IP0177-PCSB00013_00-GOLFDS00000000", "TITLE": "Self Test Golf",
        })
        patch_pkg = _build_synthetic_pkg(patch_sfo, {"eboot.bin": b"patch-eboot"}, key_type=4)
        with open(pkg_path, "wb") as f:
            f.write(patch_pkg)
        info2 = extract_pkg(pkg_path, os.path.join(tmp, "out2"))
        assert info2.kind == "patch", info2.kind
        # the folder scan's peek: the same identity from the header alone
        peek = peek_pkg(pkg_path)
        assert (peek.kind, peek.title_id, peek.app_version) == ("patch", "PCSB00013", "1.01"), peek

        # wrong key_type garbles the file table -> must raise, not produce garbage files
        corrupt = bytearray(pkg_bytes)
        ext_off = _HEADER.size
        ext_vals = list(_EXT_HEADER.unpack_from(corrupt, ext_off))
        ext_vals[8] = 0  # data_type2's low 3 bits select the key; 0 is not in PKG_VITA_KEYS
        _EXT_HEADER.pack_into(corrupt, ext_off, *ext_vals)
        bad_path = os.path.join(tmp, "bad.pkg")
        with open(bad_path, "wb") as f:
            f.write(bytes(corrupt))
        try:
            extract_pkg(bad_path, os.path.join(tmp, "out3"))
            raise AssertionError("expected PkgError for an unknown key revision")
        except PkgError:
            pass

        # streaming: a file several chunks long, a chunk size that does not divide it, and the progress callback
        global CHUNK
        big = bytes(range(256)) * 9 + b"tail"
        stream_files = {"sce_sys/param.sfo": tmp_sfo, "data/big.bin": big, "empty.bin": b"", "work/lic": b"x" * 17}
        stream_pkg = os.path.join(tmp, "stream.pkg")
        with open(stream_pkg, "wb") as f:
            f.write(_build_synthetic_pkg(tmp_sfo, stream_files, key_type=2))
        saved_chunk, CHUNK = CHUNK, 48
        try:
            ticks = []
            extract_pkg(stream_pkg, os.path.join(tmp, "out4"), progress=lambda d, t: ticks.append((d, t)))
        finally:
            CHUNK = saved_chunk
        for name, blob in stream_files.items():
            got = open(os.path.join(tmp, "out4", *name.split("/")), "rb").read()
            assert got == blob, f"{name}: streamed content differs"
        assert ticks and ticks[-1][0] == ticks[-1][1] == sum(len(b) for b in stream_files.values()), ticks[-1:]

        # the table is checked before anything is written: unsafe Windows names, repeats, a truncated file
        for bad_name in ("a/../b", "/abs", "C:evil", "x\\y", "dir/CON.txt", "trail.", "a:b", "q?", "A/b", "a/B"):
            files_bad = {"ok.bin": b"1", bad_name: b"2"}
            if bad_name in ("A/b", "a/B"):
                files_bad = {"a/b": b"1", bad_name: b"2"}
            bad_pkg = os.path.join(tmp, "unsafe.pkg")
            with open(bad_pkg, "wb") as f:
                f.write(_build_synthetic_pkg(tmp_sfo, files_bad, key_type=2))
            target = os.path.join(tmp, "unsafe_out")
            try:
                extract_pkg(bad_pkg, target)
                raise AssertionError(f"expected PkgError for the name {bad_name!r}")
            except PkgError:
                assert not os.path.exists(target), f"{bad_name!r}: files were written before the table was rejected"
        with open(stream_pkg, "rb") as f:
            whole = f.read()
        cut = os.path.join(tmp, "cut.pkg")
        for keep in (len(whole) - 5, len(whole) // 2, 100):
            with open(cut, "wb") as f:
                f.write(whole[:keep])
            try:
                inspect_pkg_file(cut)
                raise AssertionError(f"expected PkgError for a PKG cut to {keep} bytes")
            except PkgError:
                pass

        # a licence file inside the PKG is readable without extracting; a PKG without one reports None
        license_bytes = RIF.build_rif("IP0177-PCSB00013_00-GOLFDS00000000", klic)
        with_license = os.path.join(tmp, "with_license.pkg")
        with open(with_license, "wb") as f:
            f.write(_build_synthetic_pkg(tmp_sfo, {"sce_sys/param.sfo": tmp_sfo, LICENSE_NAME: license_bytes}, key_type=4))
        with open(with_license, "rb") as f:
            seen = inspect_pkg(_checked_reader(f, os.path.getsize(with_license)), os.path.getsize(with_license))
            assert seen.read_entry(_checked_reader(f, os.path.getsize(with_license)), LICENSE_NAME) == license_bytes
        assert inspect_pkg_file(stream_pkg).entry(LICENSE_NAME) is None

    print("pkg.py self-test: OK")


if __name__ == "__main__":
    raise SystemExit(main())
