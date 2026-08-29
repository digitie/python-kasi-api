"""한국천문연구원 OpenAPI용 고수준 클라이언트."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, TypeVar

from ._convert import (
    dn_yn_value,
    leap_month_value,
    normalize_service_key,
    to_day,
    to_int_or_none,
    to_month,
    to_year,
    to_yyyymmdd,
    without_none,
)
from ._http import DEFAULT_BASE_URL, AsyncKasiHttp, KasiHttp, SessionLike, public_request_params
from .debug import DebugRun, build_debug_run
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
    "DATA_GO_KR_SERVICE_KEY",
)
DEFAULT_DOTENV_NAMES = (".env", ".env.local")

SPCDE_SERVICE = "SpcdeInfoService"
LRSR_CLD_SERVICE = "LrsrCldInfoService"
RISE_SET_SERVICE = "RiseSetInfoService"
SR_ALTITUDE_SERVICE = "SrAltudeInfoService"
LUN_PHASE_SERVICE = "LunPhInfoService"
ASTRO_EVENT_SERVICE = "AstroEventInfoService"
WEEK_INFO_SERVICE = "SolcWeekInfoService_v2"

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class KasiConfig:
    """KASI 클라이언트 실행 설정."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    service_key_param: str = "serviceKey"
    timeout: float = 10.0
    retries: int = 3
    max_rps: float = 5.0
    response_format: str | None = "json"


