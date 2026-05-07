"""Auto-apply the 'unit' marker to every test collected from tests/unit/."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if "unit" in item.path.parts:
            item.add_marker(pytest.mark.unit)
