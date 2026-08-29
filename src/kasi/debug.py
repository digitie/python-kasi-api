"""디버그 UI와 fixture 저장기가 공유할 수 있는 작은 도구 모음."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel

from .catalog import get_api_catalog_entry
from .exceptions import KasiError
from .models import Page
from .processor import process_function_result

SENSITIVE_KEYS = {
    "authorization",
    "xapikey",
    "apikey",
    "api_key",
    "servicekey",
    "service_key",
    "accesstoken",
    "access_token",
    "refreshtoken",
    "refresh_token",
}
DEFAULT_ASSERTION = {
    "mode": "snapshot",
    "exclude_fields": ["fetched_at", "request_id", "updated_at", "collected_at"],
    "required_fields": [],
}


@dataclass(frozen=True, slots=True)
class DebugRun:
    """한 번의 API 디버그 실행 결과."""

    function: str
    input: dict[str, Any]
    request: dict[str, Any]
    response: dict[str, Any]
    parsed: Any
    processed: Any
    trace: list[str]
    error: dict[str, Any] | None = None
    catalog: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Streamlit이나 fixture writer에 넘길 수 있는 JSON 친화 dict를 반환합니다."""

        return {
            "function": self.function,
            "input": jsonable(self.input),
            "request": jsonable(self.request),
            "response": jsonable(self.response),
            "parsed": jsonable(self.parsed),
            "processed": jsonable(self.processed),
            "trace": jsonable(self.trace),
            "error": jsonable(self.error),
            "catalog": jsonable(self.catalog),
        }


def build_debug_run(
    client: Any,
    *,
    function_name: str,
    args: tuple[Any, ...] = (),
    kwargs: Mapping[str, Any] | None = None,
) -> DebugRun:
    """KasiClient public helper를 실행하고 DebugRun으로 감쌉니다."""

    from .parser import available_function_names

    call_kwargs = dict(kwargs or {})
    input_data = _input_data(args=args, kwargs=call_kwargs)
    trace = [f"함수 선택: {function_name}"]
    catalog = _catalog_data(function_name)
    if catalog:
        trace.append(f"데이터셋: {catalog['dataset_name']}")
        trace.append(f"서비스키 신청: {catalog['service_key_url']}")
    if function_name not in available_function_names():
        return _error_run(
            function_name=function_name,
            input_data=input_data,
            trace=trace,
            error=ValueError(f"unsupported debug function: {function_name}"),
            catalog=catalog,
        )

    target = getattr(client, function_name, None)
    if not callable(target):
        return _error_run(
            function_name=function_name,
            input_data=input_data,
            trace=trace,
            error=ValueError(f"unknown debug function: {function_name}"),
            catalog=catalog,
        )

    try:
        parsed = target(*args, **call_kwargs)
        processed = process_function_result(function_name, parsed)
    except Exception as exc:
        trace.append(f"실패: {exc.__class__.__name__}")
        return _error_run(
            function_name=function_name,
            input_data=input_data,
            trace=trace,
            error=exc,
            catalog=catalog,
        )

    trace.append("API 호출과 파싱 완료")
    if isinstance(parsed, Page):
        request = _request_from_page(parsed)
        response = _response_from_page(parsed)
        trace.append(f"item 수: {len(parsed.items)}")
    else:
        request = {}
        response = {}
    return DebugRun(
        function=function_name,
        input=redact_sensitive(input_data),
        request=request,
        response=response,
        parsed=parsed,
        processed=processed,
        trace=trace,
        catalog=catalog,
    )


def jsonable(obj: Any) -> Any:
    """Pydantic 모델과 dataclass를 JSON 저장 가능한 값으로 바꿉니다."""

    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if is_dataclass(obj) and not isinstance(obj, type):
        return {str(key): jsonable(value) for key, value in asdict(obj).items()}
    if isinstance(obj, Mapping):
        return {str(key): jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in obj]
    return obj


