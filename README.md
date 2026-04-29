# clipsmith

Local Twitch → AI clip pipeline. When a target channel posts a new archive VOD, clipsmith downloads it, transcribes the Spanish audio, ranks moments by chat activity, sends candidates to an LLM, and cuts 9:16 vertical MP4s with burned-in captions — ready for TikTok / YouTube Shorts.

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | python.org or `winget install Python.Python.3` |
| ffmpeg | `winget install Gyan.FFmpeg` — must be on `PATH` |
| twitch-dl | `pip install twitch-dl` (VOD downloader) |
| chat-downloader | `pip install chat-downloader` |
| faster-whisper | `pip install faster-whisper` (CPU int8 by default) |

## Installation

```sh
git clone https://github.com/you/clipsmith
cd clipsmith
pip install -e .
```

## Configuration

### Secrets — `.env`

Copy `.env.example` to `.env` and fill in your keys:

```
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...
ANTHROPIC_API_KEY=...       # if using provider: anthropic
OPENAI_API_KEY=...          # if using provider: openai
```

Get Twitch credentials at <https://dev.twitch.tv/console> → Register Your Application → OAuth Redirect: `http://localhost`.

### Behaviour — `config.yaml`

```yaml
channels:
  - chuyelwuero          # Twitch logins to watch

llm:
  provider: anthropic    # anthropic | openai | ollama
  model_anthropic: claude-sonnet-4-6

clip:
  min_seconds: 15
  max_seconds: 30

caption:
  font: Arial
  font_size: 72          # ASS pts at 1080×1920 PlayRes
  outline: 3
  position: bottom       # bottom | middle | top

reframe:
  mode: center           # center | webcam
  # webcam_rect: [x, y, w, h]  # source pixels, when mode=webcam
```

## Usage

### Daemon mode

```sh
clipsmith watch
```

Polls every `poll_interval_s` seconds (default 120). When a new archive VOD appears it runs the full pipeline automatically. State is persisted to `state.json` so already-processed VODs are skipped across restarts.

### One-off VOD

```sh
clipsmith run-vod <video_id>
```

Useful flags:

| Flag | Effect |
|------|--------|
| `--skip-download` | Use the existing `.mp4` in `work/<id>/` |
| `--skip-transcribe` | Load cached `transcript.json` |
| `--skip-chat` | Load cached `chat.json` |
| `--skip-select` | Stop after candidates, skip LLM |
| `--skip-clip` | Stop after picks, skip ffmpeg |
| `--provider anthropic\|openai` | Override config LLM |
| `--max-candidates N` | Cap LLM calls (default 20) |

### Re-cut clips

Re-run only the ffmpeg step from an existing `picks.json` (e.g. after adjusting caption style):

```sh
clipsmith clip <video_id>
```

### Sanity check

```sh
clipsmith whoami chuyelwuero
```

## Output

```
work/
  <video_id>/
    <video_id>.mp4        downloaded VOD
    transcript.json       faster-whisper segments + word timestamps
    chat.json             chat replay
    candidates.json       ranked moments
    picks.json            LLM-accepted clips with titles and reasons

out/
  <video_id>/
    clip_01_momento_gracioso.mp4
    clip_01_momento_gracioso.ass   (sidecar ASS subtitle file)
    clip_02_reaccion_epica.mp4
    ...
```

All clips are 1080×1920 (9:16), 15–30 s, h264/aac, with burned-in Spanish karaoke captions.

## Pipeline overview

```
watch → new VOD id
  ↓
downloader  (twitch-dl)          → work/<id>/<id>.mp4
  ↓
transcribe  (faster-whisper)     → transcript.json  (word timestamps, lang=es)
  ↓
chat        (chat-downloader)    → chat.json
  ↓
candidates  (density + clips + !clip commands)  → candidates.json
  ↓
selector    (LLM)                → picks.json
  ↓
clipper     (ffmpeg + libass)    → out/<id>/clip_NN_<title>.mp4
```

## Development

```sh
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest tests -q
```
