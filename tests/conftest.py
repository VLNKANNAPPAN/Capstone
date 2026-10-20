from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest


@pytest.fixture
def fixture_json() -> Any:
    def load(name: str) -> dict[str, Any]:
        path = Path(__file__).parent / "fixtures" / name
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    return load
