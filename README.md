# pykasi

`pykasi` is an unofficial Python client for Korea Astronomy and Space Science
Institute OpenAPIs on data.go.kr.

It follows the same shape as nearby `pykma`, `pykrtourapi`, `pyopinet`, and
`pykex` projects: a small `requests` transport, typed Pydantic response models,
fake-session unit tests, and opt-in live tests.

## Covered APIs

The data.go.kr search result for 한국천문연구원 lists these KASI APIs:

| Area | Methods |
|---|---|
| Special days | `holidays`, `national_holidays`, `anniversaries`, `solar_terms_24`, `sundry_days` |
| Lunar/solar calendar | `solar_to_lunar`, `lunar_to_solar`, `specific_lunar`, `julian_day` |
| Rise/set times | `area_rise_set`, `location_rise_set` |
| Solar altitude | `area_solar_altitude`, `location_solar_altitude` |
| Moon phase | `moon_phase` |
| Astronomical events | `astro_events` |
| Sundays | `sundays` |

## Install

```bash
pip install -e ".[dev]"
```

## Authentication

Use a data.go.kr decoding service key.

```powershell
$env:KASI_SERVICE_KEY="your_decoding_key"
```

`KasiClient.from_env()` also checks `TRIPMATE_DATA_GO_SERVICE_KEY`,
`DATA_GO_SERVICE_KEY`, and `DATAGOKR_SERVICE_KEY`.

data.go.kr approvals are API-specific. If a key can call one KASI service but
another service returns HTTP 403, apply for that API on data.go.kr or use a key
that already has approval. The client maps that response to `KasiAuthError`
without exposing the key in response context.

## Usage

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

Every list-style response returns `Page[T]`:

```python
page.items
page.first
page.total_count
page.context.request_params  # credentials are removed
```

## Live Tests

Live tests are disabled by default.

```powershell
$env:KASI_LIVE="1"
python -m pytest -m live -vv
```

The tests will use `KASI_SERVICE_KEY` first, then the TripMate
`TRIPMATE_DATA_GO_SERVICE_KEY` if it exists.

The TripMate key in the adjacent workspace was live-checked against the approved
KASI services for special days, lunar/solar conversion, and rise/set times.
