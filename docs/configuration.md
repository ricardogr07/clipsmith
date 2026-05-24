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

# Observability (optional — requires pip install -e ".[observability]")
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317   # send traces to local collector
APPLICATIONINSIGHTS_CONNECTION_STRING=...            # forward traces to Azure Monitor

# Azure credentials (cloud mode only)
AZURE_SUBSCRIPTION_ID=...

# Azure Service Principal — optional but recommended (see docs/cloud.md)
# Without these, DefaultAzureCredential falls back to `az login`
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_TENANT_ID=...

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
  preroll_s: 25       # seconds before the candidate timestamp to start the clip
  postroll_s: 10      # seconds after the candidate timestamp to end the clip
  min_clip_gap_s: 120 # minimum seconds between any two LLM-selected clips
```

The LLM is instructed to keep clips within `min_seconds`/`max_seconds`. `preroll_s` and `postroll_s` define how much context around each candidate is included before LLM trimming. `min_clip_gap_s` prevents two clips from being too close together.

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
  max_workers: 4
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
  density_window_s: 15               # sliding window for chat density peaks
  density_peak_multiplier: 4.0       # chat density must exceed baseline × this to score
  existing_clip_boost: 100.0         # score added per existing Twitch clip at this timestamp
  clip_command_boost: 25.0           # score added per !clip chat command
  dedupe_window_s: 60                # candidates within this window are merged (highest score wins)
  transcript_hype_score: 12.0        # score added per hype keyword hit in transcript
  audio_energy_enabled: true
  audio_energy_window_s: 2.0         # RMS peak detection window
  audio_energy_peak_multiplier: 2.0  # RMS must exceed baseline × this to score
  audio_energy_boost: 15.0           # score added per audio energy peak
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
  resource_group: clipsmith-rg   # used only by `clipsmith cloud status`
  location: eastus
  aci_cpu: 4.0
  aci_memory_gb: 16.0
  docker_image: "<yourdockerhubuser>/clipsmith:latest"
  gpu_sku: ""          # V100 | P100 | K80 — empty means CPU-only
```

| Key | Description |
|-----|-------------|
| `resource_group` | Resource group prefix used by `clipsmith cloud status` to list running jobs. Actual run resource groups are ephemeral and unique per run. |
| `location` | Azure region for ephemeral resources (e.g. `eastus`, `westus2`) |
| `aci_cpu` | vCPU count for the container (4.0 handles a 2-hr VOD in ~60 min) |
| `aci_memory_gb` | RAM for the container in GB |
| `docker_image` | Full Docker Hub image tag (built by `clipsmith cloud build`) |
| `gpu_sku` | Optional NVIDIA GPU model — requires quota increase from Azure |

Storage accounts and file shares are provisioned automatically per run and torn down on completion. No manual storage setup is required. The `cloud` section is only used by `clipsmith cloud` commands — local `run-vod` and `process` ignore it.

---

## Database

clipsmith uses SQLite by default (stored at `work/clipsmith.db`). To use PostgreSQL in
production, set `DATABASE_URL` before starting the server or running migrations:

```bash
# SQLite (default — no configuration needed)
clipsmith serve

# PostgreSQL
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/clipsmith"
alembic upgrade head   # run once per environment, then:
clipsmith serve
```

`DATABASE_URL` follows the [SQLAlchemy engine URL format](https://docs.sqlalchemy.org/en/20/core/engines.html).

### Applying migrations

Run once on a fresh environment, or after pulling new migrations from source control:

```bash
alembic upgrade head
```

### Adding schema changes

Never edit the database directly. Always create a migration:

```bash
# 1. Edit src/clipsmith/db/models.py
# 2. Generate the migration:
alembic revision --autogenerate -m "add my_column to clips"
# 3. Review the generated file under alembic/versions/
# 4. Apply:
alembic upgrade head
```
