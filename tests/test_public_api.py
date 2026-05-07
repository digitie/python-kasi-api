from __future__ import annotations

import pykasi


def test_public_imports() -> None:
    exported = set(pykasi.__all__)

    assert "KasiClient" in exported
    assert "Page" in exported
    assert "SpecialDay" in exported
    assert "KasiAuthError" in exported
