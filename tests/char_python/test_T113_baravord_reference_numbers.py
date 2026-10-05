# -*- coding: utf-8 -*-
# T113 — ریشه‌یابیِ اختلافِ برآورد ۱۴۰۵Q1 (فاز E-۷ بخش ۱).
#
# دو عددِ مرجع که نیاز به توضیح داشتند:
#   ۴۵٬۴۳۷٬۷۴۲٬۸۲۰٫۳۲  ← baravord_it_period = "q4"       (۱۴۰۴Q4 قطعی، پیش‌فرض)
#   ۵۲٬۳۹۲٬۰۷۳٬۸۱۱٫۸۷  ← baravord_it_period = "1405Q1"  (موقت، CPI + m)
#
# نتیجهٔ ریشه‌یابی: باگ نیست. این دو عدد دو سناریوی متفاوت‌اند (دورهٔ هدفِ
# It). نسبتِ آن‌ها دقیقاً ضریبِ موقتِ ۱۴۰۵Q1 است:
#   ۱ + ۰٫۷ × (۶۱۹٫۶ ÷ میانگین(۴۶۹٫۴، ۵۱۳٫۶، ۵۴۲٫۳) − ۱) = ۱٫۱۵۳۰۵۱۸۵۸۶۵
# و عددِ ۵۲٫۳۹ میلیارد ریال دقیقاً با It = ۱۴۰۵Q1 بازتولید می‌شود.
#
# این آزمون‌ها هر دو عدد را روی خطِ لولهٔ کاملِ پروژهٔ مرجع قفل می‌کنند
# (آینهٔ test_T113_baravord_reference_numbers.ts).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser,
                  TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

# ضریب موقت ۱۴۰۵Q1 (بخشنامهٔ ۱۴۴۳۷۳، m=۰٫۷ ابنیه)
PROV_COEF = 1.1530518586507572

# ── مقادیرِ مرجعِ استخراج‌شده از موتور (خطِ لولهٔ کامل) ──
RESULT_Q4 = 45_437_742_820.323151
RESULT_1405Q1 = 52_392_073_811.868721
GRAND_CURRENT = 31_391_251_567.639599

# فصل | مبلغ پایه | Io | It(۱۴۰۴Q4) | نسبت | مبلغ به‌هنگام‌شده
CHAPTERS_Q4 = {
    "06": (12_526_794_300.800001, 7273.8, 10632.1, 1.461698149523,
           18_310_392_048.933941),
    "08": (11_964_500_668.921591, 9787.4, 14154.7, 1.446216564154,
           17_303_259_049.224968),
    "07": (6_422_284_001.701364, 10794.8, 15334.7, 1.420563604699,
           9_123_262_911.854774),
    "10": (468_045_467.354608, 8507.9, 12489.6, 1.468000329106,
           687_090_900.113085),
    "28": (9_627_128.862033, 13243.1, 18897.9, 1.426999720609,
           13_737_910.196390),
}


def _pipeline(settings):
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    map_df = DynamoMappingParser.merge_formats(results)
    return TechnicalOfficeEngine(_default_fehrest_db(), settings).compute(
        tables, map_df)


def _on(**extra):
    s = default_settings()
    s["baravord_enabled"] = True
    s["baravord_approved"] = True
    s.update(extra)
    return s


# ── دو عددِ مرجع ──

def test_T113_baravord_default_it_q4():
    b = _pipeline(_on())["adjustment"]["baravord"]
    assert b["it_q"] == "1404Q4"
    assert b["result_amount"] == pytest.approx(RESULT_Q4, rel=1e-12)
    assert b["grand_updated"] == pytest.approx(RESULT_Q4, rel=1e-12)
    assert b["grand_current"] == pytest.approx(GRAND_CURRENT, rel=1e-12)


def test_T113_baravord_it_1405q1_provisional():
    b = _pipeline(_on(baravord_it_period="1405Q1",
                      provisional_coef_1405q1=PROV_COEF)
                  )["adjustment"]["baravord"]
    assert b["it_q"] == "1405Q1"
    assert b["result_amount"] == pytest.approx(RESULT_1405Q1, rel=1e-12)


def test_T113_two_numbers_differ_exactly_by_provisional_coef():
    q4 = _pipeline(_on())["adjustment"]["baravord"]["result_amount"]
    prov = _pipeline(_on(baravord_it_period="1405Q1",
                         provisional_coef_1405q1=PROV_COEF)
                     )["adjustment"]["baravord"]["result_amount"]
    # نسبتِ دو عدد = ضریبِ موقت (علتِ ریشه‌ایِ اختلاف)
    assert prov / q4 == pytest.approx(PROV_COEF, rel=1e-11)
    assert prov - q4 == pytest.approx(6_954_330_991.545570, rel=1e-9)


# ─ـ جزئیاتِ فصل‌به‌فصل (It = ۱۴۰۴Q4) ──

def test_T113_chapter_table_q4():
    b = _pipeline(_on())["adjustment"]["baravord"]
    rows = {r["chapter"]: r for r in b["chapters"]}
    assert set(rows) == set(CHAPTERS_Q4)
    for code, (amt, io, it, ratio, value) in CHAPTERS_Q4.items():
        r = rows[code]
        assert r["amount"] == pytest.approx(amt, rel=1e-9)
        assert r["io"] == pytest.approx(io, rel=1e-9)
        assert r["it"] == pytest.approx(it, rel=1e-9)
        assert r["ratio"] == pytest.approx(ratio, rel=1e-9)
        assert r["value"] == pytest.approx(value, rel=1e-9)
        assert r["status"] == "قطعی"
    # Σ مبالغِ فصل = جمع کلِ فعلی (A)
    assert sum(r["amount"] for r in b["chapters"]) == pytest.approx(
        GRAND_CURRENT, rel=1e-9)
    # Σ مبالغِ به‌هنگام‌شده = نتیجه
    assert sum(r["value"] for r in b["chapters"]) == pytest.approx(
        RESULT_Q4, rel=1e-9)


def test_T113_chapter_table_1405q1_status_provisional():
    b = _pipeline(_on(baravord_it_period="1405Q1",
                      provisional_coef_1405q1=PROV_COEF)
                  )["adjustment"]["baravord"]
    rows = {r["chapter"]: r for r in b["chapters"]}
    q4 = {r["chapter"]: r for r in
          _pipeline(_on())["adjustment"]["baravord"]["chapters"]}
    for code, r in rows.items():
        assert r["status"] == "موقت"
        assert r["amount"] == pytest.approx(q4[code]["amount"], rel=1e-12)
        assert r["io"] == pytest.approx(q4[code]["io"], rel=1e-12)
        # It موقت = It قطعی × ضریب موقت
        assert r["it"] == pytest.approx(q4[code]["it"] * PROV_COEF, rel=1e-11)
