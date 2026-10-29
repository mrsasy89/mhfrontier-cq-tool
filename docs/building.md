# Conservative BIN building

The first writer preserves the original raw file and patches only verified fixed metadata. It is not a full serializer reconstruction. Uninterpreted bytes and existing absolute pointer graphs remain in place. Every export requires review and a client test.

## Workflow

1. `plan` uses the configured provider to propose a referenced quest plan.
2. `compile --project PLAN --id ID --notes TEXT --output SPEC` performs one more model turn and creates a typed specification. Notes resolve missing user choices. For the Gemini/OpenAI API alternatives, `compile --ask-key` provides the same scoped masked prompt as `plan --ask-key`; Codex account mode needs no key. The model receives supported fields and structured reference summaries; it cannot supply binary offsets, source paths or executable patches. The host binds the base and target ID and validates all variants in memory.
3. `build --spec SPEC --output-dir DIR --dry-run` validates and previews without exporting. `build` without `--dry-run` writes new BIN variants and a manifest to a new workspace directory. It makes no model call.

`spec-template --source PATH --id ID --output SPEC` starts a manual specification without AI. It gathers the available variants of the base ID. Native d0/n0 payloads may differ and are patched independently; identical source content shares backups but retains each output role. Ambiguous duplicate roles are rejected. The first profile supports up to 16 variants with filenames such as `65026d0.bin`; it never changes daytime flags merely from a filename.

`roundtrip PATH` compares a no-op opaque-preserving raw write against the original raw payload. With compressed input, ReFrontier processes an isolated copy first; the original compressed container remains unchanged. Byte identity of the decoded payload does not mean the container was recompressed identically.

## Supported fields

| Field | Initial writer behavior |
| --- | --- |
| Quest ID | 16-bit ID, reflected in five-digit output filenames (for example `00001d0.bin`) |
| Time limit | Whole minutes, converted to native 1800 ticks/minute |
| Stat table | Explicit bounded raw selector; no HP lookup or inferred stats |
| Variant selectors | Five explicit bytes at the verified offsets; no inferred form meanings |
| Quest flags | Four explicit bytes; no automatic HC/G inference |
| Finish requirement | Explicit raw byte; runtime semantics are not certified |
| Quest text | Eight named strings with strict CP932 encoding and read-back |
| Main/Sub A/Sub B | Nothing, Hunt, Capture, Slay, Damage, Slay_or_Damage, Slay_All and Slay_Total; species targets must exist in the final roster |

Null fields and an empty objective-edit list preserve the original values. Objective edits require corresponding text, preserve the unknown objective byte except when clearing to Nothing, and cannot introduce new duplicate active objectives. Native preexisting duplicates can be preserved. Unsupported objective types can remain untouched in the base but cannot be created by this writer.

Hash-bound spawn records, same-map position evidence and selected reward tables can be edited through append-only packages; see [authoring engine](AUTHORING-ENGINE.md). Native map packages, equipment, supplies and unknown fields remain preserved; arbitrary edits to those sections are unsupported. The writer accepts the studied raw layout with body at `0xC0`; other layouts are explicitly rejected for writing, even when the partial inspector can read them.

Changed strings are appended using a new eight-pointer table. Unchanged pointers still reference their original bytes. Only the fixed text-table pointer changes in the original file; old tables and strings remain intact, including aliases. The appended extension ends in the CQ Tool `ARCA` metadata footer so later CQ Tool processing can recognize it. This footer is editor metadata, not a repel or client-animation setting. Unrepresentable text, NULs and non-round-tripping CP932 characters are rejected.

Offsets and format definitions were compared with `src-tauri/src/editor/quest/quest_type_flags.rs`, `quest_string.rs`, `quest_file.rs`, `quest_end_flag.rs` and `offsets.rs` in [CQ Tool](https://github.com/mrsasy89/mhfrontier-cq-tool). This project uses its own conservative implementation rather than copying that serializer.

## Damage percentages

Damage quantity uses 100 damage points per raw unit. `damage --hp 13299 --percent 50` refuses an unrepresentable exact result. With `--rounding ceil`, quantity 67 represents 6700 points (about 50.38%); floor gives 66 / 6600. The helper reports the requested damage and effective percentage and flags a rounded threshold above reference HP. HP is supplied by the caller and is not independently verified or written to the monster. Compiler notes must specify the threshold or explicit rounding; the model must not invent an HP table.

## Export protections and evidence

All input hashes and filenames are checked, source originals are preserved by SHA256 and output files are read back. An occupied target ID belonging to a different base is rejected using corpus filenames; database availability is not checked. Output is restricted to a new directory under the configured workspace, outside the source corpus. Existing directories/builds are not overwritten. Failed exports keep a failed manifest rather than silently publishing a valid result.

The manifest records source/output hashes, original-byte differences, appended size, field summaries and the canonical specification hash. Every original byte outside the explicitly supported write ranges is checked for equality. The map, player stages and other protected fields are compared before/after; requested spawn/reward packages are reparsed and checked separately. This preserves native packages physically but is not a complete semantic validator for their contents.

Exports are raw/uncompressed. Automated recompression, encryption, server installation, database registration, event-file export and client execution are not performed. ReFrontier remains available for manual workflows. Gameplay compatibility, AI migration, completion logic and reward delivery require separate tests.

## Verified locally

No-op raw round trips passed for all 75 currently parsed corpus files, plus decoded native quest 21982; source hashes stayed unchanged. This is not analysis of the remaining compressed corpus.

A real Codex compilation produced a laboratory 65027 d0/n0 pair from base 65026, changing only the ID, title, Sub B text and Sub B Damage threshold to 10000 points. Each output is 13453 bytes: seven original bytes differ and 104 bytes are appended. An independent struct/byte-diff check confirmed the requested fields and preserved original bytes. The files were not installed or tested in the client. The first compiler attempt correctly remained blocked when it mixed runtime caveats into missing decisions; the schema now keeps nonblocking warnings separate from missing values.
