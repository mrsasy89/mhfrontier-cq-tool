# ReFrontier and CQ Tool reference

References: [CQ Tool](https://github.com/mrsasy89/mhfrontier-cq-tool), particularly `src-tauri/src/app/re_frontier.rs`, `src/events/refrontier.ts` and `src/context/QuestEditorContext.tsx`; [legacy ReFrontier](https://github.com/mhvuze/ReFrontier); [modern fork](https://github.com/Houmgaor/ReFrontier).

In the inspected CQ Tool revision, the frontend passes a path, but the backend uses `cwd/ReFrontier/ReFrontier.exe`. The new adapter uses the configured path, checks the exit code and preserves logs. ReFrontier is external and is not copied or distributed with this project.

The installed legacy version can overwrite its input during decompression. The builder therefore runs it only on a copy with `-log -close`, preserves the initial BIN and verifies the source hash afterward. Each manifest identifies the tool, arguments, input and output.

Detection distinguishes legacy help from the modern `unpack` command. The legacy version has been verified locally; the modern branch still needs testing with a corresponding executable. Compatibility with every fork is not claimed. Recompression, encryption and automatic final BIN creation are not implemented in this foundation: preserve logs when working manually with ReFrontier.
