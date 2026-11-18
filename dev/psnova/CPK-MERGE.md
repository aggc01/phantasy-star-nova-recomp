# CPK merge (rePatch archive + one missing entry)

Tool: `dev/psnova/cpk_merge.py <base.cpk> <out.cpk> --add <source.cpk>:<entry name> [--add ...]`
(Python 3.14, standard library, imports `cpk.py` unchanged.)

Built with:

    python -I cpk_merge.py  .../repatch0/NOVA_FileList_Vita_patch.cpk
                            .../merged/NOVA_FileList_Vita_patch.cpk
                            --add .../patch0/NOVA_FileList_Vita_patch.cpk:tex_nova_ui_common.aif

Output: `dump/decrypted/PCSG00351/merged/NOVA_FileList_Vita_patch.cpk`, 233,706,960 bytes
(base 232,657,896 + 1,049,064).

## What the tool does

Copies the base archive and adds the named entries. The added file's stored bytes, FileSize and
ExtractSize are copied verbatim from the source archive. It refuses (does not guess) if the base
has an ITOC, GTOC, HTOC or HGTOC, has no ETOC, has directory names, is not sorted by the rule
below, or if a constant TOC column differs between base and source (it would have to change a
column's storage, which it never does).

## Format facts relied on (checked on the real archives)

- Header `CPK ` chunk at 0: magic, u32 flag, u64 size (0x350), then the @UTF table at 0x10.
  `TOC ` and `ETOC` chunks have the same 16-byte chunk header (magic, u32 flag, u64 chunk size =
  table size + 8). Base flag = 0xFF and tables unscrambled; the 1.05 archive has flag 0 and
  scrambled tables. The tool keeps each table's state per archive (here: all unscrambled).
- Base header: TocOffset 2048, ContentOffset 1,092,864, EtocOffset 232,473,512 (= ContentOffset +
  ContentSize, file ends exactly at ETOC end), Align 8, Sorted 1, Files 23,033. No ITOC, GTOC,
  HTOC. FileOffset is relative to min(TocOffset, ContentOffset) = 2048 (as in cpk.py).
- The TOC (2048..1,000,712) is followed by 92,152 zero bytes before ContentOffset. The TOC can
  grow in place there.
- TOC columns: DirName (constant ''), FileName, FileSize, ExtractSize, FileOffset (u64), ID,
  UserString (constant '<NULL>'). Row width 24. Strings area is at the end; no data area.
- Row order rule: byte order of the upper-cased file name (flat archive, `sorted(key=upper)`
  is true for all 23,033 base rows; plain and lower-cased orders are not). The new name
  `tex_nova_ui_common.aif` therefore goes at row 22,915, between `tex_nova_Result.aif` and
  `tex_nova_ui_Title.aif`.
- In the base, ID == row index for every row. In the 1.05 archive IDs are not row indexes, and
  that archive works in the game, so the game does not need ID == row index (not proven for
  the CRI library itself).
- ETOC: columns UpdateDateTime (u64 per row), LocalDir (constant ''). It has Files + 1 rows; the
  last row is all zero in both archives (treated as a terminator and left last). Row i is taken
  to belong to TOC row i (assumed, not documented in cpk.py).
- Header sums: EnabledPackedSize = 2 x sum(ExtractSize); EnabledDataSize = sum(ExtractSize) +
  sum(FileSize). Both hold exactly on the base and on the 1.05 archive, so they were updated
  with the same formula (+2,098,112 each).

## Choices

- Layout: header table patched in place (same size); TOC rewritten at the same offset (grows by 48
  bytes into the zero slack); old content area copied byte for byte; new file data appended at the
  old ETOC offset (8-aligned); new ETOC after it. Reason: ContentOffset and every base FileOffset
  stay exactly as they were, so base entries are untouched and the diff is tiny and easy to audit.
  Re-serialising everything would have moved all data for no gain.
- Header fields changed: ContentSize, TocSize, EtocOffset, EtocSize, Files (23,034),
  EnabledPackedSize, EnabledDataSize. Nothing else.
- All base IDs kept. New entry ID = max ID + 1 = 23,033 (unique). Consequence: ID is no longer
  equal to the row index for rows after 22,914 (those rows now sit one row later). A packer
  that renumbers would shift 118 IDs; I chose not to, to keep base IDs identical.
- New TOC row: FileName string appended at the end of the strings area (old strings region kept
  verbatim, then the new name, then zero padding to 8). No column changed storage; none of
  the constants needed converting.
- New ETOC row: the 1.05 archive's own UpdateDateTime value for that entry
  (07df020600253000), inserted at row 22,915.
- GTOC/ITOC/HTOC: none in either archive, nothing to change.

## Self-check results (all passed)

- cpk.py list on the output: 23,034 entries, header.Files = 23,034, index TOC, no errors.
- All 23,033 base entries present with identical name, ID, FileSize, ExtractSize, sha1 of stored
  bytes, and identical absolute offset.
- New entry: ID 23,033, size 1,049,056, ExtractSize 1,049,056, sha1 of stored bytes
  96f8f6244d1ff087e9488e2b70b5ac35d0ab4182 (match). `cpk.py extract --match
  tex_nova_ui_common.aif` extracts 1 file, no length warnings, same sha1.
- Header values vs file: TocOffset 2048 + TocSize 998,712 = 1,000,760 <= ContentOffset 1,092,864;
  ContentOffset + ContentSize = 233,522,568 = EtocOffset; EtocOffset + EtocSize (184,392) =
  233,706,960 = file size. TOC and ETOC chunk size fields = table size + 8; magics and flag
  bytes (0xFF) unchanged.
- TOC and ETOC: same column definitions (names, flags, types), same row width, same table name
  offset; all base TOC rows equal after decoding (names, sizes, FileOffset, ID); all base ETOC
  rows equal; new rows are at row 22,915.
- Order: entry names are sorted by the base's rule across the whole output.
- Byte diff against base: 0..0x800 differs in 15 bytes (offsets 289..343: the changed header
  fields); 0x800..ContentOffset (TOC) differs from the insert point on (rows shifted by 24
  bytes, string offsets after the strings area start, plus the new row and string); content
  area 1,092,864..232,473,512 is byte-identical (sha1 compared); appended: 1,049,056 bytes of
  file data at 232,473,512; new ETOC at 233,522,568 (base ETOC differs only by the inserted
  8-byte row).

## NOT verified

- The game's CRI library has not read this archive. Things it could be picky about that I could
  not test: IDs no longer equal to row index after row 22,914; ETOC row-to-TOC-row mapping
  (assumed by index); the unusual-looking (but copied) ETOC date of the new row; the file
  data sitting after old content rather than in sorted order (offsets in the base are not in
  row order either, since the tool only appends).
- If the game refuses the archive, the first alternative to try is renumbering IDs to equal
  row index (what a CRI packer produces), then changing the new ETOC date to the base's
  usual value.
