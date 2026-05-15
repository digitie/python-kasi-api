"""kasi가 반환하는 public Pydantic 모델."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ._convert import to_bool_yn, to_float_or_none, to_int_or_none

RawRecord = Mapping[str, Any]
T = TypeVar("T")


class KasiModel(BaseModel):
    """불변 kasi 모델의 기반 클래스."""

    model_config = ConfigDict(frozen=True)


class KasiCallContext(KasiModel):
    """응답을 만든 API 호출 metadata."""

    service_name: str | None = None
    endpoint: str | None = None
    request_method: str | None = None
    request_url: str | None = None
    request_params: RawRecord = Field(default_factory=dict)
    response_status_code: int | None = None
    response_headers: RawRecord = Field(default_factory=dict)
    collected_at: datetime | None = None


class Page(KasiModel, Generic[T]):
    """정규화된 KASI 페이지."""

    items: tuple[T, ...]
    page_no: int | None = None
    num_of_rows: int | None = None
    total_count: int | None = None
    raw: RawRecord = Field(default_factory=dict, repr=False)
    context: KasiCallContext = Field(default_factory=KasiCallContext)

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    @property
    def first(self) -> T | None:
        return self.items[0] if self.items else None

    @property
    def is_empty(self) -> bool:
        return not self.items

    @property
    def has_next_page(self) -> bool:
        if not self.page_no or not self.num_of_rows or self.total_count is None:
            return False
        return self.page_no * self.num_of_rows < self.total_count

    @property
    def next_page_no(self) -> int | None:
        if not self.has_next_page or self.page_no is None:
            return None
        return self.page_no + 1


class SpecialDay(KasiModel):
    """공휴일, 기념일, 24절기, 잡절 같은 특일 record."""

    locdate: str | None
    seq: int | None
    date_kind: str | None
    is_holiday: bool | None
    date_name: str | None
    raw: RawRecord = Field(repr=False)

    @property
    def date(self) -> date | None:
        if not self.locdate or len(self.locdate) != 8 or not self.locdate.isdigit():
            return None
        return date(int(self.locdate[:4]), int(self.locdate[4:6]), int(self.locdate[6:8]))


class LunarSolarDate(KasiModel):
    """음양력 변환 record."""

    sol_year: str | None
    sol_month: str | None
    sol_day: str | None
    sol_week: str | None
    sol_leapyear: str | None
    sol_jd: str | None
    lun_year: str | None
    lun_month: str | None
    lun_day: str | None
    lun_leapmonth: str | None
    lun_nday: int | None
    lun_secha: str | None
    lun_wolgeon: str | None
    lun_iljin: str | None
    raw: RawRecord = Field(repr=False)

    @property
    def solar_date(self) -> date | None:
        if not self.sol_year or not self.sol_month or not self.sol_day:
            return None
        try:
            return date(int(self.sol_year), int(self.sol_month), int(self.sol_day))
        except ValueError:
            return None


class RiseSet(KasiModel):
    """지역 또는 좌표 기준의 해와 달 출몰시각."""

    locdate: str | None
    location: str | None
    longitude: str | None
    latitude: str | None
    longitude_num: float | None = None
    latitude_num: float | None = None
    sunrise: str | None
    suntransit: str | None
    sunset: str | None
    moonrise: str | None
    moontransit: str | None
    moonset: str | None
    civilm: str | None
    civile: str | None
    nautm: str | None
    naute: str | None
    astm: str | None
    aste: str | None
    raw: RawRecord = Field(repr=False)


class SolarAltitude(KasiModel):
    """태양 고도와 방위각 정보."""

    locdate: str | None
    location: str | None
    longitude: str | None
    latitude: str | None
    longitude_num: float | None
    latitude_num: float | None
    azimuth_09: str | None
    altitude_09: str | None
    azimuth_12: str | None
    altitude_12: str | None
    azimuth_15: str | None
    altitude_15: str | None
    azimuth_18: str | None
    altitude_18: str | None
    altitude_meridian: str | None
    raw: RawRecord = Field(repr=False)


class MoonPhase(KasiModel):
    """양력일 기준 월령 정보."""

    sol_year: str | None
    sol_month: str | None
    sol_day: str | None
    lun_age: float | None
    raw: RawRecord = Field(repr=False)


class AstroEvent(KasiModel):
    """천문현상 record."""

    locdate: str | None
    seq: int | None
    astro_title: str | None
    astro_time: str | None
    astro_event: str | None
    remarks: str | None
    raw: RawRecord = Field(repr=False)


class WeekInfo(KasiModel):
    """SolcWeekInfoService_v2의 일요일/요일 조회 record."""

    year: str | None
    month: str | None
    day: str | None
    week: str | None
    raw: RawRecord = Field(repr=False)

    @property
    def locdate(self) -> str | None:
        if not self.year or not self.month or not self.day:
            return None
        return f"{self.year}{self.month}{self.day}"

    @property
    def date(self) -> date | None:
        locdate = self.locdate
        if not locdate:
            return None
        return date(int(locdate[:4]), int(locdate[4:6]), int(locdate[6:8]))


def collected_now() -> datetime:
    return datetime.now(timezone.utc)


def special_day_from_row(row: RawRecord) -> SpecialDay:
    return SpecialDay(
        locdate=_text(row.get("locdate")),
        seq=to_int_or_none(row.get("seq")),
        date_kind=_text(row.get("dateKind")),
        is_holiday=to_bool_yn(row.get("isHoliday")),
        date_name=_text(row.get("dateName")),
        raw=row,
    )


def lunar_solar_from_row(row: RawRecord) -> LunarSolarDate:
    return LunarSolarDate(
        sol_year=_text(row.get("solYear")),
        sol_month=_text(row.get("solMonth")),
        sol_day=_text(row.get("solDay")),
        sol_week=_text(row.get("solWeek")),
        sol_leapyear=_text(row.get("solLeapyear")),
        sol_jd=_text(row.get("solJd")),
        lun_year=_text(row.get("lunYear")),
        lun_month=_text(row.get("lunMonth")),
        lun_day=_text(row.get("lunDay")),
        lun_leapmonth=_text(row.get("lunLeapmonth")),
        lun_nday=to_int_or_none(row.get("lunNday")),
        lun_secha=_text(row.get("lunSecha")),
        lun_wolgeon=_text(row.get("lunWolgeon")),
        lun_iljin=_text(row.get("lunIljin")),
        raw=row,
    )


def rise_set_from_row(row: RawRecord) -> RiseSet:
    return RiseSet(
        locdate=_text(row.get("locdate")),
        location=_text(row.get("location") or row.get("locatiaon")),
        longitude=_text(row.get("longitude")),
        latitude=_text(row.get("latitude")),
        longitude_num=to_float_or_none(row.get("longitudeNum") or row.get("longitude_num")),
        latitude_num=to_float_or_none(row.get("latitudeNum") or row.get("latitude_num")),
        sunrise=_text(row.get("sunrise")),
        suntransit=_text(row.get("suntransit")),
        sunset=_text(row.get("sunset")),
        moonrise=_text(row.get("moonrise")),
        moontransit=_text(row.get("moontransit")),
        moonset=_text(row.get("moonset")),
        civilm=_text(row.get("civilm")),
        civile=_text(row.get("civile")),
        nautm=_text(row.get("nautm")),
        naute=_text(row.get("naute")),
        astm=_text(row.get("astm")),
        aste=_text(row.get("aste")),
        raw=row,
    )


def solar_altitude_from_row(row: RawRecord) -> SolarAltitude:
    return SolarAltitude(
        locdate=_text(row.get("locdate")),
        location=_text(row.get("location")),
        longitude=_text(row.get("longitude")),
        latitude=_text(row.get("latitude")),
        longitude_num=to_float_or_none(row.get("longitude_num") or row.get("longitudeNum")),
        latitude_num=to_float_or_none(row.get("latitude_num") or row.get("latitudeNum")),
        azimuth_09=_text(row.get("azimuth_09") or row.get("azimuth09")),
        altitude_09=_text(row.get("altitude_09") or row.get("altitude09")),
        azimuth_12=_text(row.get("azimuth_12") or row.get("azimuth12")),
        altitude_12=_text(row.get("altitude_12") or row.get("altitude12")),
        azimuth_15=_text(row.get("azimuth_15") or row.get("azimuth15")),
        altitude_15=_text(row.get("altitude_15") or row.get("altitude15")),
        azimuth_18=_text(row.get("azimuth_18") or row.get("azimuth18")),
        altitude_18=_text(row.get("altitude_18") or row.get("altitude18")),
        altitude_meridian=_text(row.get("altitude_meridian") or row.get("altitudeMeridian")),
        raw=row,
    )


def moon_phase_from_row(row: RawRecord) -> MoonPhase:
    return MoonPhase(
        sol_year=_text(row.get("solYear")),
        sol_month=_text(row.get("solMonth")),
        sol_day=_text(row.get("solDay")),
        lun_age=to_float_or_none(row.get("lunAge")),
        raw=row,
    )


def astro_event_from_row(row: RawRecord) -> AstroEvent:
    return AstroEvent(
        locdate=_text(row.get("locdate")),
        seq=to_int_or_none(row.get("seq")),
        astro_title=_text(row.get("astroTitle")),
        astro_time=_text(row.get("astroTime")),
        astro_event=_text(row.get("astroEvent")),
        remarks=_text(row.get("remarks")),
        raw=row,
    )


def week_info_from_row(row: RawRecord) -> WeekInfo:
    return WeekInfo(
        year=_text(row.get("yyyy") or row.get("year")),
        month=_text(row.get("mm") or row.get("month")),
        day=_text(row.get("dd") or row.get("day")),
        week=_text(row.get("week")),
        raw=row,
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
