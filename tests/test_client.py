from __future__ import annotations

from datetime import date

import pytest

from kasi import KasiClient, SpecialDay

from .conftest import FakeResponse, kasi_payload


def test_special_days_holidays_builds_request_and_model(fake_client_factory) -> None:
    client, session = fake_client_factory(
        FakeResponse(
            kasi_payload(
                {
                    "dateKind": "01",
                    "dateName": "Children's Day",
                    "isHoliday": "Y",
                    "locdate": "20260505",
                    "seq": "1",
                }
            ),
            text='{"response":{}}',
        )
    )

    page = client.holidays(sol_year=2026, sol_month=5)

    assert session.calls[0]["url"].endswith("/SpcdeInfoService/getRestDeInfo")
    assert session.calls[0]["params"]["solYear"] == "2026"
    assert session.calls[0]["params"]["solMonth"] == "05"
    assert session.calls[0]["params"]["pageNo"] == 1
    assert session.calls[0]["params"]["numOfRows"] == 10
    assert "serviceKey" in session.calls[0]["params"]
    assert "serviceKey" not in page.context.request_params
    assert page.context.endpoint == "getRestDeInfo"
    assert isinstance(page.first, SpecialDay)
    assert page.first is not None
    assert page.first.is_holiday is True
    assert page.first.date == date(2026, 5, 5)


def test_calendar_conversion_helpers(fake_client_factory) -> None:
    row = {
        "solYear": "2026",
        "solMonth": "05",
        "solDay": "07",
        "solWeek": "Thu",
        "lunYear": "2026",
        "lunMonth": "03",
        "lunDay": "21",
        "lunNday": "29",
    }
    client, session = fake_client_factory(
        FakeResponse(kasi_payload(row), text='{"response":{}}'),
        FakeResponse(kasi_payload(row), text='{"response":{}}'),
        FakeResponse(kasi_payload([row, row]), text='{"response":{}}'),
        FakeResponse(kasi_payload(row), text='{"response":{}}'),
    )

    solar_to_lunar = client.solar_to_lunar(sol_year=2026, sol_month=5, sol_day=7)
    lunar_to_solar = client.lunar_to_solar(lun_year=2026, lun_month=3, lun_day=21)
    specific = client.specific_lunar(
        from_sol_year=2026,
        to_sol_year=2027,
        lun_month=1,
        lun_day=1,
        leap_month=False,
    )
    julian = client.julian_day(2461168)

    assert solar_to_lunar.first is not None
    assert solar_to_lunar.first.solar_date == date(2026, 5, 7)
    assert lunar_to_solar.first is not None
    assert lunar_to_solar.first.lun_month == "03"
    assert len(specific.items) == 2
    assert julian.first is not None
    assert julian.first.lun_nday == 29
    assert session.calls[0]["url"].endswith("/LrsrCldInfoService/getLunCalInfo")
    assert session.calls[1]["params"]["lunDay"] == "21"
    assert session.calls[2]["params"]["leapMonth"] == "평"
    assert session.calls[3]["params"]["solJd"] == "2461168"


def test_rise_set_and_solar_altitude_helpers(fake_client_factory) -> None:
    rise_row = {
        "locdate": "20260507",
        "location": "서울",
        "longitude": "12659",
        "latitude": "3734",
        "sunrise": "0530",
        "sunset": "1925",
    }
    altitude_row = {
        "locdate": "20260507",
        "location": "서울",
        "longitude_num": "126.9833330",
        "latitude_num": "37.5666660",
        "azimuth_09": "101",
        "altitude_09": "30",
    }
    client, session = fake_client_factory(
        FakeResponse(kasi_payload(rise_row), text='{"response":{}}'),
        FakeResponse(kasi_payload(rise_row), text='{"response":{}}'),
        FakeResponse(kasi_payload(altitude_row), text='{"response":{}}'),
        FakeResponse(kasi_payload(altitude_row), text='{"response":{}}'),
    )

    area = client.area_rise_set(locdate=date(2026, 5, 7), location="서울")
    location = client.location_rise_set(locdate="20260507", longitude=126.98, latitude=37.56)
    altitude_area = client.area_solar_altitude(locdate="2026-05-07", location="서울")
    altitude_location = client.location_solar_altitude(
        locdate=20260507,
        longitude="12659",
        latitude="3734",
    )

    assert area.first is not None
    assert area.first.sunrise == "0530"
    assert location.first is not None
    assert session.calls[1]["params"]["dnYn"] == "Y"
    assert altitude_area.first is not None
    assert altitude_area.first.longitude_num == 126.983333
    assert altitude_location.first is not None
    assert session.calls[3]["params"]["dnYn"] == "N"


