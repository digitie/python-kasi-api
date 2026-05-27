from __future__ import annotations

from pathlib import Path

import kasi


def test_public_imports() -> None:
    exported = set(kasi.__all__)

    assert "KasiClient" in exported
    assert "KasiConfig" in exported
    assert "AsyncKasiClient" in exported
    assert "PROVIDER_NAME" in exported
    assert "__version__" in exported
    assert "DebugRun" in exported
    assert "Page" in exported
    assert "SpecialDay" in exported
    assert "KasiAuthError" in exported
    assert "api_catalog" in exported
    assert "api_catalog_rows" in exported
    assert "normalize_service_key" in exported
    assert "save_fixture" in exported


def test_runtime_dependencies_do_not_include_external_address_base() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    removed_dependency = "python-" + "kr" + "addr-base"

    assert removed_dependency not in pyproject
