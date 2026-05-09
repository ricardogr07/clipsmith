# Examples

## Google Colab Notebooks

Four notebooks — pick the one that matches your setup:

| Notebook | Runtime | LLM | Cost |
|---|---|---|---|
| [01 — Local MP4](https://colab.research.google.com/github/ricardogr07/clipsmith/blob/main/examples/01_local_mp4.ipynb) | CPU | Anthropic or OpenAI | API cost only |
| [02 — Local VOD](https://colab.research.google.com/github/ricardogr07/clipsmith/blob/main/examples/02_local_vod.ipynb) | CPU | Anthropic or OpenAI | API cost only |
| [03 — Local VOD + Ollama](https://colab.research.google.com/github/ricardogr07/clipsmith/blob/main/examples/03_local_vod_ollama.ipynb) | T4 GPU | Ollama (free) | Free |
| [04 — Cloud (Azure ACI)](https://colab.research.google.com/github/ricardogr07/clipsmith/blob/main/examples/04_cloud.ipynb) | CPU (Colab triggers Azure) | Anthropic | ~$0.30/VOD |

### 01 — Local MP4

Upload a recording you already have. No Twitch credentials needed.

- Upload your MP4 directly in the notebook
- Transcribes and selects clips using Anthropic or OpenAI
- Downloads finished clips back to your computer

### 02 — Local VOD

Download a Twitch VOD and process it end-to-end on Colab's CPU.

- Requires a Twitch VOD ID
- Transcription takes ~25–40 min for a 2-hr VOD (CPU `small` model)
- Uses Anthropic or OpenAI for clip selection

### 03 — Local VOD + Ollama (free)

Same as 02 but uses a T4 GPU for fast transcription and Ollama for free LLM inference — no API key or cost.

- Requires **T4 GPU runtime** (Runtime → Change runtime type)
- Transcription takes ~8–12 min for a 2-hr VOD (GPU `medium` model)
- Ollama model (~4.7 GB) downloads once per session; optionally persisted to Drive

### 04 — Cloud (Azure ACI)

Trigger a full Azure cloud run from Colab. Colab just orchestrates — all compute happens in Azure.

- Requires Azure credentials, Docker Hub image already pushed (`clipsmith cloud build`)
- ACI container runs the full pipeline (~60 min for a 2-hr VOD)
- Clips are uploaded automatically to Google Drive; Azure resources deleted on completion
- Cost: ~$0.30 per 2-hr VOD

---

## Common workflows

### Process a local recording

```sh
clipsmith process recording.mp4
```

### Process with captions and center-crop reframe

```sh
clipsmith process recording.mp4 --captions --reframe
```

### Download and process a Twitch VOD

```sh
clipsmith run-vod 2345678901
```

### Re-cut clips after changing caption font size

Edit `config.yaml`, then:

```sh
clipsmith clip 2345678901
```

### Use a specific LLM provider for one run

```sh
clipsmith run-vod 2345678901 --provider openai
```

### Limit expensive LLM calls during testing

```sh
clipsmith run-vod 2345678901 --max-candidates 5
```

### Skip re-downloading when the MP4 is already in `work/`

```sh
clipsmith run-vod 2345678901 --skip-download
```

### Process only the second half of a long VOD

```sh
clipsmith process recording.mp4 --start-at 1:30:00
```

### Auto-detect webcam rect and generate stacked clips

```sh
# 1. detect and write webcam_rect into config.yaml
clipsmith detect-webcam 2345678901

# 2. process normally (flat clips first)
clipsmith run-vod 2345678901

# 3. reframe the best ones
clipsmith reframe 2345678901 clip_01 clip_03 clip_07
```

### Watch a channel continuously

```sh
clipsmith watch chuyelwuero
```

Polls every 120 s. `Ctrl+C` to stop. State is persisted so it picks up where it left off.
