"""저장된 KASI raw body를 Page 모델로 replay 파싱합니다."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ._convert import sanitize_request_params, to_int_or_none
from .client import (
    ASTRO_EVENT_SERVICE,
    LRSR_CLD_SERVICE,
    LUN_PHASE_SERVICE,
    RISE_SET_SERVICE,
    SPCDE_SERVICE,
    SR_ALTITUDE_SERVICE,
    WEEK_INFO_SERVICE,
    _extract_items,
)
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
    lunar_solar_from_row,
    moon_phase_from_row,
    rise_set_from_row,
    solar_altitude_from_row,
    special_day_from_row,
    week_info_from_row,
)

ParsedRecord = (
    AstroEvent | LunarSolarDate | MoonPhase | RiseSet | SolarAltitude | SpecialDay | WeekInfo
)
RowParser = Callable[[RawRecord], ParsedRecord]


@dataclass(frozen=True, slots=True)
class ResponseParser:
    """fixture replay에 필요한 함수별 파싱 metadata."""

    function_name: str
    service_name: str
    endpoint: str
    row_parser: RowParser


PARSERS: dict[str, ResponseParser] = {
    "holidays": ResponseParser("holidays", SPCDE_SERVICE, "getRestDeInfo", special_day_from_row),
    "national_holidays": ResponseParser(
        "national_holidays",
        SPCDE_SERVICE,
        "getHoliDeInfo",
        special_day_from_row,
    ),
    "anniversaries": ResponseParser(
        "anniversaries",
        SPCDE_SERVICE,
        "getAnniversaryInfo",
        special_day_from_row,
    ),
    "solar_terms_24": ResponseParser(
        "solar_terms_24",
        SPCDE_SERVICE,
        "get24DivisionsInfo",
        special_day_from_row,
    ),
    "sundry_days": ResponseParser(
        "sundry_days",
        SPCDE_SERVICE,
        "getSundryDayInfo",
        special_day_from_row,
    ),
    "solar_to_lunar": ResponseParser(
        "solar_to_lunar",
        LRSR_CLD_SERVICE,
        "getLunCalInfo",
        lunar_solar_from_row,
    ),
    "lunar_to_solar": ResponseParser(
        "lunar_to_solar",
        LRSR_CLD_SERVICE,
        "getSolCalInfo",
        lunar_solar_from_row,
    ),
    "specific_lunar": ResponseParser(
        "specific_lunar",
        LRSR_CLD_SERVICE,
        "getSpcifyLunCalInfo",
        lunar_solar_from_row,
    ),
    "julian_day": ResponseParser(
        "julian_day",
        LRSR_CLD_SERVICE,
        "getJulDayInfo",
        lunar_solar_from_row,
    ),
    "area_rise_set": ResponseParser(
        "area_rise_set",
        RISE_SET_SERVICE,
        "getAreaRiseSetInfo",
        rise_set_from_row,
    ),
    "location_rise_set": ResponseParser(
        "location_rise_set",
        RISE_SET_SERVICE,
        "getLCRiseSetInfo",
        rise_set_from_row,
    ),
    "area_solar_altitude": ResponseParser(
        "area_solar_altitude",
        SR_ALTITUDE_SERVICE,
        "getAreaSrAltudeInfo",
        solar_altitude_from_row,
    ),
    "location_solar_altitude": ResponseParser(
        "location_solar_altitude",
        SR_ALTITUDE_SERVICE,
        "getLCSrAltudeInfo",
        solar_altitude_from_row,
    ),
    "moon_phase": ResponseParser(
        "moon_phase",
        LUN_PHASE_SERVICE,
        "getLunPhInfo",
        moon_phase_from_row,
    ),
    "astro_events": ResponseParser(
        "astro_events",
        ASTRO_EVENT_SERVICE,
        "getAstroEventInfo",
        astro_event_from_row,
    ),
    "sundays": ResponseParser(
        "sundays",
        WEEK_INFO_SERVICE,
        "getWeekInfo_v2",
        week_info_from_row,
    ),
}


def available_function_names() -> tuple[str, ...]:
    """fixture replay가 지원하는 public helper 이름을 반환합니다."""

    return tuple(PARSERS)


def parse_function_response(
    function_name: str,
    body: Mapping[str, Any],
    *,
    request_params: Mapping[str, Any] | None = None,
    response_status_code: int | None = None,
    response_headers: Mapping[str, Any] | None = None,
) -> Page[ParsedRecord]:
    """fixture에 저장된 response.body를 함수별 Page 모델로 파싱합니다."""

    try:
        spec = PARSERS[function_name]
    except KeyError as exc:
        raise KasiParseError(
            f"unknown fixture function: {function_name}",
            failure_kind="parse",
        ) from exc

    rows = _extract_items(body, spec.endpoint, service_name=spec.service_name)
    try:
        parsed = tuple(spec.row_parser(row) for row in rows)
    except (TypeError, ValueError) as exc:
        raise KasiParseError(
            f"{spec.endpoint}: failed to parse fixture item: {exc}",
            service_name=spec.service_name,
            endpoint=spec.endpoint,
            failure_kind="parse",
            response=rows,
        ) from exc

    return Page(
        items=parsed,
        page_no=to_int_or_none(body.get("pageNo")),
        num_of_rows=to_int_or_none(body.get("numOfRows")),
        total_count=to_int_or_none(body.get("totalCount")) or len(parsed),
        raw=body,
        context=KasiCallContext(
            service_name=spec.service_name,
            endpoint=spec.endpoint,
            request_method="GET",
            request_params=sanitize_request_params(dict(request_params or {})),
            response_status_code=response_status_code,
            response_headers=dict(response_headers or {}),
        ),
    )


__all__ = [
    "PARSERS",
    "ResponseParser",
    "available_function_names",
    "parse_function_response",
]
