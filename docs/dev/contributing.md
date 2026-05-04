# Dev Setup

## Install

```sh
git clone https://github.com/ricardogr07/clipsmith
cd clipsmith
pip install -e ".[dev]"
pip install -e ".[vision]"   # optional — for detect-webcam and OpenCV tests
```

## Run tests

```sh
pytest tests/ -q
```

The test suite has 115 tests and runs in ~2 s. Core pipeline logic has >96% coverage.
No external services are called — all LLM and Twitch API calls are mocked.

## Type checking

```sh
mypy src/
```

Strict mode is off; `disallow_untyped_defs = true` is enforced. Must report
`Success: no issues found` before merging.

## Linting

```sh
ruff check src tests
```

Line length: 100. Target: Python 3.11.

## Security scanning

```sh
bandit -r src/ -ll -x tests/
pip-audit
```

Both run in CI. `bandit` must report `No issues identified`. `pip-audit` flags known CVEs
in the installed environment.

## CI

GitHub Actions runs on every push and PR (`.github/workflows/ci.yml`):

| Job | Steps |
|-----|-------|
| `ci` | ruff → mypy → pytest |
| `security` | bandit → pip-audit |

## Docs

```sh
pip install -e ".[dev]"   # includes mkdocs + mkdocs-material
mkdocs serve              # live-reload at http://127.0.0.1:8000
mkdocs build --strict     # production build, fails on warnings
```

Doc source lives in `docs/`. The site config is `mkdocs.yml` at the repo root.

## Module layout

```
src/clipsmith/
├── cli.py              Entry point — registers commands from cli_run/clip/setup
├── cli_run.py          process, watch, run-vod, whoami
├── cli_clip.py         clip, reframe
├── cli_setup.py        setup, check-ollama, detect-webcam
├── cli_utils.py        _resolve_config, _parse_start_at
├── pipeline.py         Orchestrator — calls stages 1-6
├── downloader.py       twitch-dl wrapper
├── detect.py           OpenCV Haar cascade webcam detection
├── transcribe.py       faster-whisper wrapper
├── chat.py             Twitch GQL chat replay
├── candidates.py       Signal merging and scoring
├── candidates_math.py  Sliding-window density + peak detection
├── audio_signal.py     ffmpeg RMS energy extraction
├── selector.py         LLM loop → PickResult list
├── llm/
│   ├── base.py         ClipPicker Protocol, ClipPick dataclass
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   └── ollama_provider.py
├── clipper.py          ffmpeg clip cutting + ASS caption burn-in
├── captions.py         Transcript → ASS subtitle file
├── settings.py         AppConfig (YAML) + Secrets (.env)
├── state.py            Persists seen VOD IDs
└── watcher.py          Twitch poll daemon
```

## Adding a new LLM provider

1. Create `src/clipsmith/llm/<name>_provider.py` implementing the `ClipPicker` Protocol
   from `src/clipsmith/llm/base.py`.
2. Add a branch in `src/clipsmith/selector.py` where providers are instantiated.
3. Add the provider name to the `--provider` help strings in `cli_run.py` and `cli_setup.py`.
4. Write tests in `tests/test_selector.py` mocking the new provider.
