# python-kasi-api

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![GPL-3.0-or-later 라이선스](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)
![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)

`python-kasi-api`는 공공데이터포털(data.go.kr)의 한국천문연구원(KASI) OpenAPI를 위한 비공식
Python 클라이언트입니다. Python 코드에서는 `kasi` 이름으로 import하며, `httpx` 기반 동기/비동기
클라이언트와 타입화된 Pydantic 응답 모델을 제공합니다. 좌표와 지역명 입력은 별도 주소 모델 없이
API wire 값에 가까운 문자열·숫자 값으로 받습니다.

현재 상태와 변경 이력은 [CHANGELOG.md](CHANGELOG.md)의 `[Unreleased]`를 참고하세요.

## 제공 표면

| 표면 | 진입점 | 설명 |
|---|---|---|
| 동기 클라이언트 | `KasiClient` | 특일/음양력/출몰시각/태양고도/월령/천문현상 API를 동기 호출, context manager 지원 |
| 비동기 클라이언트 | `AsyncKasiClient`, `KasiClient.aio()` | 같은 API 표면을 `async`/`await`로 호출, `httpx.AsyncClient` 기반 |
| API 카탈로그 | `api_catalog()`, `api_catalog_rows()` | 함수별 데이터셋명, data.go.kr 활용신청 링크, 파라미터 metadata 조회 |
| 디버그 실행과 fixture | `KasiClient.debug_*()`, `save_fixture()` | 요청/응답/파싱 결과를 캡처하고 JSON fixture로 저장·재생 검증 |
| 디버그 웹 UI (optional) | `debug_ui/app.py` (`pip install -e ".[debug-ui]"`) | Streamlit 기반 API 탐색기, 라이브러리 본체와 분리된 별도 실행 진입점 |

## 먼저 읽을 문서

| 필요한 정보 | 문서 |
|---|---|
| 에이전트 작업 규칙, 모듈 소유권, 반복 실수 방지 | [AGENTS.md](AGENTS.md) |
| 구조적 설계 결정과 근거 | [docs/decisions.md](docs/decisions.md) |
| 사용자 가시적 변경 이력 | [CHANGELOG.md](CHANGELOG.md) |
| 라이선스 전문 | [LICENSE](LICENSE) |

## 설치

```bash
pip install -e ".[dev]"
```

## 인증

data.go.kr decoding 서비스 키를 사용합니다.

```powershell
$env:DATA_GO_KR_SERVICE_KEY="your_decoding_key"
```

`KasiClient()`와 `KasiClient.from_env()`는 `DATA_GO_KR_SERVICE_KEY` 환경변수를 확인합니다.
실제 환경변수가 없으면 현재 작업 디렉터리의 `.env`, `.env.local`도 같은 이름으로 확인합니다.
복사/붙여넣기 과정에서 서비스키 앞뒤나 중간에 들어간 공백, 탭, 줄바꿈은 자동으로 제거합니다.

```dotenv
DATA_GO_KR_SERVICE_KEY=your_decoding_key
```

data.go.kr 활용승인은 API별로 분리되어 있습니다. 한 키가 일부 KASI 서비스는 호출하지만 다른
서비스에서 HTTP 403을 반환할 수 있습니다. 이 경우 해당 API를 data.go.kr에서 추가 활용신청하거나
이미 승인된 키를 사용해야 합니다. 클라이언트는 이 응답을 `KasiAuthError`로 매핑하며, 응답
context에는 인증키를 노출하지 않습니다.

## 예제

```python
from kasi import KasiClient

with KasiClient() as client:
    holidays = client.holidays(sol_year=2026, sol_month=5)
    for day in holidays:
        print(day.locdate, day.date_name, day.is_holiday)
```

이 예제는 `holidays`(특일 조회) 하나만 다룹니다. 나머지 API 진입점은 위 "제공 표면" 표를
참고하세요.

## 사용법 상세

`python-krheritage-api`와 같은 형태로 명시 키를 넘길 때는 `api_key=`를 사용합니다. 기존
`service_key=`도 계속 지원합니다.

목록형 응답은 모두 `Page[T]`를 반환합니다.

```python
page.items
page.first
page.total_count
page.context.request_params  # 인증 파라미터는 제거됨
```

