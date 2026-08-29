# decisions.md — 의사결정 기록

이 문서는 이 프로젝트의 구조적 결정을 결정 시점 순서로 누적한다.
결정이 뒤집힐 때는 새 항목을 추가하고, 옛 항목은 지우지 않은 채
(supersedes: 위 항목)으로 표시한다.

## D-001: 라이브러리 본체는 Streamlit에 의존하지 않고, 디버그 UI는 optional extra로 분리한다

- 상태: accepted
- 날짜: 2026-05-15

### 컨텍스트

디버그 웹 UI에서 API 호출 결과를 바로 확인·저장할 수 있어야 했지만, `kasi`를 라이브러리로만
쓰는 downstream(TripMate 등 다른 서비스)까지 Streamlit과 그 하위 의존성을 강제로 설치하게
만들면 안 됐다.

### 결정

`KasiClient`가 `DebugRun`(입력/요청/응답/파싱 결과/오류를 분리 보존)을 반환하도록 하고,
`debug_ui/app.py`의 Streamlit 앱은 이 패키지를 wheel/editable install로 import해서만 쓰게
분리한다. Streamlit은 `pyproject.toml`의 `[project.optional-dependencies]`의 `debug-ui`
extra에만 넣고, 기본 런타임 의존성(`httpx`, `pydantic`)에는 포함하지 않는다.

### 근거

- 라이브러리만 필요한 downstream이 웹 프레임워크 의존성을 떠안지 않아야 한다.
- 디버그 흐름(요청/응답/파싱 결과 확인, fixture 저장)은 UI 프레임워크와 무관하게 그 자체로
  가치가 있다.

### 결과

- `pip install python-kasi-api`만으로는 Streamlit이 설치되지 않고, `pip install -e ".[debug-ui]"`로
  디버그 UI를 켤 때만 추가된다.
- fixture 저장/재생(`save_fixture`, `tests/test_generated_fixtures.py`)이 UI 존재 여부와
  무관하게 네트워크 없이 동작한다.

## D-002: 기본 HTTP transport를 `httpx.AsyncClient`로 두고, 동기 `KasiClient`는 그 위의 facade로 둔다

- 상태: accepted
- 날짜: 2026-05-19

### 컨텍스트

동기 클라이언트만 있던 초기 구조에서는 async 코드가 이 클라이언트를 직접 쓸 수 없었다.
동기/비동기 구현을 각각 따로 유지하면 retry, rate limit, JSON/XML envelope 정규화, 오류
매핑 로직이 두 곳으로 갈라져 중복되고 어긋나기 쉬웠다.

### 결정

HTTP 호출 구현은 `httpx.AsyncClient` 기반 하나만 두고, `AsyncKasiClient`가 이를 직접 쓴다.
동기 `KasiClient`는 별도 구현이 아니라 이 비동기 transport를 실행하는 facade로 두어, 두
클라이언트가 항상 같은 retry·rate limit·오류 매핑 경로를 통과하게 한다.

### 근거

- 하나의 HTTP 구현만 유지하면 동기/비동기 경로가 다른 버그를 갖는 일을 막을 수 있다.
- `python-krheritage-api`와 같은 공개 인터페이스 형태(`PROVIDER_NAME`, `client.config`,
  context manager, `api_key=`)를 따르면서도 async 소비자를 함께 지원할 수 있다.

### 결과

- `with KasiClient() as client: ...`와 `async with AsyncKasiClient() as client: ...`가 같은
  이름의 메서드로 동일한 `Page[T]`를 반환한다.
- 동기 API를 async 이벤트 루프 안에서 호출하면 안 된다는 제약이 새로 생겼고, 그 경우
  `AsyncKasiClient` 또는 `KasiClient.aio()`를 써야 한다.
