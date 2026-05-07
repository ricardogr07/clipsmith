"""Root conftest: e2e gate, shared helpers re-exported for backward compatibility."""

from __future__ import annotations

import pytest

from helpers import _seg, _transcript, _word  # noqa: F401  (re-export for legacy bare imports)

__all__ = ["_word", "_seg", "_transcript"]


# ── E2E gate ──────────────────────────────────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Include e2e tests (skipped by default; requires real credentials + ffmpeg).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-e2e"):
        return
    skip_e2e = pytest.mark.skip(reason="e2e tests are skipped unless --run-e2e is passed")
    for item in items:
        if "tests/e2e/" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip_e2e)
