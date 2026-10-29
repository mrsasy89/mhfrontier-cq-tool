# Optional CQ desktop interface

The complete CQ editor frontend, native quest editor and supporting metadata are reused under the license in LICENSE. See the root NOTICE.md for origin and modifications. This is a separate application; the original editor is not modified.

## Known blocker / paused development

Preview investigation (2026-10-28): selecting Siege Fortress Day was reported to leave the window white. The installed frontend API 1.6.0 calls `window.__TAURI__.convertFileSrc`, which the locked native Tauri 1.2.4 runtime does not provide. The API dependency is now pinned to 1.2.0, whose URL conversion works with that runtime; `npm run test:asset-runtime` checks this compatibility. The frontend and native release were rebuilt successfully. The runtime regression and TypeScript checks pass. The actual map interaction must still be retested before calling the desktop blocker resolved. The source overview has WebP bytes despite its PNG extension; it remains unchanged and is not established as the cause.


Snapshot 0.2.0b12 is unfinished. A user reported the application freezing after clicking a map preview. No cause or fix has been established. The provider page and automatic discovery were visually checked; the map-preview interaction and end-to-end graphical flow were not validated. A successful build does not resolve this blocker. Resume with a small, reversible reproduction before claiming the preview works.

The shared AI writer now supports hash-bound spawn/position records and selected custom reward tables; old tkinter reward drafts are no longer required by the authoring flow. Existing native editor behavior also needs representative BIN and client checks. No validated desktop release or installer is provided by this snapshot.

## Run

After successful Codex sign-in, the editor remembers the selected account flow for its remaining lifetime, including new quests and leaving/reopening the AI tab. New flows skip AI selection while checking that the official CLI login is still valid. Back returns to provider selection. The memory marker disappears when the editor closes; the official CLI's own saved login is neither copied nor removed.

Install Node.js, Rust, the Windows C++ build tools and WebView2 as required by Tauri 1. From this directory run `npm install`, then `npm run dev`. Build the frontend with `npm run build` and native release with `npx tauri build`. Python 3.11+ and the root builder project are still required for AI sessions; the desktop binary does not bundle Python or Codex.

Choose **AIQuestBuilder** in Tool. The builder project and Python 3.11+ are detected automatically, including when opening the executable directly from its distribution directory. First select Codex/ChatGPT, Gemini or OpenAI API and optionally a model. The official personal login is reused or the UI offers browser/device-code login; API keys are masked and temporary. Next choose from all catalog maps, with every associated full overview/layer shown inside the page. Native PNGs remain local; approved icon-footers are hidden only in the display. Missing/provisional associations are explicit. Continue to the multiline description, statistics, position, flag descriptions, rewards, proposed ID confirmation and review. The GUI uses graphical controls rather than the terminal's numeric menu. Back is available on each question; stop preserves completed session files without automatic retries.

Choose **QuestEditor** to load a generated laboratory BIN and use the original information, strings, monsters, small monsters, equipment, supply, rewards and flags tabs. Quest saves ask for a destination inside the configured workspace and preserve SHA256-addressed originals. The workspace guard is detected automatically; no AI request or login is required for manual saves. Reference/server paths are rejected even when manually selected. The failure field is a raw u32, not a universal cart count: HR often uses reward reduction, while G Rank can use a count. Verify mode before editing.

Direct legacy ReFrontier calls and database commands are disabled; use the builder's copy-based unpack/index flow and SQL previews. Questlist writing is not exposed in this beta. Source code for the old advanced views is retained for later audits. Optional map resources are not bundled: set MHFZ_MAP_RESOURCES to your local CQ resources directory before running Vite if needed.

Custom rewards and position requests enter the shared compiler; missing parameters become explicit questions. Configured reward totals are preserved without normalization. Engine details are in AUTHORING-ENGINE.md.

Imported editor behavior is not fully audited. Loading/saving and in-game behavior still need representative quest testing; no client success is claimed.
