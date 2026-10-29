# Quest Fix

Quest Fix starts with a read-only diagnosis of every filename variant of the selected quest in the configured corpus. The terminal menu exposes **6. Quest Fix diagnosis**. Reports stay in the separate workspace. No model request, database connection, server install or restart is performed.

```powershell
python -m mhfz_builder quest-fix "C:/MHF/bin/quests/65025d0.bin" --output-dir .workspace/quest-fix/review-1
```

## First implemented checks

- Read the main reward and full 32-bit failure value; expose both conditional HR reward-penalty arithmetic and a direct-cart interpretation. G-rank and Diva markers are reported as byte facts, not sufficient proof of runtime semantics.
- Report non-100 configured reward totals without changing them. Rate is a table weight, not a guaranteed quest-wide probability.
- Preserve intentional Diva/Interception flags, all unknown bytes, native maps/spawns/rewards and objectives. NPC eligibility has a comparison checklist, not an invented automatic fix.
- Hash-check all source variants before/after the operation. If explicitly exporting faint candidates, preserve source backups, exact changed offsets and candidate hashes. Sources remain untouched.

An optional laboratory candidate requires an explicit profile:

```powershell
python -m mhfz_builder quest-fix "C:/MHF/bin/quests/65025d0.bin" --output-dir .workspace/quest-fix/candidate-1 --faints 3 --candidate-profile hr-penalty
```

`hr-penalty` uses an existing penalty if it already reaches the requested faint count; otherwise it proposes `ceil(main_reward / faints)` and verifies that the integer result represents that count. `g-carts` writes a direct count. The G marker must agree with the explicitly selected profile; this consistency guard does not prove that a special quest uses that profile. Quest 65005 is protected from candidate edits. Only body 0xC0 is writable. The operation patches all four bytes of the field and never changes the main reward. Unknown, special and zero-reward cases require manual research. Exported raw candidates are unverified and are never installed.

## Regression evidence supplied by the user

The historical 65025 case had reward22500/raw3 and displayed76. `(22500 // 3) % 256 == 76` is a strong explanation, but the internal client calculation was not traced. A penalty7500 was proposed for three faints. Historical batch correction distinguished HR penalties from G direct counts, and preserved a different penalty already consistent with three faints. These are regression evidence, not universal format rules.

For missing companions, four hunter capacity and absence of a known No NPCs requirement did not identify the cause. Diva was intentional for the spawn sequence. Rebuilding on native21736n0 preserved the custom content in that session, but companion/sequence results were still awaiting client tests. This implementation does not transplant a new base or repair unknown fields automatically.

## Remaining work

Validated native-base comparison/rebuild, effective server-card comparison, broader NPC and spawn diagnosis, named designer reward exports and structured client-result capture remain future extensions. Do not treat a successful structural parse as proof of loading, NPC access, migrations, faint failure or rewards. Record each client outcome separately with the build hash. See [research sources](../knowledge/SOURCES.md).
