# Getting Started

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | [python.org](https://python.org) or `winget install Python.Python.3` |
| ffmpeg | `winget install Gyan.FFmpeg` — must be on `PATH` |
| twitch-dl | bundled via `pip install -e .` |
| chat-downloader | bundled via `pip install -e .` |
| faster-whisper | bundled via `pip install -e .` |

Optional — webcam auto-detection:

```sh
pip install -e ".[vision]"   # installs opencv-python-headless
```

## Installation

```sh
git clone https://github.com/ricardogr07/clipsmith
cd clipsmith
pip install -e .
```

## First-time setup

Run the setup wizard once to configure your LLM provider and verify ffmpeg:

```sh
clipsmith setup
```

You'll be asked to choose a provider (`anthropic`, `openai`, or `ollama`) and paste your API key.

- Anthropic API keys: <https://console.anthropic.com>
- OpenAI API keys: <https://platform.openai.com>
- Ollama (local, free): `clipsmith setup --provider ollama`

The key is saved to `.env` next to the executable.

## Process a local MP4

```sh
clipsmith process "C:\path\to\your_recording.mp4"
```

Runs the full pipeline — transcribe → score candidates → LLM selection → cut clips.
Output goes to `out\<video_id>\` (the video_id is the filename without extension).

!!! note "First run"
    The first time you run, faster-whisper downloads the transcription model (~500 MB) to
    `%USERPROFILE%\.cache\huggingface`. Subsequent runs use the cached copy.

## Process a Twitch VOD directly

```sh
clipsmith run-vod <video_id>
```

Downloads the VOD from Twitch (requires `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` in `.env`)
and runs the full pipeline.

## Daemon mode

```sh
clipsmith watch
```

Polls Twitch every `poll_interval_s` seconds (default 120). When a new archive VOD appears
it runs the pipeline automatically. Processed VODs are tracked in `state.json`.

## Reprocessing without re-running everything

```sh
# Re-cut clips only (e.g. after changing caption settings)
clipsmith clip <video_id>

# Re-run from existing download, redo transcription + LLM
clipsmith run-vod --local --skip-download <video_id>
```

## Stacked layout (webcam + gameplay)

After reviewing the flat clips, reframe selected ones into a two-panel 9:16 layout:

```sh
clipsmith reframe <video_id> clip_01 clip_04 clip_09
```

Output goes to `out\<video_id>\stacked\`.

**Auto-detecting the webcam rectangle:**

```sh
clipsmith detect-webcam <video_id>
```

This samples frames, detects the face rectangle using OpenCV, and writes `reframe.webcam_rect`
directly into `config.yaml`. Requires `pip install -e ".[vision]"`.

## Common troubleshooting

| Symptom | Fix |
|---------|-----|
| `ffmpeg not found` | Ensure `ffmpeg.exe` is on `PATH` (`winget install Gyan.FFmpeg`) |
| API key errors | Re-run `clipsmith setup` and paste the key again |
| Slow first run | Transcription model is downloading — wait for it to finish |
| Stacked clips empty | Set `reframe.webcam_rect` in `config.yaml` or run `detect-webcam` |
| `VOD not found` | Check `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` in `.env` |
