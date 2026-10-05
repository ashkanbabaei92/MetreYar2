# -*- coding: utf-8 -*-
# T90 — رجیستری مرکزی هشدارها (ایراد ۱۰) و چگالی میلگرد (ایراد ۱۴).
#
# هر ردیف needs_review باید هشدار متناظر داشته باشد. همهٔ هشدارها
# ساختاریافته‌اند: سطح | دسته | المان | شرح | اقدام | بند مرجع.
# چگالی میلگرد هر گروه = وزن ÷ حجم بتن؛ خارج از محدوده → هشدار خطا
# (اپ عدد را تغییر نمی‌دهد).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 REBAR_DENSITY_CFG, _default_fehrest_db, default_settings)

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


def _eng(settings=None):
    return TechnicalOfficeEngine(_default_fehrest_db(), settings or default_settings())


def test_T90_warnings_structure():
    """هر هشدار شامل همهٔ فیلدهای الزامی است."""
    r = _pipeline(default_settings())
    assert r["warnings"]
    for w in r["warnings"]:
        assert set(w) == {"level", "category", "item", "message", "action", "ref"}
        assert w["level"] in ("خطا", "هشدار", "اطلاع")
        assert w["message"]


def test_T90_needs_review_lines_have_warnings():
    """قاعدهٔ کیفی: هر خط needs_review یک هشدار دارد."""
    r = _pipeline(default_settings())
    review = [l for l in r["lines"] if l["needs_review"]]
    items = {w["item"] for w in r["warnings"] if w["category"] == "تطبیق ردیف"}
    assert {l["code"] for l in review} <= items
    for l in review:
        assert any(w["item"] == l["code"] and "بازبینی" in w["message"]
                   for w in r["warnings"])


def test_T90_rebar_density_thresholds_loaded():
    """آستانه‌ها از config/rebar_density_thresholds.json."""
    th = REBAR_DENSITY_CFG["thresholds_kg_m3"]
    assert th["پی"] == [50, 120]
    assert th["ستون"] == [100, 250]
    assert th["تیر"] == [100, 200]
    assert th["دال"] == [60, 120]
    assert th["پله"] == [60, 120]


def test_T90_rebar_density_out_of_range_warns():
    """چگالی ۲۰۰ kg/m³ برای پی (محدودهٔ ۵۰–۱۲۰) → هشدار خطا."""
    lines = [
        {"code": "080105", "unit": "مترمکعب", "sources": [{"group": "پی", "qty": 100.0}]},
        {"code": "070202", "unit": "کیلوگرم", "sources": [{"group": "پی", "qty": 20000.0}]},
    ]
    warns = []
    eng = _eng()
    eng._rebar_density_warnings(lines, warns)
    assert len(warns) == 1
    assert warns[0]["level"] == "خطا"
    assert warns[0]["item"] == "پی"
    assert "۲۰۰" in warns[0]["message"]
    assert "۵۰" in warns[0]["message"] and "۱۲۰" in warns[0]["message"]


def test_T90_rebar_density_in_range_silent():
    """چگالی ۱۰۰ kg/m³ داخل محدوده → بدون هشدار."""
    lines = [
        {"code": "080105", "unit": "مترمکعب", "sources": [{"group": "ستون", "qty": 100.0}]},
        {"code": "070202", "unit": "کیلوگرم", "sources": [{"group": "ستون", "qty": 10000.0}]},
    ]
    warns = []
    _eng()._rebar_density_warnings(lines, warns)
    assert warns == []


def test_T90_rebar_manual_weight_info():
    """وزن دستی میلگرد → هشدار اطلاع (دست‌نخوردن عدد مدل)."""
    s = dict(default_settings(), rebar_manual_weight={"پی": 20000.0})
    lines = [
        {"code": "080105", "unit": "مترمکعب", "sources": [{"group": "پی", "qty": 100.0}]},
        {"code": "070202", "unit": "کیلوگرم", "sources": [{"group": "پی", "qty": 20000.0}]},
    ]
    warns = []
    _eng(s)._rebar_density_warnings(lines, warns)
    assert len(warns) == 1
    assert warns[0]["level"] == "اطلاع"


def test_T90_status_and_levels():
    """شمارش سطوح و پرچم «ناقص» در حالت پیش‌فرض (طبقات ناقص)."""
    r = _pipeline(default_settings())
    by_level = r["warnings_by_level"]
    assert by_level["خطا"] == 1
    assert r["status"]["errors"] == 1
    assert r["status"]["complete"] is False
    # با تکمیل مساحت طبقات دیگر خطایی نباید باشد
    areas = {n: 63.0 for n in ("Foundation Top", "Story1", "Story2", "Story3",
                               "Story4", "Story5", "Story6")}
    r2 = _pipeline(dict(default_settings(), floors_data=areas))
    assert r2["status"]["errors"] == 0
    assert r2["status"]["complete"] is True
