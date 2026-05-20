# Sprint 9 — Database Migrations + PostgreSQL

## Goal

Replace `create_all(checkfirst=True)` with proper Alembic migrations so schema changes are
applied safely in production. Abstract the database connection string so SQLite remains the
default for local development and CI while PostgreSQL can be opted-in via `DATABASE_URL`.
This makes the project genuinely production-ready at the data layer.

This sprint also creates the initial migration that captures the full schema from Sprints 1–5
so that any future column added has a trackable history.

---

## Step 0 — Doc Pre-flight

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 9 status | `🔜 Planned` → `🚧 In Progress` |

---

## Step 1 — Install Alembic and Add to Dev Extras

### `pyproject.toml`

```toml
[project.optional-dependencies]
dev = [
    "pytest>=9.0.3",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
    "types-PyYAML>=6.0",
    "pre-commit>=3.7",
    "bandit>=1.7",
    "pip-audit>=2.7",
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "alembic>=1.13",          # NEW
    "psycopg2-binary>=2.9",   # NEW — optional PostgreSQL driver (binary for CI ease)
]
```

```bash
pip install -e ".[dev,server]"
```

---

## Step 2 — `DATABASE_URL` Abstraction

### `src/clipsmith/db/session.py`

Replace the hardcoded SQLite path with a `DATABASE_URL` environment variable. When not set,
fall back to `sqlite:///./work/clipsmith.db` relative to the CWD (same default as before,
but now matches what Alembic needs).

```python
"""SQLAlchemy engine initialisation and session factory."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None  # type: ignore[type-arg]


def _default_url() -> str:
    """SQLite URL relative to CWD work dir (matches historic default)."""
    return f"sqlite:///{Path('work/clipsmith.db').resolve()}"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", _default_url())


def init_db(db_path: Path | str | None = None) -> None:
    """Create engine, run DDL via Alembic (preferred) or create_all, store factory.

    `db_path` is kept for backward-compat with existing callers; when DATABASE_URL
    is set it takes precedence.
    """
    global _engine, _SessionLocal

    url = os.getenv("DATABASE_URL")
    if url is None and db_path is not None:
        url = f"sqlite:///{db_path}"
    if url is None:
        url = _default_url()

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(_engine)   # kept as fallback; Alembic takes over in Sprint 9+


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("DB not initialised — call init_db() before using get_session()")
    return _SessionLocal()
```

The `create_all` call is kept as a safety net for local dev / tests. Once Alembic is in
place, the CI runs `alembic upgrade head` before the test suite which makes `create_all`
a no-op (tables already exist).

---

## Step 3 — Alembic Initialisation

```bash
alembic init alembic
```

This creates:

```
alembic/
├── env.py          Migration runner (customise to read DATABASE_URL)
├── script.py.mako  Migration file template
└── versions/       (empty — migrations created here)
alembic.ini         Top-level config file
```

### `alembic/env.py` (replace generated content)

