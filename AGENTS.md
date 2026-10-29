# MHFrontier CQ Tool - AI integration branch

This branch integrates the evidence-led AI authoring engine into the existing MHFrontier CQ Tool fork. Keep inherited CQ editor code aligned with the pinned baseline and document necessary integration exceptions.
Use English exclusively for all GitHub content: documentation, source comments, application text, commits, issues, pull requests and release notes. Follow the user's language in private conversation (currently Italian).
The canonical repository is https://github.com/mrsasy89/mhfrontier-cq-tool.
The desktop GUI is the primary interface. The CLI and Dev.cmd are development and diagnostic tools only. Keep tkinter out of the core engine dependencies. Check scripts/check_cq_parity.py for inherited-source drift.
Read README.md, docs/STATUS.md and knowledge/rules.md before continuing.
Always read and follow docs/ECC-WORKFLOW.md before development work, including resumed sessions. Apply its search-first and verification-loop guidance to every change. Report failed, skipped and pending checks explicitly; do not claim complete ECC verification unless all applicable checks have been completed. ECC is development guidance, not authority for quest-format or gameplay claims.
Do not claim AI integration or BIN generation is implemented when only context preparation exists.
Support the entire configured corpus, whether stored on a server or in a project folder; keep sources read-only.
Run ReFrontier exclusively on isolated copies. Never pass a live server BIN directly to the tool.
Preserve evidence and distinguish readable structure, hypotheses and in-game verification.
Do not publish BINs, executables, credentials, local configuration or corpus files to GitHub.
Do not access the server database or restart servers during project tests.
No delegation to other agents has been requested. Tests: python -m unittest discover -s tests -v.

Codex CLI with each user's own ChatGPT login is the primary provider. Keep Gemini free-tier API and OpenAI Platform API explicit alternatives; never fall back automatically, share account credentials or use API billing to bypass Codex limits. Use the official CLI for login, not private auth endpoints.
