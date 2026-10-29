# Provider integration

## Primary: personal Codex account

The application integrates the official Codex CLI rather than implementing its own OAuth client or accessing a private Codex endpoint. Each user logs in through `codex-login`, which invokes the official browser/device authentication flow. Existing login state is detected by `codex login status`; no credential files are read by this application. `codex-login` leaves an existing ChatGPT login intact.

An installed CLI is preferred. `codex-install` only downloads when no CLI is found and installs the official pinned `@openai/codex@0.164.0` npm package under `.workspace/tools/codex`. Node/npm are required for that installation path. No CLI binary is committed or redistributed. npm handles package integrity. Newer compatible installed CLIs can be reused; execution checks required flags rather than silently downgrading or replacing an installation. Configure `--codex-path` for an official native executable at a custom location. Windows npm shims are resolved to the native binary and are not executed through a command shell.

`plan` sends each stage through `codex exec`, using stdin, JSON Schema output and an isolated run directory. User configuration is ignored for these runs while authentication remains with the official CLI. Execution is ephemeral, read-only and non-interactive; shell, apps/plugins, browser/computer tools and subagents are disabled, web search is disabled, and parent AGENTS documents are not loaded. Unexpected tool-action events cause the plan to be rejected. Managed host policies still apply and may prevent execution. The sandbox is not a claim that a child process has no access to any host data; the application only supplies sanitized summaries and does not hand the model a server path.

Account mode refuses an API-key login and removes API-key/endpoint overrides from its child environment. It does not fall back to API billing, another user or another provider. A shared Codex login is owned by the official CLI: signing out or changing the account there affects applications using the same login. This application does not offer an implicit logout action.

No model is forced by default: Codex chooses its account-available default. `ai-configure --provider codex --model MODEL` overrides it explicitly. Account plan eligibility, availability and quotas remain controlled by OpenAI. Two model turns are used for a normal quest plan; compiling a reviewed plan to a typed build specification uses one additional turn, while deterministic building uses none; no Platform API key is required.

Local schema/output/event diagnostics remain under `.workspace/codex-runs`. They can contain prompts and quest summaries and must not be published. No model reply becomes an executable patch. Source hashes and references are checked by the shared planner before a JSON plan is accepted.

Official references: [authentication](https://learn.chatgpt.com/docs/auth), [scripted execution](https://learn.chatgpt.com/docs/non-interactive-mode), [CLI flags](https://learn.chatgpt.com/docs/cli/reference), [configuration](https://learn.chatgpt.com/docs/config-file/config-reference).

## Optional: Gemini free-tier-capable API

Select `ai-configure --provider gemini`. The initial model is `gemini-3.8-flash`; set another supported model explicitly if needed. The adapter uses the documented Interactions API with JSON Schema, `store: false`, bounded input/output, a timeout and no external tools. Supply `GEMINI_API_KEY` through your environment or the masked local `--ask-key` prompt.

A free tier is offered for eligible Google projects/models, with quotas and conditions. This application cannot determine your project's billing settings or guarantee that a request using a paid project is free. To use the free option, configure a free-tier project; review its quotas and data policies. Free-tier content may be used to improve Google's products according to Google's current terms. There is no automatic billing upgrade, provider switch, model fallback or retry after quota errors.

Official references: [pricing and free tier](https://ai.google.dev/gemini-api/docs/pricing), [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [REST reference](https://ai.google.dev/api/interactions-api).

## Explicit alternative: OpenAI Platform API

Use `ai-configure --provider openai --model gpt-6.1-sol` and configure `OPENAI_API_KEY` or use `--ask-key`. This path retains separate Platform API billing and is never selected by default or used to bypass Codex account limits. See [API setup](openai.md).

All providers share the same catalog, domain rules, historical case notes, intent schema, reference selection and reviewed plan schema. The legacy `api_calls` JSON field remains an alias for compatibility; new consumers should use `model_calls` and `provider`.

## Verification

The primary Codex route has completed a live two-stage Toa/Tower planning test using the existing personal ChatGPT login, with source hashes unchanged. Gemini has offline transport/schema/quota tests, but no live Google key was available. The managed npm download and first-time interactive login are implemented but were not exercised because the installed authenticated CLI was reused. A conservative BIN export has since been generated and statically checked; client gameplay remains unverified. See [building](building.md).
