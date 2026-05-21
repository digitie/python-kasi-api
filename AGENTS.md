# AGENTS.md

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성합니다. 공식 API 필드명, 코드 식별자, 명령어, URL, provider 원문처럼 그대로 보존해야 하는 값만 영어를 유지합니다. 새 문서나 기존 문서를 수정할 때도 이 규칙을 우선합니다.

## 역할

이 문서는 `python-kasi-api`에서 작업하는 에이전트를 위한 운영 가이드입니다. 작업 전에 빠르게 프로젝트 기준, 문서 위치, 반복 실수 방지 규칙을 확인하기 위한 문서입니다.

## 지시 우선순위

1. 사용자 요청
2. 이 `AGENTS.md`
3. `README.md`
4. 기존 코드와 테스트
5. 최소한의 되돌릴 수 있는 가정

문서가 충돌하면 더 높은 우선순위를 따르고, 낮은 우선순위 문서는 함께 갱신합니다.

## 프로젝트 기준

- `python-kasi-api`는 한국천문연구원(KASI) 공공데이터포털 OpenAPI용 비공식 Python 클라이언트입니다.
- Python import 패키지명은 `kasi`입니다.
- 기본 서버는 `https://apis.data.go.kr/B090041/openapi/service`입니다.
- 인증 파라미터는 기본적으로 `serviceKey`입니다. 문서나 게이트웨이가 다른 대소문자를 요구하면 `service_key_param`으로 조정합니다.
- 서비스키는 `api_key`/`service_key` 명시 인자, 환경변수, 로컬 `.env`/`.env.local` 순서로 찾으며 복사/붙여넣기 중 섞인 공백 문자를 제거합니다.
- public 사용 형태는 `python-krheritage-api`처럼 `PROVIDER_NAME`, `client.config`, context manager, `api_key=` 명명 인자를 우선 지원합니다.
- 기본 HTTP transport는 `httpx.AsyncClient` 기반입니다. 동기 `KasiClient`는 비동기 transport를 실행하는 facade이고, async 코드에서는 `AsyncKasiClient`를 사용합니다.
- 기본 응답 형식은 `_type=json`이지만, XML 응답도 같은 `Page[T]` 형태로 정규화해야 합니다.
- 기본 테스트는 실제 네트워크를 호출하지 않습니다. 실제 API 검증은 `@pytest.mark.live`와 `KASI_LIVE=1`로 분리합니다.
- Web UI 연동은 라이브러리 본체에 Streamlit을 넣지 않고, `DebugRun`과 JSON fixture 저장/replay 구조로 지원합니다.
- Python 지원 기준은 3.10 이상입니다.
- 런타임 의존성은 `httpx`, `pydantic`, `python-kraddr-base`입니다.

## Provider API 사용 원칙

- 외부 API 관련 작업은 다른 구현보다 먼저 wrapper/adapter/gateway 지양 원칙을 확인하고 문서/코드에 반영한 뒤 진행합니다.
- downstream이 직접 사용할 안정된 public client, typed model, enum, helper를 제공합니다.
- 단순 전달용 wrapper, 장기 호환 alias, 임시 facade를 만들지 않습니다.
- TripMate나 `python-krtour-map`에서 필요한 endpoint, pagination, cursor, exception, raw payload 계약이 부족하면 이 저장소의 public API를 먼저 안정화합니다.
- 다른 라이브러리에 검증된 구현이 있으면 wrapper로 감싸지 말고 라이선스와 출처를 확인한 뒤 현재 구조에 직접 반영합니다.

## 구현 방향

- 책임이 얇은 wrapper나 단순 위임용 helper를 새로 만드는 일은 지양합니다. 필요한 동작은 기존 흐름에 직접 녹이고, 새 추상화는 중복 제거, 오류 차단, public API 안정화처럼 분명한 책임이 있을 때만 둡니다.
- 검증된 다른 라이브러리의 구현 방식이 문제를 더 직접적으로 해결한다면, 최소수정 원칙에만 묶이지 말고 그 방향을 `kasi` 코드에 바로 적용합니다.
- 외부 라이브러리 구현을 참고하거나 반영할 때는 라이선스 호환성, 출처, public API 영향, 기존 테스트 기대값을 함께 확인합니다.

## 문서 구성