def test_moon_phase_astro_events_and_sundays(fake_client_factory) -> None:
    client, session = fake_client_factory(
        FakeResponse(
            kasi_payload(
                {"solYear": "2026", "solMonth": "05", "solDay": "07", "lunAge": "20.1"}
            ),
            text='{"response":{}}',
        ),
        FakeResponse(
            kasi_payload(
                {
                    "locdate": "20260507",
                    "seq": "1",
                    "astroTitle": "Event",
                    "astroTime": "12:00",
                    "astroEvent": "desc",
                }
            ),
            text='{"response":{}}',
        ),
        FakeResponse(
            kasi_payload({"yyyy": "2026", "mm": "05", "dd": "03", "week": "일"}),
            text='{"response":{}}',
        ),
    )

    moon = client.moon_phase(sol_year=2026, sol_month=5, sol_day=7)
    events = client.astro_events(sol_year=2026, sol_month=5)
    sundays = client.sundays(sol_year=2026, sol_month=5)

    assert moon.first is not None
    assert moon.first.lun_age == 20.1
    assert events.first is not None
    assert events.first.astro_title == "Event"
    assert sundays.first is not None
    assert sundays.first.locdate == "20260503"
    assert session.calls[2]["url"].endswith("/SolcWeekInfoService_v2/getWeekInfo_v2")
    assert "pageNo" not in session.calls[2]["params"]


def test_raw_endpoint_and_iter_pages(fake_client_factory) -> None:
    client, _session = fake_client_factory(
        FakeResponse(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "OK"},
                    "body": {
                        "items": {"item": [{"id": "1"}]},
                        "pageNo": 1,
                        "numOfRows": 1,
                        "totalCount": 2,
                    },
                }
            },
            text='{"response":{}}',
        ),
        FakeResponse(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "OK"},
                    "body": {
                        "items": {"item": [{"id": "2"}]},
                        "pageNo": 2,
                        "numOfRows": 1,
                        "totalCount": 2,
                    },
                }
            },
            text='{"response":{}}',
        ),
    )

    pages = list(
        client.iter_pages(
            client.raw_endpoint,
            "S",
            "O",
            num_of_rows=1,
            max_pages=2,
        )
    )

    assert [page.page_no for page in pages] == [1, 2]
    assert [item["id"] for page in pages for item in page.items] == ["1", "2"]


def test_from_env_and_validation(monkeypatch, fake_client_factory) -> None:
    monkeypatch.delenv("KASI_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATAGOKR_SERVICE_KEY", raising=False)
    monkeypatch.setenv("DATA_GO_SERVICE_KEY", "ENV_KEY")

    client = KasiClient.from_env(session=fake_client_factory(FakeResponse(kasi_payload([])))[1])
    assert client.service_key == "ENV_KEY"

    with pytest.raises(ValueError, match="sol_month"):
        client.holidays(sol_year=2026, sol_month=13)
    with pytest.raises(ValueError, match="dn_yn"):
        client.location_rise_set(
            locdate="20260507",
            longitude=126.98,
            latitude=37.56,
            dn_yn="maybe",
        )


def test_service_key_copy_paste_whitespace_is_removed(monkeypatch) -> None:
    monkeypatch.setenv("KASI_SERVICE_KEY", "  ABCD\r\n EFGH\t ")

    client = KasiClient.from_env()

    assert client.service_key == "ABCDEFGH"


def test_service_key_loads_from_local_dotenv_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("KASI_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATAGOKR_SERVICE_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath(".env").write_text("KASI_SERVICE_KEY=' LOCAL\\n KEY '\n", encoding="utf-8")

    client = KasiClient.from_env()

    assert client.service_key == "LOCALKEY"