```python
from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all models so Alembic's autogenerate sees them
from clipsmith.db.models import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    from clipsmith.db.session import get_database_url
    return get_database_url()


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,   # required for SQLite ALTER support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,   # required for SQLite ALTER support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### `alembic.ini` (key lines only — keep rest as generated)

```ini
[alembic]
script_location = alembic
# sqlalchemy.url is set dynamically in env.py — leave blank here
sqlalchemy.url =
```

---

## Step 4 — Initial Migration

Generate the initial migration from the current ORM models (Sprints 1–5 schema):

```bash
alembic revision --autogenerate -m "initial schema"
```

This produces `alembic/versions/<hash>_initial_schema.py`. Review the generated
`upgrade()` and `downgrade()` functions — autogenerate should produce the full
`runs`, `clips`, and `pipeline_events` tables including Sprint 5 columns
(`signal_breakdown`, `prompt_version`).

If `signal_breakdown` or `prompt_version` are missing (added after the ORM was last
used), add them manually to the migration:

```python
def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vod_id", sa.String(64), nullable=False, index=True),
        sa.Column("channel", sa.String(128), nullable=False, server_default=""),
        sa.Column("status", sa.Enum("pending", "running", "done", "failed", name="runstatus"), nullable=False),
        sa.Column("stage", sa.String(64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.String(32), server_default="v1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "clips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("title", sa.String(256), nullable=False, server_default=""),
        sa.Column("start_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("end_s", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approved", sa.Boolean(), nullable=True),
        sa.Column("published_url", sa.String(512), nullable=True),
        sa.Column("signal_breakdown", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("pct", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
```

Verify the migration round-trips cleanly:

```bash
alembic upgrade head      # applies migration
alembic downgrade -1      # reverts it
alembic upgrade head      # re-applies
```

---

## Step 5 — CI Update

### `.github/workflows/ci.yml`

```yaml
  tests:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: sudo apt-get install -y ffmpeg
      - run: pip install -e ".[dev,server]"
      - run: alembic upgrade head          # NEW — apply migrations before tests
      - run: python -m pytest tests/ -q
```

The test suite's `conftest.py` in `tests/api/` uses an in-memory SQLite DB via `StaticPool`
and calls `Base.metadata.create_all` directly — this remains correct for unit/integration
tests. The CI migration step validates the migration file itself against a real SQLite file,
not the in-memory test DB.

Add `work/clipsmith.db` to `.gitignore` if not already present:

```
work/
*.db
```

---

## Step 6 — PostgreSQL Local Test (Optional but Recommended)

Verify the full stack works with PostgreSQL using Docker:

```bash
docker run -d \
  -e POSTGRES_DB=clipsmith \
  -e POSTGRES_USER=clipsmith \
  -e POSTGRES_PASSWORD=clipsmith \
  -p 5432:5432 \
  postgres:16-alpine

export DATABASE_URL="postgresql+psycopg2://clipsmith:clipsmith@localhost:5432/clipsmith"
alembic upgrade head
clipsmith serve
```

The `JSON` column type maps to `jsonb` in PostgreSQL automatically via SQLAlchemy.

---

## Step 7 — Documentation Update

### `docs/configuration.md` — new section

```markdown
## Database

clipsmith uses SQLite by default. To use PostgreSQL, set `DATABASE_URL`:

```bash
# SQLite (default)
# No configuration needed — uses work/clipsmith.db

# PostgreSQL
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/clipsmith"

# Apply migrations (run once per environment)
alembic upgrade head
```

`DATABASE_URL` follows the [SQLAlchemy engine URL format](https://docs.sqlalchemy.org/en/20/core/engines.html).

### Adding schema changes

Never edit the DB directly. Always create a new migration:

```bash
# After editing src/clipsmith/db/models.py:
alembic revision --autogenerate -m "add my_column to clips"
# Review the generated file, then:
alembic upgrade head
```
```

---

## File Layout (final state after Sprint 9)

```
alembic/
├── env.py                          NEW — reads DATABASE_URL, render_as_batch=True
├── script.py.mako                  NEW (generated)
└── versions/
    └── <hash>_initial_schema.py    NEW — full schema Sprints 1–5

alembic.ini                         NEW — sqlalchemy.url left blank (env.py sets it)

src/clipsmith/db/
└── session.py                      MODIFIED — DATABASE_URL env var, get_database_url()

.github/workflows/
└── ci.yml                          MODIFIED — alembic upgrade head before pytest

pyproject.toml                      MODIFIED — alembic, psycopg2-binary in [dev]

docs/
└── configuration.md                MODIFIED — DATABASE_URL section, migration guide
```

---

## Verification Checklist

### Alembic
- [ ] `alembic upgrade head` on a clean environment creates all three tables
- [ ] `alembic downgrade -1` removes them cleanly
- [ ] `alembic upgrade head` a second time is idempotent (no errors)
- [ ] `alembic current` shows the latest revision

### DATABASE_URL
- [ ] `DATABASE_URL=sqlite:///./custom.db alembic upgrade head` uses the custom path
- [ ] `clipsmith serve` with `DATABASE_URL` set uses that database
- [ ] `DATABASE_URL` unset → defaults to `work/clipsmith.db` (same as before)

### PostgreSQL
- [ ] `alembic upgrade head` works against a local PostgreSQL instance
- [ ] `clipsmith serve` starts with PostgreSQL; `POST /runs` stores a run correctly
- [ ] `signal_breakdown` column is `jsonb` in PostgreSQL (not text)

### CI
- [ ] CI test job passes after adding `alembic upgrade head` step
- [ ] Tests still pass using in-memory SQLite (they use `StaticPool`, not Alembic)
- [ ] Migration file is committed; `alembic check` shows no schema drift

### Backward Compatibility
- [ ] Existing `clipsmith serve` without `DATABASE_URL` behaves identically to pre-Sprint 9
- [ ] Old SQLite databases (pre-Sprint 9) can be migrated with `alembic upgrade head` (no data loss)
