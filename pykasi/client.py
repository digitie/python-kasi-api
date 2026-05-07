"""High-level client for Korea Astronomy and Space Science Institute OpenAPIs."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, TypeVar

from ._convert import (
    dn_yn_value,
    leap_month_value,
    sanitize_request_params,
    to_day,
    to_int_or_none,
    to_month,
    to_year,
    to_yyyymmdd,
    without_none,
)
from ._http import DEFAULT_BASE_URL, KasiHttp, SessionLike, public_request_params
from .exceptions import KasiParseError
from .models import (
    AstroEvent,
    KasiCallContext,
    LunarSolarDate,
    MoonPhase,
    Page,
    RawRecord,
    RiseSet,
    SolarAltitude,
    SpecialDay,
    WeekInfo,
    astro_event_from_row,
    collected_now,
    lunar_solar_from_row,
    moon_phase_from_row,
    rise_set_from_row,
    solar_altitude_from_row,
    special_day_from_row,
    week_info_from_row,
)

DEFAULT_ENV_NAMES = (
    "KASI_SERVICE_KEY",
    "TRIPMATE_DATA_GO_SERVICE_KEY",
    "DATA_GO_SERVICE_KEY",
    "DATAGOKR_SERVICE_KEY",
)

SPCDE_SERVICE = "SpcdeInfoService"
LRSR_CLD_SERVICE = "LrsrCldInfoService"
RISE_SET_SERVICE = "RiseSetInfoService"
SR_ALTITUDE_SERVICE = "SrAltudeInfoService"
LUN_PHASE_SERVICE = "LunPhInfoService"
ASTRO_EVENT_SERVICE = "AstroEventInfoService"
WEEK_INFO_SERVICE = "SolcWeekInfoService_v2"

T = TypeVar("T")


class KasiClient:
    """Client entrypoint for KASI public APIs on data.go.kr."""

    def __init__(
        self,
        service_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        timeout: float = 10.0,
        retries: int = 3,
        session: SessionLike | None = None,
        response_format: str | None = "json",
    ) -> None:
        key = service_key or _first_env(DEFAULT_ENV_NAMES)
        if not key:
            names = ", ".join(DEFAULT_ENV_NAMES)
            from .exceptions import KasiAuthError

            raise KasiAuthError(f"service_key is required. Set one of: {names}")
        self.service_key = key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.response_format = response_format
        self._http = KasiHttp(
            key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            session=session,
            timeout=timeout,
            retries=retries,
        )
        self.special_days = SpecialDaysNamespace(self)
        self.calendar = CalendarNamespace(self)
        self.rise_set = RiseSetNamespace(self)
        self.solar_altitude = SolarAltitudeNamespace(self)

    @classmethod
    def from_env(
        cls,
        name: str = "KASI_SERVICE_KEY",
        *,
        fallback_names: tuple[str, ...] = (
            "TRIPMATE_DATA_GO_SERVICE_KEY",
            "DATA_GO_SERVICE_KEY",
            "DATAGOKR_SERVICE_KEY",
        ),
        **kwargs: Any,
    ) -> KasiClient:
        from .exceptions import KasiAuthError

        service_key = os.getenv(name) or _first_env(fallback_names)
        if not service_key:
            names = ", ".join((name, *fallback_names))
            raise KasiAuthError(f"none of these environment variables are set: {names}")
        return cls(service_key=service_key, **kwargs)

    def request(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = None,
    ) -> Mapping[str, Any]:
        """Call a KASI operation and return the normalized response body."""

        return self._http.get(
            service_name,
            operation,
            without_none(dict(params or {})),
            response_format=self._resolve_format(response_format),
        )

    def raw_endpoint(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[RawRecord]:
        """Call a service operation and return raw item mappings in a Page."""

        request_params = dict(params or {})
        request_params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return self._get_page(
            service_name,
            operation,
            request_params,
            lambda row: row,
            response_format=response_format,
        )

    def iter_pages(
        self,
        fetch_page: Callable[..., Page[T]],
        *args: Any,
        page_no: int = 1,
        num_of_rows: int = 10,
        max_pages: int | None = None,
        max_items: int | None = None,
        **kwargs: Any,
    ) -> Iterator[Page[T]]:
        """Iterate a page-returning client method using response pagination metadata."""

        next_page = page_no
        yielded_pages = 0
        yielded_items = 0
        while True:
            page = fetch_page(
                *args,
                page_no=next_page,
                num_of_rows=num_of_rows,
                **kwargs,
            )
            if not page.items:
                break
            yield page
            yielded_pages += 1
            yielded_items += len(page.items)
            if max_pages is not None and yielded_pages >= max_pages:
                break
            if max_items is not None and yielded_items >= max_items:
                break
            if page.next_page_no is None:
                break
            next_page = page.next_page_no

    def holidays(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return self.special_days.holidays(*args, **kwargs)

    def national_holidays(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return self.special_days.national_holidays(*args, **kwargs)

    def anniversaries(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return self.special_days.anniversaries(*args, **kwargs)

    def solar_terms_24(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return self.special_days.solar_terms_24(*args, **kwargs)

    def sundry_days(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return self.special_days.sundry_days(*args, **kwargs)

    def solar_to_lunar(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return self.calendar.solar_to_lunar(*args, **kwargs)

    def lunar_to_solar(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return self.calendar.lunar_to_solar(*args, **kwargs)

    def specific_lunar(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return self.calendar.specific_lunar(*args, **kwargs)

    def julian_day(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return self.calendar.julian_day(*args, **kwargs)

    def area_rise_set(self, *args: Any, **kwargs: Any) -> Page[RiseSet]:
        return self.rise_set.area(*args, **kwargs)

    def location_rise_set(self, *args: Any, **kwargs: Any) -> Page[RiseSet]:
        return self.rise_set.location(*args, **kwargs)

    def area_solar_altitude(self, *args: Any, **kwargs: Any) -> Page[SolarAltitude]:
        return self.solar_altitude.area(*args, **kwargs)

    def location_solar_altitude(self, *args: Any, **kwargs: Any) -> Page[SolarAltitude]:
        return self.solar_altitude.location(*args, **kwargs)

    def moon_phase(
        self,
        *,
        sol_year: str | int,
        sol_month: str | int,
        sol_day: str | int | None = None,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[MoonPhase]:
        params = _solar_params(
            sol_year=sol_year,
            sol_month=sol_month,
            sol_day=sol_day,
            page_no=page_no,
            num_of_rows=num_of_rows,
        )
        return self._get_page(
            LUN_PHASE_SERVICE,
            "getLunPhInfo",
            params,
            moon_phase_from_row,
            response_format=response_format,
        )

    def astro_events(
        self,
        *,
        sol_year: str | int,
        sol_month: str | int,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[AstroEvent]:
        params: dict[str, Any] = {
            "solYear": to_year(sol_year, field="sol_year"),
            "solMonth": to_month(sol_month, field="sol_month"),
        }
        params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return self._get_page(
            ASTRO_EVENT_SERVICE,
            "getAstroEventInfo",
            params,
            astro_event_from_row,
            response_format=response_format,
        )

    def sundays(
        self,
        *,
        sol_year: str | int,
        sol_month: str | int | None = None,
        response_format: str | None = None,
    ) -> Page[WeekInfo]:
        params: dict[str, Any] = {
            "solYear": to_year(sol_year, field="sol_year"),
            "solMonth": to_month(sol_month, field="sol_month"),
        }
        return self._get_page(
            WEEK_INFO_SERVICE,
            "getWeekInfo_v2",
            params,
            week_info_from_row,
            response_format=response_format,
        )

    def _get_page(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any],
        parser: Callable[[RawRecord], T],
        *,
        response_format: str | None = None,
    ) -> Page[T]:
        fmt = self._resolve_format(response_format)
        body = self._http.get(service_name, operation, params, response_format=fmt)
        rows = _extract_items(body, operation, service_name=service_name)
        try:
            parsed = tuple(parser(row) for row in rows)
        except (TypeError, ValueError) as exc:
            raise KasiParseError(
                f"{operation}: failed to parse item: {exc}",
                service_name=service_name,
                endpoint=operation,
                failure_kind="parse",
                response=rows,
            ) from exc
        public_params = public_request_params(params=params, response_format=fmt)
        return Page(
            items=parsed,
            page_no=to_int_or_none(body.get("pageNo")) or to_int_or_none(params.get("pageNo")),
            num_of_rows=(
                to_int_or_none(body.get("numOfRows")) or to_int_or_none(params.get("numOfRows"))
            ),
            total_count=to_int_or_none(body.get("totalCount")) or len(parsed),
            raw=body,
            context=KasiCallContext(
                service_name=service_name,
                endpoint=operation,
                request_params=sanitize_request_params(public_params),
                collected_at=collected_now(),
            ),
        )

    def _resolve_format(self, response_format: str | None) -> str | None:
        return self.response_format if response_format is None else response_format


@dataclass(frozen=True, slots=True)
class SpecialDaysNamespace:
    _client: KasiClient

    def anniversaries(self, **kwargs: Any) -> Page[SpecialDay]:
        return self._special_day("getAnniversaryInfo", **kwargs)

    def holidays(self, **kwargs: Any) -> Page[SpecialDay]:
        return self._special_day("getRestDeInfo", **kwargs)

    def national_holidays(self, **kwargs: Any) -> Page[SpecialDay]:
        return self._special_day("getHoliDeInfo", **kwargs)

    def solar_terms_24(self, **kwargs: Any) -> Page[SpecialDay]:
        return self._special_day("get24DivisionsInfo", **kwargs)

    def sundry_days(self, **kwargs: Any) -> Page[SpecialDay]:
        return self._special_day("getSundryDayInfo", **kwargs)

    def _special_day(
        self,
        operation: str,
        *,
        sol_year: str | int,
        sol_month: str | int | None = None,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[SpecialDay]:
        params: dict[str, Any] = {
            "solYear": to_year(sol_year, field="sol_year"),
            "solMonth": to_month(sol_month, field="sol_month"),
        }
        params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return self._client._get_page(
            SPCDE_SERVICE,
            operation,
            params,
            special_day_from_row,
            response_format=response_format,
        )


@dataclass(frozen=True, slots=True)
class CalendarNamespace:
    _client: KasiClient

    def solar_to_lunar(
        self,
        *,
        sol_year: str | int,
        sol_month: str | int,
        sol_day: str | int | None = None,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[LunarSolarDate]:
        return self._client._get_page(
            LRSR_CLD_SERVICE,
            "getLunCalInfo",
            _solar_params(
                sol_year=sol_year,
                sol_month=sol_month,
                sol_day=sol_day,
                page_no=page_no,
                num_of_rows=num_of_rows,
            ),
            lunar_solar_from_row,
            response_format=response_format,
        )

    def lunar_to_solar(
        self,
        *,
        lun_year: str | int,
        lun_month: str | int,
        lun_day: str | int | None = None,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[LunarSolarDate]:
        params: dict[str, Any] = {
            "lunYear": to_year(lun_year, field="lun_year"),
            "lunMonth": to_month(lun_month, field="lun_month"),
            "lunDay": to_day(lun_day, field="lun_day"),
        }
        params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return self._client._get_page(
            LRSR_CLD_SERVICE,
            "getSolCalInfo",
            params,
            lunar_solar_from_row,
            response_format=response_format,
        )

    def specific_lunar(
        self,
        *,
        from_sol_year: str | int,
        to_sol_year: str | int,
        lun_month: str | int,
        lun_day: str | int,
        leap_month: bool | str,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[LunarSolarDate]:
        params: dict[str, Any] = {
            "fromSolYear": to_year(from_sol_year, field="from_sol_year"),
            "toSolYear": to_year(to_sol_year, field="to_sol_year"),
            "lunMonth": to_month(lun_month, field="lun_month"),
            "lunDay": to_day(lun_day, field="lun_day"),
            "leapMonth": leap_month_value(leap_month),
        }
        params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return self._client._get_page(
            LRSR_CLD_SERVICE,
            "getSpcifyLunCalInfo",
            params,
            lunar_solar_from_row,
            response_format=response_format,
        )

    def julian_day(
        self,
        sol_jd: str | int,
        *,
        response_format: str | None = None,
    ) -> Page[LunarSolarDate]:
        return self._client._get_page(
            LRSR_CLD_SERVICE,
            "getJulDayInfo",
            {"solJd": str(sol_jd).strip()},
            lunar_solar_from_row,
            response_format=response_format,
        )


@dataclass(frozen=True, slots=True)
class RiseSetNamespace:
    _client: KasiClient

    def area(
        self,
        *,
        locdate: str | int | date | datetime,
        location: str,
        response_format: str | None = None,
    ) -> Page[RiseSet]:
        return self._client._get_page(
            RISE_SET_SERVICE,
            "getAreaRiseSetInfo",
            {"locdate": to_yyyymmdd(locdate, field="locdate"), "location": location},
            rise_set_from_row,
            response_format=response_format,
        )

    def location(
        self,
        *,
        locdate: str | int | date | datetime,
        longitude: str | int | float,
        latitude: str | int | float,
        dn_yn: bool | str | None = None,
        response_format: str | None = None,
    ) -> Page[RiseSet]:
        return self._client._get_page(
            RISE_SET_SERVICE,
            "getLCRiseSetInfo",
            {
                "locdate": to_yyyymmdd(locdate, field="locdate"),
                "longitude": longitude,
                "latitude": latitude,
                "dnYn": dn_yn_value(dn_yn, longitude=longitude, latitude=latitude),
            },
            rise_set_from_row,
            response_format=response_format,
        )


@dataclass(frozen=True, slots=True)
class SolarAltitudeNamespace:
    _client: KasiClient

    def area(
        self,
        *,
        locdate: str | int | date | datetime,
        location: str,
        response_format: str | None = None,
    ) -> Page[SolarAltitude]:
        return self._client._get_page(
            SR_ALTITUDE_SERVICE,
            "getAreaSrAltudeInfo",
            {"locdate": to_yyyymmdd(locdate, field="locdate"), "location": location},
            solar_altitude_from_row,
            response_format=response_format,
        )

    def location(
        self,
        *,
        locdate: str | int | date | datetime,
        longitude: str | int | float,
        latitude: str | int | float,
        dn_yn: bool | str | None = None,
        response_format: str | None = None,
    ) -> Page[SolarAltitude]:
        return self._client._get_page(
            SR_ALTITUDE_SERVICE,
            "getLCSrAltudeInfo",
            {
                "locdate": to_yyyymmdd(locdate, field="locdate"),
                "longitude": longitude,
                "latitude": latitude,
                "dnYn": dn_yn_value(dn_yn, longitude=longitude, latitude=latitude),
            },
            solar_altitude_from_row,
            response_format=response_format,
        )


def _first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _page_params(*, page_no: int | None, num_of_rows: int | None) -> dict[str, int]:
    if page_no is not None and page_no < 1:
        raise ValueError("page_no must be >= 1")
    if num_of_rows is not None and num_of_rows < 1:
        raise ValueError("num_of_rows must be >= 1")
    params: dict[str, int] = {}
    if page_no is not None:
        params["pageNo"] = page_no
    if num_of_rows is not None:
        params["numOfRows"] = num_of_rows
    return params


def _solar_params(
    *,
    sol_year: str | int,
    sol_month: str | int,
    sol_day: str | int | None,
    page_no: int | None,
    num_of_rows: int | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "solYear": to_year(sol_year, field="sol_year"),
        "solMonth": to_month(sol_month, field="sol_month"),
        "solDay": to_day(sol_day, field="sol_day"),
    }
    params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
    return params


def _extract_items(
    body: Mapping[str, Any],
    endpoint: str,
    *,
    service_name: str | None = None,
) -> tuple[RawRecord, ...]:
    items = body.get("items")
    if items in (None, "", []):
        return ()
    item_data: Any
    if isinstance(items, Mapping):
        item_data = items.get("item")
    else:
        item_data = items
    if item_data in (None, "", []):
        return ()
    if isinstance(item_data, Mapping):
        return (item_data,)
    if isinstance(item_data, list) and all(isinstance(item, Mapping) for item in item_data):
        return tuple(item_data)
    raise KasiParseError(
        f"{endpoint}: response.body.items.item was not an object or list",
        endpoint=endpoint,
        service_name=service_name,
        failure_kind="parse",
        response=body,
    )
