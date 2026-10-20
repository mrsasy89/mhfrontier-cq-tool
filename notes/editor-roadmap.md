# Quest editor completion roadmap

Baseline: `51cb4b51e4fd9264dbe962e47a02369bf7df1ca2` (main).

## First increment: English text previews

The Strings tab can preview English hunt/capture/slay/delivery objectives using
the existing monster and item names. Unsupported types and unverified target
names are preserved. The two target bytes are combined for uint16 item IDs.
Nothing is written to disk by generating or applying a preview; the existing
Save Quest command remains responsible for persistence.

Success templates follow the editor's existing `requirement_to_finish` labels.
Failure templates require an explicit choice (preserve, faint limit, or reward
reaching zero). They do not infer failure policy from the G-rank bit. Templates
do not alter objectives, conditions, rewards, titles, giver or description.
Review special quests manually before saving.

Tests: Node 24, no new packages required:

```sh
node --experimental-strip-types --experimental-test-coverage --test tests/questStringTemplates.test.mjs
```

The first increment tests pure template functions. It does not validate binary
round trips, the React interface, native packaging, or runtime quest behavior.
The session environment lacked Rust and its network proxy was unavailable, so
full build/type/lint checks could not be run locally. Keep this change in draft
until project CI and a Windows smoke test pass.

## Existing functionality to extend

The fork already includes supply items, small-monster editing, forced equipment,
weapon restrictions, player-spawn controls, equipment/item data, a configuration
editor, quest lists and embedded ReFrontier code. The older Paxlord future-plans
image is not a list of missing features in this fork. Verify completeness of
each existing screen rather than implementing a second version.

## Next: binary integrity and custom quests

1. Replace silent `Ok("invalid text")` decoding in
   `src-tauri/better_cursor/core/cursor/read.rs` with contextual errors.
2. Validate all eight string pointers, pointer-table length, checked address
   addition and NUL termination in `quest_string.rs`. Allow legitimate empty
   strings. Never assume every custom quest uses the same repaired offset.
3. Validate encodability before writes. Save to a temporary copy, reread it,
   preserve an original backup and only then replace the destination.
4. Bound loaded-stage ranges, supply/reward lists and map structures before
   iterating. Validate ARCA footer length and start pointer before truncation.
5. Add real custom-quest fixtures only when redistribution is authorized; include
   malformed-pointer, missing-terminator and failed-save preservation tests.

The prior `64551d0.bin` repair set the pointer at `0xE8` to `0xB50` for that
specific analyzed file. It is not a general repair recipe for arbitrary quests.

## Then: translation workflow

- CSV/JSON export/import with quest ID, variant, source text and English text.
- Preview changed fields and encoded byte lengths; preserve unsupported text.
- Batch editing across d0/d1/d2/n0/n1/n2 with per-file validation and backups.
- Add part-break/damage/special-objective templates only after validating the
  corresponding binary semantics; never fabricate missing objectives.

## Then: Erupe integration and editor completion

- Separate server event `quest_type`, internal client menu IDs, BIN flags and
  event schedule controls in the interface.
- Use confirmed menu names: type 9 Promotional; type 54 Gear Acquisition. Preserve
  explicit HR Event exceptions for the user's Akantor/Teostra event set.
- Audit `get_season`/`getSeasonFromQuestTypeFlags`: suffix mapping is breeding 0,
  warm 1, cold 2. Automatic flags cannot identify a single fixed variant.
- Expose raw unknown values without silently normalizing or deleting them.
- Audit gathering points, map editing and auto-skills before adding controls.
- Add undo/redo, Save As, batch management and update delivery after binary
  round-trip preservation is verified.

## ECC use in this session

Applied the research-first and verification-loop workflows, with independent
code review. No ECC global installer, hooks, credentials or MCP configuration
were installed or changed. ECC is development guidance, not an editor runtime
dependency.

- https://github.com/affaan-m/ECC/blob/main/skills/search-first/SKILL.md
- https://github.com/affaan-m/ECC/blob/main/skills/verification-loop/SKILL.md

Paxlord's editor was inspected as a functional reference. No implementation was
copied from it; its repository does not declare a license in the GitHub metadata.
