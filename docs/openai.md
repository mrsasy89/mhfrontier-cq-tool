# Optional OpenAI Platform API quest planning

The primary mode now uses your personal Codex/ChatGPT account. See [provider setup](providers.md). This page documents the separate, explicitly selected Platform API option.

This adapter uses the official OpenAI Responses API at `https://api.openai.com/v1/responses`, with strict JSON Schema output. It does not launch Codex CLI or reuse credentials from a Codex/ChatGPT login.

Official references: [authentication](https://developers.openai.com/api/reference/overview), [Codex authentication methods](https://learn.chatgpt.com/docs/auth), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

## Local setup

Create a Platform API key in your own OpenAI account. API-key usage is billed through OpenAI Platform, separately from included ChatGPT/Codex plan usage. Account and model access must be checked with your own credentials.

```powershell
python -m mhfz_builder ai-configure --provider openai --model gpt-6.1-sol
python -m mhfz_builder plan --prompt "Toa in the Tower, Damage as Sub B" --dry-run --output .workspace/projects/preflight.json
python -m mhfz_builder plan --prompt "Toa in the Tower, Damage as Sub B" --ask-key --output .workspace/projects/plan.json
```

`--ask-key` requests the key in your local terminal without displaying or saving it. Alternatively, provide `OPENAI_API_KEY` through your local environment. Do not put a key in command arguments, configuration, prompts, chat or repository files. Configuration changes preserve a hash-addressed backup locally. `doctor` reports configuration and key presence, not verified connectivity.

The initial model is configurable and defaults to `gpt-6.1-sol`, documented for Codex and the Responses API at implementation time. There is no automatic model fallback. `--max-output-tokens` on `ai-configure` sets a per-response cap (default 4096). Each live plan makes two requests, so this is not a total project spending limit. No automatic retry is made after timeouts or HTTP errors. `--dry-run` makes no API requests. Existing output paths are rejected before any request.

## Data flow and validation

1. Send the prompt, portable domain rules and monster/map catalog to extract structured intent.
2. Search all parsed records in the local index using the extracted IDs. Verify source hashes, group identical content while preserving file variants and retain at most 12 distinct references.
3. Send structural reference summaries, hashes and coverage statistics to propose a plan. Source paths, complete quest text, credentials and binary data are not included in reference summaries. User prompts and quest titles are included as supplied.
4. Check schema, IDs, citations and reference hashes again. Save the plan, local provenance, API request/response IDs and token counts. Always mark it unverified in game and requiring review; no BIN or SQL is executed.

Incomplete corpus coverage is visible in the saved plan. Missing references produce a request for more evidence, not an invented base. A cited reference is provenance, not proof that a proposed change works in the game. The model has no shell, filesystem or database tools. `store: false` is sent; this does not claim zero retention or override the API account's data policies.

The shipped knowledge resource bundles `knowledge/rules.md` and `knowledge/cases.json`; update the packaged resource when changing either source. Historical case notes guide planning but do not prove compatibility with the current BIN revision. The current parser only understands part of the quest format. Reading a map reference does not yet validate every byte of its package or its runtime transitions.

## Verification status

Transport, schema validation, provenance, missing-key behavior and the two-request pipeline are covered by offline tests with simulated responses. No live API request has been made during implementation because no Platform key was available. Live authentication, model availability, latency, token usage and planning quality still require a real test. A deterministic BIN writer and client gameplay tests remain separate future work.
