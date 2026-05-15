from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.runners import RUNNERS
from tests.utils import assert_case

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def all_fixture_files() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*/*.json"))


@pytest.mark.parametrize(
    "fixture_path",
    all_fixture_files(),
    ids=lambda path: f"{path.parent.name}/{path.stem}",
)
def test_generated_fixtures(fixture_path: Path) -> None:
    with fixture_path.open("r", encoding="utf-8") as file:
        case: dict[str, Any] = json.load(file)

    function_name = case["function"]
    runner = RUNNERS[function_name]
    request = case.get("request", {})
    response = case["response"]

    parsed = runner["parse"](
        response["body"],
        request_params=request.get("query", {}),
        response_status_code=response.get("status_code"),
        response_headers=response.get("headers", {}),
    )
    processed = runner["process"](parsed)
    assertion = case.get("assertion", {"mode": "snapshot"})

    assert_case(processed, case["processed"], assertion)
