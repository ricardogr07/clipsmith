# Clipsmith Architecture

## Overview

Clipsmith turns a Twitch VOD into a set of 9:16 vertical clips with burned-in Spanish captions, ready for TikTok / YouTube Shorts. The pipeline has two entry points: a continuous **watcher** (daemon) that polls Twitch for new VODs, and a one-shot **run-vod** command for manual runs. Both feed the same five-stage pipeline.

---

## Pipeline Stages

```
VOD (mp4)
    │
    ▼
[1] Transcribe ──────────────── faster-whisper (Spanish, CPU int8)
    │ transcript.json            864 segments, word timestamps
    │
    ▼
[2] Chat Download ──────────── chat-downloader (Twitch replay API)
    │ chat.json                  raw messages → ChatMessage (time, author, emotes)
    │                            fallback: evenly-spaced transcript samples
    │
    ▼
[3] Candidate Scoring ────────  three signals merged & deduped
    │ candidates.json
    │   Signal A: existing Twitch clips  (+100 pts/clip)
    │   Signal B: !clip chat commands    (+25 pts each)
    │   Signal C: chat density peaks     (sliding window, 4× baseline)
    │
    ▼
[4] LLM Selection ────────────  one API call per candidate (top-20)
    │ picks.json                 returns: include, start_s, end_s, title_es, reason
    │   Providers: Anthropic │ OpenAI │ Ollama
    │
    ▼
[5] Clip Cutting ─────────────  ffmpeg per pick
    out/<vod_id>/               crop → 9:16 reframe → burned ASS captions
    clip_01_<title>.mp4         libx264 fast / aac 128k / faststart
```

---

## Module Map

```
src/clipsmith/
│
├── cli.py            CLI entry point (Typer)
│     commands:  watch | run-vod | clip | whoami
│
├── pipeline.py       Orchestrator — calls stages 1-5 in order
│                     holds the transcript-fallback logic when chat is empty
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
├── captions.py       Transcript → ASS subtitle file (burn-in, Spanish)
│
└── settings.py       AppConfig (YAML) + Secrets (.env / env vars)
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
        WATCH[watch\ndaemon]
        RUNVOD[run-vod\none-shot]
        CLIP[clip\nre-cut only]
    end

    subgraph Twitch["Twitch API (optional)"]
        HELIX[Helix REST\nget_videos / get_clips]
        TWITCHDL[twitch-dl\ndownload]
    end

    subgraph Pipeline
        DL[Downloader\ndownloader.py]
        TR[Transcriber\ntranscribe.py\nfaster-whisper]
        CH[Chat\nchat.py\nchat-downloader]
        CA[Candidates\ncandidates.py\n+ candidates_math.py]
        SEL[Selector\nselector.py]
        CUT[Clipper\nclipper.py + captions.py\nffmpeg]
    end

    subgraph LLM["LLM Provider (llm/)"]
        ANT[Anthropic\nclaude-sonnet-4-6]
        OAI[OpenAI\ngpt-4.1]
        OLL[Ollama\nllama3.1]
    end

    subgraph Artifacts["work/VIDEO_ID/"]
        T_JSON[transcript.json]
        C_JSON[chat.json]
        CA_JSON[candidates.json]
        P_JSON[picks.json]
    end

    subgraph Output["out/VIDEO_ID/"]
        MP4S[clip_NN_title.mp4\n9:16 · 15-30s · burned captions]
    end

    CFG --> WATCH
    CFG --> RUNVOD
    ENV --> WATCH
    ENV --> RUNVOD

    WATCH -->|new VOD event| Pipeline
    RUNVOD --> Pipeline
    CLIP -->|picks.json exists| CUT

    HELIX -->|existing clips| CA
    TWITCHDL --> DL
    DL --> VOD

    VOD --> TR
    TR --> T_JSON
    T_JSON --> CA
    T_JSON --> SEL
    T_JSON --> CUT

    CH --> C_JSON
    C_JSON --> CA
    CA --> CA_JSON
    CA_JSON --> SEL

    SEL --> ANT & OAI & OLL
    ANT & OAI & OLL --> P_JSON
    P_JSON --> CUT

    VOD --> CUT
    CUT --> MP4S
```

---

## Candidate Scoring Detail

| Signal | Source | Score |
|--------|--------|-------|
| Existing Twitch clip at this VOD offset | Helix API | +100 pts |
| `!clip` chat command in window | Chat replay | +25 pts each |
| Chat density peak (>4× baseline in 15s window) | Chat replay | proportional |
| Evenly-spaced sample (fallback, no chat data) | Transcript | 1 pt (uniform) |

Candidates within 60 s of each other are merged (highest-score center kept, scores summed). Top 20 by score are sent to the LLM.

---

## LLM Prompt Architecture

Each provider sends **two stable blocks + one variable block** to maximise prompt caching:

1. **System prompt** (stable) — role, rules, JSON schema (~300 tokens, cached after first call)
2. **Stream context** (stable per VOD) — channel, title, duration, language (~50 tokens, cached)
3. **Candidate prompt** (varies) — transcript ±60 s window + viewer signals (~200–400 tokens)

The LLM returns a single JSON object: `{ include, start_offset_s, end_offset_s, title_es, reason }`.

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
│       ├── transcript.json
│       ├── chat.json
│       ├── candidates.json
│       └── picks.json
└── out/
    └── <video_id>/
        ├── clip_01_<title>.mp4
        ├── clip_01_<title>.ass
        └── ...
```
