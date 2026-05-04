# Examples

## Google Colab notebook

Run clipsmith entirely in the cloud — no local GPU or ffmpeg install required.

[**Open in Colab →**](https://colab.research.google.com/github/ricardogr07/clipsmith/blob/main/examples/clipsmith_colab.ipynb){ .md-button }

The notebook covers:

- Installing clipsmith and dependencies in a Colab runtime
- Configuring Anthropic or OpenAI as the LLM provider
- Downloading and processing a Twitch VOD
- Downloading the output clips

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
