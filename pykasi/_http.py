"""HTTP and response-envelope handling for KASI data.go.kr APIs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ._convert import sanitize_request_params, without_none
from .exceptions import (
    KasiAuthError,
    KasiParseError,
    KasiRateLimitError,
    KasiRequestError,
    KasiServerError,
)

DEFAULT_BASE_URL = "https://apis.data.go.kr/B090041/openapi/service"
DEFAULT_USER_AGENT = "pykasi/0.1 (+https://github.com/digitie/pykasi)"
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}


class ResponseLike(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class SessionLike(Protocol):
    def get(self, url: str, *, params: Mapping[str, Any], timeout: float) -> ResponseLike: ...


def build_session(retries: int = 3) -> SessionLike:
    """Build a requests session with conservative GET retries."""

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.8",
        }
    )
    if retries <= 0:
        return cast(SessionLike, session)
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.3,
        status_forcelist=tuple(sorted(TRANSIENT_STATUSES)),
        allowed_methods=frozenset({"GET"}),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return cast(SessionLike, session)


class KasiHttp:
    """Low-level data.go.kr client for KASI services."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        service_key_param: str = "serviceKey",
        session: SessionLike | None = None,
        timeout: float = 10.0,
        retries: int = 3,
    ) -> None:
        if not service_key:
            raise KasiAuthError("service_key is required", failure_kind="auth")
        if not service_key_param:
            raise ValueError("service_key_param must not be empty")
        self.service_key = service_key
        self.base_url = base_url.rstrip("/")
        self.service_key_param = service_key_param
        self.session = session or build_session(retries)
        self.timeout = timeout

    def get(
        self,
        service_name: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        response_format: str | None = "json",
    ) -> Mapping[str, Any]:
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
        try:
            response = self.session.get(
                url,
                params=without_none(request_params),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise KasiRequestError(
                "KASI request timed out",
                service_name=service_path,
                endpoint=operation_path,
                failure_kind="timeout",
                retryable=True,
                params=public_params,
            ) from exc
        except requests.ConnectionError as exc:
            raise KasiRequestError(
                "KASI request failed to connect",
                service_name=service_path,
                endpoint=operation_path,
                failure_kind="network",
                retryable=True,
                params=public_params,
            ) from exc
        except requests.RequestException as exc:
            raise KasiRequestError(
                "KASI request failed",
                service_name=service_path,
                endpoint=operation_path,
                failure_kind="network",
                retryable=True,
                params=public_params,
            ) from exc

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
        return _extract_body(
            payload,
            service_name=service_path,
            endpoint=operation_path,
            status_code=response.status_code,
            params=public_params,
        )


def kasi_request_params(
    *,
    service_key: str,
    service_key_param: str = "serviceKey",
    params: Mapping[str, Any] | None = None,
    response_format: str | None = "json",
) -> dict[str, Any]:
    request_params: dict[str, Any] = {service_key_param: service_key}
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


def _redact_secret(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")
