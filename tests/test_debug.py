from __future__ import annotations

import json

import pytest

from kasi import save_fixture

from .conftest import FakeResponse, kasi_payload


def test_debug_holidays_returns_fixture_ready_run(fake_client_factory) -> None:
    row = {
        "dateKind": "01",
        "dateName": "Children's Day",
        "isHoliday": "Y",
        "locdate": "20260505",
        "seq": "1",
    }
    client, _session = fake_client_factory(
        FakeResponse(
            kasi_payload(row),
            text='{"response":{}}',
            headers={"content-type": "application/json"},
        )
    )

    run = client.debug_holidays(sol_year=2026, sol_month=5)

    assert run.error is None
    assert run.function == "holidays"
    assert run.input == {"sol_year": 2026, "sol_month": 5}
    assert run.request["query"]["solMonth"] == "05"
    assert "serviceKey" not in run.request["query"]
    assert run.response["status_code"] == 200
    assert run.response["headers"]["content-type"] == "application/json"
    assert run.processed["items"][0]["locdate"] == "20260505"
    assert run.catalog is not None
    assert run.catalog["dataset_name"] == "한국천문연구원 특일 정보 - 공휴일"
    assert run.catalog["service_key_url"] == "https://www.data.go.kr/data/15012690/openapi.do"
    assert any("데이터셋:" in item for item in run.trace)


def test_debug_returns_error_without_raising(fake_client_factory) -> None:
    client, _session = fake_client_factory()

    run = client.debug_holidays(sol_year=2026, sol_month=13)

    assert run.error is not None
    assert run.error["type"] == "ValueError"
    assert run.parsed is None
    assert run.processed is None


def test_save_fixture_redacts_sensitive_values(tmp_path, fake_client_factory) -> None:
    row = {
        "dateKind": "01",
        "dateName": "Children's Day",
        "isHoliday": "Y",
        "locdate": "20260505",
        "seq": "1",
    }
    client, _session = fake_client_factory(FakeResponse(kasi_payload(row), text='{"response":{}}'))
    run = client.debug_holidays(sol_year=2026, sol_month=5)

    path = save_fixture(
        base_dir=tmp_path,
        function_name=run.function,
        case_name="children day",
        description="어린이날 정상 응답 fixture",
        input_data={"serviceKey": "SECRET", **run.input},
        request_data={"query": {"serviceKey": "SECRET", **run.request["query"]}},
        response_data={**run.response, "headers": {"Authorization": "Bearer SECRET"}},
        parsed_result=run.parsed,
        processed_result=run.processed,
        library_version="0.1.0",
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["input"]["serviceKey"] == "<REDACTED>"
    assert data["request"]["query"]["serviceKey"] == "<REDACTED>"
    assert data["response"]["headers"]["Authorization"] == "<REDACTED>"
    assert data["processed"]["items"][0]["locdate"] == "20260505"

    with pytest.raises(FileExistsError):
        save_fixture(
            base_dir=tmp_path,
            function_name=run.function,
            case_name="children day",
            description="중복 저장 방지",
            input_data=run.input,
            request_data=run.request,
            response_data=run.response,
            parsed_result=run.parsed,
            processed_result=run.processed,
        )
