# -*- coding: utf-8 -*-
# T63 - تطابق تابع normalize_text میان پایتون و تایپ‌اسکریپت
#
# normalize.ts یک بازهٔ `^_+|_+$` اضافه داشت که در پایتون نبود؛ این بازه
# اکنون حذف شده زیرا اضافی بود (زیرخط‌ها در همان مرحلهٔ بعدی به فاصله تبدیل
# و در پایان trim می‌شوند). این تست با golden تولیدشدهٔ پایتون، تطابق را
# تضمین می‌کند. موارد: زیرخط ابتدا/انتها/داخل، نقطه‌گذاری، پسوند «ها/های»،
# ارقام فارسی، ی عربی (U+064A)، نیم‌فاصله.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import normalize_text

from helper import load_json, golden_path, record  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "char_shared",
                       "fixtures", "normalize_cases.json")


def _compute():
    cases = load_json(FIXTURE)
    return [{"id": c["id"], "input": c["input"],
             "output": normalize_text(c["input"])} for c in cases]


def test_T63_normalize_underscore_parity():
    """زیرخط ابتدا/انها باید مانند پایتون نرمال شود (تبدیل به فاصله + trim)."""
    assert normalize_text("_بتن مگر_") == normalize_text("بتن مگر")
    assert normalize_text("___") == ""
    assert normalize_text("تهیه_و_اجرا") == "تهیه و اجرا"


def test_T63_normalize_golden():
    snap = {"cases": _compute()}
    record("T63_normalize", snap, generate=os.environ.get("GENERATE") == "1")
    golden = load_json(golden_path("T63_normalize"))
    assert snap == golden


if __name__ == "__main__":
    test_T63_normalize_underscore_parity()
    test_T63_normalize_golden()
    print("T63 ok")
