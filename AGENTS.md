# AGENTS.md

## 목표

`python-kasi-api`(GitHub/PyPI 저장소 이름 `python-kasi-api`, Python import 이름 `kasi`)는
공공데이터포털(data.go.kr)이 제공하는 한국천문연구원(KASI) OpenAPI를 감싸는 타입 지정 Python
클라이언트 라이브러리입니다. `KasiClient`/`AsyncKasiClient`가 특일·음양력·출몰시각·태양고도·
월령·천문현상 조회를 typed `Page[T]`로 제공하며, downstream이 직접 소비할 수 있는 안정된
public API를 목표로 합니다.

## Think Before Coding

- 변경 전 `src/kasi/client.py`, `src/kasi/catalog.py`, `src/kasi/_http.py`의 관련 함수를 먼저
  읽고 기존 계약(파라미터 이름, 반환 타입)을 확인할 것.
- 새 endpoint를 추가하기 전 공공데이터포털의 실제 API 명세와 `service_key_param` 대소문자를
  확인할 것.
- 응답 파싱을 바꾸기 전 `tests/fixtures/`의 실제 캡처 응답으로 가정을 검증할 것.

## Simplicity First

- 책임이 얇은 wrapper나 단순 위임용 helper를 새로 만들지 말 것. 필요한 동작은 기존 흐름에
  직접 녹일 것.
- 새 추상화는 중복 제거, 오류 차단, public API 안정화처럼 분명한 책임이 있을 때만 둘 것.

## Surgical Changes

- 버그 수정은 원인이 되는 코드만 건드리고 주변 리팩터링을 곁들이지 말 것.
- `pageNo`/`numOfRows`가 필요 없는 endpoint에 pagination 파라미터를 임의로 추가하지 말 것.
- 검증된 다른 라이브러리의 구현이 문제를 더 직접적으로 해결한다면, 최소수정 원칙에만 묶이지
  말고 라이선스·출처·기존 테스트 기대값을 확인한 뒤 그 방향을 바로 적용할 것.

## Goal-Driven Execution

- 지시 우선순위는 사용자 요청 > 이 `AGENTS.md` > `README.md`/기존 테스트 순입니다.
- 완료 기준은 관련 pytest가 통과하고, 바뀐 공개 동작이 `README.md`와 이 파일에 반영된
  상태입니다.
- 애매한 요구사항은 최소한의, 되돌릴 수 있는 가정으로 진행합니다.

## Practical Bias

- data.go.kr은 HTTP 200으로도 본문 오류를 반환하므로 `response.header.resultCode`를 항상
  확인할 것.
- API별 활용승인은 분리되어 있습니다. 한 키로 일부 KASI API만 성공하고 다른 API가 HTTP 403을
  반환해도 전체 키가 잘못됐다고 단정하지 말 것.
- `items.item`은 단일 dict 또는 list일 수 있으므로 항상 정규화할 것.
- 이 Windows 환경에서 `rg`가 권한 문제로 실패하면 `Get-ChildItem -Recurse -File`과
  `Select-String`으로 우회하고, 한글 문서를 읽을 때는 `Get-Content -Raw -Encoding UTF8`을
  사용할 것.

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성합니다. 공식 API 필드명, 코드 식별자, 명령어,
URL, provider 원문처럼 그대로 보존해야 하는 값만 영어를 유지합니다. 새 문서나 기존 문서를
수정할 때도 이 규칙을 우선합니다.

## 식별자 표

| 항목 | 값 |
|---|---|
| GitHub/PyPI 저장소 이름 | `python-kasi-api` |
| Python import 이름 | `kasi` |
| 데이터 소스 | 한국천문연구원(KASI) OpenAPI, 공공데이터포털(data.go.kr) |
| 기본 서버 | `https://apis.data.go.kr/B090041/openapi/service` |
| 인증 환경변수 | `DATA_GO_KR_SERVICE_KEY` |
| live test 활성화 변수 | `KASI_LIVE=1` |

## 절대 하지 말 것 (DO NOT)

- 실제 `serviceKey`를 출력, 로그, fixture, 문서, 커밋, 요청 context나 예외 metadata에 남기지
  말 것.
- 라이브러리 본체(`src/kasi/`)의 runtime dependency로 Streamlit을 추가하지 말 것 — 디버그
  UI는 `debug-ui` extra로만 분리합니다([D-001](docs/decisions.md)).
- 단순 전달용 wrapper/adapter/gateway나 장기 호환 alias를 만들지 말 것 — downstream(TripMate,
  `python-krtour-map` 등)이 직접 쓸 안정된 public client·typed model·helper를 제공하는 것이
  목표입니다.
- 선행 0이 의미 있는 날짜, 월, 일, 코드 값을 함부로 `int`로 바꾸지 말 것.
- 일반(비-live) 테스트에서 실제 네트워크를 호출하지 말 것 — fake session과 fixture로
  검증합니다.
- `.env`, `.env.local`, 캐시 디렉터리, coverage 산출물을 커밋하지 말 것.

## Module ownership

- `src/kasi/client.py`: 사용자용 `KasiClient`, `AsyncKasiClient`, endpoint namespace,
  `Page[T]` 조립
- `src/kasi/catalog.py`: 함수별 API 카탈로그, 데이터셋명, data.go.kr 활용신청 링크
- `src/kasi/_http.py`: httpx 기반 비동기 HTTP 호출, retry/rate limit, JSON/XML envelope
  정규화, 오류 매핑
- `src/kasi/_convert.py`: 요청 파라미터와 응답 필드 변환 helper
- `src/kasi/debug.py`: `DebugRun`, JSON 직렬화, 민감정보 마스킹, fixture 저장 helper
- `src/kasi/parser.py`: 저장된 raw response body를 함수별 `Page[T]`로 replay 파싱
- `src/kasi/processor.py`: fixture assertion에 사용할 안정적인 processed 결과 생성
- `src/kasi/models.py`: public Pydantic 응답 모델과 row parser
- `src/kasi/exceptions.py`: 예외 계층
- `tests/`: 네트워크 없는 단위 테스트, `tests/fixtures/**/*.json` replay test, opt-in live test
- `examples/streamlit_debug_ui.py`: 별도 Streamlit 앱 — 이 패키지를 wheel/editable install로
  import해서만 사용합니다(라이브러리 본체와 분리)

## Test 기준

- 기본 테스트는 fake session으로 URL, 파라미터, 파싱, 오류 매핑을 검증합니다.
- live test는 `@pytest.mark.live`를 붙이고 `KASI_LIVE=1`과 서비스 키가 있을 때만 실행합니다.
- fixture 저장 전 `input`/`request`/`response`/`parsed`/`processed`에 민감정보 마스킹을
  적용합니다.
- `snapshot`/`schema_only`/`required_fields` assertion mode는 기본 테스트에서 네트워크 없이
  동작해야 합니다.

## 검증

```bash
python -m pytest -q -m "not live"
python -m ruff check .
python -m mypy src/kasi
```

실제 API 검증은 의도적으로 할 때만 실행합니다.

```powershell
$env:KASI_LIVE="1"
python -m pytest -m live -vv
```
