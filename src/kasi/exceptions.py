"""kasi 예외 계층."""

from __future__ import annotations

from typing import Any


class KasiError(Exception):
    """모든 kasi 예외의 기반 클래스."""

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
        """비어 있지 않은 구조화 오류 metadata를 반환합니다."""

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
    """data.go.kr 서비스 키가 없거나, 잘못됐거나, 승인되지 않았을 때 발생합니다."""


class KasiRateLimitError(KasiError):
    """data.go.kr 할당량 또는 트래픽 제한을 초과했을 때 발생합니다."""


class KasiRequestError(KasiError):
    """API가 잘못된 요청을 거부했을 때 발생합니다."""


class KasiServerError(KasiError):
    """상위 서비스의 서버 측 실패에 대해 발생합니다."""


class KasiParseError(KasiError):
    """KASI 응답을 기대한 형태로 파싱할 수 없을 때 발생합니다."""


class KasiNoDataError(KasiError):
    """strict helper에서 데이터 없음 응답을 실패로 취급할 때 발생합니다."""
