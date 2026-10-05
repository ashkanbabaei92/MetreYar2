# -*- coding: utf-8 -*-
# T60 - تطبیق پاریتی موتور فازی میان پایتون و تایپ‌اسکریپت
#
# هدف: اطمینان از اینکه `fuzzy_match`/`_token_set_ratio` در app.py و
# `fuzzyScore`/`tokenSetRatio` در src/lib/matching.ts برای یک ورودی یکسان،
# دقیقاً یکسان امتیاز می‌دهند.golden این تست با محاسبهٔ واقعی موتور پایتون
# تولید می‌شود (GENERATE=1) و نسخهٔ TS باید دقیقاً به آن برسد.
#
# شامل مواردی است که در آن‌ها LCS واقعی با difflib.SequenceMatcher اختلاف
# دارد (adv_*)، ورودی‌های فارسی واقعی، رشته‌های بلند (autojunk) و حالت‌های تهی.
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import fuzzy_match, _token_set_ratio  # noqa: E402

from helper import load_json, golden_path, record  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "char_shared",
                       "fixtures", "fuzzy_parity_cases.json")


def _compute():
    cases = json.load(open(FIXTURE, encoding="utf-8"))
    out = []
    for c in cases:
        out.append({
            "id": c["id"],
            "a": c["a"],
            "b": c["b"],
            "fuzzy_score": round(fuzzy_match(c["a"], [c["b"]], threshold=0.0)[1], 6),
            "token_set_ratio": round(_token_set_ratio(c["a"], c["b"]), 6),
        })
    return out


def test_T60_fuzzy_parity():
    results = _compute()
    record("T60_fuzzy_parity", {"cases": results},
           generate=os.environ.get("GENERATE") == "1")
    # مقایسهٔ دقیق با golden (تولیدشده توسط همین موتور)
    golden = load_json(golden_path("T60_fuzzy_parity"))
    for case in golden["cases"]:
        got = next(c for c in results if c["id"] == case["id"])
        assert got == case, f"{case['id']}: {got} != {case}"


def test_T60_ts_golden_matches():
    """نسخهٔ TS باید به همان golden برسد (پاریتی دوزبانه)."""
    ts_path = os.path.join(os.path.dirname(__file__), "..", "char_ts",
                           "golden", "T60_fuzzy_parity.json")
    if not os.path.exists(ts_path):
        pytest.skip("golden تایپ‌اسکریپت هنوز ساخته نشده است")
    ts = json.load(open(ts_path, encoding="utf-8"))
    for case in ts["cases"]:
        got = next(c for c in _compute() if c["id"] == case["id"])
        assert got == case, f"اختلاف پاریتی در {case['id']}: PY={got} TS={case}"


if __name__ == "__main__":
    test_T60_fuzzy_parity()
    try:
        test_T60_ts_golden_matches()
        print("TS golden: تطابق کامل")
    except pytest.skip.Exception:
        print("TS golden: وجود ندارد")
