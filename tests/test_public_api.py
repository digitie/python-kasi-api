from __future__ import annotations

import kasi


def test_public_imports() -> None:
    exported = set(kasi.__all__)

    assert "KasiClient" in exported
    assert "DebugRun" in exported
    assert "Page" in exported
    assert "SpecialDay" in exported
    assert "KasiAuthError" in exported
    assert "api_catalog" in exported
    assert "api_catalog_rows" in exported
    assert "normalize_service_key" in exported
    assert "save_fixture" in exported
