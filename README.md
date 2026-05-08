# pykasi

`pykasi`는 공공데이터포털(data.go.kr)의 한국천문연구원 OpenAPI를 Python에서 쓰기 위한 비공식 클라이언트입니다.

인접한 `pykma`, `pykrtourapi`, `pyopinet`, `pykex` 프로젝트와 같은 형태를 따릅니다. 작은 `requests` transport, 타입화된 Pydantic 응답 모델, fake session 단위 테스트, opt-in live test를 기본 구조로 둡니다.

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
$env:KASI_SERVICE_KEY="your_decoding_key"
```

`KasiClient.from_env()`는 `KASI_SERVICE_KEY`를 먼저 보고, 이어서 `TRIPMATE_DATA_GO_SERVICE_KEY`, `DATA_GO_SERVICE_KEY`, `DATAGOKR_SERVICE_KEY`를 확인합니다.

data.go.kr 활용승인은 API별로 분리되어 있습니다. 한 키가 일부 KASI 서비스는 호출하지만 다른 서비스에서 HTTP 403을 반환할 수 있습니다. 이 경우 해당 API를 data.go.kr에서 추가 활용신청하거나 이미 승인된 키를 사용해야 합니다. 클라이언트는 이 응답을 `KasiAuthError`로 매핑하며, 응답 context에는 인증키를 노출하지 않습니다.

## 사용 예시

```python
from pykasi import KasiClient

client = KasiClient.from_env()

holidays = client.holidays(sol_year=2026, sol_month=5)
for day in holidays:
    print(day.locdate, day.date_name, day.is_holiday)

converted = client.solar_to_lunar(sol_year=2026, sol_month=5, sol_day=7)
print(converted.first.lun_year, converted.first.lun_month, converted.first.lun_day)

sun = client.area_rise_set(locdate="20260507", location="서울")
print(sun.first.sunrise, sun.first.sunset)
```

목록형 응답은 모두 `Page[T]`를 반환합니다.

```python
page.items
page.first
page.total_count
page.context.request_params  # 인증 파라미터는 제거됨
```

## Live Test

live test는 기본적으로 비활성화되어 있습니다.

```powershell
$env:KASI_LIVE="1"
python -m pytest -m live -vv
```

테스트는 `KASI_SERVICE_KEY`를 먼저 사용하고, 없으면 TripMate의 `TRIPMATE_DATA_GO_SERVICE_KEY`를 확인합니다.

인접 workspace의 TripMate 키로는 승인된 KASI 서비스인 특일, 음양력 변환, 출몰시각에 대해 live check를 수행했습니다.

## 문서와 작업 규칙

에이전트와 기여자는 `AGENTS.md`를 먼저 확인합니다.

- 문서의 파일 위치 정보는 `pykasi/client.py`, `tests/test_live.py`처럼 프로젝트 기준 상대 경로로 씁니다.
- Python 내부 문서와 유지보수용 주석은 한글로 작성합니다.
- 이 Windows 환경에서 `rg`가 권한 문제로 실패하면 `Get-ChildItem -Recurse -File`과 `Select-String`으로 우회합니다.
- PowerShell에서 한글 문서를 읽을 때는 `Get-Content -Raw -Encoding UTF8`처럼 인코딩을 명시합니다.
