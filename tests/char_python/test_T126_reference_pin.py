# -*- coding: utf-8 -*-
# T126 — فاز E-10 §۱ — قفلِ اعداد مرجع به docs/REFERENCE_NUMBERS.md.
#
# این آزمون همهٔ اعداد مرجع را با اجرایِ خطِ لولهٔ کاملِ پروژهٔ مرجع
# بازمحاسبه می‌کند و با بلوکِ JSONِ fenced در docs/REFERENCE_NUMBERS.md
# مقایسه می‌کند. **اگر کسی موتور را طوری تغییر دهد که این اعداد تغییر
# کنند و REFERENCE_NUMBERS.md را به‌روز نکند، این آزمون قرمز می‌شود.**
#
# ریشهٔ تغییرِ ΔP از ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴ به ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲: commit 8760bd3
# (baseline: E-6 complete) — گردکردنِ بند ۸-۲ بخشنامهٔ ۲۰۸۰ پیش‌فرض شد
# (coef_rounding_2080 = true). اختلاف = +۴۶٬۸۶۹٬۵۳۰٫۵۸ (= D-03).
import json
import os
import re
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")
REF_MD = os.path.join(ROOT, "docs", "REFERENCE_NUMBERS.md")

PROV_COEF = 1.1530518586507572
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"
WP_MIX = ("۱۴۰۴/۰۱/۰۱", "۱۴۰۵/۰۲/۱۵")     # قطعی + علی‌الحساب
WP_ALLDEF = ("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۱۲/۲۹")  # کاملاً قطعی


def _pipeline(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    tables = []
    for fn in sorted(os.listdir(REVIT_DIR)):
        if fn.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fn), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fn, fh.read()))
    res = []
    for root, _d, fns in os.walk(DYNAMO_DIR):
        for fn in sorted(fns):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    res.append(DynamoMappingParser.auto_detect_and_parse(
                        fh.read(), fn))
    mdf = DynamoMappingParser.merge_formats(res)
    return TechnicalOfficeEngine(_default_fehrest_db(), s).compute(tables, mdf)


def _pinned():
    """خواندنِ بلوکِ JSONِ fenced از REFERENCE_NUMBERS.md."""
    with open(REF_MD, encoding="utf-8") as fh:
        txt = fh.read()
    m = re.search(r"```json\r?\n(.*?)\r?\n```", txt, re.S)
    assert m, "بلوکِ JSON در docs/REFERENCE_NUMBERS.md پیدا نشد"
    return json.loads(m.group(1))


def test_T126_reference_numbers_match_doc():
    doc = _pinned()
    expected_keys = {"base_total", "grand_total", "dp_total", "dp_definitive",
                     "dp_provisional", "dp_fallback", "baravord_q4",
                     "baravord_1405q1"}
    assert set(doc) == expected_keys, \
        "کلیدهای بلوک باید همین هشت تا باشند: %s" % sorted(set(doc) ^ expected_keys)

    got = {}

    r0 = _pipeline()
    got["base_total"] = round(r0["base_total"], 2)
    got["grand_total"] = round(r0["grand_total"], 2)

    r1 = _pipeline(baravord_enabled=True, work_period_start=WP_MIX[0],
                   work_period_end=WP_MIX[1], provisional_coef_1405q1=PROV_COEF)
    t = r1["adjustment"]["tadil"]
    assert t, "موتور تعدیل باید روشن باشد"
    got["dp_total"] = round(t["delta_p"], 2)
    got["dp_definitive"] = round(t["delta_p_definitive"], 2)
    got["dp_provisional"] = round(t["delta_p_provisional"], 2)

    # یکپارچگیِ داخلی (قاعدهٔ طلایی): قطعی + علی‌الحساب ≡ مجموع
    assert (got["dp_definitive"] + got["dp_provisional"]
            == pytest.approx(got["dp_total"], abs=1e-6))

    r2 = _pipeline(provisional_coef_1405q1=PROV_COEF)
    got["dp_fallback"] = round(r2["adjustment"]["tadil"]["delta_p"], 2)
    assert any(w["item"] == "work_period_missing_for_it"
               for w in r2.get("warnings", [])), \
        "دورهٔ کارکردِ خالی باید هشدارِ work_period_missing_for_it بدهد"

    r3 = _pipeline(baravord_enabled=True, baravord_it_period="q4",
                   work_period_start=WP_ALLDEF[0], work_period_end=WP_ALLDEF[1],
                   provisional_coef_1405q1=PROV_COEF)
    got["baravord_q4"] = round(r3["adjustment"]["baravord"]["grand_updated"], 2)

    r4 = _pipeline(baravord_enabled=True, baravord_it_period="1405Q1",
                   work_period_start=WP_ALLDEF[0], work_period_end=WP_ALLDEF[1],
                   provisional_coef_1405q1=PROV_COEF)
    got["baravord_1405q1"] = round(r4["adjustment"]["baravord"]["grand_updated"], 2)

    bad = {k: (doc[k], got[k]) for k in expected_keys if doc[k] != got[k]}
    assert not bad, (
        "اعداد مرجع با docs/REFERENCE_NUMBERS.md مطابق نیستند — اگر موتور "
        "را تغییر داده‌اید، آن سند را هم به‌روز کنید:\n%s" %
        "\n".join("  %s: سند=%s موتور=%s" % (k, v[0], v[1])
                  for k, v in sorted(bad.items()))
    )


def test_T126_rounding_flip_is_d03():
    # ریشه‌یابیِ §۱: ۹٬۹۸۴ (گردکردن روشن) − ۹٬۹۳۷ (خاموش) = ۴۶٬۸۶۹٬۵۳۰٫۵۸
    on = _pipeline(baravord_enabled=True, work_period_start=WP_MIX[0],
                   work_period_end=WP_MIX[1], provisional_coef_1405q1=PROV_COEF)
    off = _pipeline(baravord_enabled=True, work_period_start=WP_MIX[0],
                    work_period_end=WP_MIX[1], provisional_coef_1405q1=PROV_COEF,
                    coef_rounding_2080=False)
    d_on = on["adjustment"]["tadil"]["delta_p"]
    d_off = off["adjustment"]["tadil"]["delta_p"]
    assert round(d_on, 2) == 9984277408.22
    assert round(d_off, 2) == 9937407877.64
    assert round(d_on - d_off, 2) == 46869530.58
