"""Streamlit 기반 KASI API 디버그 카탈로그 뷰어."""
# ruff: noqa: E402,I001

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
for module_name, module in list(sys.modules.items()):
    if module_name != "kasi" and not module_name.startswith("kasi."):
        continue
    module_file = getattr(module, "__file__", None)
    if module_file is not None and not Path(module_file).resolve().is_relative_to(SRC):
        del sys.modules[module_name]

try:
    import pandas as pd
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - 선택 실행 도구
    raise SystemExit('Streamlit UI를 쓰려면 `pip install -e ".[debug-ui]"`를 실행하세요.') from exc

from kasi import (
    ApiCatalogEntry,
    ApiParameter,
    DebugRun,
    KasiClient,
    api_catalog,
    api_catalog_rows,
    build_error,
    jsonable,
    normalize_service_key,
    redact_sensitive,
    save_fixture,
)

DATA_SOURCE_LABEL = "KASI (data.go.kr)"
ENV_VAR_NAME = "DATA_GO_KR_SERVICE_KEY"
SERVICE_KEY_PARAM = "serviceKey"
DEFAULT_EXCLUDE_FIELDS = ("fetched_at", "request_id", "updated_at", "collected_at")
PAGING_PARAM_NAMES = {"page_no", "num_of_rows"}


def main() -> None:
    st.set_page_config(page_title="python-kasi-api debug", layout="wide")
    st.title("python-kasi-api debug")

    # 1. Data source — kasi는 data.go.kr KASI 묶음 하나만 다루므로 카탈로그가 50개 미만이면
    #    Category 단계 없이 API 선택으로 바로 이어진다.
    st.sidebar.selectbox("Data source", [DATA_SOURCE_LABEL])

    catalog = api_catalog()
    labels = [entry.display_name for entry in catalog]
    selected_label = st.sidebar.selectbox("API", labels)
    selected = catalog[labels.index(selected_label)]

    # 2. 선택한 API 설명 (무엇을 하는지 + 어떤 데이터를 반환하는지, 2줄)
    st.sidebar.caption(selected.description)
    st.sidebar.caption(
        f"반환: {selected.response_model} ({selected.service_name}/{selected.endpoint})"
    )

    # 3. Environment
    env_sources = _env_key_sources()
    st.sidebar.subheader("Environment")
    if env_sources:
        environment = st.sidebar.radio("Environment", ["env", "manual"], horizontal=True)
        if environment == "env":
            source_info = env_sources[0]
            st.sidebar.caption(f"{ENV_VAR_NAME} 값을 사용합니다 (source: {source_info['source']}).")
        else:
            st.sidebar.caption("아래 수동 입력값을 사용합니다.")
    else:
        environment = "manual"
        st.sidebar.caption(f"{ENV_VAR_NAME} 환경변수가 없어 수동 입력을 사용합니다.")

    # 4. Auth — 실제 요청 쿼리 파라미터명(serviceKey) 그대로 사용
    st.sidebar.subheader("Auth")
    if environment == "env":
        manual_key = ""
        st.sidebar.caption(f"환경변수 {ENV_VAR_NAME}에서 자동으로 읽습니다.")
    else:
        manual_key = st.sidebar.text_input(
            SERVICE_KEY_PARAM,
            value="",
            type="password",
            placeholder="직접 입력",
            help=f"data.go.kr 서비스 키를 `{SERVICE_KEY_PARAM}` 쿼리 파라미터로 사용합니다. "
            f"env: {ENV_VAR_NAME}",
        )

    # 5. 서비스키 발급 링크
    st.sidebar.link_button("서비스키 발급/확인", selected.service_key_url)

    # 6. Timeout
    timeout = st.sidebar.number_input(
        "Timeout",
        min_value=1.0,
        max_value=120.0,
        value=10.0,
        step=1.0,
        help="API 요청 timeout seconds입니다.",
    )

    # 7. Fixture 저장 기준 디렉터리
    fixture_base_dir = _fixture_base_dir_sidebar()

    tabs = st.tabs(
        [
            "Raw Response",
            "Pydantic Model",
            "Processed Result",
            "Validation Errors",
            "Debug Trace",
            "Fixture / Testcase",
        ]
    )

    with tabs[0]:
        _raw_response_tab(selected, manual_key, environment=environment, timeout=float(timeout))
    with tabs[1]:
        _pydantic_model_tab(selected)
    with tabs[2]:
        _processed_result_tab(selected)
    with tabs[3]:
        _validation_errors_tab(selected)
    with tabs[4]:
        _debug_trace_tab(selected)
    with tabs[5]:
        _fixture_tab(selected, fixture_base_dir)