- `README.md`: 사용자용 개요, 설치, 인증, 예제, live test 안내.
- `AGENTS.md`: 작업 라우팅, 모듈 소유권, 반복 실수 방지 규칙.
- `pyproject.toml`: 패키징, 의존성, lint, test, mypy 설정.
- `src/kasi/client.py`: 사용자용 `KasiClient`, `AsyncKasiClient`, endpoint namespace, `Page[T]` 조립.
- `src/kasi/catalog.py`: 함수별 API 카탈로그, 데이터셋명, data.go.kr 활용신청 링크.
- `src/kasi/_http.py`: httpx 기반 비동기 HTTP 호출, retry/rate limit, JSON/XML envelope 정규화, 오류 매핑.
- `src/kasi/_convert.py`: 요청 파라미터와 응답 필드 변환 helper.
- `src/kasi/debug.py`: `DebugRun`, JSON 직렬화, 민감정보 마스킹, fixture 저장 helper.
- `src/kasi/parser.py`: 저장된 raw response body를 함수별 `Page[T]`로 replay 파싱.
- `src/kasi/processor.py`: fixture assertion에 사용할 안정적인 processed 결과 생성.
- `src/kasi/models.py`: public Pydantic 응답 모델과 row parser.
- `src/kasi/exceptions.py`: 예외 계층.
- `tests/`: 네트워크 없는 단위 테스트, `tests/fixtures/**/*.json` replay test, opt-in live test.

## 문서 작성 규칙

- 프로젝트 문서는 한글로 작성합니다.
- 문서에서 파일 위치를 언급할 때는 프로젝트 루트 기준 상대 경로만 씁니다. 예: `src/kasi/client.py`, `tests/test_live.py`.
- 저장소 문서에 로컬 절대 경로를 남기지 않습니다.
- Python 내부 문서, 즉 모듈·클래스·함수·메서드 docstring과 유지보수용 주석은 한글로 작성합니다.
- 코드 식별자, API 파라미터 이름, endpoint 이름, 외부 오류 메시지처럼 원문 자체가 의미 있는 값은 그대로 둡니다.

## 로컬 도구와 인코딩

- 이 Windows 환경에서는 `rg.exe`가 `Access is denied`로 실패할 수 있습니다. 같은 실패를 반복하지 말고 PowerShell 파일 목록으로 우회합니다.
- 파일 목록은 `Get-ChildItem -Recurse -File`을 사용하고, 텍스트 검색은 `Select-String`을 사용합니다.
- 한글 Markdown이나 Python 파일을 PowerShell에서 읽을 때는 기본 출력 인코딩을 믿지 말고 `Get-Content -Raw -Encoding UTF8` 또는 `Get-Content -Encoding UTF8`을 사용합니다.
- 한글이 깨져 보이면 파일이 깨졌다고 판단하기 전에 UTF-8 인코딩을 명시해서 다시 확인합니다.

## 반드시 지킬 것

- 실제 `serviceKey`를 출력, 로그, fixture, 문서, 커밋에 남기지 않습니다.
- `.env`, `.env.local`, 캐시 디렉터리, coverage 산출물은 커밋하지 않습니다.
- data.go.kr은 HTTP 200으로도 본문 오류를 반환하므로 `response.header.resultCode`를 항상 확인합니다.
- API별 활용승인은 분리되어 있습니다. 한 키로 일부 KASI API만 성공하고 다른 API가 HTTP 403을 반환할 수 있습니다.
- `items.item`은 단일 dict 또는 list일 수 있으므로 항상 정규화합니다.
- 선행 0이 의미 있는 날짜, 월, 일, 코드 값은 함부로 `int`로 바꾸지 않습니다.
- 사용자에게 반환하는 안정 필드는 Pydantic 모델로 타입화하고, 원문 응답은 `raw`에 보존합니다.
- 요청 context나 예외 metadata에는 인증키를 포함하지 않습니다.
- `.env` 파일을 읽더라도 값을 출력하지 않고, 테스트 fixture나 문서에 실제 키를 남기지 않습니다.
- fixture 저장 전 `input`, `request`, `response`, `parsed`, `processed`에 민감정보 마스킹을 적용합니다.
- fixture replay 테스트는 저장된 `response.body`만 사용하고 실제 API를 호출하지 않습니다.

## 작업 소유권

### 클라이언트와 namespace

담당 파일:

- `src/kasi/client.py`
- `tests/test_client.py`

