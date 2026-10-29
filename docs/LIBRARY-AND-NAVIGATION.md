# Reference library, custom output and navigation

## Separate directories

Use `corpus/quests` inside the project as the default local reference library. Populate it with decompressed quests from your collection; all filename variants must be preserved. Game files are private user data and are not included in Git or the beta ZIP. The source library is read-only to the builder. An existing server directory can still be selected as the reference source when needed.

Prompt-generated custom BINs are exported to `.workspace/custom-quests/<session-id>/`. Plans and typed specifications remain under `.workspace/sessions/<session-id>/`. Existing exports are preserved at their previous locations. No generated custom is promoted into the reference library automatically. Library files may themselves include existing custom quests; being indexed does not certify them as original or verified in the client.

**Settings > Optional server destination** stores an existing server quest directory separately. This is preparation for an eventual transfer workflow: setting the path does not transfer, install, overwrite or register anything. Server transfer remains manual in this beta.

## Full indexing

**Corpus > Analyze all quests** has no compressed-file batch cap. **Inventory only** lists all files without decoding; **Decode a bounded batch** remains available. Reference search considers the whole parsed corpus before selecting a bounded set of relevant summaries for the model. Sending the entire corpus in one model request is not required.

The create screen reports parsed/total counts, pending decoding and errors. Every file variant remains represented separately. Completed records are committed incrementally, and interrupted indexing can resume without parsing unchanged successful records again. Error/unsupported files remain explicit; complete structural coverage is not proof of gameplay compatibility.

During indexing, Windows interactive users can press B or Esc to return to the menu; completed records are preserved. Ctrl+C also preserves completed records and ends the current terminal session. The progress counter updates periodically. For a pre-decompressed library, indexing does not need ReFrontier.

## Back navigation

Every terminal screen displays **[B] Back**. At ordinary prompts, enter `b` or `back` and press Enter. `indietro` is also accepted. Subpages return to their parent menu; provider/path/account pages return to Settings. The initial map, description and quest-ID steps support returning to the previous input. Returning from the first create step opens the main menu. Back from the main menu exits.

Back after planning/compilation preserves saved session files and never automatically replays model requests. Back while preparing optional SQL leaves generated BINs intact and skips SQL export. `cls` and `clear` redraw the current screen without navigating. Shell commands are not executed from menu input.
