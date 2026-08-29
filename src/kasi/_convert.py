"""KASI API 요청 파라미터와 응답 값을 변환하는 작은 helper."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def normalize_service_key(value: Any) -> str | None:
    """복사/붙여넣기로 섞인 공백 문자를 제거한 서비스 키를 반환합니다."""

    if value is None:
        return None
    text = str(value).replace("\\r", "").replace("\\n", "").replace("\\t", "")
    normalized = "".join(text.split())
    return normalized or None


def strip_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_int_or_none(value: Any) -> int | None:
    text = strip_or_none(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (ValueError, OverflowError):
        return None


def to_float_or_none(value: Any) -> float | None:
    text = strip_or_none(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_bool_yn(value: Any) -> bool | None:
    text = strip_or_none(value)
    if text is None:
        return None
    upper = text.upper()
    if upper == "Y":
        return True
    if upper == "N":
        return False
    return None


def without_none(params: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def _seoul_timezone() -> tzinfo:
    try:
        return ZoneInfo("Asia/Seoul")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=9))


def to_yyyymmdd(value: str | int | date | datetime, *, field: str = "date") -> str:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_seoul_timezone())
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text.replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"{field} must be YYYYMMDD")
    return text


def to_year(value: str | int, *, field: str = "year") -> str:
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        raise ValueError(f"{field} must be a 4-digit year")
    return text


def to_month(value: str | int | None, *, field: str = "month") -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        text = f"{value:02d}"
    else:
        text = str(value).strip()
        if len(text) == 1 and text.isdigit():
            text = f"0{text}"
    if len(text) != 2 or not text.isdigit() or not 1 <= int(text) <= 12:
        raise ValueError(f"{field} must be MM")
    return text


def to_day(value: str | int | None, *, field: str = "day") -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        text = f"{value:02d}"
    else:
        text = str(value).strip()
        if len(text) == 1 and text.isdigit():
            text = f"0{text}"
    if len(text) != 2 or not text.isdigit() or not 1 <= int(text) <= 31:
        raise ValueError(f"{field} must be DD")
    return text


def leap_month_value(value: bool | str) -> str:
    if isinstance(value, bool):
        return "윤" if value else "평"
    text = str(value).strip()
    if text in {"평", "윤"}:
        return text
    upper = text.upper()
    if upper in {"N", "NORMAL", "FALSE", "0"}:
        return "평"
    if upper in {"Y", "LEAP", "TRUE", "1"}:
        return "윤"
    raise ValueError("leap_month must be bool, '평', or '윤'")


def _decimal_degrees_flag(value: str | int | float) -> bool | None:
    if isinstance(value, float):
        return True
    if isinstance(value, int):
        return None
    return "." in str(value)


def dn_yn_value(
    dn_yn: bool | str | None,
    *,
    longitude: str | int | float,
    latitude: str | int | float,
) -> str:
    if dn_yn is None:
        lon_decimal = _decimal_degrees_flag(longitude)
        lat_decimal = _decimal_degrees_flag(latitude)
        if lon_decimal is None or lat_decimal is None or lon_decimal != lat_decimal:
            raise ValueError(
                "dn_yn must be specified explicitly for whole-number longitude/latitude "
                "(the decimal-degree vs degree-minute format cannot be inferred)"
            )
        return "Y" if lon_decimal else "N"
    if isinstance(dn_yn, bool):
        return "Y" if dn_yn else "N"
    upper = str(dn_yn).strip().upper()
    if upper in {"Y", "N"}:
        return upper
    raise ValueError("dn_yn must be 'Y', 'N', True, or False")


def sanitize_request_params(
    params: Mapping[str, Any],
    *,
    extra_sensitive_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """모델 context에 노출해도 안전한 요청 파라미터를 반환합니다."""

    sensitive_keys = {"servicekey"} | {
        str(key).replace("_", "").lower() for key in extra_sensitive_keys
    }
    return {
        key: value
        for key, value in without_none(params).items()
        if str(key).replace("_", "").lower() not in sensitive_keys
    }
