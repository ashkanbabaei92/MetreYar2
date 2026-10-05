# -*- coding: utf-8 -*-
# T97 — فاز E-6: ضریب مشتق‌شدهٔ k (بخشنامهٔ ۲۰۸۰، بند ۱-۸ و تبصرهٔ ۲)
# و گردکردن ضریب طبق بند ۸-۲.
#
# منبع: docs/sources/2080.pdf — بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳)،
# پس فقط نامی که کاربر معرفی کرده استفاده می‌شود: «بخشنامهٔ ۲۰۸۰»).
#
# k ورودی کاربر نیست:
#   completed_within_term = True  => k = ۱    (تبصرهٔ ۲ بند ۱-۸)
#   completed_within_term = False => k = ۰٫۹۵ (بند ۱-۸)
#   completed_within_term = None  => k = ۰٫۹۵ (علی‌الحساب، تکلیف نامشخص)
# مابه‌التفاوت ۰٫۹۵ → ۱ طبق بند ۸-۴ همزمان با صورت‌وضعیت قطعی (k_diff).
import json
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, _tadil_k, default_settings, round_coef_2080)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")
PROV_COEF = 1.1530518586507572
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"

REF = dict(baravord_enabled=True,
           work_period_start="۱۴۰۴/۰۱/۰۱",
           work_period_end="۱۴۰۵/۰۲/۱۵",
           provisional_coef_1405q1=PROV_COEF)


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    return s


def _ctx(chapters=None, base=10_000_000_000.0, setup=0.0, advance=0.0):
    return {"chapter_amounts": chapters or {"06": base},
            "floors_amount": base, "base_total": base, "site_setup": setup,
            "advance_payment": advance,
            "overhead_coef": 1.3, "regional_coef": 1.04,
            "grand_total": base * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": base, "excluded_total": 0.0}}


def _tadil(settings, ctx=None, warns=None):
    warns = warns if warns is not None else []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._tadil_engine(ctx or _ctx(), warns), warns


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
                    results.append(DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    map_df = DynamoMappingParser.merge_formats(results)
    return TechnicalOfficeEngine(_default_fehrest_db(), settings).compute(tables, map_df)


def _split(t, d):
    return TechnicalOfficeEngine(_default_fehrest_db(), default_settings())._split_rounded(
        t, d, 2)


# ── گردکردن ضریب (بند ۸-۲) ──

def test_T97_round_coef_table():
    # جدول بازبینی فاز E-6 (تفسیر الف: ۳ رقم اعشار، سپس گردکردن رقم دوم)
    for x, exp in [(0.1234, 0.12), (0.1235, 0.12), (0.1249, 0.13),
                   (0.1250, 0.13), (0.0049, 0.01), (0.0050, 0.01),
                   (0.0, 0.0), (0.9995, 1.0), (0.4473, 0.45)]:
        got = round_coef_2080(x)
        assert got == pytest.approx(exp, abs=1e-9), (x, got, exp)


def test_T97_round_coef_negative_on_absolute_value():
    # بخشنامه دربارهٔ ضرایب منفی ساکتی است؛ عمل روی قدر مطلق (گرد به‌سمت بزرگتر)
    for x, exp in [(-0.1250, -0.13), (-0.1249, -0.13), (-0.1235, -0.12),
                   (-0.1234, -0.12), (-0.0049, -0.01), (-0.4473, -0.45)]:
        got = round_coef_2080(x)
        assert got == pytest.approx(exp, abs=1e-9), (x, got, exp)


def test_T97_round_coef_none():
    assert round_coef_2080(None) is None


# ── مشتق‌شدن k (بند ۱-۸ و تبصرهٔ ۲) ──

def test_T97_k_default_is_095():
    s = default_settings()
    assert s["completed_within_term"] is None
    assert _tadil_k(s)[0] == 0.95


def test_T97_k_variants():
    s = default_settings()
    s["completed_within_term"] = True
    k, lbl, src = _tadil_k(s)
    assert k == 1.0 and "تبصرهٔ ۲" in lbl and "تبصرهٔ ۲" in src
    s["completed_within_term"] = False
    k, lbl, _src = _tadil_k(s)
    assert k == 0.95 and "تمام نشد" in lbl
    s["completed_within_term"] = None
    k, lbl, _src = _tadil_k(s)
    assert k == 0.95 and "نامشخص" in lbl


def test_T97_k_source_carries_bulletin_number():
    # شماره و تاریخ روی صفحهٔ ۴ سند درج شده‌اند (بخش ۰)
    _k, _lbl, src = _tadil_k(default_settings())
    assert "۲۰۸۰" in src
    assert "۹۷۰۶" in src
    assert "۱۳۷۰" in src


def test_T97_engine_ignores_legacy_tadil_coef():
    t, warns = _tadil(_on(tadil_coef=1.5))
    assert t["coef"] == 0.95
    assert t["completed_within_term"] is False
    assert not any(w["item"] == "tadil_coef" for w in warns)


def test_T97_pending_k_status_reflects_cwt():
    t_none, _w = _tadil(_on())
    k_none = [p for p in t_none["pending"] if "ضریب قانونی" in p["item"]][0]
    assert k_none["value"] == 0.95
    assert "نامشخص" in k_none["status"]
    t_true, _w2 = _tadil(_on(completed_within_term=True))
    k_true = [p for p in t_true["pending"] if "ضریب قانونی" in p["item"]][0]
    assert k_true["value"] == 1.0
    assert "تبصرهٔ ۲" in k_true["page"]

def test_T97_config_references_2080_pdf():
    # فاز E-6:config باید به اسکن بخشنامهٔ ۲۰۸۰ ارجاع دهد و فایل موجود باشد
    cfg = json.load(open("config/index_bulletins.json", encoding="utf-8"))
    b = cfg["bulletin_2080"]
    assert b["source_file"] == "docs/sources/2080.pdf"
    assert os.path.exists(b["source_file"])
    clauses = {r["clause"] for r in b["rules"]}
    assert {"۱-۸", "۱-۸ تبصرهٔ ۲", "۸-۲", "۸-۴"} <= clauses
