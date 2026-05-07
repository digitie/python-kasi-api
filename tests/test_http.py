from __future__ import annotations

import pytest

from pykasi._http import KasiHttp, kasi_request_params
from pykasi.exceptions import KasiAuthError, KasiParseError, KasiRateLimitError

from .conftest import FakeResponse, FakeSession, kasi_payload


def test_kasi_request_params_hide_format_and_key_choices() -> None:
    params = kasi_request_params(
        service_key="KEY",
        service_key_param="ServiceKey",
        params={"solYear": "2026"},
        response_format="xml",
    )

    assert params["ServiceKey"] == "KEY"
    assert params["_type"] == "xml"
    assert params["solYear"] == "2026"


def test_http_parses_json_envelope() -> None:
    session = FakeSession(FakeResponse(kasi_payload({"dateName": "holiday"}), text='{"ok":true}'))
    http = KasiHttp("KEY", session=session)

    body = http.get("SpcdeInfoService", "getRestDeInfo", {"solYear": "2026"})

    assert body["items"]["item"]["dateName"] == "holiday"
    assert session.calls[0]["url"].endswith("/SpcdeInfoService/getRestDeInfo")
    assert session.calls[0]["params"]["serviceKey"] == "KEY"
    assert session.calls[0]["params"]["_type"] == "json"


def test_http_parses_xml_envelope() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
<body><items><item><dateName>New Year</dateName><locdate>20260101</locdate></item></items>
<pageNo>1</pageNo><numOfRows>10</numOfRows><totalCount>1</totalCount></body></response>"""
    session = FakeSession(FakeResponse(text=xml))
    http = KasiHttp("KEY", session=session)

    body = http.get("SpcdeInfoService", "getRestDeInfo", response_format="xml")

    assert body["items"]["item"]["dateName"] == "New Year"
    assert body["totalCount"] == "1"


def test_http_maps_service_errors() -> None:
    auth = FakeResponse(
        {
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {
                    "returnReasonCode": "30",
                    "returnAuthMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
                }
            }
        },
        text='{"OpenAPI_ServiceResponse":{}}',
    )
    quota = FakeResponse(
        {
            "response": {
                "header": {"resultCode": "22", "resultMsg": "LIMITED"},
                "body": {},
            }
        },
        text='{"response":{}}',
    )

    with pytest.raises(KasiAuthError):
        KasiHttp("BAD", session=FakeSession(auth)).get("S", "O")
    with pytest.raises(KasiRateLimitError):
        KasiHttp("KEY", session=FakeSession(quota)).get("S", "O")


def test_http_no_data_returns_empty_body() -> None:
    session = FakeSession(
        FakeResponse(
            {"response": {"header": {"resultCode": "03", "resultMsg": "NO_DATA"}, "body": {}}},
            text='{"response":{}}',
        )
    )

    assert KasiHttp("KEY", session=session).get("S", "O") == {}


def test_http_rejects_malformed_payload() -> None:
    session = FakeSession(FakeResponse({"bad": {}}, text='{"bad":{}}'))

    with pytest.raises(KasiParseError):
        KasiHttp("KEY", session=session).get("S", "O")
