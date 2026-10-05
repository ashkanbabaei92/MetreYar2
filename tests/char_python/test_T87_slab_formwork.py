# -*- coding: utf-8 -*-
# T87 — قالب‌بندی دال مستقل (ایراد ۲ — مرحلهٔ ۱۳).
#
# المان‌های مستقل Floors/Slab به ردیف ۰۶۰۴۰۱ (تاوه/دال ≤ ۳/۵ متر) نگاشت
# می‌شوند. در پروژهٔ مرجع: SL01-ST01 = ۱۱ مترمربع → ۱۱ × ۴٬۱۰۷٬۰۰۰ =
# ۴۵٬۱۷۷٬۰۰۰ ریال افزایش پایه.
# هر سطح قالب نگاشت‌نشده → هشدار «قالب بدون ردیف» در رجیستری مرکزی.
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

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


def _mktable(kind, rows):
    return {"file_name": "t.txt", "title": "T", "headers": [],
            "kind": kind, "kind_conf": 0.9, "col_map": {}, "warnings": [],
            "grand_total": {},
            "rows": [{"cells": [], "values": v, "texts": t, "is_subtotal": False}
                     for v, t in rows]}


def test_T87_real_project_slab_formwork():
    """SL01 (دال مستقل) → ۰۶۰۴۰۱ با ۱۱ مترمربع."""
    r = _pipeline(default_settings())
    line = next(l for l in r["lines"] if l["id"] == "form-slab")
    assert line["code"] == "060401"
    assert line["price"] == 4107000.0
    assert line["qty"] == pytest.approx(11.0, abs=1e-6)
    assert line["total"] == pytest.approx(45177000.0, abs=1.0)
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)


def test_T87_joist_topping_excluded():
    """رویهٔ سقف تیرچه‌بلوک (JSL-TOP01، ۵۲ m²) در فصل ۰۶ قیمت‌گذاری نمی‌شود."""
    r = _pipeline(default_settings())
    by_id = {l["id"]: l for l in r["lines"]}
    assert "form-slab" in by_id
    slab_src_refs = {sr["ref"] for sr in by_id["form-slab"]["sources"]}
    assert "JSL-TOP01-ST01" not in slab_src_refs
    assert "SL01-ST01" in slab_src_refs


def test_T87_joist_formwork_info_warnings():
    """قالب تیرچه (JSL) داخل نرخ ۱۰۰۳۰۵ است → هشدار اطلاع، نه خطا."""
    r = _pipeline(default_settings())
    msgs = [w for w in r["warnings"] if w["category"] == "قالب بدون ردیف"]
    items = {w["item"] for w in msgs}
    assert "JSL-TOP01-ST01" in items
    assert "JSL01-ST01" in items
    assert all(w["level"] == "اطلاع" for w in msgs)


def test_T87_unpriced_formwork_warns():
    """المان قالب بدون ردیف (مثل دیوار) → هشدار سطح «هشدار»."""
    tbl = _mktable("formwork_super", [
        ({"area": 7.5}, {"mark": "ZZ99-ST01", "category": "Walls",
                         "familyType": "Wall: Weird"}),
    ])
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    recs = eng._records_from_table(tbl)
    warns = []
    eng._unpriced_formwork_warnings([], recs, warns)
    assert len(warns) == 1
    assert warns[0]["level"] == "هشدار"
    assert warns[0]["item"] == "ZZ99-ST01"
    assert "۷.۵" in warns[0]["message"]


def test_T87_height_tier_setting():
    """انتخاب ردیف بر اساس ارتفاع طبقه (تنظیم slab_formwork_height_m)."""
    s = dict(default_settings(), slab_formwork_height_m=6.0)
    eng = TechnicalOfficeEngine(_default_fehrest_db(), s)
    plans = {p["id"]: p for p in eng._plans()}
    assert plans["form-slab"]["target"] == "060403"      # بیش از ۵/۵ تا ۷/۵ متر
    assert plans["form-slab"]["price"] == 5287000.0
    s2 = dict(default_settings(), slab_formwork_height_m=4.0)
    eng2 = TechnicalOfficeEngine(_default_fehrest_db(), s2)
    assert {p["id"]: p for p in eng2._plans()}["form-slab"]["target"] == "060402"
