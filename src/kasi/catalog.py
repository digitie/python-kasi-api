"""KASI public helper와 data.go.kr endpoint 대응 카탈로그."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ApiParameter:
    """디버그 UI가 입력 폼을 만들 때 사용할 파라미터 metadata."""

    name: str
    wire_name: str
    label: str
    required: bool = True
    kind: str = "str"
    default: Any | None = None
    description: str | None = None
    choices: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ApiCatalogEntry:
    """라이브러리 함수와 KASI API 항목의 대응 정보."""

    function_name: str
    dataset_name: str
    dataset_id: str
    data_portal_url: str
    service_name: str
    endpoint: str
    response_model: str
    description: str
    category: str
    supports_pagination: bool
    required_params: tuple[ApiParameter, ...]
    optional_params: tuple[ApiParameter, ...] = ()
    method: str = "GET"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["service_key_url"] = self.service_key_url
        data["display_name"] = self.display_name
        return data

    @property
    def display_name(self) -> str:
        """UI 선택 목록에서 쓸 사람이 읽기 좋은 이름입니다."""

        return f"{self.dataset_name} ({self.function_name})"

    @property
    def service_key_url(self) -> str:
        """공공데이터포털 활용신청으로 서비스키를 받을 수 있는 상세 페이지입니다."""

        return self.data_portal_url


def api_catalog() -> tuple[ApiCatalogEntry, ...]:
    """지원하는 KASI API 카탈로그를 사람이 읽기 좋은 데이터셋명과 함께 반환합니다."""

    return _CATALOG


def api_catalog_rows() -> list[dict[str, Any]]:
    """표 표시용으로 평탄화한 API 카탈로그 row를 반환합니다."""

    rows: list[dict[str, Any]] = []
    for entry in _CATALOG:
        rows.append(
            {
                "데이터셋명": entry.dataset_name,
                "데이터셋 ID": entry.dataset_id,
                "함수": entry.function_name,
                "서비스": entry.service_name,
                "오퍼레이션": entry.endpoint,
                "서비스키 신청 링크": entry.service_key_url,
                "분류": entry.category,
                "응답 모델": entry.response_model,
                "페이지네이션": entry.supports_pagination,
                "필수 파라미터": _param_names(entry.required_params),
                "선택 파라미터": _param_names(entry.optional_params),
                "설명": entry.description,
            }
        )
    return rows


def get_api_catalog_entry(function_name: str) -> ApiCatalogEntry:
    """함수 이름에 해당하는 API 카탈로그 항목을 반환합니다."""

    try:
        return _CATALOG_BY_FUNCTION[function_name]
    except KeyError as exc:
        raise ValueError(f"unknown KASI API function: {function_name}") from exc


def _param_names(params: Iterable[ApiParameter]) -> str:
    return ", ".join(param.name for param in params)


_PAGING_PARAMS = (
    ApiParameter("page_no", "pageNo", "페이지 번호", required=False, kind="int", default=1),
    ApiParameter("num_of_rows", "numOfRows", "페이지 크기", required=False, kind="int", default=10),
)
_RESPONSE_FORMAT_PARAM = ApiParameter(
    "response_format",
    "_type",
    "응답 형식",
    required=False,
    kind="choice",
    default="json",
    choices=("json", "xml"),
)
_SOL_YEAR = ApiParameter("sol_year", "solYear", "양력 연도", kind="year")
_SOL_MONTH_OPTIONAL = ApiParameter(
    "sol_month",
    "solMonth",
    "양력 월",
    required=False,
    kind="month",
)
_SOL_MONTH_REQUIRED = ApiParameter("sol_month", "solMonth", "양력 월", kind="month")
_SOL_DAY_OPTIONAL = ApiParameter(
    "sol_day",
    "solDay",
    "양력 일",
    required=False,
    kind="day",
)
_LOCDATE = ApiParameter("locdate", "locdate", "조회일", kind="date", description="YYYYMMDD")
_LOCATION = ApiParameter("location", "location", "지역명")
_LONGITUDE = ApiParameter("longitude", "longitude", "경도")
_LATITUDE = ApiParameter("latitude", "latitude", "위도")
_DN_YN = ApiParameter(
    "dn_yn",
    "dnYn",
    "좌표 형식",
    required=False,
    kind="choice",
    choices=("Y", "N"),
    description="Y: 도 단위 소수, N: 도분 형식",
)

_DATA_PORTAL_BASE = "https://www.data.go.kr/data/{dataset_id}/openapi.do"
_SPCDE_DATASET_ID = "15012690"
_LRSR_DATASET_ID = "15012679"
_RISE_SET_DATASET_ID = "15012688"
_SOLAR_ALTITUDE_DATASET_ID = "15012692"
_MOON_PHASE_DATASET_ID = "15012689"
_ASTRO_EVENT_DATASET_ID = "15012691"
_SUNDAY_DATASET_ID = "15125130"


def _data_portal_url(dataset_id: str) -> str:
    return _DATA_PORTAL_BASE.format(dataset_id=dataset_id)


_CATALOG = (
    ApiCatalogEntry(
        function_name="holidays",
        dataset_name="한국천문연구원 특일 정보 - 공휴일",
        dataset_id=_SPCDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SPCDE_DATASET_ID),
        service_name="SpcdeInfoService",
        endpoint="getRestDeInfo",
        response_model="Page[SpecialDay]",
        description="양력 연월 기준 공휴일 정보를 조회합니다.",
        category="특일",
        supports_pagination=True,
        required_params=(_SOL_YEAR,),
        optional_params=(_SOL_MONTH_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="national_holidays",
        dataset_name="한국천문연구원 특일 정보 - 국경일",
        dataset_id=_SPCDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SPCDE_DATASET_ID),
        service_name="SpcdeInfoService",
        endpoint="getHoliDeInfo",
        response_model="Page[SpecialDay]",
        description="양력 연월 기준 국경일 정보를 조회합니다.",
        category="특일",
        supports_pagination=True,
        required_params=(_SOL_YEAR,),
        optional_params=(_SOL_MONTH_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="anniversaries",
        dataset_name="한국천문연구원 특일 정보 - 기념일",
        dataset_id=_SPCDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SPCDE_DATASET_ID),
        service_name="SpcdeInfoService",
        endpoint="getAnniversaryInfo",
        response_model="Page[SpecialDay]",
        description="양력 연월 기준 기념일 정보를 조회합니다.",
        category="특일",
        supports_pagination=True,
        required_params=(_SOL_YEAR,),
        optional_params=(_SOL_MONTH_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="solar_terms_24",
        dataset_name="한국천문연구원 특일 정보 - 24절기",
        dataset_id=_SPCDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SPCDE_DATASET_ID),
        service_name="SpcdeInfoService",
        endpoint="get24DivisionsInfo",
        response_model="Page[SpecialDay]",
        description="양력 연월 기준 24절기 정보를 조회합니다.",
        category="특일",
        supports_pagination=True,
        required_params=(_SOL_YEAR,),
        optional_params=(_SOL_MONTH_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="sundry_days",
        dataset_name="한국천문연구원 특일 정보 - 잡절",
        dataset_id=_SPCDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SPCDE_DATASET_ID),
        service_name="SpcdeInfoService",
        endpoint="getSundryDayInfo",
        response_model="Page[SpecialDay]",
        description="양력 연월 기준 잡절 정보를 조회합니다.",
        category="특일",
        supports_pagination=True,
        required_params=(_SOL_YEAR,),
        optional_params=(_SOL_MONTH_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="solar_to_lunar",
        dataset_name="한국천문연구원 음양력 변환 - 양력에서 음력",
        dataset_id=_LRSR_DATASET_ID,
        data_portal_url=_data_portal_url(_LRSR_DATASET_ID),
        service_name="LrsrCldInfoService",
        endpoint="getLunCalInfo",
        response_model="Page[LunarSolarDate]",
        description="양력일을 음력일로 변환합니다.",
        category="음양력",
        supports_pagination=True,
        required_params=(_SOL_YEAR, _SOL_MONTH_REQUIRED),
        optional_params=(_SOL_DAY_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="lunar_to_solar",
        dataset_name="한국천문연구원 음양력 변환 - 음력에서 양력",
        dataset_id=_LRSR_DATASET_ID,
        data_portal_url=_data_portal_url(_LRSR_DATASET_ID),
        service_name="LrsrCldInfoService",
        endpoint="getSolCalInfo",
        response_model="Page[LunarSolarDate]",
        description="음력일을 양력일로 변환합니다.",
        category="음양력",
        supports_pagination=True,
        required_params=(
            ApiParameter("lun_year", "lunYear", "음력 연도", kind="year"),
            ApiParameter("lun_month", "lunMonth", "음력 월", kind="month"),
        ),
        optional_params=(
            ApiParameter("lun_day", "lunDay", "음력 일", required=False, kind="day"),
            *_PAGING_PARAMS,
            _RESPONSE_FORMAT_PARAM,
        ),
    ),
    ApiCatalogEntry(
        function_name="specific_lunar",
        dataset_name="한국천문연구원 음양력 변환 - 특정 음력일",
        dataset_id=_LRSR_DATASET_ID,
        data_portal_url=_data_portal_url(_LRSR_DATASET_ID),
        service_name="LrsrCldInfoService",
        endpoint="getSpcifyLunCalInfo",
        response_model="Page[LunarSolarDate]",
        description="양력 연도 범위에서 특정 음력 월일에 해당하는 날짜를 조회합니다.",
        category="음양력",
        supports_pagination=True,
        required_params=(
            ApiParameter("from_sol_year", "fromSolYear", "시작 양력 연도", kind="year"),
            ApiParameter("to_sol_year", "toSolYear", "종료 양력 연도", kind="year"),
            ApiParameter("lun_month", "lunMonth", "음력 월", kind="month"),
            ApiParameter("lun_day", "lunDay", "음력 일", kind="day"),
            ApiParameter(
                "leap_month",
                "leapMonth",
                "윤달 여부",
                kind="choice",
                choices=("평", "윤"),
            ),
        ),
        optional_params=(*_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="julian_day",
        dataset_name="한국천문연구원 음양력 변환 - 율리우스일",
        dataset_id=_LRSR_DATASET_ID,
        data_portal_url=_data_portal_url(_LRSR_DATASET_ID),
        service_name="LrsrCldInfoService",
        endpoint="getJulDayInfo",
        response_model="Page[LunarSolarDate]",
        description="율리우스일 기준 음양력 정보를 조회합니다.",
        category="음양력",
        supports_pagination=False,
        required_params=(ApiParameter("sol_jd", "solJd", "율리우스일"),),
        optional_params=(_RESPONSE_FORMAT_PARAM,),
    ),
    ApiCatalogEntry(
        function_name="area_rise_set",
        dataset_name="한국천문연구원 출몰시각 정보 - 지역별",
        dataset_id=_RISE_SET_DATASET_ID,
        data_portal_url=_data_portal_url(_RISE_SET_DATASET_ID),
        service_name="RiseSetInfoService",
        endpoint="getAreaRiseSetInfo",
        response_model="Page[RiseSet]",
        description="지역명과 날짜 기준 해와 달의 출몰시각을 조회합니다.",
        category="출몰시각",
        supports_pagination=False,
        required_params=(_LOCDATE, _LOCATION),
        optional_params=(_RESPONSE_FORMAT_PARAM,),
    ),
    ApiCatalogEntry(
        function_name="location_rise_set",
        dataset_name="한국천문연구원 출몰시각 정보 - 좌표별",
        dataset_id=_RISE_SET_DATASET_ID,
        data_portal_url=_data_portal_url(_RISE_SET_DATASET_ID),
        service_name="RiseSetInfoService",
        endpoint="getLCRiseSetInfo",
        response_model="Page[RiseSet]",
        description="좌표와 날짜 기준 해와 달의 출몰시각을 조회합니다.",
        category="출몰시각",
        supports_pagination=False,
        required_params=(_LOCDATE, _LONGITUDE, _LATITUDE),
        optional_params=(_DN_YN, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="area_solar_altitude",
        dataset_name="한국천문연구원 태양고도 정보 - 지역별",
        dataset_id=_SOLAR_ALTITUDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SOLAR_ALTITUDE_DATASET_ID),
        service_name="SrAltudeInfoService",
        endpoint="getAreaSrAltudeInfo",
        response_model="Page[SolarAltitude]",
        description="지역명과 날짜 기준 태양 고도와 방위각 정보를 조회합니다.",
        category="태양고도",
        supports_pagination=False,
        required_params=(_LOCDATE, _LOCATION),
        optional_params=(_RESPONSE_FORMAT_PARAM,),
    ),
    ApiCatalogEntry(
        function_name="location_solar_altitude",
        dataset_name="한국천문연구원 태양고도 정보 - 좌표별",
        dataset_id=_SOLAR_ALTITUDE_DATASET_ID,
        data_portal_url=_data_portal_url(_SOLAR_ALTITUDE_DATASET_ID),
        service_name="SrAltudeInfoService",
        endpoint="getLCSrAltudeInfo",
        response_model="Page[SolarAltitude]",
        description="좌표와 날짜 기준 태양 고도와 방위각 정보를 조회합니다.",
        category="태양고도",
        supports_pagination=False,
        required_params=(_LOCDATE, _LONGITUDE, _LATITUDE),
        optional_params=(_DN_YN, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="moon_phase",
        dataset_name="한국천문연구원 월령 정보",
        dataset_id=_MOON_PHASE_DATASET_ID,
        data_portal_url=_data_portal_url(_MOON_PHASE_DATASET_ID),
        service_name="LunPhInfoService",
        endpoint="getLunPhInfo",
        response_model="Page[MoonPhase]",
        description="양력일 기준 월령 정보를 조회합니다.",
        category="월령",
        supports_pagination=True,
        required_params=(_SOL_YEAR, _SOL_MONTH_REQUIRED),
        optional_params=(_SOL_DAY_OPTIONAL, *_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="astro_events",
        dataset_name="한국천문연구원 천문현상 정보",
        dataset_id=_ASTRO_EVENT_DATASET_ID,
        data_portal_url=_data_portal_url(_ASTRO_EVENT_DATASET_ID),
        service_name="AstroEventInfoService",
        endpoint="getAstroEventInfo",
        response_model="Page[AstroEvent]",
        description="양력 연월 기준 천문현상 정보를 조회합니다.",
        category="천문현상",
        supports_pagination=True,
        required_params=(_SOL_YEAR, _SOL_MONTH_REQUIRED),
        optional_params=(*_PAGING_PARAMS, _RESPONSE_FORMAT_PARAM),
    ),
    ApiCatalogEntry(
        function_name="sundays",
        dataset_name="한국천문연구원 일요일/요일 정보",
        dataset_id=_SUNDAY_DATASET_ID,
        data_portal_url=_data_portal_url(_SUNDAY_DATASET_ID),
        service_name="SolcWeekInfoService_v2",
        endpoint="getWeekInfo_v2",
        response_model="Page[WeekInfo]",
        description="양력 연월 기준 일요일과 요일 정보를 조회합니다.",
        category="일요일",
        supports_pagination=False,
        required_params=(_SOL_YEAR,),
        optional_params=(_SOL_MONTH_OPTIONAL, _RESPONSE_FORMAT_PARAM),
    ),
)
_CATALOG_BY_FUNCTION = {entry.function_name: entry for entry in _CATALOG}


__all__ = [
    "ApiCatalogEntry",
    "ApiParameter",
    "api_catalog",
    "api_catalog_rows",
    "get_api_catalog_entry",
]
