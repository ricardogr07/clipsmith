# Clipsmith Architecture

## Overview

Clipsmith turns a Twitch VOD (or any local MP4) into a set of 9:16 vertical clips ready for TikTok / YouTube Shorts. The pipeline has three entry points:

- **`watch`** — daemon that polls Twitch for new archive VODs
- **`run-vod`** — one-shot run for a specific Twitch video ID
- **`process`** — one-shot run from a local MP4 file

All three feed the same six-stage pipeline. A separate **`reframe`** command is available as a manual post-processing step to produce stacked webcam+gameplay layouts for selected clips.

---

## Pipeline Stages

```
VOD (mp4)
    │
    ▼
[1] Webcam Detection ────────── opencv Haar cascade (optional, cached)
    │ webcam_rect.json           fires only when reframe.mode != none
    │                            and webcam_rect not already set in config
    │
    ▼
[2] Transcribe ──────────────── faster-whisper (Spanish, CPU int8)
    │ transcript.json            segments + word timestamps
    │
    ▼
[3] Chat Download ──────────── chat-downloader (Twitch replay API)
    │ chat.json                  raw messages → ChatMessage (time, author, emotes)
    │                            fallback: evenly-spaced transcript samples
    │
    ▼
[4] Candidate Scoring ────────  three signals merged & deduped
    │ candidates.json
    │   Signal A: existing Twitch clips  (+100 pts/clip)
    │   Signal B: !clip chat commands    (+25 pts each)
    │   Signal C: chat density peaks     (sliding window, 4× baseline)
    │   Signal D: transcript hype words  (+20 pts/hit)
    │
    ▼
[5] LLM Selection ────────────  one API call per candidate (top-20)
    │ picks.json                 returns: include, start_s, end_s, title_es, reason
    │   Providers: Anthropic │ OpenAI │ Ollama
    │
    ▼
[6] Clip Cutting ─────────────  ffmpeg per pick
    out/<vod_id>/               9:16 reframe → optional burned ASS captions
    clip_01_<title>.mp4         libx264 fast / aac 128k / faststart

    [manual: clipsmith reframe]
    ▼
[7] Stacked Reframe ──────────  ffmpeg filter_complex (human-in-the-loop)
    out/<vod_id>/stacked/       webcam panel (top) + gameplay panel (bottom)
    clip_01_<title>.mp4         1080×1920, split_ratio configurable
```

---

## Module Map

```
src/clipsmith/
│
├── cli.py            CLI entry point (Typer)
│     commands:  process | watch | run-vod | clip | reframe | detect-webcam | whoami
│
├── pipeline.py       Orchestrator — calls stages 1-6 in order
│                     holds transcript-fallback logic when chat is empty
│
├── watcher.py        Daemon: polls Helix every poll_interval_s seconds
│                     emits VodEvent for each unseen archive VOD
│
├── twitch_client.py  Helix API wrapper (httpx): get_user_id, get_videos, get_clips_for_vod
│
├── state.py          Persists seen video IDs to state.json between runs
│
├── downloader.py     Subprocess wrapper around `python -m twitchdl download`
│
├── detect.py         Webcam/face detection (OpenCV Haar cascade, optional)
│                     load_or_detect_webcam_rect: cache-first, updates cfg.reframe in-place
│
├── transcribe.py     faster-whisper wrapper → Transcript(segments, words, language)
│
├── chat.py           `python -m chat_downloader` wrapper → ChatLog(messages)
│                     parses JSON array or NDJSON; tags !clip commands and hype emotes
│
├── candidates.py     Merges signals → list[CandidateMoment] sorted by score desc
├── candidates_math.py  Sliding-window density + peak detection
│
├── selector.py       Loops candidates → LLM → PickResult; clamps clip duration 15-30s
│
├── llm/
│   ├── base.py       ClipPicker Protocol, ClipPick dataclass, SYSTEM_PROMPT, JSON schema
│   ├── anthropic_provider.py   Prompt-cached: system + stream context cached, per-candidate varies
│   ├── openai_provider.py      Structured outputs (json_schema); system cached after first call
│   └── ollama_provider.py      Local Ollama stub
│
├── clipper.py        cut_all_clips: writes ASS file, runs ffmpeg per pick
│                     modes: center | webcam | stacked | none
│                     stacked: _stacked_filter_complex builds filter_complex chain
├── captions.py       Transcript → ASS subtitle file (burn-in, Spanish)
│
└── settings.py       AppConfig (YAML) + Secrets (.env / env vars)
                      ReframeConfig: mode, webcam_rect, gameplay_rect, split_ratio
```

---

## Data Flow Diagram

