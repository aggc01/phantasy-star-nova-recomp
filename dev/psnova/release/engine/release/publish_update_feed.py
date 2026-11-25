"""Maintainer tool: sign and publish an update feed for Phantasy Star Nova Recomp. Not used by players.

  keygen   --private KEY --public KEY.pub        a new Ed25519 key pair (the private key is a hex seed: keep it out of the release)
  publish  --private KEY --out FEED --release N --version V (--notes TEXT | --notes-file FILE)
           [--channel stable] [--engine-root DIR] [--localization-root DIR] [--min-updater 1] [--components engine,text,movies]
  verify   --public KEY.pub --feed FEED [--channel stable]       check a feed the way Setup does

A feed is plain files, so any static host serves it:  <feed>/<channel>/manifest.json, manifest.sig (hex) and
payloads/<kind>-<content>.zip. The manifest lists, per component, the payload name, its size and SHA-256 and the SHA-256 of the
unpacked files; it is signed with the key whose public half is pinned in a release's engine\\release\\update.json. Run with the
release's own Python:  engine\\python\\python.exe -B engine\\release\\publish_update_feed.py ...
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine" / "decrypt"))
import setup_updates as U  # noqa: E402
from Crypto.PublicKey import ECC  # noqa: E402
from Crypto.Signature import eddsa  # noqa: E402

FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def load_private(path):
    return ECC.construct(curve="Ed25519", seed=bytes.fromhex(Path(path).read_text(encoding="ascii").strip()))


def keygen(args):
    key = ECC.generate(curve="Ed25519")
    Path(args.private).write_text(key.seed.hex() + "\n", encoding="ascii")
    Path(args.public).write_text(key.public_key().export_key(format="raw").hex() + "\n", encoding="ascii")
    print(f"public key (pin this in update.json): {Path(args.public).read_text().strip()}")


def build_payload(kind, root, out_dir):
    files = U.list_component(kind, root)
    if not files:
        raise SystemExit(f"nothing to publish for {kind} under {root}")
    content = U.tree_sha256(files)
    name = f"{kind}-{content[:16]}.zip"
    target = out_dir / name
    if not target.is_file():
        temporary = target.with_name(name + ".part")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for relative, path in files.items():
                info = zipfile.ZipInfo(relative, FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        temporary.replace(target)
    payload = target.read_bytes()
    return {"payload": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "content_sha256": content,
            "files": len(files), "rebuild": U.REBUILD[kind]}


def publish(args):
    key = load_private(args.private)
    engine_root = Path(args.engine_root or ROOT / "engine")
    localization_root = Path(args.localization_root or ROOT / "localization")
    roots = {"engine": engine_root, "text": localization_root, "movies": localization_root}
    out_dir = Path(args.out) / args.channel
    (out_dir / "payloads").mkdir(parents=True, exist_ok=True)
    notes = args.notes if args.notes is not None else Path(args.notes_file).read_text(encoding="utf-8")
    kinds = [k for k in args.components.split(",") if k]
    manifest = {"schema": 1, "app": U.APP_ID, "channel": args.channel, "release": args.release, "version": args.version,
                "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "min_updater": args.min_updater,
                "notes": notes.strip(), "components": {k: build_payload(k, roots[k], out_dir / "payloads") for k in kinds}}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    signature = eddsa.new(key, "rfc8032").sign(U.SIGN_PREFIX + manifest_bytes)
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    (out_dir / "manifest.sig").write_text(signature.hex() + "\n", encoding="ascii")
    print(f"published release {args.release} ({args.version}) to {out_dir}")
    for kind, item in manifest["components"].items():
        print(f"  {kind:7} {item['size']:>12,} bytes  {item['payload']}  content {item['content_sha256'][:16]}")


def verify(args):
    config = U.Config(enabled=True, channel=args.channel, public_key=bytes.fromhex(Path(args.public).read_text().strip()))
    base = Path(args.feed) / args.channel
    manifest = U.verify_manifest((base / "manifest.json").read_bytes(), bytes.fromhex((base / "manifest.sig").read_text().strip()), config)
    for kind, item in manifest["components"].items():
        U.verify_payload(base / "payloads" / item["payload"], item["size"], item["sha256"])
    print(f"feed OK: release {manifest['release']} ({manifest['version']}), components {', '.join(manifest['components'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    k = commands.add_parser("keygen")
    k.add_argument("--private", required=True)
    k.add_argument("--public", required=True)
    p = commands.add_parser("publish")
    p.add_argument("--private", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--release", type=int, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--notes")
    p.add_argument("--notes-file")
    p.add_argument("--channel", default="stable")
    p.add_argument("--engine-root")
    p.add_argument("--localization-root")
    p.add_argument("--min-updater", type=int, default=1)
    p.add_argument("--components", default="engine,text,movies")
    v = commands.add_parser("verify")
    v.add_argument("--public", required=True)
    v.add_argument("--feed", required=True)
    v.add_argument("--channel", default="stable")
    args = parser.parse_args()
    if args.command == "publish" and args.notes is None and not args.notes_file:
        parser.error("publish needs --notes or --notes-file")
    {"keygen": keygen, "publish": publish, "verify": verify}[args.command](args)


if __name__ == "__main__":
    main()
