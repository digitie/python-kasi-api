from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.is_dir():
    sys.path.insert(0, str(SRC_DIR))

from kasi import (  # noqa: E402
    KasiClient,
    api_catalog,
    api_catalog_rows,
    jsonable,
    normalize_service_key,
    save_fixture,
)
from kasi.catalog import ApiCatalogEntry, ApiParameter  # noqa: E402

FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"


def main() -> None:
    st.set_page_config(page_title="python-kasi-api debug", layout="wide")
    st.title("python-kasi-api debug")

    catalog = api_catalog()
    labels = [entry.display_name for entry in catalog]
    selected_label = st.sidebar.selectbox("API", labels)
    selected = catalog[labels.index(selected_label)]

    st.sidebar.link_button("공공데이터포털 활용신청", selected.service_key_url)
    st.sidebar.caption(selected.dataset_name)
    service_key = st.sidebar.text_input("Service key", type="password")
    timeout = st.sidebar.number_input("Timeout", min_value=1.0, max_value=120.0, value=10.0)

    st.subheader(selected.dataset_name)
    st.caption(f"{selected.service_name}/{selected.endpoint}")
    st.link_button("서비스키 받기", selected.service_key_url)

    with st.form("debug-form"):
        params = _input_params(selected)
        run = st.form_submit_button("Run")

    if not run:
        st.dataframe(api_catalog_rows(), use_container_width=True, hide_index=True)
        return

    key = normalize_service_key(service_key)
    try:
        client = KasiClient(service_key=key, timeout=timeout)
        debug_run = client.debug(selected.function_name, **params)
    except Exception as exc:
        st.error(str(exc))
        return

    raw_tab, parsed_tab, processed_tab, error_tab, trace_tab, fixture_tab = st.tabs(
        [
            "Raw Response",
            "Pydantic Model",
            "Processed Result",
            "Validation Errors",
            "Debug Trace",
            "Fixture",
        ]
    )
    with raw_tab:
        st.json(jsonable(debug_run.response))
    with parsed_tab:
        st.json(jsonable(debug_run.parsed))
    with processed_tab:
        st.json(jsonable(debug_run.processed))
    with error_tab:
        st.json(jsonable(debug_run.error))
    with trace_tab:
        _render_trace(debug_run.trace, selected)
    with fixture_tab:
        _render_fixture_form(debug_run)


def _input_params(entry: ApiCatalogEntry) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for param in (*entry.required_params, *entry.optional_params):
        value = _input_param(param)
        if value in (None, ""):
            continue
        params[param.name] = value
    return params


def _input_param(param: ApiParameter) -> Any:
    label = f"{param.label} ({param.name})"
    if param.kind == "int":
        value = param.default if isinstance(param.default, int) else 1
        return st.number_input(label, min_value=1, value=value, step=1)
    if param.kind == "choice":
        options = list(param.choices)
        if not param.required:
            options = [""] + options
        index = options.index(param.default) if param.default in options else 0
        return st.selectbox(label, options, index=index)
    default = "" if param.default is None else str(param.default)
    if param.kind == "date":
        default = default or "20260505"
    if param.kind == "year":
        default = default or "2026"
    if param.kind == "month":
        default = default or "05"
    if param.kind == "day":
        default = default or "05"
    return st.text_input(label, value=default, placeholder=param.description)


def _render_trace(trace: list[str], entry: ApiCatalogEntry) -> None:
    st.markdown(f"**데이터셋명:** {entry.dataset_name}")
    st.markdown(f"**함수:** `{entry.function_name}`")
    st.markdown(f"**서비스:** `{entry.service_name}`")
    st.markdown(f"**오퍼레이션:** `{entry.endpoint}`")
    st.link_button("서비스키 받기", entry.service_key_url)
    st.json(entry.to_dict())
    st.write(trace)


def _render_fixture_form(debug_run: Any) -> None:
    case_name = st.text_input("Case name", value=f"{debug_run.function}_case")
    description = st.text_area("Description")
    assertion_mode = st.selectbox("Assertion mode", ["snapshot", "schema_only", "required_fields"])
    exclude_fields = st.text_input("Exclude fields", value="fetched_at, request_id, updated_at")
    required_fields = st.text_input("Required fields")
    overwrite = st.checkbox("Overwrite existing fixture", value=False)
    assertion = {
        "mode": assertion_mode,
        "exclude_fields": [field.strip() for field in exclude_fields.split(",") if field.strip()],
        "required_fields": [field.strip() for field in required_fields.split(",") if field.strip()],
    }
    if st.button("Save as fixture"):
        path = save_fixture(
            base_dir=FIXTURE_DIR,
            function_name=debug_run.function,
            case_name=case_name,
            description=description,
            input_data=debug_run.input,
            request_data=debug_run.request,
            response_data=debug_run.response,
            parsed_result=debug_run.parsed,
            processed_result=debug_run.processed,
            assertion=assertion,
            overwrite=overwrite,
        )
        st.success(f"Saved: {path.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
