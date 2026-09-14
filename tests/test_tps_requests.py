"""공개 KASI 요청과 디버그의 공유 TPS 예산을 검증합니다."""
import asyncio
import time

import httpx
import pytest

from kasi import AsyncTokenBucket, KasiAuthError, KasiClient

from .conftest import kasi_payload


class CountingBucket(AsyncTokenBucket):
    def __init__(self):
        super().__init__(100)
        self.calls = 0

    async def acquire(self):
        self.calls += 1
        await super().acquire()


async def test_shared_request_debug_retry_and_redirect_budget():
    bucket = CountingBucket()
    seen = []
    payload = kasi_payload({"dateName": "어린이날", "locdate": "20260505", "isHoliday": "Y"})

    def respond(request):
        seen.append(request.url.path)
        if len(seen) == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        if len(seen) == 2:
            return httpx.Response(307, headers={"Location": "/result"})
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as session:
        async with KasiClient("test-key", session=session, rate_limiter=bucket) as first:
            async with KasiClient("test-key", session=session, rate_limiter=bucket) as second:
                page = await first.holidays(sol_year=2026, sol_month=5)
                run = await second.debug_holidays(sol_year=2026, sol_month=5)
                assert run.error is None
                assert run.parsed.items == page.items
        assert bucket.calls == len(seen) == 4
        assert not session.is_closed
        with pytest.raises(RuntimeError, match="closed"):
            await first.holidays(sol_year=2026)
        assert len(seen) == 4


async def test_concurrent_public_requests_obey_capacity_one_budget():
    sent = []

    def respond(request):
        sent.append(time.monotonic())
        return httpx.Response(200, json=kasi_payload([]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as session:
        async with KasiClient(
            "test-key", session=session, rate_limiter=AsyncTokenBucket(20, capacity=1)
        ) as client:
            await asyncio.gather(*(client.holidays(sol_year=2026) for _ in range(5)))
    assert len(sent) == 5
    assert sent[-1] - sent[0] >= 0.195


@pytest.mark.parametrize("rate", [0, -1, float("inf"), float("nan"), True])
def test_invalid_rate_rejected(rate):
    with pytest.raises(ValueError):
        KasiClient("test-key", max_rps=rate)


def test_sync_injection_rejected_without_request():
    assert not hasattr(KasiClient, "aio")
    assert not hasattr(KasiClient, "__enter__")
    with httpx.Client() as session:
        with pytest.raises(TypeError, match="must be async"):
            KasiClient("test-key", session=session)


@pytest.mark.parametrize("key,code", [("test-key", "30"), ("KEY", "40")])
async def test_body_auth_error_classification_precedes_secret_scrubbing(key, code):
    payload = {"response": {"header": {
        "resultCode": code, "resultMsg": f"SERVICE_KEY_IS_NOT_REGISTERED_ERROR {key}"
    }, "body": {}}}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as session:
        async with KasiClient(key, session=session) as client:
            with pytest.raises(KasiAuthError) as error:
                await client.holidays(sol_year=2026)
            assert key not in str(error.value)
            assert key not in repr(error.value.response)
            run = await client.debug_holidays(sol_year=2026)
            assert run.error["type"] == "KasiAuthError"
            assert key not in repr(run.error)
