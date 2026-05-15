"""fixture replay에서 비교할 안정적인 processed 결과를 만듭니다."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from .models import Page


def process_page(page: Page[Any]) -> dict[str, Any]:
    """Page 모델에서 raw/context를 뺀 비교용 결과를 반환합니다."""

    return {
        "items": [_jsonable(item) for item in page.items],
        "page_no": page.page_no,
        "num_of_rows": page.num_of_rows,
        "total_count": page.total_count,
    }


def process_function_result(function_name: str, parsed: Any) -> Any:
    """함수별 parsed 결과를 fixture snapshot에 맞는 processed 형태로 변환합니다."""

    if isinstance(parsed, Page):
        return process_page(parsed)
    return _jsonable(parsed)


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Mapping):
        return {str(key): _jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(item) for item in obj]
    return obj


__all__ = ["process_function_result", "process_page"]
