# Commands

All commands share the global `--help` flag. Run `clipsmith --help` for the full list.

---

## `clipsmith serve`

Start the FastAPI REST API server (requires `pip install -e ".[server]"`).

```sh
clipsmith serve [--host HOST] [--port PORT] [--reload]
```

| Flag | Description |
|------|-------------|
| `--host` | Bind address (default: `0.0.0.0`) |
| `--port` | Port number (default: `8000`) |
| `--reload` | Auto-reload on code changes (development only) |

The server exposes:
- `GET /health` — DB + server health
- `GET /metrics` — Prometheus scrape endpoint (text format)
- `GET /stats` — Run counts by status (JSON)
- `POST /runs` — Start a pipeline run
- `GET /runs`, `GET /runs/{id}` — List / inspect runs
- `GET /runs/{id}/clips` — Clips for a run
- `PATCH /clips/{id}` — Approve or reject a clip
- `GET /runs/{id}/progress` — SSE progress stream
- Full API docs at `http://localhost:8000/docs`

---

## `clipsmith setup`

First-run wizard: configure LLM provider, save API key, verify ffmpeg.

```sh
clipsmith setup [--provider anthropic|openai|ollama] [--key KEY] [--model MODEL]
```

| Flag | Description |
|------|-------------|
| `--provider` | `anthropic`, `openai`, or `ollama` (prompted if omitted) |
| `--key` | API key (prompted interactively if omitted; not needed for ollama) |
| `--model` | Ollama model to pull (default: `llama3.1:8b`) |

---

## `clipsmith process`

Process a local MP4 through the full pipeline: transcribe → LLM → clips.

```sh
clipsmith process <mp4> [options]
```

| Flag | Description |
|------|-------------|
| `--config`, `-c` | Path to `config.yaml` (default: `config.yaml`) |
| `--provider` | Override LLM provider (`anthropic`\|`openai`) |
| `--captions / --no-captions` | Override caption config |
| `--reframe / --no-reframe` | Override reframe config |
| `--skip-transcribe` | Load cached `transcript.json` instead of re-transcribing |
| `--start-at` | Skip content before this timestamp (`MM:SS`, `H:MM:SS`, or seconds) |
| `--verbose`, `-v` | Enable debug logging |

---

## `clipsmith run-vod`

Download a Twitch VOD and run the full pipeline.

```sh
clipsmith run-vod <video_id> [options]
```

| Flag | Description |
|------|-------------|
| `--local` | Skip Twitch API calls; use a manually placed MP4 |
| `--skip-download` | Use existing MP4 in `work/<id>/` |
| `--skip-transcribe` | Load cached `transcript.json` |
| `--skip-chat` | Load cached `chat.json` |
| `--skip-select` | Stop after candidates, skip LLM |
| `--skip-clip` | Stop after picks, skip ffmpeg |
| `--provider` | Override LLM provider |
| `--captions / --no-captions` | Override caption config |
| `--reframe / --no-reframe` | Override reframe config |
| `--max-candidates N` | Cap candidates sent to LLM (default: 20) |
| `--start-at` | Skip content before timestamp |
| `--verbose`, `-v` | Enable debug logging |

---

## `clipsmith watch`

Daemon: poll Twitch for new archive VODs and process each one automatically.

```sh
clipsmith watch [<channel>] [options]
```

| Flag | Description |
|------|-------------|
| `<channel>` | Override config channel (positional, optional) |
| `--once` | Single poll pass, then exit |
| `--verbose`, `-v` | Enable debug logging |

State is persisted to `state.json` — already-processed VODs are skipped across restarts.

---

## `clipsmith clip`

Re-run only the ffmpeg clipper from an existing `picks.json` (no LLM re-call).
Useful when adjusting caption style or reframe mode without redoing the expensive steps.

```sh
clipsmith clip <video_id> [options]
```

| Flag | Description |
|------|-------------|
| `--captions / --no-captions` | Override caption config |
| `--reframe / --no-reframe` | Override reframe config |
| `--verbose`, `-v` | Enable debug logging |

---

## `clipsmith reframe`

Re-cut selected clips in stacked layout (webcam top, gameplay bottom) → `out/<id>/stacked/`.

```sh
clipsmith reframe <video_id> <clip_01> [<clip_02> ...] [options]
```

Clip identifiers match the filename prefix, e.g. `clip_01`, `clip_04`.

| Flag | Description |
|------|-------------|
| `--verbose`, `-v` | Enable debug logging |

---

## `clipsmith detect-webcam`

Auto-detect the webcam/face rectangle from sampled frames via OpenCV Haar cascade.
Writes `reframe.webcam_rect` directly into `config.yaml`. Requires `.[vision]`.

```sh
clipsmith detect-webcam <video_id> [options]
```

| Flag | Description |
|------|-------------|
| `--samples N` | Number of frames to sample (default: 20) |
| `--verbose`, `-v` | Enable debug logging |

---

## `clipsmith check-ollama`

Verify the Ollama Python client, server, and configured model are all ready.

```sh
clipsmith check-ollama [--config config.yaml]
```

---

## `clipsmith whoami`

Sanity check: resolve a Twitch login to a user ID via the Helix API.

```sh
clipsmith whoami <login>
```

---

## `clipsmith cloud` — Azure cloud commands

Provision an Azure Container Instance, run the pipeline in Docker, upload clips to Google Drive, and tear everything down.

### `clipsmith cloud setup`

Validate Azure credentials.

```sh
clipsmith cloud setup [--config config.yaml]
```

Confirms that `DefaultAzureCredential` resolves successfully (via Service Principal env vars or `az login`). Storage accounts and file shares are provisioned automatically per run — no manual setup or storage verification is needed.

---

### `clipsmith cloud build`

Build the Docker image locally and push it to Docker Hub.

```sh
clipsmith cloud build [--config config.yaml] [--no-push]
```

| Flag | Description |
|------|-------------|
| `--push / --no-push` | Push to Docker Hub after build (default: push) |

The image tag is read from `cloud.docker_image` in `config.yaml`.

---

### `clipsmith cloud run`

Full end-to-end cloud run: provision ACI → pipeline → Google Drive upload → teardown.

```sh
clipsmith cloud run <vod_id> --game <game_name> [options]
```

| Flag | Description |
|------|-------------|
| `--game`, `-g` | Game name (used as Drive subfolder) — **required** |
| `--date`, `-d` | Stream date as `YYYY-MM-DD` (default: today) |
| `--config`, `-c` | Path to `config.yaml` (default: `config.yaml`) |
| `--dry-run` | Print ACI spec without provisioning anything |
| `--verbose`, `-v` | Stream container logs to the terminal while polling |

Clips are uploaded to Google Drive under `<root_folder>/<game>/<date>/` and the local temp copy is deleted on success.

---

### `clipsmith cloud drive-auth`

One-time OAuth2 authorization for Google Drive. Opens a browser, asks you to log in with your Google account, and saves a refresh token to `~/.clipsmith_drive_token.json`.

```sh
clipsmith cloud drive-auth
```

Requires `GOOGLE_OAUTH_CLIENT_JSON` to be set in `.env`. Only needs to be run once; the token auto-refreshes on subsequent `cloud run` calls.

---

### `clipsmith cloud status`

List all active clipsmith ACI jobs in the configured resource group.

```sh
clipsmith cloud status [--config config.yaml]
```

Shows container group name, current state, location, and Docker image for each running job.
