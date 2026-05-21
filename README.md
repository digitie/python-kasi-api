# python-kasi-api

`python-kasi-api`는 공공데이터포털(data.go.kr)의 한국천문연구원 OpenAPI를 Python에서 쓰기 위한 비공식 클라이언트입니다. Python 코드에서는 `kasi` 이름으로 import합니다.

`httpx` 기반 비동기 transport, 동기/비동기 클라이언트, 타입화된 Pydantic 응답 모델, fake session 단위 테스트, opt-in live test를 기본 구조로 둡니다. 공통 한국 주소·위치 기반 타입은 `python-kraddr-base` 의존성을 기준으로 둡니다.

## 지원 API

공공데이터포털의 한국천문연구원 검색 결과 기준으로 다음 API 묶음을 다룹니다.

| 영역 | 메서드 |
|---|---|
| 특일 | `holidays`, `national_holidays`, `anniversaries`, `solar_terms_24`, `sundry_days` |
| 음양력 | `solar_to_lunar`, `lunar_to_solar`, `specific_lunar`, `julian_day` |
| 출몰시각 | `area_rise_set`, `location_rise_set` |
| 태양고도 | `area_solar_altitude`, `location_solar_altitude` |
| 월령 | `moon_phase` |
| 천문현상 | `astro_events` |
| 일요일 | `sundays` |

## 설치

```bash
pip install -e ".[dev]"
```

## 인증

data.go.kr decoding 서비스 키를 사용합니다.

```powershell
$env:DATA_GO_KR_SERVICE_KEY="your_decoding_key"
```

`KasiClient()`와 `KasiClient.from_env()`는 `DATA_GO_KR_SERVICE_KEY`를 먼저 보고, 이어서 `DATA_GO_KR_SERVICE_KEY`를 확인합니다.
실제 환경변수가 없으면 현재 작업 디렉터리의 `.env`, `.env.local`도 같은 이름으로 확인합니다. 복사/붙여넣기 과정에서 서비스키 앞뒤나 중간에 들어간 공백, 탭, 줄바꿈은 자동으로 제거합니다.

```dotenv
DATA_GO_KR_SERVICE_KEY=your_decoding_key
```

data.go.kr 활용승인은 API별로 분리되어 있습니다. 한 키가 일부 KASI 서비스는 호출하지만 다른 서비스에서 HTTP 403을 반환할 수 있습니다. 이 경우 해당 API를 data.go.kr에서 추가 활용신청하거나 이미 승인된 키를 사용해야 합니다. 클라이언트는 이 응답을 `KasiAuthError`로 매핑하며, 응답 context에는 인증키를 노출하지 않습니다.

## 사용 예시

```python
from kasi import KasiClient, PROVIDER_NAME

print(PROVIDER_NAME)  # python-kasi-api

with KasiClient() as client:
    print(client.config.base_url)
    holidays = client.holidays(sol_year=2026, sol_month=5)
    for day in holidays:
        print(day.locdate, day.date_name, day.is_holiday)

    converted = client.solar_to_lunar(sol_year=2026, sol_month=5, sol_day=7)
    print(converted.first.lun_year, converted.first.lun_month, converted.first.lun_day)

    sun = client.area_rise_set(locdate="20260507", location="서울")
    print(sun.first.sunrise, sun.first.sunset)
```

`python-krheritage-api`와 같은 형태로 명시 키를 넘길 때는 `api_key=`를 사용합니다. 기존 `service_key=`도 계속 지원합니다.

목록형 응답은 모두 `Page[T]`를 반환합니다.

```python
page.items
page.first
page.total_count
page.context.request_params  # 인증 파라미터는 제거됨
```

비동기 코드에서는 `AsyncKasiClient` 또는 `KasiClient.aio()`를 사용합니다. 내부 HTTP 호출은 `httpx.AsyncClient` 기반이며, retry와 간단한 async token bucket rate limit을 적용합니다.

```python
from kasi import AsyncKasiClient

async with AsyncKasiClient.from_env() as client:
    page = await client.holidays(sol_year=2026, sol_month=5)
    print(page.first)
```

동기 클라이언트에서 바로 비동기 클라이언트를 만들 때는 `KasiClient.aio(api_key=...)`를 사용할 수 있습니다.

## 디버그 실행과 Fixture Replay

`KasiClient`는 Web UI나 로컬 디버그 도구가 바로 사용할 수 있는 `DebugRun`을 반환합니다. 라이브러리 본체는 Streamlit에 의존하지 않고, UI는 wheel 또는 editable install된 `kasi`를 import해서 아래 결과만 표시하거나 저장하면 됩니다.

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

의미 있는 실행 결과는 JSON fixture로 저장할 수 있습니다. `save_fixture()`는 `serviceKey`, `Authorization`, `api_key`, `access_token` 같은 민감 key를 저장 전에 마스킹하고, 같은 파일명은 기본적으로 덮어쓰지 않습니다.

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

저장된 fixture는 `tests/test_generated_fixtures.py`에서 자동으로 읽어 replay 방식으로 검증합니다. 이 테스트는 외부 API를 호출하지 않고, fixture의 `response.body`를 `kasi.parser.parse_function_response()`로 다시 파싱한 뒤 `kasi.processor.process_function_result()` 결과를 fixture의 `processed`와 비교합니다.

지원 assertion mode는 `snapshot`, `schema_only`, `required_fields`이며, `count`는 간단한 결과 개수 비교용으로 사용할 수 있습니다.

## API 카탈로그와 디버그 UI

`api_catalog()`는 지원 API의 함수명, 사람이 읽기 좋은 데이터셋명, data.go.kr 데이터셋 ID, 서비스키 활용신청 링크, 서비스명, operation, 파라미터 metadata를 반환합니다.

```python
from kasi import api_catalog

for entry in api_catalog():
    print(entry.dataset_name, entry.function_name, entry.service_key_url)
```

Streamlit 디버그 UI는 라이브러리 본체와 분리된 `debug_ui/app.py`에 있습니다. 선택한 API의 Debug Trace 탭에는 카탈로그 항목과 서비스키 신청 링크가 함께 표시됩니다.

```bash
pip install -e ".[debug-ui]"
streamlit run debug_ui/app.py
```

## Live Test

live test는 기본적으로 비활성화되어 있습니다.

```powershell
$env:KASI_LIVE="1"
python -m pytest -m live -vv
```

테스트는 `DATA_GO_KR_SERVICE_KEY`를 먼저 사용하고, 없으면 `DATA_GO_KR_SERVICE_KEY`를 확인합니다.

## 문서와 작업 규칙

에이전트와 기여자는 `AGENTS.md`를 먼저 확인합니다.

- 문서의 파일 위치 정보는 `src/kasi/client.py`, `tests/test_live.py`처럼 프로젝트 기준 상대 경로로 씁니다.
- 소스 코드는 `src/kasi/` 아래에 둡니다.
- Python 내부 문서와 유지보수용 주석은 한글로 작성합니다.
- 이 Windows 환경에서 `rg`가 권한 문제로 실패하면 `Get-ChildItem -Recurse -File`과 `Select-String`으로 우회합니다.
- PowerShell에서 한글 문서를 읽을 때는 `Get-Content -Raw -Encoding UTF8`처럼 인코딩을 명시합니다.
