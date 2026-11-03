# Hackathon Change Log

Hackathon work is isolated to the `hackathon` branch, based on the
`pre-hackathon` tag (`4fa9b01`). The links below identify the commits that
introduce each feature or file.

## `7b54995` — Add the local-first provider router

- Add `nook/router.py` for Auto/Local/Cloud routing, RAM-aware model choice,
  provider fallback, context limits, connectivity checks, and per-session
  cloud-call limits.
- Add `nook/meta_client.py` for the configurable Meta chat-completions API and
  SSE token streaming.
- Extend Ollama client/configuration with streaming, `num_ctx`, model choice,
  and router settings.
- Add `.env.example`; ignore local environment files and benchmark output.
- Add router, config, and Meta API contract tests.

## `42f8ca7` — Add guarded agent tools and live chat controls

- Route the ReAct agent through the provider router and improve parsing and
  small-model prompting.
- Add `explain_error` and dry-run-first `organize_files`; confirm destructive
  shell commands and file moves, and avoid overwriting existing files.
- Add live streaming, provider/model status, agent activity, confirmation
  dialogs, settings, and light/dark themes to the PyQt interface.
- Keep Ollama discovery off the UI thread and report startup/Wayland issues.
- Add agent and tool tests; replace the obsolete model-status test with router
  status coverage.

## `765f86f` — Report the provider actually available

- Show the local provider when Cloud mode is selected but cloud access is
  disabled, instead of displaying a cloud model that cannot be used.

## `b69d80d` — Document and package the hackathon features

- Replace the README with English setup, usage, configuration, architecture,
  and pre-hackathon/new-feature sections linked to the branch comparison.
- Update `install.sh` to check for Ollama, offer official installation, and
  offer to pull the 3B and 1B default models.

## Not completed

- The optional five-prompt performance benchmark was not run or added. It
  requires local Ollama models and hardware-specific measurements.
