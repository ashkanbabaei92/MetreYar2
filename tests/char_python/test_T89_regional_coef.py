# -*- coding: utf-8 -*-
# T89 — ضریب منطقه‌ای (ایراد ۴ — مرحلهٔ ۱۳).
#
# جدول ضرایب منطقه‌ای از بخشنامهٔ ۹۴/۶۹۴۱۶ (S5) در
# config/regional_coefficients.json: ۳۱ استان، ۱۰۷۷ ردیف.
# پروژهٔ مرجع: گلستان/گرگان/بخش مرکزی/ابنیه = ۱٫۰۴ (ردیف ۲۰).
# اولویت: ورودی دستی > جدول؛ نبودن هر دو → ناقص + هشدار خطا.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 REGIONAL_TABLE, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


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


def test_T89_regional_table_loaded():
    """جدول استخراج‌شده از بخشنامه بارگذاری شده است."""
    provs = REGIONAL_TABLE["provinces"]
    assert len(provs) == 31
    gol = provs["گلستان"]
    assert len(gol) == 36
    row20 = next(e for e in gol if e["city"] == "گرگان" and e["district"] == "مرکزی")
    assert row20["row"] == 20
    assert row20["coefs"]["ابنیه"] == 1.04


def test_T89_default_selection_gorgan_104():
    """انتخاب پیش‌فرض پروژهٔ مرجع: گرگان/مرکزی/ابنیه = ۱٫۰۴."""
    r = _pipeline(default_settings())
    reg = r["coefs"]["regional"]
    assert reg["value"] == 1.04
    assert reg["status"] == "استخراج‌شده"
    assert "ردیف ۲۰" in reg["source"]
    assert r["grand_total"] == pytest.approx(23218381337.01 * 1.0 * 1.3 * 1.04, rel=1e-6)


def test_T89_bad_province_incomplete():
    """استان ناموجود → ضریب ناقص، هشدار خطا، و ضریب ۱ در زنجیره."""
    s = dict(default_settings())
    s["regional_selection"] = {"province": "هیچ‌جا", "city": "x", "district": "y",
                               "discipline": "ابنیه"}
    r = _pipeline(s)
    assert r["coefs"]["regional"]["value"] is None
    assert r["coefs"]["regional"]["status"] == "ناقص"
    errs = [w for w in r["warnings"] if w["category"] == "ضریب منطقه‌ای"]
    assert len(errs) == 1 and errs[0]["level"] == "خطا"
    assert r["regional_amount"] == pytest.approx(r["overhead_amount"] * 1.0, rel=1e-9)


def test_T89_manual_override_wins():
    """ورودی دستی بر جدول تقدم دارد."""
    s = dict(default_settings(), regional_coef=1.10)
    r = _pipeline(s)
    assert r["coefs"]["regional"]["value"] == pytest.approx(1.10, rel=1e-9)
    assert r["coefs"]["regional"]["status"] == "دستی"
    assert r["grand_total"] == pytest.approx(23218381337.01 * 1.0 * 1.3 * 1.10, rel=1e-6)


def test_T89_discipline_switch():
    """تغییر رشته: ابنیه ۱٫۰۴ → تاسیسات مکانیکی ۱٫۰۸."""
    s = dict(default_settings())
    s["regional_selection"] = dict(s["regional_selection"], discipline="تاسیسات مکانیکی")
    r = _pipeline(s)
    assert r["coefs"]["regional"]["value"] == pytest.approx(1.08, rel=1e-9)
