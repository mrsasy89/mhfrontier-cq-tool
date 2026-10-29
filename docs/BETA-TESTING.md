# Desktop AI beta

Start.cmd/GUI.cmd launch the CQ desktop interface. Dev.cmd and the Python archive are developer/diagnostic interfaces only. See the root README and AUTHORING-ENGINE.md for current capabilities. The historical terminal beta instructions below are retained as pre-union test history, not the primary user flow.

# Beta 0.2.0b1

Extract the ZIP to a writable folder and run **Start.cmd**, or run `python quest-builder.pyz start`. Python 3.11 or newer is required. This is a Python application, not a bundled Windows executable. No Python packages need installing. The optional inspector requires tkinter.

1. Configure an existing server quest directory, or choose `project` and fill the new corpus directory with your quest files. Select a separate workspace. Supply your existing ReFrontier executable for compressed quests; it is not distributed here.
2. Use **Index/decode corpus**. Inventory covers all BIN files, but only parsed files can participate in reference search. Decode bounded batches before requesting a map/species absent from searchable content. ReFrontier runs on copies.
3. Under **Settings / account login**, keep Codex as the primary provider. Existing official CLI installations and personal ChatGPT logins are reused. Installing the official CLI when absent requires Node.js/npm. Gemini API is an explicit alternative; free-tier availability depends on your project and quotas. No fallback is automatic.
4. Choose **Create quest from prompt**, select a map name/ID, describe the quest and supply an available target ID. Database availability must be checked separately. Review the plan's questions and provide missing decisions. Planning uses two model turns; each typed compilation adds one turn.
5. Review the typed preview before exporting. Session plans, specifications, BIN variants, original backups and hash manifests stay in the workspace. SQL is optional, saved only after checking exported file hashes, and is never executed.

## Supported beta edits

The writer preserves a native reference's complete map package, monster/player spawns, rewards and unknown bytes. It supports selected fixed metadata, quest ID, whole-minute time, stat selector, variant/flag fields, finish byte, eight CP932 text fields and supported objectives against existing bosses. Damage uses 100 HP per raw quantity unit; supplied HP and rounding must be reviewed.

Changing maps by transplanting packages, adding bosses, inventing coordinates, editing reward tables, retreat animations and immediate hunter return are not supported writer operations. The AI must find a suitable native reference; unsupported or unresolved changes block export. Selecting a map does not guarantee an appropriate reference is currently decoded. The preview displays data and does not simulate the client.

## Client verification checklist

Keep the source and manifest with every test. Install manually only on your intended test server after checking ID availability and preserving the previous file/registration. The application does not perform installation, database changes or server restarts.

Record each outcome separately: quest listing and texts; loading; player and monster spawn; combat; transitions after at least five minutes where relevant; objective thresholds; quest completion; rewards. A successful load does not prove migration, completion or rewards. Do not infer a crash cause from an EOF log alone. Save the exact build hashes, client/server version and observed behavior with any report.

The conservative writer and Codex planning/compilation have local verification. These generated files still require client gameplay verification. Fresh-machine installation/login and a real Gemini free-tier request remain separate checks.

## Command-line alternatives

Run `python quest-builder.pyz --help` for all commands. `registration --manifest <workspace-build-manifest>` saves a guarded SQL preview. `damage --hp 13299 --percent 50 --rounding ceil` reports quantity 67 and an effective threshold of 6700 HP. `Inspect.cmd` opens the optional read-only inspector after configuration; it does not edit BINs.

GitHub Actions produces a beta artifact after the Windows/Linux Python test matrix passes. The ZIP contains only the application, launchers and documentation. SHA256SUMS and package-manifest.json accompany the distribution. Corpus files, ReFrontier, Codex binaries, local settings and credentials are excluded.
