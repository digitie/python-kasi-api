from __future__ import annotations

from typing import Any

import pytest

from kasi import KasiClient
from kasi.parser import parse_function_response

from .conftest import FakeResponse, FakeSession, kasi_payload


@pytest.mark.parametrize("value,expected", [
    (None, None), ("bad", None), ("", None), (False, None), (True, None),
    (-1, None), (0.0, None), (1.9, None), ("1.9", None), ("1e0", None),
    ("１２", None), ("9" * 5000, None), (2**63, None), (str(2**63), None),
    (0, 0), ("0", 0), (" 2 ", 2), (2, 2),
])
@pytest.mark.parametrize("has_item", [False, True])
async def test_live_and_replay_preserve_unverified_or_contradictory_count(
    value: Any, expected: int | None, has_item: bool,
) -> None:
    row = {"locdate": "20260927", "dateName": "휴일", "isHoliday": "Y"}
    response = kasi_payload(row if has_item else None)
    body = response["response"]["body"]
    if value is None:
        body.pop("totalCount")
    else:
        body["totalCount"] = value
    async with KasiClient(
        "fake-test-key", session=FakeSession(FakeResponse(response)), retries=0,
    ) as client:
        live = await client.holidays(sol_year=2026, sol_month=9)
    replay = parse_function_response("holidays", body)
    assert live.total_count == expected
    assert replay.total_count == expected
    assert len(live.items) == int(has_item)
    assert len(replay.items) == int(has_item)
    # 0+1행도 1로 보정하지 않아 소비자가 모순을 식별할 수 있어야 한다.
    assert live.raw == body
