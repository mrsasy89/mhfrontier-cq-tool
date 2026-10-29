# Pinned CQ source parity

The base is the existing fork at commit `1176c07ede6770117684f2643efd3315a940872b`, verified locally and through GitHub. The fork's original `src/`, `src-tauri/src/` and `src-tauri/better_cursor/` layout is retained. No application dependencies or game binaries are copied into Git to establish parity.

The manifest records 177 inherited files: 160 have identical source bytes after CRLF/LF normalization; 17 have explicit, hash-bound exceptions. There is no whitespace, syntax or semantic normalization beyond line endings. The exact original and expected hashes, paths and reasons are in `cq-baseline.json`. The check requires no external checkout or network.

Exceptions are limited to AI tool/route registration, separation of its form from native saving, workspace-only backed-up save destinations, the disabled direct ReFrontier/database routes, the verified u32 failure-field correction and associated labels/fixtures, branding, and registration of the independent export test. The native monster, reward, map, supply, string and quest-file serializers remain the pinned CQ code. These exceptions mean the whole application is not literally 1:1 upstream; each deviation is reviewable instead of hidden.

Before integration, inherited uncommitted calibration changes in `PosInput`, `MapPosition`, `maps.ts` and `math.ts` were restored to the pinned base. The manual Flags tab and an unrelated native import cleanup were also restored. The standalone prototype's private targeted backups remain outside Git. Future UI improvements and calibration changes are deferred until the first functioning beta.

Run `python scripts/check_cq_parity.py`. Missing or changed inherited source outside the documented hashes fails the check. New AI-specific files stay separate from native quest tabs. The opt-in Rust export test compares Python's manifest with the original CQ native reader; this is structural compatibility evidence, not an in-game test.
