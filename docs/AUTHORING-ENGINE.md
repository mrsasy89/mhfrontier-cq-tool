# Evidence-led authoring engine

The shared CLI/desktop engine implements a portable quest-authoring procedure. It does not fine-tune a model, inherit private conversations, or gain new abilities simply by signing in. Every provider receives explicit domain rules, historical case limitations, the requested authoring choices and current hash-checked corpus evidence.

## Request to laboratory BIN

1. Interpret the prompt into species, alternatives versus a combined roster, map and native stage. The model receives the map's area/stage catalog; visible area numbers are not binary stage IDs.
2. Search the entire parsed corpus for complete bases and complementary per-species/placement records. Incomplete decoding coverage stays visible. Authored custom-range quests are labelled as evidence, never certified originals.
3. Let the model request additional typed, read-only corpus or item-name searches. The host executes them and sends bounded structural summaries without machine paths or raw BINs. There are at most four research rounds, six queries per round and sixty supplied reference hashes. Item searches keep ambiguity visible. External web browsing is not implemented by this host research loop; the source registry remains a research lead, not audited gameplay proof.
4. Review the plan, ask for missing user decisions, and compile supported typed edits. New titles/other explicit choices use `requested` confidence; `supported` claims require a supplied evidence ID. Invalid plans and typed edits receive up to three proposals with validation feedback. Provider/auth/quota failures never trigger a provider or billing fallback.
5. Recheck sources and validate every base variant in memory. Missing quantities, weights, thresholds or ambiguous objective/completion intent block export with specific questions. A future client test is a warning rather than a missing encoding parameter.
6. Export a new workspace-only laboratory directory after review. Preserve hash-backed base/donor originals, requested edits, validation repairs, byte differences, warnings and output hashes. Reparse each result and preserve every original byte outside the explicitly supported metadata/pointer fields. No server installation, database access, SQL execution or game launch occurs.

## Spawn and reward support

`monster_spawns: null` preserves the roster. An explicit list replaces it with one to five ordered 60-byte records copied from hash-bound references. Every entry names a reference and zero-based spawn index. An optional position reference copies only stage, raw orientation and XYZ from a same-map record; species and opaque record bytes remain those of the chosen monster donor. Same-species/stage evidence is preferred. Cross-species coordinates are experimental terrain placement only. The pointer package, ID list and terminated record list are appended, leaving native data intact. Changed rosters also update the five boss icons using the native editor layout. The native map package, stage transitions, supplies, class and failure field remain unchanged.

This does not establish monster AI compatibility, simultaneous combat, valid movement, safe spacing or migration. Another species' terrain position must never be presented as proof of those behaviors. New map packages, invented XYZ positions and arbitrary edits of opaque fields remain unsupported.

`rewards: null` preserves native tables. Explicit table edits replace only named table IDs; unmentioned tables and existing header flags remain intact. New tables use the existing CQ editor profile (`unk_0=128`, `unk_1=0`). Rows use bounded item IDs from the portable editor metadata, explicit quantities and configured weights. Main/Sub A/Sub B use the editor profile IDs 1/2/3. Non-100 totals are retained with warnings; weights are not quest-wide payout probabilities. Duplicate native table IDs are rejected as ambiguous. Reward delivery still needs a client test.

The portable item catalog is a compact projection of `desktop/src/utils/data/items.json`, with its source SHA256 recorded. `Shl` and `Shell` are normalized for name lookup. No names or IDs are invented. The source-only beta includes this metadata without BINs or local configuration.

The supported aggregate `Slay_All` profile uses target zero and raw quantity one; `Slay_Total` uses target zero and an explicit nonzero total. The full parsed corpus scan found quantity one for every Slay_All record; other native target profiles are preserved when unedited rather than generalized. They are available for explicitly requested aggregate goals, alongside individual monster objectives. Objective text is mandatory when changing a slot; new duplicates and stale targets removed from the roster are rejected. Completion flags remain explicit native/profile evidence, not proof of client behavior.

## Activity and verification

The desktop displays a simple hourglass, current host phase and elapsed seconds. Questions show that the engine is waiting for the user. During a model request, the indicator reports waiting for the provider; elapsed time alone is not claimed as proof of ongoing progress. Stop preserves completed session files.

Tests cover append-only pointer graphs/terminators, opaque bytes, protected maps, donor hash changes/backups, reward headers and item IDs, non-100 weights, multi-monster objectives, missing references, cross-map/invalid coordinates, complementary research and validation feedback. A local ignored Rust test independently reads an exported manifest/BIN through the native editor parser. It requires `MHFZ_BUILDER_TEST_MANIFEST` and must be invoked explicitly; game files are not published as fixtures. Current run outcomes and pending checks are recorded in `STATUS.md`.