def _raw_response_tab(
    selected: ApiCatalogEntry,
    manual_key: str,
    *,
    environment: str,
    timeout: float,
) -> None:
    st.subheader(selected.dataset_name)
    st.caption(f"{selected.service_name}/{selected.endpoint} -> {selected.function_name}()")

    submitted, params, missing = _request_form(selected)

    if not submitted:
        st.caption("필수 파라미터를 채우고 Run을 누르면 여기에 raw response가 표시됩니다.")
        return
    if missing:
        st.error("필수 파라미터가 비어 있어 실행하지 않았습니다: " + ", ".join(missing))
        return

    run = _execute(
        selected, params, manual_key=manual_key, environment=environment, timeout=timeout
    )
    _store_run(selected, run)

    if run.error:
        st.error(run.error["message"])
    st.json(jsonable(run.response))


def _execute(
    selected: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    manual_key: str,
    environment: str,
    timeout: float,
) -> DebugRun:
    """실제 API 호출을 수행하고 항상 `DebugRun`을 돌려준다(예외를 st.error 한 줄로 뭉개지 않음)."""

    trace = [f"함수 선택: {selected.function_name}"]
    client: KasiClient | None = None
    try:
        if environment == "env":
            client = KasiClient(timeout=timeout)
            trace.append(f"{ENV_VAR_NAME} 환경변수로 클라이언트 생성")
        else:
            client = KasiClient(service_key=normalize_service_key(manual_key), timeout=timeout)
            trace.append("수동 입력 serviceKey로 클라이언트 생성")
        return client.debug(selected.function_name, **params)
    except Exception as exc:
        trace.append(f"실행 실패: {exc.__class__.__name__}")
        return DebugRun(
            function=selected.function_name,
            input=redact_sensitive(params),
            request={},
            response={},
            parsed=None,
            processed=None,
            trace=trace,
            error=build_error(exc),
            catalog=selected.to_dict(),
        )
    finally:
        if client is not None:
            client.close()


def _request_form(selected: ApiCatalogEntry) -> tuple[bool, dict[str, Any], list[str]]:
    required = list(selected.required_params)
    optional = [p for p in selected.optional_params if p.name not in PAGING_PARAM_NAMES]
    paging = [p for p in selected.optional_params if p.name in PAGING_PARAM_NAMES]
    key_prefix = selected.function_name

    with st.form(f"request-form:{key_prefix}"):
        st.subheader("Required parameters")
        if required:
            required_values = _render_param_grid(required, key_prefix=key_prefix)
        else:
            st.caption("이 API에는 필수 파라미터가 없습니다.")
            required_values = {}

        if optional:
            st.subheader("Optional parameters")
            optional_values = _render_param_grid(optional, key_prefix=key_prefix)
        else:
            optional_values = {}

        paging_values: dict[str, Any] = {}
        if selected.supports_pagination and paging:
            st.subheader("Paging")
            st.caption("supports_pagination=True — pageNo/numOfRows를 지원하는 API입니다.")
            paging_values = _render_param_grid(paging, key_prefix=key_prefix)

        submitted = st.form_submit_button("Run")

    values = {**required_values, **optional_values, **paging_values}
    params, missing = _finalize_params(required, values)
    return submitted, params, missing


