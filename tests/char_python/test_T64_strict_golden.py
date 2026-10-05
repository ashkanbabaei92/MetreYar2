# -*- coding: utf-8 -*-
# T64 - رفتار سخت‌گیرانهٔ record(): golden مفقود باید FAIL شود، نه ساخته شود.
#
# قبل از این، record() در نبود golden آن را خاموش از مقدار فعلی می‌ساخت و
# تست بی‌صدا پاس می‌شد — یعنی حذف تصادفی یک golden رگرسیون را پنهان می‌کرد.
# اکنون ساختن فقط با پرچم صریح (GENERATE / UPDATE_GOLDENS) مجاز است.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from helper import golden_path, load_json, record, save_json  # noqa: E402


def test_T64_missing_golden_fails_without_flag():
    """بدون پرچم، golden مفقود باید AssertionError بدهد."""
    tid = "T64_strict_probe"
    gp = golden_path(tid)
    assert not os.path.exists(gp)
    with pytest.raises(AssertionError, match="golden مفقود"):
        record(tid, {"probe": 1})
    assert not os.path.exists(gp), "golden نباید ساخته شود"


def test_T64_missing_golden_created_with_flag(tmp_path, monkeypatch):
    """با پرچم UPDATE_GOLDENS، golden ساخته می‌شود و مقایسهٔ بعدی پاس می‌شود."""
    tid = "T64_strict_probe_flagged"
    gp = golden_path(tid)
    assert not os.path.exists(gp)
    try:
        monkeypatch.setenv("UPDATE_GOLDENS", "1")
        out = record(tid, {"probe": 2})
        assert out["status"] == "golden_created"
        assert os.path.exists(gp)
        # بدون پرچم هم اکنون مقایسه می‌شود (نه خطا)
        monkeypatch.delenv("UPDATE_GOLDENS", raising=False)
        cmp = record(tid, {"probe": 2})
        assert cmp["status"] == "compare"
    finally:
        if os.path.exists(gp):
            os.remove(gp)


def test_T64_existing_golden_overwritten_with_generate_flag(monkeypatch):
    """با پرچم GENERATE، golden موجود باید بازنویسی شود (تولید دوباره)."""
    tid = "T64_strict_probe_overwrite"
    gp = golden_path(tid)
    assert not os.path.exists(gp)
    try:
        # ساخت اولیه
        record(tid, {"version": 1}, generate=True)
        assert load_json(gp)["version"] == 1
        # بازنویسی صریح
        out = record(tid, {"version": 2}, generate=True)
        assert out["status"] == "golden_updated"
        assert load_json(gp)["version"] == 2
        # بدون پرچم: مقایسه (نه بازنویسی)
        cmp = record(tid, {"version": 2})
        assert cmp["status"] == "compare"
    finally:
        if os.path.exists(gp):
            os.remove(gp)


if __name__ == "__main__":
    test_T64_missing_golden_fails_without_flag()
    test_T64_missing_golden_created_with_flag(None, None)
    print("T64 ok")