```mermaid
flowchart TD
    subgraph Inputs
        VOD[VOD mp4\nwork/VIDEO_ID/VIDEO_ID.mp4]
        CFG[config.yaml\nAppConfig]
        ENV[.env\nSecrets]
    end

    subgraph CLI
        PROCESS[process\nlocal mp4]
        WATCH[watch\ndaemon]
        RUNVOD[run-vod\none-shot]
        CLIP[clip\nre-cut only]
        REFRAME[reframe\nstacked layout]
        DETECTWC[detect-webcam\nstandalone]
    end

    subgraph Twitch["Twitch API (optional)"]
        HELIX[Helix REST\nget_videos / get_clips]
        TWITCHDL[twitch-dl\ndownload]
    end

    subgraph Pipeline
        DET[Detector\ndetect.py\nopencv optional]
        DL[Downloader\ndownloader.py]
        TR[Transcriber\ntranscribe.py\nfaster-whisper]
        CH[Chat\nchat.py\nchat-downloader]
        CA[Candidates\ncandidates.py\n+ candidates_math.py]
        SEL[Selector\nselector.py]
        CUT[Clipper\nclipper.py + captions.py\nffmpeg]
        STK[Stacked Reframe\nclipper.py\nffmpeg filter_complex]
    end

    subgraph LLM["LLM Provider (llm/)"]
        ANT[Anthropic\nclaude-sonnet-4-6]
        OAI[OpenAI\ngpt-4.1]
        OLL[Ollama\nllama3.1]
    end

    subgraph Artifacts["work/VIDEO_ID/"]
        WR_JSON[webcam_rect.json]
        T_JSON[transcript.json]
        C_JSON[chat.json]
        CA_JSON[candidates.json]
        P_JSON[picks.json]
    end

    subgraph Output["out/VIDEO_ID/"]
        MP4S[clip_NN_title.mp4\n9:16 · 15-30s]
        STACKED[stacked/clip_NN_title.mp4\nwebcam top + gameplay bottom]
    end

    CFG --> WATCH & RUNVOD & PROCESS
    ENV --> WATCH & RUNVOD & PROCESS

    WATCH -->|new VOD event| Pipeline
    RUNVOD --> Pipeline
    PROCESS --> Pipeline
    CLIP -->|picks.json exists| CUT
    REFRAME -->|picks.json exists| STK
    DETECTWC -->|standalone| DET

    HELIX -->|existing clips| CA
    TWITCHDL --> DL
    DL --> VOD

    VOD --> DET
    DET --> WR_JSON

    VOD --> TR
    TR --> T_JSON
    T_JSON --> CA & SEL & CUT

    CH --> C_JSON
    C_JSON --> CA
    CA --> CA_JSON
    CA_JSON --> SEL

    SEL --> ANT & OAI & OLL
    ANT & OAI & OLL --> P_JSON
    P_JSON --> CUT & STK

    VOD --> CUT & STK
    WR_JSON -.->|auto-loaded| STK
    CUT --> MP4S
    STK --> STACKED
```

---

## Reframe Modes

| Mode | Description |
|------|-------------|
| `none` | Stream-copy (no re-encode, no crop) |
| `center` | Center-crop to 9:16 |
| `webcam` | Crop to `webcam_rect`, scale to 1080×1920 |
| `stacked` | Two-panel: `webcam_rect` on top, `gameplay_rect` on bottom; heights set by `split_ratio` |

The `reframe` command always uses `stacked` mode regardless of the config value. The flat pipeline uses whatever `reframe.mode` is configured.

### Webcam auto-detection

`detect.py` samples `N` evenly-spaced frames (default 20, skipping the first/last 5% of duration), runs an OpenCV Haar frontal-face cascade on each, and clusters detections by IOU ≥ 0.3. The most-frequent cluster is returned as `[x, y, w, h]` in source-video pixels. The result is written to `work/<video_id>/webcam_rect.json` and loaded automatically on subsequent runs.

---

## Candidate Scoring Detail

| Signal | Source | Score |
|--------|--------|-------|
| Existing Twitch clip at this VOD offset | Helix API | +100 pts |
| `!clip` chat command in window | Chat replay | +25 pts each |
| Chat density peak (>4× baseline in 15 s window) | Chat replay | proportional |
| Transcript hype keyword (jaja, wow, etc.) | Transcript | +20 pts/hit |
| Evenly-spaced sample (fallback, no chat data) | Transcript | 1 pt (uniform) |

Candidates within 60 s of each other are merged (highest-score center kept, scores summed). Top 20 by score are sent to the LLM.

---

## LLM Prompt Architecture

Each provider sends **two stable blocks + one variable block** to maximise prompt caching:

1. **System prompt** (stable) — role, rules, JSON schema (~300 tokens, cached after first call)
2. **Stream context** (stable per VOD) — channel, title, duration, language (~50 tokens, cached)
3. **Candidate prompt** (varies) — transcript ±60 s window + viewer signals (~200–400 tokens)

The LLM returns a single JSON object: `{ include, start_offset_s, end_offset_s, title_es, reason }`.

`start_offset_s` and `end_offset_s` are **absolute timestamps** from the start of the VOD (not offsets from `t_center`).

---

## File Layout

```
clipsmith/
├── config.yaml          behavior (channels, model sizes, thresholds)
├── .env                 secrets (API keys, Twitch credentials)
├── state.json           seen VOD IDs (auto-created by watcher)
├── work/
│   └── <video_id>/
│       ├── <video_id>.mp4
│       ├── webcam_rect.json    (auto-detected, cached)
│       ├── transcript.json
│       ├── chat.json
│       ├── candidates.json
│       └── picks.json
└── out/
    └── <video_id>/
        ├── clip_01_<title>.mp4
        ├── clip_01_<title>.ass
        ├── ...
        └── stacked/
            ├── clip_01_<title>.mp4
            └── ...
```
