"""한국천문연구원 OpenAPI용 Python 클라이언트."""

from __future__ import annotations

from ._convert import normalize_service_key
from .catalog import ApiCatalogEntry, ApiParameter, api_catalog, api_catalog_rows
from .client import KasiClient
from .debug import DebugRun, jsonable, redact_sensitive, save_fixture
from .exceptions import (
    KasiAuthError,
    KasiError,
    KasiNoDataError,
    KasiParseError,
    KasiRateLimitError,
    KasiRequestError,
    KasiServerError,
)
from .models import (
    AstroEvent,
    KasiCallContext,
    LunarSolarDate,
    MoonPhase,
    Page,
    RiseSet,
    SolarAltitude,
    SpecialDay,
    WeekInfo,
)

__all__ = [
    "ApiCatalogEntry",
    "ApiParameter",
    "AstroEvent",
    "DebugRun",
    "KasiAuthError",
    "KasiCallContext",
    "KasiClient",
    "KasiError",
    "KasiNoDataError",
    "KasiParseError",
    "KasiRateLimitError",
    "KasiRequestError",
    "KasiServerError",
    "LunarSolarDate",
    "MoonPhase",
    "Page",
    "RiseSet",
    "SolarAltitude",
    "SpecialDay",
    "WeekInfo",
    "api_catalog",
    "api_catalog_rows",
    "jsonable",
    "normalize_service_key",
    "redact_sensitive",
    "save_fixture",
]
