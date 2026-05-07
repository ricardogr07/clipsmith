"""Auto-apply the 'e2e' marker to every test collected from tests/e2e/."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if "e2e" in item.path.parts:
            item.add_marker(pytest.mark.e2e)