def _finalize_params(
    required: list[ApiParameter],
    values: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    required_names = {param.name for param in required}
    missing: list[str] = []
    params: dict[str, Any] = {}
    for name, value in values.items():
        if isinstance(value, str):
            text = value.strip()
            if not text:
                if name in required_names:
                    missing.append(name)
                continue
            params[name] = text
        else:
            params[name] = value
    return params, missing


def _render_param_grid(params: list[ApiParameter], *, key_prefix: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for index in range(0, len(params), 2):
        columns = st.columns(2)
        for column, param in zip(columns, params[index : index + 2], strict=False):
            with column:
                values[param.name] = _param_widget(param, key_prefix=key_prefix)
    return values


def _param_widget(param: ApiParameter, *, key_prefix: str) -> Any:
    label = f"{param.label} ({param.name})"
    widget_key = f"{key_prefix}:param:{param.name}"
    help_text = param.description or None

    if param.kind == "int":
        default_value = param.default if isinstance(param.default, int) else 1
        return st.number_input(
            label,
            min_value=1,
            value=int(default_value),
            step=1,
            help=help_text,
            key=widget_key,
        )

    if param.kind == "choice":
        options = list(param.choices)
        if not param.required:
            options = ["", *options]
        default = param.default if param.default in options else (options[0] if options else "")
        return st.selectbox(
            label,
            options,
            index=options.index(default),
            help=help_text,
            key=widget_key,
        )

    return st.text_input(
        label,
        value=_default_text(param),
        placeholder=param.description or _kind_placeholder(param.kind),
        help=help_text,
        key=widget_key,
    )


def _default_text(param: ApiParameter) -> str:
    if param.default is not None:
        return str(param.default)
    if not param.required:
        return ""
    today = date.today()
    if param.kind == "date":
        return today.strftime("%Y%m%d")
    if param.kind == "year":
        return f"{today.year}"
    if param.kind == "month":
        return f"{today.month:02d}"
    if param.kind == "day":
        return f"{today.day:02d}"
    return ""


def _kind_placeholder(kind: str) -> str:
    return {"date": "YYYYMMDD", "year": "YYYY", "month": "MM", "day": "DD"}.get(kind, "")


def _pydantic_model_tab(selected: ApiCatalogEntry) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("Raw Response 탭에서 선택한 API를 실행하면 여기에서 Pydantic 모델을 확인합니다.")
        return
    if run.error:
        st.warning("실행 중 오류가 있었습니다. Validation Errors 탭을 확인하세요.")
    if run.parsed is None:
        st.info("표시할 Pydantic 모델이 없습니다.")
        return
    st.caption(selected.response_model)
    st.json(jsonable(run.parsed))


def _processed_result_tab(selected: ApiCatalogEntry) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("Raw Response 탭에서 API를 실행하면 처리된 결과를 표시합니다.")
        return
    processed = jsonable(run.processed)
    rows = processed.get("items") if isinstance(processed, dict) else None
    if isinstance(rows, list) and rows:
        st.dataframe(pd.json_normalize(rows, sep="."), width="stretch", hide_index=True)
        return
    if processed:
        st.json(processed)
        return
    st.info("표시할 처리 결과가 없습니다.")


def _validation_errors_tab(selected: ApiCatalogEntry) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("아직 실행된 API가 없습니다.")
        return
    if not run.error:
        st.success("현재 실행 결과에서 validation error가 없습니다.")
        return
    st.error(run.error["message"])
    st.json(run.error)


def _debug_trace_tab(selected: ApiCatalogEntry) -> None:
    st.subheader("Catalog")
    st.dataframe(api_catalog_rows(), width="stretch", hide_index=True)

    st.subheader("Selected API")
    st.json(selected.to_dict())
    st.link_button("서비스키 발급/확인", selected.service_key_url)
    st.caption(f"credential env: {ENV_VAR_NAME}")

    run = _current_run(selected)
    if run is None:
        st.info("아직 실행된 API가 없습니다.")
        return

    st.divider()
    st.subheader("Trace")
    st.code("\n".join(run.trace), language="text")

    st.subheader("Request")
    st.json(jsonable(run.request))

    st.subheader("Response")
    response = jsonable(run.response)
    if isinstance(response, dict):
        st.caption(f"status_code: {response.get('status_code')}")
    st.json(response)


def _fixture_tab(selected: ApiCatalogEntry, fixture_base_dir: str) -> None:
    run = _current_run(selected)
    st.caption("Fixture base dir")
    st.code(fixture_base_dir, language=None)
    if run is None:
        st.info("Raw Response 탭에서 API를 실행한 뒤 fixture를 저장할 수 있습니다.")
        return

    key_prefix = f"fixture:{selected.function_name}"
    case_name = st.text_input(
        "Case name", value=f"{selected.function_name}_case", key=f"{key_prefix}:case_name"
    )
    description = st.text_area(
        "Description",
        value=f"{selected.dataset_name} 실행 결과",
        key=f"{key_prefix}:description",
    )
    assertion_mode = st.selectbox(
        "Assertion mode",
        ["snapshot", "schema_only", "required_fields"],
        key=f"{key_prefix}:assertion_mode",
    )
    exclude_fields_raw = st.text_input(
        "Exclude fields",
        value=", ".join(DEFAULT_EXCLUDE_FIELDS),
        key=f"{key_prefix}:exclude_fields",
    )
    required_fields_raw = st.text_input(
        "Required fields", value="", key=f"{key_prefix}:required_fields"
    )
    overwrite = st.checkbox(
        "Overwrite existing fixture", value=False, key=f"{key_prefix}:overwrite"
    )

    assertion = {
        "mode": assertion_mode,
        "exclude_fields": [v.strip() for v in exclude_fields_raw.split(",") if v.strip()],
        "required_fields": [v.strip() for v in required_fields_raw.split(",") if v.strip()],
    }

    st.subheader("Fixture preview")
    st.json(
        {
            "function": run.function,
            "description": description,
            "input": jsonable(run.input),
            "request": jsonable(run.request),
            "response": jsonable(run.response),
            "processed": jsonable(run.processed),
            "assertion": assertion,
        }
    )

    if st.button("Save as fixture", key=f"{key_prefix}:save"):
        try:
            path = save_fixture(
                base_dir=fixture_base_dir,
                function_name=run.function,
                case_name=case_name,
                description=description,
                input_data=run.input,
                request_data=run.request,
                response_data=run.response,
                parsed_result=run.parsed,
                processed_result=run.processed,
                assertion=assertion,
                overwrite=overwrite,
            )
        except Exception as exc:  # pragma: no cover - UI 표시
            error = build_error(exc)
            st.error(error["message"])
            st.json(error)
        else:
            st.success(f"Saved: {path}")


def _store_run(selected: ApiCatalogEntry, run: DebugRun) -> None:
    st.session_state["last_run"] = {"selection_key": _selection_key(selected), "run": run}


def _current_run(selected: ApiCatalogEntry) -> DebugRun | None:
    stored = st.session_state.get("last_run")
    if not isinstance(stored, dict):
        return None
    if stored.get("selection_key") != _selection_key(selected):
        return None
    run = stored.get("run")
    return run if isinstance(run, DebugRun) else None


def _selection_key(selected: ApiCatalogEntry) -> str:
    return f"{DATA_SOURCE_LABEL}:{selected.function_name}"


def _env_key_sources() -> list[dict[str, str]]:
    value = normalize_service_key(os.getenv(ENV_VAR_NAME))
    if value:
        return [{"name": ENV_VAR_NAME, "source": "process env"}]
    dotenv_value = normalize_service_key(_read_local_dotenv().get(ENV_VAR_NAME))
    if dotenv_value:
        return [{"name": ENV_VAR_NAME, "source": ".env"}]
    return []


def _read_local_dotenv() -> dict[str, str]:
    """`.env`/`.env.local`을 가볍게 읽어 Environment 캡션 표시용으로만 사용한다.

    실제 인증값 해석은 `KasiClient` 내부 로직이 그대로 담당하며, 이 함수는 사이드바에
    "어느 env를 쓰는지" 보여주기 위한 표시 전용 helper다.
    """

    values: dict[str, str] = {}
    for name in (".env", ".env.local"):
        path = ROOT / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, _, raw_value = text.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export ") :].strip()
            raw_value = raw_value.strip()
            if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'}:
                raw_value = raw_value[1:-1]
            if key:
                values[key] = raw_value
    return values


def _fixture_base_dir_sidebar() -> str:
    st.sidebar.subheader("Fixtures")
    candidates = _fixture_dir_candidates()
    options = [str(path) for path in candidates]
    custom_label = "Custom..."
    selected = st.sidebar.selectbox("Fixture base dir", [*options, custom_label])
    if selected == custom_label:
        selected = st.sidebar.text_input(
            "Custom fixture base dir",
            value=str((ROOT / "tests" / "fixtures").resolve()),
        )
    st.sidebar.caption(selected)
    return selected


def _fixture_dir_candidates() -> list[Path]:
    preferred = [ROOT / "tests" / "fixtures", ROOT / "tests", ROOT / "examples", ROOT]
    candidates: list[Path] = []
    for path in preferred:
        resolved = path.resolve()
        if resolved not in candidates:
            candidates.append(resolved)
    return candidates


if __name__ == "__main__":
    main()
