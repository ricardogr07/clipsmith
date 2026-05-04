# Clipsmith Improvement Plan

Generated from a full reposage audit (report + security + api-surface + AI enrichment) on 2026-05-03.

---

## Status legend
- [ ] Not started
- [~] In progress
- [x] Done

---

## 1. Security — Subprocess hardening (Low, CWE-78)

Bandit found 17 low-severity findings: 0 medium/high.

| Rule | Count | Location | Action |
|---|---|---|---|
| B403 / B603 — subprocess import + call | 15 | `clipper.py`, `downloader.py`, `transcribe.py`, `detect.py`, `audio_signal.py` | Annotate with `# nosec B603 B404` where input is fully internal (not user-controlled). For calls that receive external data, verify args are sanitized. |
| B607 — partial executable path | 2 | `clipper.py`, `downloader.py` | Use `shutil.which("ffmpeg")` / `shutil.which("yt-dlp")` and raise a clear error if not found, or pin absolute paths from config. |
| B105 — false positive | 1 | `twitch_client.py` (OAuth URL) | Suppress with `# nosec B105`. |

- [ ] Add `# nosec` annotations with justification comments for B403/B603 where args are internal.
- [ ] Replace partial `ffmpeg`/`yt-dlp` paths with `shutil.which()` checks in `clipper.py` and `downloader.py`.
- [ ] Suppress false-positive B105 in `twitch_client.py`.

---

## 2. Security — Dependency vulnerabilities

`pip-audit` was run against the global Python 3.14 env (not the project venv). **Verify each CVE against the actual pinned versions in the project venv before acting.**

| Package | Version | CVE / Advisory | Fix |
|---|---|---|---|
| `pytest` | 9.0.2 | CVE-2025-71176 | Upgrade to ≥9.0.3 |
| `curl-cffi` | 0.13.0 | CVE-2026-33752 | Upgrade to ≥0.15.0 |
| `pillow` | 12.1.1 | CVE-2026-40192 | Upgrade to ≥12.2.0 |
| `pip` | 26.0.1 | CVE-2026-3219 | Upgrade pip |
| `uv` | 0.10.4 | GHSA-pjjw-68hj-v9mw | Upgrade to ≥0.11.6 |

- [ ] Run `pip-audit` inside the project `.venv` to confirm which apply to clipsmith's actual deps.
- [ ] Upgrade affected packages and re-run tests.

---

## 3. CI — Add security scanning to the pipeline

`bandit` and `pip-audit` are not in the CI workflow. Add them so regressions surface in PRs.

- [ ] Add a `security` job to `.github/workflows/ci.yml`:
  ```yaml
  - name: Bandit
    run: bandit -r src/ -ll -x tests/
  - name: pip-audit
    run: pip-audit --requirement requirements.txt  # or pyproject.toml
  ```
- [ ] Pin `bandit` and `pip-audit` in `pyproject.toml` under `[project.optional-dependencies] dev`.

---

## 4. Type annotations — classmethod `cls` parameters

Reposage reported 52 untyped symbols, but actual inspection found only 4 `cls` parameters in classmethods lacking annotations — a minor gap.

Files affected:
- `src/clipsmith/chat.py` — `from_json(cls, ...)`
- `src/clipsmith/transcribe.py` — `from_json(cls, ...)`
- `src/clipsmith/llm/base.py` — `from_dict(cls, ...)`, `from_json(cls, ...)`

- [ ] Add `cls: type[Self]` annotation (using `typing.Self`) to all four classmethods.
- [ ] Run `mypy` to confirm no new errors.

---

## 5. Refactor — Split `cli.py` (671 lines)

`cli.py` is the only genuinely oversized Python module. It mixes command dispatch, argument parsing, output formatting, and some business logic.

Proposed split:
- `cli.py` — entry point and top-level command group only (~100 lines)
- `cli_run.py` — `run` command handler
- `cli_pick.py` — `pick` / `picks` command handler
- `cli_export.py` — `clip` / export command handler
- `cli_fmt.py` — shared output formatting helpers (tables, progress, color)

- [ ] Identify and extract output formatting helpers to `cli_fmt.py` first (lowest risk).
- [ ] Extract each command group into its own module.
- [ ] Ensure all existing CLI tests pass after each extraction step.

---

## 6. Documentation — Media artifact management

The `ARCHITECTURE.md` exists but does not document the `work/` and `out/` directory conventions, or the fact that media files are intentionally gitignored.

- [ ] Add a **Artifacts** section to [architecture.md](../architecture.md) explaining:
  - `work/<VOD_ID>/` — raw download and processing scratch space (gitignored)
  - `out/<VOD_ID>/` — final rendered clips (gitignored)
  - How to regenerate outputs: `clipsmith run <VOD_ID>`
- [ ] Note that `.gitignore` already covers `out/`, `work/`, `*.mp4`, `*.m4a`, `*.ass`, `*.srt`.

> **Note:** Reposage flagged these as "committed binary files." This is a false positive — `git ls-files work/ out/` confirms nothing is tracked.

---

## 7. False positives (no action needed)

These were raised by reposage but are already handled:

| Finding | Status |
|---|---|
| Large video files in version control | `.gitignore` already excludes `out/`, `work/`, `*.mp4`. `git ls-files` confirmed zero tracked. |
| Missing architecture docs | `ARCHITECTURE.md` exists at repo root. |
| Missing CI | `.github/workflows/ci.yml` present with lint + test. |

---

## Priority order

1. **Security → Subprocess hardening** — annotate known-safe calls, fix partial paths.
2. **Security → Dependency audit** — run inside venv, upgrade affected packages.
3. **CI → Add bandit + pip-audit** — prevents regressions.
4. **Type annotations** — 4 classmethods, quick win.
5. **Docs → Artifact conventions** — one short section in ARCHITECTURE.md.
6. **Refactor → cli.py split** — largest effort, lowest urgency.