확인할 것:

- public helper는 `Page[T]`를 반환합니다.
- async public helper는 `await client.holidays(...)`처럼 같은 이름으로 `Page[T]`를 반환합니다.
- 요청 파라미터 이름은 data.go.kr 명세의 wire name을 유지합니다.
- `pageNo`, `numOfRows`가 필요한 endpoint와 필요 없는 endpoint를 구분합니다.
- `iter_pages()`는 응답 pagination metadata를 기준으로 멈춥니다.

### HTTP와 오류 매핑

담당 파일:

- `src/kasi/_http.py`
- `tests/test_http.py`

확인할 것:

- JSON과 XML envelope를 모두 처리합니다.
- HTTP 401/403은 `KasiAuthError`, 429와 code 22는 `KasiRateLimitError`입니다.
- `OpenAPI_ServiceResponse` 오류 응답도 놓치지 않습니다.
- 오류 메시지와 metadata에서 인증키를 제거합니다.

### 모델과 변환

담당 파일:

- `src/kasi/models.py`
- `src/kasi/_convert.py`

확인할 것:

- 날짜 문자열은 `YYYYMMDD`, 월/일은 `MM`/`DD` 문자열 형태를 보존합니다.
- 숫자로 안정적인 값만 `int` 또는 `float`로 변환합니다.
- `raw`에는 원본 row mapping을 보존합니다.
- API가 오탈자나 대체 필드를 반환하는 경우 parser에서 안전한 fallback을 둡니다.

### 테스트

담당 파일:

- `tests/`

확인할 것:

- 기본 테스트는 fake session으로 URL, 파라미터, 파싱, 오류 매핑을 검증합니다.
- live test는 `KASI_LIVE=1`과 서비스 키가 있을 때만 실행합니다.
- live test 키는 환경변수로만 주입하고 파일에 쓰지 않습니다.
- 실제 API별 활용승인 문제로 403이 날 수 있는 endpoint는 기본 live smoke 범위에 무리하게 넣지 않습니다.

### 디버그와 fixture replay

담당 파일:

- `src/kasi/debug.py`
- `src/kasi/catalog.py`
- `src/kasi/parser.py`
- `src/kasi/processor.py`
- `debug_ui/app.py`
- `tests/runners.py`
- `tests/utils.py`
- `tests/test_generated_fixtures.py`
- `tests/fixtures/`

확인할 것:

- `DebugRun`은 `input`, `request`, `response`, `parsed`, `processed`, `trace`, `error`를 분리해 보존합니다.
- API 선택 UI에는 `api_catalog()`의 사람이 읽기 좋은 데이터셋명과 data.go.kr 활용신청 링크를 표시합니다.
- `request.query`와 예외 metadata에는 인증키가 남지 않아야 합니다.
- fixture 저장기는 같은 파일명을 기본적으로 덮어쓰지 않습니다.
- fixture JSON의 `response.body`는 replay parser가 다시 처리할 수 있는 정규화 body 형태여야 합니다.
- `snapshot`, `schema_only`, `required_fields` assertion mode는 기본 테스트에서 네트워크 없이 동작해야 합니다.
- Streamlit UI나 별도 디버그 앱은 이 패키지를 import해서 사용하되, 이 패키지의 runtime dependency로 Streamlit을 추가하지 않습니다.

## 검증

기본 검증:

```bash
python -m compileall src/kasi tests
python -m pytest
python -m ruff check .
python -m mypy src/kasi
```

실제 API 검증:

```powershell
$env:KASI_LIVE="1"
python -m pytest -m live -vv
```

## 반복 실수 방지

- 이 환경에서 `rg`가 막혀 있으면 바로 PowerShell 파일 목록과 `Select-String`으로 전환합니다.
- PowerShell에서 한글 문서가 깨져 보이면 `Get-Content -Raw -Encoding UTF8`로 다시 읽습니다.
- 문서에 `F:\...` 같은 로컬 절대 경로를 남기지 않습니다.
- Python docstring을 영어로 새로 쓰지 않습니다. 새 내부 문서는 한글로 작성합니다.
- data.go.kr 키를 예제에 실제값으로 넣지 않습니다.
- 어떤 KASI API가 403이라고 해서 전체 키가 잘못됐다고 단정하지 않습니다. API별 활용승인 상태를 먼저 확인합니다.
