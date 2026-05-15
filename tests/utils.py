from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def remove_fields(obj: Any, exclude_fields: list[str]) -> Any:
    if isinstance(obj, Mapping):
        return {
            key: remove_fields(value, exclude_fields)
            for key, value in obj.items()
            if str(key) not in exclude_fields
        }
    if isinstance(obj, list):
        return [remove_fields(item, exclude_fields) for item in obj]
    return obj


def assert_case(actual: Any, expected: Any, assertion: Mapping[str, Any]) -> None:
    mode = str(assertion.get("mode", "snapshot"))

    if mode == "snapshot":
        exclude_fields = [str(field) for field in assertion.get("exclude_fields", [])]
        assert remove_fields(actual, exclude_fields) == remove_fields(expected, exclude_fields)
        return
    if mode == "required_fields":
        for field in assertion.get("required_fields", []):
            assert _has_path(actual, str(field)), f"missing required field: {field}"
        return
    if mode == "schema_only":
        assert actual is not None
        return
    if mode == "count":
        assert _result_count(actual) == _result_count(expected)
        return
    raise ValueError(f"Unknown assertion mode: {mode}")


def _has_path(obj: Any, path: str) -> bool:
    current = obj
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
            continue
        return False
    return True


def _result_count(obj: Any) -> int | None:
    if isinstance(obj, Mapping):
        if "count" in obj:
            value = obj["count"]
            return value if isinstance(value, int) else None
        items = obj.get("items")
        return len(items) if isinstance(items, list) else None
    if isinstance(obj, list):
        return len(obj)
    return None
