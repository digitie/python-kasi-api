"""KASI data.go.kr API의 httpx 기반 비동기 transport와 응답 envelope 처리."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, cast
from xml.etree import ElementTree

import httpx

from ._convert import normalize_service_key, sanitize_request_params, without_none
from .exceptions import (
    KasiAuthError,
    KasiParseError,
    KasiRateLimitError,
    KasiRequestError,
    KasiServerError,
)

DEFAULT_BASE_URL = "https://apis.data.go.kr/B090041/openapi/service"
DEFAULT_USER_AGENT = "python-kasi-api/0.1 (+https://github.com/digitie/python-kasi-api)"
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class KasiHttpResult:
    """정규화된 응답 body와 디버그용 HTTP metadata."""

    body: Mapping[str, Any]
    request: dict[str, Any]
    response: dict[str, Any]


@dataclass(slots=True)
class AsyncTokenBucket:
    """동시 비동기 호출에서 초당 요청량을 완만하게 제한합니다."""

    max_rps: float = 5.0
    capacity: float | None = None
    _tokens: float = field(init=False)
    _updated_at: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        if self.max_rps <= 0:
            raise ValueError("max_rps must be greater than 0")
        self.capacity = self.capacity or self.max_rps
        self._tokens = self.capacity
        self._updated_at = time.monotonic()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_for = (1 - self._tokens) / self.max_rps
            await asyncio.sleep(wait_for)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated_at
        self._updated_at = now
        assert self.capacity is not None
        self._tokens = min(self.capacity, self._tokens + elapsed * self.max_rps)


class ResponseLike(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class SessionLike(Protocol):
    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        timeout: float,
    ) -> ResponseLike: ...


def build_session(timeout: float = 10.0) -> SessionLike:
    """KASI 호출에 사용할 기본 httpx.AsyncClient를 만듭니다."""

    return cast(
        SessionLike,
        httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.8",
            },
        ),
    )


class AsyncKasiHttp:
    """KASI 서비스를 호출하는 비동기 data.go.kr transport."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        session: SessionLike | None = None,
        timeout: float = 10.0,
        retries: int = 3,
        max_rps: float = 5.0,
    ) -> None:
        normalized_key = normalize_service_key(service_key)
        if not normalized_key:
            raise KasiAuthError("service_key is required", failure_kind="auth")
        if not service_key_param:
            raise ValueError("service_key_param must not be empty")
        self.service_key = normalized_key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.session = session or build_session(timeout=timeout)
        self._owns_session = session is None
        self.timeout = timeout
        self.retries = max(0, retries)
        self._bucket = AsyncTokenBucket(max_rps=max_rps)

    async def __aenter__(self) -> AsyncKasiHttp:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        close = getattr(self.session, "aclose", None)
        if self._owns_session and callable(close):
            await close()

    async def get(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = "json",
    ) -> Mapping[str, Any]:
        """KASI operation을 호출하고 정규화된 body만 반환합니다."""

        return (
            await self.get_result(
                service_name,
                operation,
                params,
                response_format=response_format,
            )
        ).body

    async def get_result(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = "json",
    ) -> KasiHttpResult:
        """KASI operation을 호출하고 replay fixture에 필요한 metadata를 함께 반환합니다."""

        service_path = service_name.strip("/")
        operation_path = operation.strip("/")
        endpoint = f"{service_path}/{operation_path}"
        url = f"{self.base_url}/{endpoint}"
        request_params = kasi_request_params(
            service_key=self.service_key,
            service_key_param=self.service_key_param,
            params=params,
            response_format=response_format,
        )
        public_params = sanitize_request_params(request_params)
        response = await self._request_with_retry(
            url,
            request_params=without_none(request_params),
            service_name=service_path,
            endpoint=operation_path,
            service_key=self.service_key,
            public_params=public_params,
        )
        _raise_for_status(
            response,
            service_name=service_path,
            endpoint=operation_path,
            service_key=self.service_key,
            params=public_params,
        )
        payload = _parse_payload(
            response,
            service_name=service_path,
            endpoint=operation_path,
            service_key=self.service_key,
            params=public_params,
        )
        body = _extract_body(
            payload,
            service_name=service_path,
            endpoint=operation_path,
            status_code=response.status_code,
            params=public_params,
        )
        return KasiHttpResult(
            body=body,
            request={
                "method": "GET",
                "url": url,
                "query": public_params,
            },
            response={
                "status_code": response.status_code,
                "headers": _response_headers(response),
                "body": body,
            },
        )

    async def _request_with_retry(
        self,
        url: str,
        *,
        request_params: Mapping[str, Any],
        service_name: str,
        endpoint: str,
        service_key: str,
        public_params: dict[str, Any],
    ) -> ResponseLike:
        for attempt in range(self.retries + 1):
            await self._bucket.acquire()
            try:
                response = await self.session.get(
                    url,
                    params=request_params,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                if attempt < self.retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise KasiRequestError(
                    "KASI request timed out",
                    service_name=service_name,
                    endpoint=endpoint,
                    failure_kind="timeout",
                    retryable=True,
                    params=public_params,
                ) from exc
            except httpx.ConnectError as exc:
                if attempt < self.retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise KasiRequestError(
                    "KASI request failed to connect",
                    service_name=service_name,
                    endpoint=endpoint,
                    failure_kind="network",
                    retryable=True,
                    params=public_params,
                ) from exc
            except httpx.HTTPError as exc:
                if attempt < self.retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise KasiRequestError(
                    f"KASI request failed: {_redact_secret(str(exc), service_key)}",
                    service_name=service_name,
                    endpoint=endpoint,
                    failure_kind="network",
                    retryable=True,
                    params=public_params,
                ) from exc

            if int(response.status_code) in TRANSIENT_STATUSES and attempt < self.retries:
                await asyncio.sleep(_backoff_seconds(attempt))
                continue
            return response
        raise AssertionError("unreachable")


class KasiHttp:
    """동기 코드에서 AsyncKasiHttp를 사용할 수 있게 하는 얇은 sync facade."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        session: SessionLike | None = None,
        timeout: float = 10.0,
        retries: int = 3,
        max_rps: float = 5.0,
    ) -> None:
        self.service_key = service_key
        self.base_url = base_url
        self.service_key_param = service_key_param
        self.session = session
        self.timeout = timeout
        self.retries = retries
        self.max_rps = max_rps

    def get(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = "json",
    ) -> Mapping[str, Any]:
        """KASI operation을 호출하고 정규화된 body만 반환합니다."""

        return self.get_result(
            service_name,
            operation,
            params,
            response_format=response_format,
        ).body

    def get_result(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = "json",
    ) -> KasiHttpResult:
        """동기 호출자를 위해 비동기 transport 실행 결과를 반환합니다."""

        return _run_sync(
            lambda: self._get_result_once(
                service_name,
                operation,
                params,
                response_format=response_format,
            )
        )

    def close(self) -> None:
        """동기 facade는 요청마다 AsyncKasiHttp를 생성하므로 닫을 보유 자원이 없습니다."""

        return None

    async def _get_result_once(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = "json",
    ) -> KasiHttpResult:
        http = AsyncKasiHttp(
            self.service_key,
            base_url=self.base_url,
            service_key_param=self.service_key_param,
            session=self.session,
            timeout=self.timeout,
            retries=self.retries,
            max_rps=self.max_rps,
        )
        try:
            return await http.get_result(
                service_name,
                operation,
                params,
                response_format=response_format,
            )
        finally:
            if self.session is None:
                await http.aclose()


def kasi_request_params(
    *,
    service_key: str,
    service_key_param: str = "serviceKey",
    params: Mapping[str, Any] | None = None,
    response_format: str | None = "json",
) -> dict[str, Any]:
    normalized_key = normalize_service_key(service_key)
    if not normalized_key:
        raise KasiAuthError("service_key is required", failure_kind="auth")
    request_params: dict[str, Any] = {service_key_param: normalized_key}
    if response_format:
        fmt = response_format.lower()
        if fmt not in {"json", "xml"}:
            raise ValueError("response_format must be 'json', 'xml', or None")
        request_params["_type"] = fmt
    if params:
        request_params.update(dict(params))
    return request_params


def public_request_params(
    *,
    params: Mapping[str, Any] | None = None,
    response_format: str | None = "json",
) -> dict[str, Any]:
    request_params: dict[str, Any] = {}
    if response_format:
        request_params["_type"] = response_format.lower()
    if params:
        request_params.update(dict(params))
    return sanitize_request_params(request_params)


def _raise_for_status(
    response: ResponseLike,
    *,
    service_name: str,
    endpoint: str,
    service_key: str,
    params: dict[str, Any],
) -> None:
    status = int(response.status_code)
    text = _redact_secret(response.text, service_key)[:300]
    if status in {401, 403}:
        raise KasiAuthError(
            f"HTTP {status}: {text}",
            status_code=status,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="auth",
            retryable=False,
            params=params,
        )
    if status == 429:
        raise KasiRateLimitError(
            f"HTTP {status}: {text}",
            status_code=status,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="rate_limit",
            retryable=True,
            params=params,
        )
    if 400 <= status < 500:
        raise KasiRequestError(
            f"HTTP {status}: {text}",
            status_code=status,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="request",
            retryable=False,
            params=params,
        )
    if 500 <= status < 600:
        raise KasiServerError(
            f"HTTP {status}: {text}",
            status_code=status,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="server",
            retryable=True,
            params=params,
        )


def _parse_payload(
    response: ResponseLike,
    *,
    service_name: str,
    endpoint: str,
    service_key: str,
    params: dict[str, Any],
) -> Mapping[str, Any]:
    text = response.text.strip()
    if text.startswith("{") or text.startswith("["):
        try:
            payload = response.json()
        except ValueError as exc:
            raise KasiParseError(
                f"KASI JSON response could not be parsed: {_redact_secret(str(exc), service_key)}",
                status_code=response.status_code,
                service_name=service_name,
                endpoint=endpoint,
                failure_kind="parse",
                retryable=False,
                params=params,
            ) from exc
        if not isinstance(payload, Mapping):
            raise KasiParseError(
                "KASI JSON root was not an object",
                status_code=response.status_code,
                service_name=service_name,
                endpoint=endpoint,
                failure_kind="parse",
                retryable=False,
                response=payload,
                params=params,
            )
        return payload

    if text.startswith("<"):
        return _parse_xml_payload(
            text,
            status_code=response.status_code,
            service_name=service_name,
            endpoint=endpoint,
            params=params,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise KasiParseError(
            f"KASI response was neither JSON nor XML: {_redact_secret(text[:200], service_key)}",
            status_code=response.status_code,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            retryable=False,
            params=params,
        ) from exc
    if not isinstance(payload, Mapping):
        raise KasiParseError(
            "KASI JSON root was not an object",
            status_code=response.status_code,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            retryable=False,
            response=payload,
            params=params,
        )
    return payload


def _parse_xml_payload(
    text: str,
    *,
    status_code: int,
    service_name: str,
    endpoint: str,
    params: dict[str, Any],
) -> Mapping[str, Any]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise KasiParseError(
            f"KASI XML response could not be parsed: {exc}",
            status_code=status_code,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            retryable=False,
            params=params,
        ) from exc
    tag = _local_name(root.tag)
    return {tag: _element_to_obj(root)}


def _element_to_obj(element: ElementTree.Element) -> Any:
    children = list(element)
    text = (element.text or "").strip()
    if not children:
        return text
    result: dict[str, Any] = {}
    for child in children:
        tag = _local_name(child.tag)
        value = _element_to_obj(child)
        if tag in result:
            current = result[tag]
            if isinstance(current, list):
                current.append(value)
            else:
                result[tag] = [current, value]
        else:
            result[tag] = value
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _response_headers(response: ResponseLike) -> dict[str, str]:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return {}
    return {str(key): str(value) for key, value in headers.items()}


def _extract_body(
    payload: Mapping[str, Any],
    *,
    service_name: str,
    endpoint: str,
    status_code: int,
    params: dict[str, Any],
) -> Mapping[str, Any]:
    if "OpenAPI_ServiceResponse" in payload:
        _raise_openapi_service_error(
            payload["OpenAPI_ServiceResponse"],
            service_name=service_name,
            endpoint=endpoint,
            params=params,
        )

    try:
        response = payload["response"]
        header = response["header"]
    except (KeyError, TypeError) as exc:
        raise KasiParseError(
            "KASI response did not contain response.header",
            status_code=status_code,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            response=payload,
            params=params,
        ) from exc
    if not isinstance(response, Mapping) or not isinstance(header, Mapping):
        raise KasiParseError(
            "KASI response/header was not an object",
            status_code=status_code,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            response=payload,
            params=params,
        )

    code = str(header.get("resultCode", "")).strip()
    message = str(header.get("resultMsg", "")).strip()
    body = response.get("body", {})
    if code in {"00", "0000", "0", "NORMAL_CODE", ""}:
        if isinstance(body, Mapping):
            return body
        raise KasiParseError(
            "KASI response.body was not an object",
            status_code=status_code,
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            response=payload,
            params=params,
        )
    if code == "03":
        return body if isinstance(body, Mapping) else {}
    _raise_result_code(
        code,
        message,
        service_name=service_name,
        endpoint=endpoint,
        response=payload,
        params=params,
    )
    raise AssertionError("unreachable")


def _raise_openapi_service_error(
    data: Any,
    *,
    service_name: str,
    endpoint: str,
    params: dict[str, Any],
) -> None:
    if not isinstance(data, Mapping):
        raise KasiParseError(
            "OpenAPI_ServiceResponse was not an object",
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            response=data,
            params=params,
        )
    header = data.get("cmmMsgHeader", data)
    if not isinstance(header, Mapping):
        raise KasiParseError(
            "OpenAPI_ServiceResponse header was not an object",
            service_name=service_name,
            endpoint=endpoint,
            failure_kind="parse",
            response=data,
            params=params,
        )
    code = str(header.get("returnReasonCode", "")).strip()
    message = str(
        header.get("returnAuthMsg")
        or header.get("errMsg")
        or header.get("resultMsg")
        or "KASI service error"
    )
    _raise_result_code(
        code,
        message,
        service_name=service_name,
        endpoint=endpoint,
        response=data,
        params=params,
    )


def _raise_result_code(
    code: str,
    message: str,
    *,
    service_name: str,
    endpoint: str,
    response: Any | None,
    params: dict[str, Any],
) -> None:
    text = f"KASI API returned {code}: {message}" if code else message
    upper = text.upper()
    kwargs: dict[str, Any] = {
        "result_code": code or None,
        "service_name": service_name,
        "endpoint": endpoint,
        "response": response,
        "params": params,
    }
    if code in {"20", "21", "30", "31", "32", "33"} or "SERVICE_KEY" in upper:
        raise KasiAuthError(text, failure_kind="auth", retryable=False, **kwargs)
    if code == "22" or "LIMIT" in upper or "TRAFFIC" in upper or "QUOTA" in upper:
        raise KasiRateLimitError(text, failure_kind="rate_limit", retryable=True, **kwargs)
    if code in {"01", "02", "04", "05", "99"} or code.startswith("5"):
        raise KasiServerError(text, failure_kind="server", retryable=True, **kwargs)
    raise KasiRequestError(text, failure_kind="request", retryable=False, **kwargs)


def _backoff_seconds(attempt: int) -> float:
    return float(min(0.3 * (2**attempt), 8.0))


def _run_sync(factory: Callable[[], Coroutine[Any, Any, R]]) -> R:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    result: R | None = None
    error: BaseException | None = None

    def runner() -> None:
        nonlocal result, error
        try:
            result = asyncio.run(factory())
        except BaseException as exc:  # pragma: no cover - 방어적 thread bridge
            error = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error is not None:
        raise error
    return cast(R, result)


def _redact_secret(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")
