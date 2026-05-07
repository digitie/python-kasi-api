"""Exception hierarchy for pykasi."""

from __future__ import annotations

from typing import Any


class KasiError(Exception):
    """Base class for pykasi errors."""

    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        result_code: str | None = None,
        service_name: str | None = None,
        endpoint: str | None = None,
        failure_kind: str | None = None,
        retryable: bool | None = None,
        response: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.result_code = result_code
        self.service_name = service_name
        self.endpoint = endpoint
        self.failure_kind = failure_kind
        self.retryable = retryable
        self.response = response
        self.params = params

    @property
    def metadata(self) -> dict[str, Any]:
        """Return non-empty structured error metadata."""

        values: dict[str, Any | None] = {
            "status_code": self.status_code,
            "result_code": self.result_code,
            "service_name": self.service_name,
            "endpoint": self.endpoint,
            "failure_kind": self.failure_kind,
            "retryable": self.retryable,
            "params": self.params,
        }
        return {key: value for key, value in values.items() if value is not None}


class KasiAuthError(KasiError):
    """Raised when the data.go.kr service key is missing, invalid, or unauthorized."""


class KasiRateLimitError(KasiError):
    """Raised when data.go.kr quota or traffic limits are exceeded."""


class KasiRequestError(KasiError):
    """Raised when the API rejects a malformed request."""


class KasiServerError(KasiError):
    """Raised for upstream server-side failures."""


class KasiParseError(KasiError):
    """Raised when a KASI response cannot be parsed."""


class KasiNoDataError(KasiError):
    """Raised by strict helpers when an operation returns no data."""
