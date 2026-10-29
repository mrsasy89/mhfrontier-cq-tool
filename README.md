# MHFrontier CQ Tool - AI integration

This is the **ai-quest-builder development branch of the MHFrontier CQ Editor fork**, adding evidence-led quest authoring through each user's own Codex/ChatGPT account. The CQ Editor is the base of the application: its quest tabs, native Rust parser/serializer, better_cursor library and metadata are reused under LGPL v3. Original authors retain their copyrights. See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).

Repository: [mrsasy89/mhfrontier-cq-tool](https://github.com/mrsasy89/mhfrontier-cq-tool/tree/ai-quest-builder). This branch starts at CQ commit [1176c07](https://github.com/mrsasy89/mhfrontier-cq-tool/commit/1176c07ede6770117684f2643efd3315a940872b). Existing branches remain separate. The earlier standalone prototype remains as development/test history in [mhfz-ai-quest-builder](https://github.com/mrsasy89/mhfz-ai-quest-builder).

## Primary interface: CQ desktop editor

Run **Start.cmd** or **GUI.cmd** from a local desktop build. The GUI is the user interface; the terminal wizard is available through **Dev.cmd** for development and diagnosis only. Python 3.11+, Microsoft Edge WebView2 and a local native build are required. This is a development beta, not a validated installer or a guarantee of client compatibility. No BINs, game corpus, executables, account credentials or private configuration are committed.

Choose **AIQuestBuilder** to sign in, select a map, describe a quest, set preferences, confirm an unused file ID, answer missing decisions and review/export. Codex is primary, using the official CLI and each user's own login. Access is reused throughout the editor session. Gemini API and OpenAI Platform API are explicit alternatives; there is no automatic provider, account or billing fallback.

An hourglass shows the current phase and elapsed time. The GUI distinguishes waiting for the provider from waiting for your response. Elapsed time alone is not presented as verified progress. Choose **QuestEditor** to inspect or manually edit a laboratory BIN with the inherited CQ tabs.

## Evidence-led authoring engine

The engine interprets the prompt, searches the entire configured parsed corpus, compares current references and can request further typed corpus/item searches. It receives explicit domain rules and qualified historical case notes. This is portable authoring logic and evidence, **not model fine-tuning or automatic access to private chat memory**.

Typed compilation supports quest ID, texts, duration, stat-table selectors, flags, variants, completion settings, individual/aggregate objectives, copied native spawn records and same-map position evidence, and selected reward tables using catalog item IDs. Unknown original bytes and the native map package are preserved. Missing quantities, weights, thresholds or ambiguous goals produce questions. Invalid proposals receive bounded validation feedback. Custom choices no longer stop before calling the model.

Sources stay read-only. Laboratory exports, hash-backed originals/donors, plans, validation feedback and byte-diff manifests stay in a separate workspace. No server installation, database access, SQL execution, server restart or game launch occurs. Cross-species terrain placement, simultaneous combat, migration, HC behavior, completion and payout still require client tests. See [engine workflow](docs/AUTHORING-ENGINE.md), [BIN support](docs/building.md), [domain rules](knowledge/rules.md) and [verification status](docs/STATUS.md).

## CQ baseline

Inherited editor code is compared with the pinned CQ revision. Unrelated local calibration experiments were removed. The [parity manifest](docs/cq-baseline.json) records identical baseline files and narrow, explicit exceptions: AI routing, workspace save guards, disabled direct database/ReFrontier actions and the verified full u32 failure field. **The whole application is not claimed byte-identical to upstream.** Run `python scripts/check_cq_parity.py` to detect unreviewed drift. See [CQ parity](docs/CQ-PARITY.md).

## Development only

The frontend stays in src/ and the native editor in src-tauri/, matching CQ's layout. The shared engine is in mhfz_builder/. The source-only Python archive is a developer artifact, not the desktop distribution.

```powershell
python -m unittest discover -s tests -v
python scripts/check_cq_parity.py
npm run check-types
npm exec -- eslint src/tabs/AIQuestBuilder.tsx
npm run test:asset-runtime
npm run build
```

Build the native editor with `cargo build --release --locked` from src-tauri using compatible Rust/MSVC tools. Dev.cmd and `python -m mhfz_builder --help` expose the same engine for diagnosis. ReFrontier operates exclusively on copies. Report skipped fixtures, coverage gaps and pending GUI/client checks explicitly; follow [ECC-WORKFLOW.md](docs/ECC-WORKFLOW.md) for every change.
