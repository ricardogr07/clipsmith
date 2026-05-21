# clipsmith

Local Twitch → AI clip pipeline. Downloads a VOD, transcribes Spanish audio, ranks moments by chat activity, sends candidates to an LLM, and cuts 9:16 vertical MP4s — optionally with burned-in captions and a stacked webcam/gameplay layout for TikTok / YouTube Shorts.

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | python.org or `winget install Python.Python.3` |
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
  - chuyelwuero             # Twitch logins to watch

llm:
  provider: anthropic       # anthropic | openai | ollama
  model_anthropic: claude-sonnet-4-6

clip:
  min_seconds: 15
  max_seconds: 30

caption:
  enabled: false            # set true to burn subtitles into the video
  font: Arial
  font_size: 72             # ASS pts at 1080×1920 PlayRes
  outline: 3
  position: bottom          # bottom | middle | top

reframe:
  # center | webcam | stacked | none
  mode: none
  # Source-pixel crop for the webcam/face panel [x, y, w, h]
  # Leave null to use center-crop fallback; set once per stream layout.
  webcam_rect: null
  # Source-pixel crop for the gameplay panel (stacked mode only)
  # null = center-crop fallback
  gameplay_rect: null
  # Fraction of 1920px height given to the top (webcam) panel in stacked mode
  # e.g. 0.4 → 768px webcam on top, 1152px gameplay on bottom
  split_ratio: 0.4
```

## Usage

### First-time setup

```sh
clipsmith setup
```

Saves your API key to `.env` and verifies ffmpeg is available.

### Process a local MP4

```sh
clipsmith process path/to/recording.mp4
```

Runs the full pipeline — transcribe → score candidates → LLM selection → cut clips. Clips appear in `out/<video_id>/`.

Useful flags:

| Flag | Effect |
|------|--------|
| `--skip-transcribe` | Load cached `transcript.json` |
| `--captions / --no-captions` | Override caption config |
| `--reframe / --no-reframe` | Override reframe config |
| `--provider anthropic\|openai` | Override LLM provider |

### Daemon mode

```sh
clipsmith watch
```

Polls every `poll_interval_s` seconds (default 120). When a new archive VOD appears it runs the full pipeline automatically. State is persisted to `state.json` so already-processed VODs are skipped across restarts.

### One-off Twitch VOD

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
| `--max-candidates N` | Cap candidates sent to LLM (default 20) |

### Re-cut flat clips

Re-run only the ffmpeg step from an existing `picks.json` (e.g. after adjusting caption style):

```sh
clipsmith clip <video_id>
```

### Stacked vertical layout (webcam + gameplay)

After reviewing the flat clips, pick the best ones and reframe them into a stacked 9:16 layout — webcam on top, gameplay on bottom:

```sh
clipsmith reframe <video_id> clip_01 clip_04 clip_09
```

Output goes to `out/<video_id>/stacked/`. The reframe rects come from `config.yaml`; see the `reframe` section above.

**Auto-detecting the webcam rect:**

If `reframe.webcam_rect` is not set in `config.yaml`, clipsmith will try to detect the face rectangle automatically using OpenCV (requires `pip install -e ".[vision]"`). The result is cached to `work/<video_id>/webcam_rect.json` and reused on subsequent runs.

To run detection manually and write the result directly into `config.yaml`:

```sh
clipsmith detect-webcam <video_id>
```

This samples frames, detects the webcam rectangle, and saves `reframe.webcam_rect` in `config.yaml` automatically — no manual copy-paste needed.

### Sanity check

```sh
clipsmith whoami chuyelwuero
```

## Output

```
work/
  <video_id>/
    <video_id>.mp4          downloaded (or copied) source VOD
    transcript.json         faster-whisper segments + word timestamps
    chat.json               chat replay
    candidates.json         ranked candidate moments
    picks.json              LLM-accepted clips with titles and reasons
    webcam_rect.json        auto-detected webcam rect (cached, vision only)

out/
  <video_id>/
    clip_01_momento_gracioso.mp4    flat 9:16 clip
    clip_01_momento_gracioso.ass    sidecar ASS subtitle file
    clip_02_reaccion_epica.mp4
    ...
    stacked/
      clip_01_momento_gracioso.mp4  stacked layout (webcam top, gameplay bottom)
      clip_04_reaccion_epica.mp4
      ...
```

All clips are 1080×1920 (9:16), 15–30 s, h264/aac, with optional burned-in Spanish karaoke captions.

## Pipeline overview

```
watch / run-vod / process
  ↓
downloader      (twitch-dl)                → work/<id>/<id>.mp4
  ↓
detect-webcam   (opencv Haar cascade)      → work/<id>/webcam_rect.json  [optional]
  ↓
transcribe      (faster-whisper)           → transcript.json  (word timestamps, lang=es)
  ↓
chat            (chat-downloader)          → chat.json
  ↓
candidates      (density + clips + !clip)  → candidates.json
  ↓
selector        (LLM)                      → picks.json
  ↓
clipper         (ffmpeg + libass)          → out/<id>/clip_NN_<title>.mp4
  ↓  [manual: clipsmith reframe]
reframe         (ffmpeg filter_complex)    → out/<id>/stacked/clip_NN_<title>.mp4
```

## REST API & Dashboard

Start the FastAPI server and the Next.js dashboard to review and approve clips in a browser:

```sh
pip install -e ".[server]"
clipsmith serve                   # http://localhost:8000/docs
cd web && pnpm install && pnpm dev  # http://localhost:3000
```

Key API endpoints:

| Endpoint | Description |
|----------|-------------|
| `POST /runs` | Start a pipeline run (requires `X-Api-Key` header) |
| `GET /runs/{id}/progress` | SSE stream of live stage progress |
| `PATCH /clips/{id}` | Approve or reject a clip |
| `GET /metrics` | Prometheus scrape endpoint |
| `GET /stats` | Run counts by status (JSON) |

## Observability

Sprint 7 adds distributed tracing (OpenTelemetry → Jaeger), Prometheus metrics, and a
Grafana dashboard. Spin up the full local stack in one command:

```sh
pip install -e ".[observability]"
docker compose -f docker-compose.observability.yml up -d
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 clipsmith serve
```

| UI | URL |
|----|-----|
| Grafana dashboard | http://localhost:3001 (admin / `$GRAFANA_ADMIN_PASSWORD`, default: admin) |
| Jaeger traces | http://localhost:16686 |
| Prometheus | http://localhost:9090 |

In production, set `APPLICATIONINSIGHTS_CONNECTION_STRING` to export traces to Azure Monitor Application Insights.

## Development

```sh
pip install -e ".[dev,server,observability]"
pip install -e ".[vision]"   # optional, for detect-webcam tests
python -m pytest tests -q
```
