from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from kasi import KasiClient


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        text: str | None = None,
        status_code: int = 200,
    ) -> None:
        self.payload = payload
        self.text = text if text is not None else ""
        self.status_code = status_code

    def json(self) -> Any:
        if self.payload is None:
            raise ValueError("not json")
        return self.payload


class FakeSession:
    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if not self.responses:
            raise AssertionError("no fake response queued")
        return self.responses.pop(0)


def kasi_payload(item: Any, *, page_no: int = 1, num_of_rows: int = 10) -> dict[str, Any]:
    if item is None:
        items: Any = ""
        total_count = 0
    else:
        items = {"item": item}
        total_count = len(item) if isinstance(item, list) else 1
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": items,
                "pageNo": page_no,
                "numOfRows": num_of_rows,
                "totalCount": total_count,
            },
        }
    }


@pytest.fixture
def fake_client_factory():
    def factory(*responses: FakeResponse) -> tuple[KasiClient, FakeSession]:
        session = FakeSession(*responses)
        return KasiClient("TEST_KEY", session=session, retries=0), session

    return factory


def load_tripmate_env() -> None:
    for env_file in (
        Path(r"F:\dev\mapplan\.env"),
        Path(r"F:\dev\mapplan\apps\api\.env"),
    ):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
