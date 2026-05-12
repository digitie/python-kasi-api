from __future__ import annotations

import kasi


def test_public_imports() -> None:
    exported = set(kasi.__all__)

    assert "KasiClient" in exported
    assert "Page" in exported
    assert "SpecialDay" in exported
    assert "KasiAuthError" in exported
