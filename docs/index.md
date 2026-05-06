# clipsmith

**Twitch VOD → AI vertical clips, locally or in the cloud.** Downloads a VOD, transcribes Spanish audio, ranks moments by five signals (chat density, `!clip` commands, existing Twitch clips, hype keywords, audio peaks), sends candidates to an LLM, and cuts 9:16 MP4s — optionally with burned-in captions and a stacked webcam/gameplay layout.

---

## What it does

```
VOD download  →  transcribe  →  chat signals  →  LLM selection  →  ffmpeg clips
```

1. **Downloads** a Twitch VOD (or takes a local MP4)
2. **Transcribes** Spanish audio with word-level timestamps via faster-whisper
3. **Scores candidates** by merging chat density, `!clip` commands, Twitch clips, audio RMS peaks, and hype keywords
4. **Selects** the best moments via an LLM (Anthropic, OpenAI, or local Ollama)
5. **Cuts** 9:16 vertical MP4s with optional burned-in ASS captions
6. **Uploads** to Google Drive — automatically, via cloud mode

## Quick start

```sh
git clone https://github.com/ricardogr07/clipsmith
cd clipsmith
pip install -e .
clipsmith setup          # save your API key, verify ffmpeg
clipsmith process recording.mp4
```

Clips appear in `out/<video_id>/`.

## Features

- **Two modes** — run locally on your workstation, or offload to Azure Container Instances with `clipsmith cloud run`
- **Three LLM providers** — Anthropic (claude-sonnet-4-6), OpenAI (gpt-4.1), Ollama (local/free)
- **Five candidate signals** — Twitch clips, chat `!clip`, chat density peaks, transcript hype keywords, audio RMS peaks
- **Chunked parallel transcription** — splits long VODs into overlapping chunks, transcribes concurrently
- **Burned-in captions** — ASS subtitle generation with configurable font, size, position
- **Stacked layout** — two-panel webcam-top + gameplay-bottom via ffmpeg `filter_complex`
- **Webcam auto-detection** — OpenCV Haar cascade detects and caches the face rectangle
- **Daemon mode** — `clipsmith watch` polls Twitch and processes new VODs automatically
- **Google Drive upload** — cloud mode uploads finished clips and returns a shareable link

## Navigation

| Page | What's there |
|------|-------------|
| [Getting Started](getting-started.md) | Install, first run, common workflows |
| [Commands](commands.md) | Full CLI reference with all flags |
| [Configuration](configuration.md) | `config.yaml` and `.env` reference |
| [Architecture](architecture.md) | Pipeline stages, module map, data flow diagrams |
| [Cloud Mode](cloud.md) | ACI workflow, design decisions, cost, troubleshooting |
| [Examples](examples.md) | Colab notebook, usage patterns |
| [Dev Setup](dev/contributing.md) | Running tests, mypy, bandit, CI |
| [Azure Setup](dev/azure-cloud-setup.md) | One-time cloud infrastructure provisioning |
