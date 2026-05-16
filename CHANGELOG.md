# Changelog

## [0.3.0](https://github.com/ricardogr07/clipsmith/compare/v0.2.1...v0.3.0) (2026-05-16)


### Features

* Spanish Colab notebook + Drive save with clip selection ([#6](https://github.com/ricardogr07/clipsmith/issues/6)) ([24a58bc](https://github.com/ricardogr07/clipsmith/commit/24a58bc5997c2612c5ee05e1e7c5b9d68e8157d6))
* Sprint 1 — FastAPI REST layer + SQLite persistence ([#7](https://github.com/ricardogr07/clipsmith/issues/7)) ([0f64418](https://github.com/ricardogr07/clipsmith/commit/0f644181c0cfdc71a888687b96c1987852b461c9))
* Sprint 2 — Next.js 16 dashboard ([#9](https://github.com/ricardogr07/clipsmith/issues/9)) ([ea7b0be](https://github.com/ricardogr07/clipsmith/commit/ea7b0bebde1a40dc2975738a2a3698260a9f13f0))
* Sprint 3 — Observability + Pipeline Reliability ([#11](https://github.com/ricardogr07/clipsmith/issues/11)) ([858f447](https://github.com/ricardogr07/clipsmith/commit/858f447735585942fcc0f1da1bbf3af8a0698638))
* Sprint 4 — Publishing + Polish ([#12](https://github.com/ricardogr07/clipsmith/issues/12)) ([4d48e73](https://github.com/ricardogr07/clipsmith/commit/4d48e7367944da1b67714dee1b75b4434fb5e855))


### Bug Fixes

* use PAT for release-please so tag pushes trigger publish workflow ([#4](https://github.com/ricardogr07/clipsmith/issues/4)) ([50e0610](https://github.com/ricardogr07/clipsmith/commit/50e0610cb5aa739a6769e44f9ac8aa031645ff2d))

## [0.2.1](https://github.com/ricardogr07/clipsmith/compare/v0.2.0...v0.2.1) (2026-05-09)


### Bug Fixes

* use pip install clipsmith-ai in all Colab notebooks ([#3](https://github.com/ricardogr07/clipsmith/issues/3)) ([6eedef5](https://github.com/ricardogr07/clipsmith/commit/6eedef5d7ed4724741d969ebf1b882e3718be489))

## [0.2.0](https://github.com/ricardogr07/clipsmith/compare/v0.1.0...v0.2.0) (2026-05-09)


### Features

* add --local flag to skip Twitch API calls for offline runs ([f7a2dd1](https://github.com/ricardogr07/clipsmith/commit/f7a2dd1c3662ca8dee8245c612284addb2a7b7cf))
* add process and setup commands for non-technical users ([78a6b80](https://github.com/ricardogr07/clipsmith/commit/78a6b8087c0a0b34012be5e8375486d515849e6b))
* add PyInstaller spec, Windows build script, and user README ([ec4ac9a](https://github.com/ricardogr07/clipsmith/commit/ec4ac9aa240beb8d248c526e8f04173e406ec6ac))
* add reframe=none stream-copy and transcript-sample fallback ([5d2f84c](https://github.com/ricardogr07/clipsmith/commit/5d2f84cf5457d1817b2727f923c9a4bbbc1321e4))
* PyPI distribution as clipsmith-ai with release-please and OIDC publish ([42673c4](https://github.com/ricardogr07/clipsmith/commit/42673c449d69bd38bb24fe74a13d101d5fcfa428))
* replace chat_downloader with direct Twitch GQL pagination ([44933e7](https://github.com/ricardogr07/clipsmith/commit/44933e79b628ffead0307672bf26b89aeac8c670))
* two-path .env discovery and bundled ffmpeg detection ([d10d6b6](https://github.com/ricardogr07/clipsmith/commit/d10d6b6482eeb9aeca4f619cf38a87b9cec9b72d))


### Bug Fixes

* install ffmpeg in tests job; upgrade pip and skip editable in pip-audit ([a570434](https://github.com/ricardogr07/clipsmith/commit/a570434e23aa14608f2e80f7169e97dccc7bf353))


### Documentation

* add ARCHITECTURE.md with pipeline diagram and module map ([ef554eb](https://github.com/ricardogr07/clipsmith/commit/ef554eb4999dc41e3f9c8032c3363e0ebb08f454))
* add Artifacts section to architecture.md ([e0a0b37](https://github.com/ricardogr07/clipsmith/commit/e0a0b37d151a0323b631a7d985d464c40f1bc78d))
* add MkDocs site with Material theme ([0765f6e](https://github.com/ricardogr07/clipsmith/commit/0765f6e9b9849a6b947d9a1e0a7d768476f8e0b3))
* refresh all docs, add SP setup, replace Colab notebook ([41c9faf](https://github.com/ricardogr07/clipsmith/commit/41c9faf3c0ea76994a00dd83f38a9124e5d2f3d1))
* refresh architecture, add cloud guide, update commands and configuration ([4b50d2d](https://github.com/ricardogr07/clipsmith/commit/4b50d2d1a7065f8e1484827c4a0580df027f48e2))