비동기 코드에서는 `AsyncKasiClient` 또는 `KasiClient.aio()`를 사용합니다. 내부 HTTP 호출은
`httpx.AsyncClient` 기반이며, retry와 간단한 async token bucket rate limit을 적용합니다
(설계 근거: [D-002](docs/decisions.md#d-002-기본-http-transport를-httpxasyncclient로-두고-동기-kasiclient는-그-위의-facade로-둔다)).

```python
from kasi import AsyncKasiClient

async with AsyncKasiClient.from_env() as client:
    page = await client.holidays(sol_year=2026, sol_month=5)
    print(page.first)
```

동기 클라이언트에서 바로 비동기 클라이언트를 만들 때는 `KasiClient.aio(api_key=...)`를 사용할
수 있습니다.

### 디버그 실행과 Fixture Replay

`KasiClient`는 Web UI나 로컬 디버그 도구가 바로 사용할 수 있는 `DebugRun`을 반환합니다.
라이브러리 본체는 Streamlit에 의존하지 않고, UI는 wheel 또는 editable install된 `kasi`를
import해서 아래 결과만 표시하거나 저장하면 됩니다(설계 근거:
[D-001](docs/decisions.md#d-001-라이브러리-본체는-streamlit에-의존하지-않고-디버그-ui는-optional-extra로-분리한다)).

```python
from kasi import KasiClient

client = KasiClient.from_env()
run = client.debug_holidays(sol_year=2026, sol_month=5)

run.input      # 사용자가 넣은 입력값
run.request    # 인증키가 제거된 요청 method/url/query
run.response   # status_code, headers, 정규화된 response body
run.parsed     # Page[SpecialDay] 같은 Pydantic 결과
run.processed  # fixture snapshot 비교용 안정 결과
run.error      # 실패 시 type/message/metadata
```

의미 있는 실행 결과는 JSON fixture로 저장할 수 있습니다. `save_fixture()`는 `serviceKey`,
`Authorization`, `api_key`, `access_token` 같은 민감 key를 저장 전에 마스킹하고, 같은 파일명은
기본적으로 덮어쓰지 않습니다.

```python
from kasi import save_fixture

save_fixture(
    base_dir="tests/fixtures",
    function_name=run.function,
    case_name="children_day_2026",
    description="2026년 5월 어린이날 정상 응답",
    input_data=run.input,
    request_data=run.request,
    response_data=run.response,
    parsed_result=run.parsed,
    processed_result=run.processed,
)
```

저장된 fixture는 `tests/test_generated_fixtures.py`에서 자동으로 읽어 replay 방식으로
검증합니다. 이 테스트는 외부 API를 호출하지 않고, fixture의 `response.body`를
`kasi.parser.parse_function_response()`로 다시 파싱한 뒤
`kasi.processor.process_function_result()` 결과를 fixture의 `processed`와 비교합니다.

지원 assertion mode는 `snapshot`, `schema_only`, `required_fields`이며, `count`는 간단한 결과
개수 비교용으로 사용할 수 있습니다.

### API 카탈로그와 디버그 UI

`api_catalog()`는 지원 API의 함수명, 사람이 읽기 좋은 데이터셋명, data.go.kr 데이터셋 ID,
서비스키 활용신청 링크, 서비스명, operation, 파라미터 metadata를 반환합니다.

```python
from kasi import api_catalog

for entry in api_catalog():
    print(entry.dataset_name, entry.function_name, entry.service_key_url)
```

Streamlit 디버그 UI는 라이브러리 본체와 분리된 `debug_ui/app.py`에 있습니다. 선택한 API의
Debug Trace 탭에는 카탈로그 항목과 서비스키 신청 링크가 함께 표시됩니다.

```bash
pip install -e ".[debug-ui]"
streamlit run debug_ui/app.py
```

### Live Test

live test는 기본적으로 비활성화되어 있습니다.

```powershell
$env:KASI_LIVE="1"
python -m pytest -m live -vv
```

테스트는 `DATA_GO_KR_SERVICE_KEY` 환경변수를 사용합니다.

## 검증

```bash
python -m pytest -q -m "not live"
python -m ruff check .
python -m mypy src/kasi
```

## 데이터·API 출처

- 공공데이터포털(data.go.kr) 검색 결과 기준 한국천문연구원(KASI) OpenAPI 묶음입니다.
- 기본 서버는 `https://apis.data.go.kr/B090041/openapi/service`입니다.
- API별 data.go.kr 활용신청 페이지는 `api_catalog()`가 반환하는 `service_key_url`로
  조회할 수 있습니다.

## 디렉터리 개요

| 경로 | 설명 |
|---|---|
| `src/kasi/` | 라이브러리 소스 — `client.py`, `catalog.py`, `_http.py`, `models.py`, `debug.py`, `parser.py`, `processor.py` |
| `tests/` | 네트워크 없는 단위 테스트, `tests/fixtures/**/*.json` replay test, opt-in live test |
| `debug_ui/` | Streamlit 기반 디버그 웹 UI (optional, 라이브러리 본체와 분리) |
| `docs/` | 설계 결정 기록(`decisions.md`) |

## 문서와 기여 규칙

- 프로젝트 문서는 한글로 작성합니다. 코드 식별자, API 파라미터 이름, URL처럼 원문 표기가
  의미 있는 값만 예외입니다.
- 문서에서 파일 위치를 언급할 때는 `src/kasi/client.py`, `tests/test_live.py`처럼 프로젝트
  루트 기준 상대 경로로 씁니다. 저장소 문서에 로컬 절대 경로를 남기지 않습니다.
- 에이전트와 기여자는 작업 전에 [AGENTS.md](AGENTS.md)를 먼저 확인합니다.
- 구조적 설계 결정을 새로 내리면 [docs/decisions.md](docs/decisions.md)에 항목을 추가합니다.

## 법적 고지

이 저장소의 라이선스(GPL-3.0-or-later, [LICENSE](LICENSE) 참고)는 이 저장소의 코드에만
적용됩니다. 이 라이브러리가 감싸는 공공데이터포털·한국천문연구원의 데이터와 OpenAPI 이용은
각 제공기관의 이용약관과 데이터 이용 조건을 따르며, 이 프로젝트는 해당 데이터의 정확성이나
API의 가용성에 대해 법적 효력을 갖는 어떠한 보증도 하지 않습니다.
