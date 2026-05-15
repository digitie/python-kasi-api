from __future__ import annotations

from kasi import api_catalog, api_catalog_rows
from kasi.catalog import get_api_catalog_entry


def test_api_catalog_has_human_readable_dataset_names_and_key_links() -> None:
    entry = get_api_catalog_entry("holidays")

    assert entry.dataset_name == "한국천문연구원 특일 정보 - 공휴일"
    assert entry.dataset_id == "15012690"
    assert entry.service_key_url == "https://www.data.go.kr/data/15012690/openapi.do"
    assert entry.display_name == "한국천문연구원 특일 정보 - 공휴일 (holidays)"


def test_api_catalog_rows_are_table_friendly() -> None:
    rows = api_catalog_rows()

    assert len(rows) == len(api_catalog())
    assert rows[0]["데이터셋명"]
    assert rows[0]["서비스키 신청 링크"].startswith("https://www.data.go.kr/data/")
