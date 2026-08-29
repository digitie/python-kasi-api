"""한국천문연구원 OpenAPI용 Python 클라이언트."""

from __future__ import annotations

from ._convert import normalize_service_key
from .catalog import ApiCatalogEntry, ApiParameter, api_catalog, api_catalog_rows
from .client import AsyncKasiClient, KasiClient, KasiConfig
from .debug import DebugRun, build_error, jsonable, redact_sensitive, save_fixture
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

__version__ = "0.1.0"
PROVIDER_NAME = "python-kasi-api"

__all__ = [
    "ApiCatalogEntry",
    "ApiParameter",
    "AsyncKasiClient",
    "AstroEvent",
    "DebugRun",
    "KasiAuthError",
    "KasiCallContext",
    "KasiClient",
    "KasiConfig",
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
    "PROVIDER_NAME",
    "__version__",
    "api_catalog",
    "api_catalog_rows",
    "build_error",
    "jsonable",
    "normalize_service_key",
    "redact_sensitive",
    "save_fixture",
]
