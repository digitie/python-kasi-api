from __future__ import annotations

import os

import pytest

from kasi import KasiClient

LIVE_KEY_ENV_NAMES = ("KASI_SERVICE_KEY", "DATA_GO_SERVICE_KEY", "DATAGOKR_SERVICE_KEY")


def _live_client() -> KasiClient:
    if os.getenv("KASI_LIVE") != "1":
        pytest.skip("set KASI_LIVE=1 to run live KASI data.go.kr tests")
    if not any(os.getenv(name) for name in LIVE_KEY_ENV_NAMES):
        pytest.skip("KASI_SERVICE_KEY, DATA_GO_SERVICE_KEY, or DATAGOKR_SERVICE_KEY is not set")
    return KasiClient.from_env(timeout=15, retries=1)


@pytest.mark.live
def test_live_holidays_from_env_key() -> None:
    client = _live_client()

    page = client.holidays(sol_year=2026, sol_month=5, num_of_rows=20)

    assert page.total_count is not None
    assert page.raw
    assert all(item.locdate for item in page.items)
    assert any(item.date_name for item in page.items)
    assert "serviceKey" not in page.context.request_params


@pytest.mark.live
def test_live_solar_to_lunar() -> None:
    client = _live_client()

    page = client.solar_to_lunar(sol_year=2026, sol_month=5, sol_day=7)

    assert page.items
    first = page.items[0]
    assert first.sol_year == "2026"
    assert first.sol_month == "05"
    assert first.sol_day == "07"
    assert first.lun_month is not None


@pytest.mark.live
def test_live_area_rise_set() -> None:
    client = _live_client()

    page = client.area_rise_set(locdate="20260507", location="서울")

    assert page.items
    first = page.items[0]
    assert first.location == "서울"
    assert first.sunrise
    assert first.sunset
