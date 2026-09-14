# 비동기 전용 사용과 TPS

`KasiClient`의 조회와 디버그 helper는 await, 페이지 순회는 async for를 사용한다.
기존 AsyncKasiClient/aio/동기 context manager/close는 제거했다. 생성자와 from_env는
네트워크 요청이 없는 일반 함수다. 기존 함수 이름·키워드 인자·typed Page는 유지한다.

```python
from kasi import AsyncTokenBucket, KasiClient

async def collect():
    bucket = AsyncTokenBucket(max_rps=2, capacity=1)
    async with KasiClient.from_env(rate_limiter=bucket) as client:
        async for page in client.iter_pages(
            fetch_page=client.holidays, sol_year=2026, max_pages=2
        ):
            print(page.items)
        return await client.debug_holidays(sol_year=2026, sol_month=5)
```

`max_rps` 기본값은 5이며 유한한 양수만 받는다(0·음수·NaN·무한대·bool 거부).
용량 기본값은 max(1, max_rps)이며 최초에는 가득 차 있다. capacity=1로 초기 burst를
한 건으로 줄인다. 0.5 TPS도 지원한다. 고정 1초 구간의 호출 수를 세는 방식은 아니다.
버킷의 rate_limiter 주입이 max_rps보다 우선한다. 같은 객체를 여러 클라이언트에
주입하면 합산 예산을 공유한다. 한 이벤트 루프에서만 사용해야 한다.

모든 서비스·디버그·페이지 요청과 재시도·HTTPX redirect 추가 송신에 토큰을 사용한다.
대기 취소는 토큰을 소비하지 않고 후속 대기자가 진행한다. 임의 사용자 인증 흐름이나
transport 내부에서 발생한 별도 송신은 제어하지 않는다. 같은 코드의 공통 버킷과
redirect 처리기를 다른 Python API 라이브러리에도 적용한다.

async with 또는 await client.aclose()로 자체 세션을 닫는다. 외부 세션은 호출자가
닫으며 종료된 클라이언트는 추가 요청을 거부한다. Streamlit은 실행 경계에서 한 번
asyncio.run을 호출하고 같은 루프에서 생성·사용·종료한다.
