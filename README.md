# Nook

Nook is a local-first desktop AI assistant for Linux. It combines a lightweight
PyQt6 interface with a ReAct agent, local Ollama models, and optional Meta Model
API access.

## Before the hackathon

- A compact PyQt6 desktop interface with a global shortcut.
- A basic ReAct agent loop with local command and file tools.
- Automatic discovery of an installed Ollama chat model.
- An Ubuntu installer and desktop launcher.

## Built during the hackathon (Oct 26 - Nov 4, 2026)

See the [comparison with the pre-hackathon baseline](https://github.com/rayann1405/Nook/compare/pre-hackathon...hackathon).

- A local-first router with Auto, Local, and Cloud modes. Auto uses local
  inference by default, can route explicitly marked hard tasks to Meta, and
  falls back between providers on failures.
- RAM-aware Ollama selection (`llama3.2:3b`, or `llama3.2:1b` when available
  memory is low), bounded context size, and a configurable per-session cloud
  call cap.
- Optional Meta Model API chat completions with token streaming and no
  automatic retry loop.
- Streaming assistant replies, live provider/model status, visible agent
  activity, collapsible steps, mode/model controls, and light/dark themes.
- Offline-friendly `explain_error` and dry-run-first `organize_files` tools.
- Explicit confirmation before potentially destructive shell commands or
  file moves; existing destination files are never overwritten.
- Unit tests for routing, provider fallback and limits, agent confirmations,
  safety tools, and the Meta HTTP/SSE contract.
- An installer that checks for Ollama and offers to install it and pull the
  default 3B and 1B models.

## Requirements

- Debian or Ubuntu Linux with Python 3.10+ and a graphical desktop session.
- Ollama for local inference. Nook can also use the optional Meta Model API.
- At least one local chat model; `llama3.2:3b` is preferred when enough memory
  is available, with `llama3.2:1b` as a lighter option.

## Install

Install system packages:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl rsync \
  libxcb-cursor0 libxkbcommon-x11-0 libegl1 python3-xlib
```

Run the interactive installer. It checks for Ollama, offers to install it with
the official installer, and offers to pull `llama3.2:3b` and `llama3.2:1b`
when the Ollama service is reachable:

```bash
chmod +x install.sh
./install.sh
```

The installer creates a virtual environment and adds Nook to the desktop app
menu. If Ollama is not running, start it and pull a model:

```bash
ollama serve
ollama pull llama3.2:3b
```

## Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m nook
```

## Use

- Open Nook from the application menu or run `nook`.
- Click the compact Nook bubble to open the chat. The default global shortcut
  is `Ctrl+Alt+Space`.
- Choose **Auto**, **Local**, or **Cloud** in the settings row. Mark a request
  **Hard task** to allow Auto mode to try the cloud provider first.
- Select an installed local model or **Automatic**. The status badge shows the
  active provider and model; cloud usage also shows the session count.
- Review agent activity in the collapsible steps panel. Potentially destructive
  shell commands and file moves require explicit confirmation.
- Choose a light or dark theme in the settings panel.

On Wayland, desktop policies may prevent global shortcuts or always-on-top
behavior. Nook displays a notice and remains available from the application menu.

## Configuration

The user configuration is stored at `~/.config/nook/config.yaml`. The installer
creates it from `config.example.yaml`. Important settings include:

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: auto
  num_ctx: 2048

router:
  mode: auto
  cloud_enabled: true
  max_cloud_calls: 5

meta:
  base_url: "https://api.meta.ai/v1"
  model: "muse-spark-1.3"

ui:
  theme: dark
```

For optional cloud access, set `META_API_KEY` in Nook's environment, for
example before launching from a terminal:

```bash
export META_API_KEY="your-key"
nook
```

`META_API_BASE_URL` and `META_MODEL` can override the endpoint and model. The
`.env.example` file documents these variables; Nook does not automatically
load `.env` files. Shell commands run by the agent do not inherit Meta API key
environment variables.

The Meta client uses the configured OpenAI-compatible
`POST /chat/completions` interface with Bearer authentication. If your Meta
account uses a different base URL, model name, or authentication setup, update
the corresponding configuration before enabling Cloud mode. Cloud calls
require connectivity, an API key, Cloud enabled, and remaining session quota.

## Agent tools

- `run_command` — run a shell command; potentially destructive commands prompt
  for confirmation.
- `read_file` and `list_directory` — inspect local files and folders.
- `explain_error` — summarize a terminal error and suggest a likely fix.
- `organize_files` — preview a folder organization plan; moves occur only after
  explicit confirmation and never overwrite existing destinations.

## Architecture

```text
PyQt6 chat UI
  -> ReAct agent (bounded steps, confirmations, streamed final answer)
      -> Model router
          -> Ollama HTTP API (local-first, RAM-aware model selection)
          -> Meta Model API (optional, connectivity/key/quota gated)
      -> Local tools (commands, files, error explanation, organization preview)
```

## Tests

Run the unit tests without Ollama or internet access:

```bash
python -m unittest discover -s tests -v
```

## License

MIT