class KasiClient:
    """data.go.kr KASI 공공 API의 클라이언트 진입점."""

    def __init__(
        self,
        service_key: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        timeout: float = 10.0,
        retries: int = 3,
        max_rps: float = 5.0,
        session: SessionLike | None = None,
        response_format: str | None = "json",
        dotenv_path: str | os.PathLike[str] | None = None,
    ) -> None:
        key = _explicit_service_key(api_key=api_key, service_key=service_key) or _first_env(
            DEFAULT_ENV_NAMES,
            dotenv_path=dotenv_path,
        )
        if not key:
            names = ", ".join(DEFAULT_ENV_NAMES)
            from .exceptions import KasiAuthError

            raise KasiAuthError(f"service_key is required. Set one of: {names}")
        self.service_key = key
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.response_format = response_format
        self.config = KasiConfig(
            api_key=key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            timeout=timeout,
            retries=retries,
            max_rps=max_rps,
            response_format=response_format,
        )
        self._http = KasiHttp(
            key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            session=session,
            timeout=timeout,
            retries=retries,
            max_rps=max_rps,
        )
        self.special_days = SpecialDaysNamespace(self)
        self.calendar = CalendarNamespace(self)
        self.rise_set = RiseSetNamespace(self)
        self.solar_altitude = SolarAltitudeNamespace(self)
        self.closed = False

    def __enter__(self) -> KasiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()
        self.closed = True

    @classmethod
    def from_env(
        cls,
        name: str = "DATA_GO_KR_SERVICE_KEY",
        *,
        api_key: str | None = None,
        service_key: str | None = None,
        fallback_names: tuple[str, ...] = (),
        dotenv_path: str | os.PathLike[str] | None = None,
        **kwargs: Any,
    ) -> KasiClient:
        from .exceptions import KasiAuthError

        resolved_key = _explicit_service_key(
            api_key=api_key,
            service_key=service_key,
        ) or _first_env(
            (name, *fallback_names),
            dotenv_path=dotenv_path,
        )
        if not resolved_key:
            names = ", ".join((name, *fallback_names))
            env_files = ", ".join(DEFAULT_DOTENV_NAMES)
            raise KasiAuthError(
                f"none of these environment variables are set: {names}; "
                f"also checked local {env_files}"
            )
        return cls(api_key=resolved_key, **kwargs)

    @classmethod
    def aio(
        cls,
        service_key: str | None = None,
        *,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> AsyncKasiClient:
        """비동기 클라이언트를 생성합니다."""

        return AsyncKasiClient(service_key=service_key, api_key=api_key, **kwargs)

    def request(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = None,
    ) -> Mapping[str, Any]:
        """KASI operation을 호출하고 정규화된 응답 body를 반환합니다."""

        return self._http.get(
            service_name,
            operation,
            without_none(dict(params or {})),
            response_format=self._resolve_format(response_format),
        )

    def debug(self, function_name: str, /, *args: Any, **kwargs: Any) -> DebugRun:
        """public helper를 실행하고 fixture 저장용 DebugRun을 반환합니다."""

        return build_debug_run(self, function_name=function_name, args=args, kwargs=kwargs)

    def debug_holidays(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("holidays", *args, **kwargs)

    def debug_national_holidays(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("national_holidays", *args, **kwargs)

    def debug_anniversaries(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("anniversaries", *args, **kwargs)

    def debug_solar_terms_24(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("solar_terms_24", *args, **kwargs)

    def debug_sundry_days(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("sundry_days", *args, **kwargs)

    def debug_solar_to_lunar(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("solar_to_lunar", *args, **kwargs)

    def debug_lunar_to_solar(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("lunar_to_solar", *args, **kwargs)

    def debug_specific_lunar(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("specific_lunar", *args, **kwargs)

    def debug_julian_day(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("julian_day", *args, **kwargs)

    def debug_area_rise_set(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("area_rise_set", *args, **kwargs)

    def debug_location_rise_set(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("location_rise_set", *args, **kwargs)

    def debug_area_solar_altitude(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("area_solar_altitude", *args, **kwargs)

    def debug_location_solar_altitude(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("location_solar_altitude", *args, **kwargs)

    def debug_moon_phase(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("moon_phase", *args, **kwargs)

    def debug_astro_events(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("astro_events", *args, **kwargs)

    def debug_sundays(self, *args: Any, **kwargs: Any) -> DebugRun:
        return self.debug("sundays", *args, **kwargs)

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
        """서비스 operation을 호출하고 원본 item mapping을 Page로 반환합니다."""

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
        """응답 pagination metadata를 사용해 Page 반환 메서드를 순회합니다."""

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
            next_page += 1

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
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[WeekInfo]:
        params: dict[str, Any] = {
            "solYear": to_year(sol_year, field="sol_year"),
            "solMonth": to_month(sol_month, field="sol_month"),
        }
        params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
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
        http_result = self._http.get_result(service_name, operation, params, response_format=fmt)
        body = http_result.body
        rows = _extract_items(body, operation, service_name=service_name)
        parsed_rows: list[T] = []
        parse_error: Exception | None = None
        for row in rows:
            try:
                parsed_rows.append(parser(row))
            except (TypeError, ValueError) as exc:
                parse_error = exc
        if rows and not parsed_rows:
            raise KasiParseError(
                f"{operation}: failed to parse item: {parse_error}",
                service_name=service_name,
                endpoint=operation,
                failure_kind="parse",
                response=rows,
            ) from parse_error
        parsed = tuple(parsed_rows)
        public_params = public_request_params(params=params, response_format=fmt)
        return Page(
            items=parsed,
            page_no=to_int_or_none(params.get("pageNo")) or to_int_or_none(body.get("pageNo")),
            num_of_rows=(
                to_int_or_none(params.get("numOfRows")) or to_int_or_none(body.get("numOfRows"))
            ),
            total_count=to_int_or_none(body.get("totalCount")),
            raw=body,
            context=KasiCallContext(
                service_name=service_name,
                endpoint=operation,
                request_method=_text_or_none(http_result.request.get("method")),
                request_url=_text_or_none(http_result.request.get("url")),
                request_params=public_params,
                response_status_code=to_int_or_none(http_result.response.get("status_code")),
                response_headers=_mapping_or_empty(http_result.response.get("headers")),
                collected_at=collected_now(),
            ),
        )

    def _resolve_format(self, response_format: str | None) -> str | None:
        return self.response_format if response_format is None else response_format


class AsyncKasiClient:
    """asyncio 환경에서 사용하는 data.go.kr KASI 공공 API 클라이언트."""

    def __init__(
        self,
        service_key: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        timeout: float = 10.0,
        retries: int = 3,
        max_rps: float = 5.0,
        session: SessionLike | None = None,
        response_format: str | None = "json",
        dotenv_path: str | os.PathLike[str] | None = None,
    ) -> None:
        key = _explicit_service_key(api_key=api_key, service_key=service_key) or _first_env(
            DEFAULT_ENV_NAMES,
            dotenv_path=dotenv_path,
        )
        if not key:
            names = ", ".join(DEFAULT_ENV_NAMES)
            from .exceptions import KasiAuthError

            raise KasiAuthError(f"service_key is required. Set one of: {names}")
        self.service_key = key
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.response_format = response_format
        self.config = KasiConfig(
            api_key=key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            timeout=timeout,
            retries=retries,
            max_rps=max_rps,
            response_format=response_format,
        )
        self._http = AsyncKasiHttp(
            key,
            base_url=self.base_url,
            service_key_param=service_key_param,
            session=session,
            timeout=timeout,
            retries=retries,
            max_rps=max_rps,
        )
        self.special_days = AsyncSpecialDaysNamespace(self)
        self.calendar = AsyncCalendarNamespace(self)
        self.rise_set = AsyncRiseSetNamespace(self)
        self.solar_altitude = AsyncSolarAltitudeNamespace(self)
        self.closed = False

    async def __aenter__(self) -> AsyncKasiClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """내부 httpx.AsyncClient를 닫습니다."""

        await self._http.aclose()
        self.closed = True

    @classmethod
    def from_env(
        cls,
        name: str = "DATA_GO_KR_SERVICE_KEY",
        *,
        api_key: str | None = None,
        service_key: str | None = None,
        fallback_names: tuple[str, ...] = (),
        dotenv_path: str | os.PathLike[str] | None = None,
        **kwargs: Any,
    ) -> AsyncKasiClient:
        from .exceptions import KasiAuthError

        resolved_key = _explicit_service_key(
            api_key=api_key,
            service_key=service_key,
        ) or _first_env(
            (name, *fallback_names),
            dotenv_path=dotenv_path,
        )
        if not resolved_key:
            names = ", ".join((name, *fallback_names))
            env_files = ", ".join(DEFAULT_DOTENV_NAMES)
            raise KasiAuthError(
                f"none of these environment variables are set: {names}; "
                f"also checked local {env_files}"
            )
        return cls(api_key=resolved_key, **kwargs)

    async def request(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = None,
    ) -> Mapping[str, Any]:
        """KASI operation을 비동기로 호출하고 정규화된 응답 body를 반환합니다."""

        return await self._http.get(
            service_name,
            operation,
            without_none(dict(params or {})),
            response_format=self._resolve_format(response_format),
        )

    async def raw_endpoint(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[RawRecord]:
        """서비스 operation을 비동기로 호출하고 원본 item mapping을 Page로 반환합니다."""

        request_params = dict(params or {})
        request_params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return await self._get_page(
            service_name,
            operation,
            request_params,
            lambda row: row,
            response_format=response_format,
        )

    async def holidays(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return await self.special_days.holidays(*args, **kwargs)

    async def national_holidays(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return await self.special_days.national_holidays(*args, **kwargs)

    async def anniversaries(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return await self.special_days.anniversaries(*args, **kwargs)

    async def solar_terms_24(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return await self.special_days.solar_terms_24(*args, **kwargs)

    async def sundry_days(self, *args: Any, **kwargs: Any) -> Page[SpecialDay]:
        return await self.special_days.sundry_days(*args, **kwargs)

    async def solar_to_lunar(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return await self.calendar.solar_to_lunar(*args, **kwargs)

    async def lunar_to_solar(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return await self.calendar.lunar_to_solar(*args, **kwargs)

    async def specific_lunar(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return await self.calendar.specific_lunar(*args, **kwargs)

    async def julian_day(self, *args: Any, **kwargs: Any) -> Page[LunarSolarDate]:
        return await self.calendar.julian_day(*args, **kwargs)

    async def area_rise_set(self, *args: Any, **kwargs: Any) -> Page[RiseSet]:
        return await self.rise_set.area(*args, **kwargs)

    async def location_rise_set(self, *args: Any, **kwargs: Any) -> Page[RiseSet]:
        return await self.rise_set.location(*args, **kwargs)

    async def area_solar_altitude(self, *args: Any, **kwargs: Any) -> Page[SolarAltitude]:
        return await self.solar_altitude.area(*args, **kwargs)

    async def location_solar_altitude(self, *args: Any, **kwargs: Any) -> Page[SolarAltitude]:
        return await self.solar_altitude.location(*args, **kwargs)

    async def moon_phase(
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
        return await self._get_page(
            LUN_PHASE_SERVICE,
            "getLunPhInfo",
            params,
            moon_phase_from_row,
            response_format=response_format,
        )

    async def astro_events(
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
        return await self._get_page(
            ASTRO_EVENT_SERVICE,
            "getAstroEventInfo",
            params,
            astro_event_from_row,
            response_format=response_format,
        )

    async def sundays(
        self,
        *,
        sol_year: str | int,
        sol_month: str | int | None = None,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[WeekInfo]:
        params: dict[str, Any] = {
            "solYear": to_year(sol_year, field="sol_year"),
            "solMonth": to_month(sol_month, field="sol_month"),
        }
        params.update(_page_params(page_no=page_no, num_of_rows=num_of_rows))
        return await self._get_page(
            WEEK_INFO_SERVICE,
            "getWeekInfo_v2",
            params,
            week_info_from_row,
            response_format=response_format,
        )

    async def _get_page(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any],
        parser: Callable[[RawRecord], T],
        *,
        response_format: str | None = None,
    ) -> Page[T]:
        fmt = self._resolve_format(response_format)
        http_result = await self._http.get_result(
            service_name,
            operation,
            params,
            response_format=fmt,
        )
        body = http_result.body
        rows = _extract_items(body, operation, service_name=service_name)
        parsed_rows: list[T] = []
        parse_error: Exception | None = None
        for row in rows:
            try:
                parsed_rows.append(parser(row))
            except (TypeError, ValueError) as exc:
                parse_error = exc
        if rows and not parsed_rows:
            raise KasiParseError(
                f"{operation}: failed to parse item: {parse_error}",
                service_name=service_name,
                endpoint=operation,
                failure_kind="parse",
                response=rows,
            ) from parse_error
        parsed = tuple(parsed_rows)
        public_params = public_request_params(params=params, response_format=fmt)
        return Page(
            items=parsed,
            page_no=to_int_or_none(params.get("pageNo")) or to_int_or_none(body.get("pageNo")),
            num_of_rows=(
                to_int_or_none(params.get("numOfRows")) or to_int_or_none(body.get("numOfRows"))
            ),
            total_count=to_int_or_none(body.get("totalCount")),
            raw=body,
            context=KasiCallContext(
                service_name=service_name,
                endpoint=operation,
                request_method=_text_or_none(http_result.request.get("method")),
                request_url=_text_or_none(http_result.request.get("url")),
                request_params=public_params,
                response_status_code=to_int_or_none(http_result.response.get("status_code")),
                response_headers=_mapping_or_empty(http_result.response.get("headers")),
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


@dataclass(frozen=True, slots=True)
class AsyncSpecialDaysNamespace:
    _client: AsyncKasiClient

    async def anniversaries(self, **kwargs: Any) -> Page[SpecialDay]:
        return await self._special_day("getAnniversaryInfo", **kwargs)

    async def holidays(self, **kwargs: Any) -> Page[SpecialDay]:
        return await self._special_day("getRestDeInfo", **kwargs)

    async def national_holidays(self, **kwargs: Any) -> Page[SpecialDay]:
        return await self._special_day("getHoliDeInfo", **kwargs)

    async def solar_terms_24(self, **kwargs: Any) -> Page[SpecialDay]:
        return await self._special_day("get24DivisionsInfo", **kwargs)

    async def sundry_days(self, **kwargs: Any) -> Page[SpecialDay]:
        return await self._special_day("getSundryDayInfo", **kwargs)

    async def _special_day(
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
        return await self._client._get_page(
            SPCDE_SERVICE,
            operation,
            params,
            special_day_from_row,
            response_format=response_format,
        )


@dataclass(frozen=True, slots=True)
class AsyncCalendarNamespace:
    _client: AsyncKasiClient

    async def solar_to_lunar(
        self,
        *,
        sol_year: str | int,
        sol_month: str | int,
        sol_day: str | int | None = None,
        page_no: int | None = 1,
        num_of_rows: int | None = 10,
        response_format: str | None = None,
    ) -> Page[LunarSolarDate]:
        return await self._client._get_page(
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

    async def lunar_to_solar(
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
        return await self._client._get_page(
            LRSR_CLD_SERVICE,
            "getSolCalInfo",
            params,
            lunar_solar_from_row,
            response_format=response_format,
        )

    async def specific_lunar(
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
        return await self._client._get_page(
            LRSR_CLD_SERVICE,
            "getSpcifyLunCalInfo",
            params,
            lunar_solar_from_row,
            response_format=response_format,
        )

    async def julian_day(
        self,
        sol_jd: str | int,
        *,
        response_format: str | None = None,
    ) -> Page[LunarSolarDate]:
        return await self._client._get_page(
            LRSR_CLD_SERVICE,
            "getJulDayInfo",
            {"solJd": str(sol_jd).strip()},
            lunar_solar_from_row,
            response_format=response_format,
        )


@dataclass(frozen=True, slots=True)
class AsyncRiseSetNamespace:
    _client: AsyncKasiClient

    async def area(
        self,
        *,
        locdate: str | int | date | datetime,
        location: str,
        response_format: str | None = None,
    ) -> Page[RiseSet]:
        return await self._client._get_page(
            RISE_SET_SERVICE,
            "getAreaRiseSetInfo",
            {"locdate": to_yyyymmdd(locdate, field="locdate"), "location": location},
            rise_set_from_row,
            response_format=response_format,
        )

    async def location(
        self,
        *,
        locdate: str | int | date | datetime,
        longitude: str | int | float,
        latitude: str | int | float,
        dn_yn: bool | str | None = None,
        response_format: str | None = None,
    ) -> Page[RiseSet]:
        return await self._client._get_page(
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
class AsyncSolarAltitudeNamespace:
    _client: AsyncKasiClient

    async def area(
        self,
        *,
        locdate: str | int | date | datetime,
        location: str,
        response_format: str | None = None,
    ) -> Page[SolarAltitude]:
        return await self._client._get_page(
            SR_ALTITUDE_SERVICE,
            "getAreaSrAltudeInfo",
            {"locdate": to_yyyymmdd(locdate, field="locdate"), "location": location},
            solar_altitude_from_row,
            response_format=response_format,
        )

    async def location(
        self,
        *,
        locdate: str | int | date | datetime,
        longitude: str | int | float,
        latitude: str | int | float,
        dn_yn: bool | str | None = None,
        response_format: str | None = None,
    ) -> Page[SolarAltitude]:
        return await self._client._get_page(
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


def _explicit_service_key(
    *,
    api_key: str | None,
    service_key: str | None,
) -> str | None:
    return normalize_service_key(api_key if api_key is not None else service_key)


def _first_env(
    names: tuple[str, ...],
    *,
    dotenv_path: str | os.PathLike[str] | None = None,
) -> str | None:
    for name in names:
        value = normalize_service_key(os.getenv(name))
        if value:
            return value
    dotenv_values = _read_dotenv(dotenv_path)
    for name in names:
        value = normalize_service_key(dotenv_values.get(name))
        if value:
            return value
    return None


def _read_dotenv(dotenv_path: str | os.PathLike[str] | None) -> dict[str, str]:
    paths = (
        (Path(dotenv_path),)
        if dotenv_path is not None
        else tuple(Path.cwd() / name for name in DEFAULT_DOTENV_NAMES)
    )
    values: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_dotenv_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            values[key] = value
    return values


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#") or "=" not in text:
        return None
    key, value = text.split("=", 1)
    key = key.strip()
    if key.startswith("export "):
        key = key[7:].strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


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
    if isinstance(item_data, list):
        valid_items = tuple(item for item in item_data if isinstance(item, Mapping))
        if valid_items:
            return valid_items
    raise KasiParseError(
        f"{endpoint}: response.body.items.item was not an object or list",
        endpoint=endpoint,
        service_name=service_name,
        failure_kind="parse",
        response=body,
    )


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
