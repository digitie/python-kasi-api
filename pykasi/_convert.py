"""Small conversion helpers for KASI API parameters and responses."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any


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
    except ValueError:
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


def to_yyyymmdd(value: str | int | date | datetime, *, field: str = "date") -> str:
    if isinstance(value, datetime):
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


def dn_yn_value(
    dn_yn: bool | str | None,
    *,
    longitude: str | int | float,
    latitude: str | int | float,
) -> str:
    if dn_yn is None:
        text = f"{longitude}{latitude}"
        return "Y" if "." in text else "N"
    if isinstance(dn_yn, bool):
        return "Y" if dn_yn else "N"
    upper = str(dn_yn).strip().upper()
    if upper in {"Y", "N"}:
        return upper
    raise ValueError("dn_yn must be 'Y', 'N', True, or False")


def sanitize_request_params(params: Mapping[str, Any]) -> dict[str, Any]:
    """Return params safe to expose in model context."""

    return {
        key: value
        for key, value in without_none(params).items()
        if str(key).replace("_", "").lower() != "servicekey"
    }