def redact_sensitive(obj: Any) -> Any:
    """fixture와 debug output에서 인증값으로 보이는 key의 값을 제거합니다."""

    value = jsonable(obj)
    if isinstance(value, Mapping):
        return {
            str(key): "<REDACTED>" if _is_sensitive_key(key) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def slugify(value: str) -> str:
    """case name을 파일명으로 쓰기 좋은 값으로 바꿉니다."""

    text = value.strip().lower()
    text = re.sub(r"[^\w가-힣]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return text or "case"


def save_fixture(
    *,
    base_dir: str | Path,
    function_name: str,
    case_name: str,
    description: str,
    input_data: Mapping[str, Any],
    request_data: Mapping[str, Any],
    response_data: Mapping[str, Any],
    parsed_result: Any,
    processed_result: Any,
    assertion: Mapping[str, Any] | None = None,
    library_version: str | None = None,
    overwrite: bool = False,
) -> Path:
    """DebugRun 결과를 tests/fixtures/{function}/{case}.json 형식으로 저장합니다."""

    safe_function_name = slugify(function_name)
    safe_case_name = slugify(case_name)
    fixture_dir = Path(base_dir) / safe_function_name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / f"{safe_case_name}.json"

    if fixture_path.exists() and not overwrite:
        raise FileExistsError(f"Fixture already exists: {fixture_path}")

    fixture = {
        "name": safe_case_name,
        "function": function_name,
        "description": description,
        "input": redact_sensitive(input_data),
        "request": redact_sensitive(request_data),
        "response": redact_sensitive(response_data),
        "parsed": redact_sensitive(parsed_result),
        "processed": redact_sensitive(processed_result),
        "assertion": dict(assertion or DEFAULT_ASSERTION),
        "meta": {
            "created_at": _now_seoul().isoformat(),
            "library_version": (
                library_version if library_version is not None else _package_version()
            ),
            "source": "debug_ui",
        },
    }

    with fixture_path.open("w", encoding="utf-8") as file:
        json.dump(fixture, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return fixture_path


def _input_data(*, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(kwargs)
    if args:
        data["_args"] = list(args)
    return data


def _request_from_page(page: Page[Any]) -> dict[str, Any]:
    context = page.context
    request = redact_sensitive(
        {
            "method": context.request_method or "GET",
            "url": context.request_url,
            "query": dict(context.request_params),
            "service_name": context.service_name,
            "endpoint": context.endpoint,
        }
    )
    return cast(dict[str, Any], request)


def _response_from_page(page: Page[Any]) -> dict[str, Any]:
    context = page.context
    response = redact_sensitive(
        {
            "status_code": context.response_status_code,
            "headers": dict(context.response_headers),
            "body": page.raw,
        }
    )
    return cast(dict[str, Any], response)


def _error_run(
    *,
    function_name: str,
    input_data: dict[str, Any],
    trace: list[str],
    error: Exception,
    catalog: dict[str, Any] | None,
) -> DebugRun:
    return DebugRun(
        function=function_name,
        input=redact_sensitive(input_data),
        request={},
        response={},
        parsed=None,
        processed=None,
        trace=trace,
        error=_error_data(error),
        catalog=catalog,
    )


def _error_data(error: Exception) -> dict[str, Any]:
    metadata = error.metadata if isinstance(error, KasiError) else {}
    return {
        "type": error.__class__.__name__,
        "message": str(error),
        "metadata": redact_sensitive(metadata),
    }


def _catalog_data(function_name: str) -> dict[str, Any] | None:
    try:
        return get_api_catalog_entry(function_name).to_dict()
    except ValueError:
        return None


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).replace("_", "").replace("-", "").lower()
    sensitive_keys = {item.replace("_", "").replace("-", "").lower() for item in SENSITIVE_KEYS}
    return normalized in sensitive_keys


def _now_seoul() -> datetime:
    tz: tzinfo
    try:
        tz = ZoneInfo("Asia/Seoul")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=9))
    return datetime.now(tz)


def _package_version() -> str | None:
    try:
        return version("python-kasi-api")
    except PackageNotFoundError:
        return None


__all__ = [
    "DEFAULT_ASSERTION",
    "DebugRun",
    "SENSITIVE_KEYS",
    "build_debug_run",
    "jsonable",
    "redact_sensitive",
    "save_fixture",
    "slugify",
]
