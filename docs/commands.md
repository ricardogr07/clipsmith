# Commands

All commands share the global `--help` flag. Run `clipsmith --help` for the full list.

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
