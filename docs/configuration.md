# Configuration

clipsmith uses two config files: `.env` for secrets and `config.yaml` for behaviour.

---

## `.env` — Secrets

Copy `.env.example` to `.env` and fill in your keys:

```env
# Twitch app credentials (https://dev.twitch.tv/console)
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...

# LLM providers (only set the one(s) you'll use)
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...

# Azure credentials (cloud mode only)
AZURE_SUBSCRIPTION_ID=...
AZURE_STORAGE_ACCOUNT=...
AZURE_STORAGE_KEY=...

# Docker Hub credentials (cloud mode — prevents ACI rate-limit errors)
DOCKER_HUB_USERNAME=...
DOCKER_HUB_PASSWORD=...     # use a read-only access token, not your password

# Google Drive (cloud mode — run `clipsmith cloud drive-auth` once after setting this)
GOOGLE_OAUTH_CLIENT_JSON=C:\git\clipsmith\google_oauth_client.json
GOOGLE_DRIVE_FOLDER_ID=...
```

Get Twitch credentials at <https://dev.twitch.tv/console> → Register Your Application →
OAuth Redirect: `http://localhost`.

---

## `config.yaml` — Behaviour

### `channels`

```yaml
channels:
  - chuyelwuero   # Twitch logins to watch in daemon mode
```

List of Twitch logins that `clipsmith watch` polls. Override per-run with a positional argument.

---

### `llm`

```yaml
llm:
  provider: anthropic          # anthropic | openai | ollama
  model_anthropic: claude-sonnet-4-6
  model_openai: gpt-4.1
  model_ollama: llama3.1:8b
```

| Key | Description |
|-----|-------------|
| `provider` | Active LLM provider. Override per-run with `--provider`. |
| `model_anthropic` | Anthropic model ID |
| `model_openai` | OpenAI model ID |
| `model_ollama` | Ollama model name (must be pulled locally) |

---

### `clip`

```yaml
clip:
  min_seconds: 15
  max_seconds: 30
```

The LLM is instructed to keep clips within this window. ffmpeg trims to these bounds.

---

### `caption`

```yaml
caption:
  enabled: false      # burn subtitles into the video
  font: Arial
  font_size: 72       # ASS pts at 1080×1920 PlayRes
  outline: 3
  position: bottom    # bottom | middle | top
```

| Key | Description |
|-----|-------------|
| `enabled` | Set `true` to burn Spanish karaoke captions into every clip |
| `font` | Font family name (must be installed on the system) |
| `font_size` | Size in ASS points at 1080×1920 resolution |
| `outline` | Subtitle outline thickness in pixels |
| `position` | Vertical position: `bottom`, `middle`, or `top` |

Override per-run with `--captions` / `--no-captions`.

---

### `reframe`

```yaml
reframe:
  mode: none                # center | webcam | stacked | none
  webcam_rect: null         # [x, y, w, h] in source pixels
  gameplay_rect: null       # [x, y, w, h] in source pixels (stacked only)
  split_ratio: 0.4          # fraction of 1920px for the top (webcam) panel
```

| Mode | Description |
|------|-------------|
| `none` | Stream-copy, no re-encode or crop |
| `center` | Center-crop to 9:16, scale to 1080×1920 |
| `webcam` | Crop to `webcam_rect`, scale to 1080×1920 |
| `stacked` | Two-panel: `webcam_rect` top + `gameplay_rect` bottom |

`webcam_rect` and `gameplay_rect` are source-pixel coordinates `[x, y, w, h]`.
Run `clipsmith detect-webcam <video_id>` to auto-detect and write `webcam_rect` into this file.

Override reframe mode per-run with `--reframe` / `--no-reframe`.

---

### `transcribe`

```yaml
transcribe:
  model: small              # tiny | small | medium | large-v3
  language: es
  compute_type: int8
  chunk_minutes: 10         # 0 = no chunking
  chunk_overlap_s: 30
  max_workers: 2
```

| Key | Description |
|-----|-------------|
| `model` | faster-whisper model size. `large-v3` is most accurate; `tiny` is fastest. |
| `language` | Source audio language (ISO 639-1) |
| `compute_type` | `int8` (CPU, fast) or `float16` (GPU) |
| `chunk_minutes` | Split audio into N-minute chunks for parallel transcription. `0` = disabled. |
| `chunk_overlap_s` | Overlap between chunks to avoid cutting words mid-sentence |
| `max_workers` | Thread pool size for parallel chunk transcription |

---

### `candidates`

```yaml
candidates:
  max_candidates: 20        # top-N sent to the LLM
  merge_window_s: 60        # candidates within this window are merged
```

---

### `poll_interval_s`

```yaml
poll_interval_s: 120   # seconds between Twitch polls in watch mode
```

---

### `cloud`

```yaml
cloud:
  resource_group: clipsmith-rg
  location: eastus
  storage_account: <your-storage-account>
  aci_cpu: 4.0
  aci_memory_gb: 16.0
  docker_image: "<yourdockerhubuser>/clipsmith:latest"
  gpu_sku: ""          # V100 | P100 | K80 — empty means CPU-only
```

| Key | Description |
|-----|-------------|
| `resource_group` | Azure resource group containing ACI and storage |
| `location` | Azure region (e.g. `eastus`, `westus2`) |
| `storage_account` | Storage account name (must match `AZURE_STORAGE_ACCOUNT` in `.env`) |
| `aci_cpu` | vCPU count for the container (4.0 handles a 2-hr VOD in ~60 min) |
| `aci_memory_gb` | RAM for the container in GB |
| `docker_image` | Full Docker Hub image tag (built by `clipsmith cloud build`) |
| `gpu_sku` | Optional NVIDIA GPU model — requires quota increase from Azure |

The `cloud` section is only used by `clipsmith cloud` commands. Local `run-vod` and `process` commands ignore it.
