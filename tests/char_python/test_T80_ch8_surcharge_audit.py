# -*- coding: utf-8 -*-
# T80 — حسابرسی پایهٔ اضافه‌بهای فصل ۸ (مرحلهٔ ۱۱ بخش ۳).
#
# فصل ۸ بند ۳-۵: ردیف‌های ۰۸۰۳۰۱/۰۸۰۳۰۲/۰۸۰۳۰۴/۰۸۰۳۱۰/۰۸۰۳۱۱ به سقف
# تیرچه‌بلوک تعلق نمی‌گیرد → حجم JSL (تیرچه + رویهٔ JSL-TOP*) از پایهٔ
# همهٔ اضافه‌بها کسر می‌شود.
# فصل ۸ بند ۳-۳ (۰۸۰۳۰۴): فقط دال روی زمین (ردیفی که در جدول خودش هم
# حجم و هم مساحت دارد)؛ سقف‌های معلق شامل نمی‌شوند.
# فصل ۸ بند ۳-۶ (۰۸۰۳۱۰): per-element — فقط المان‌های با تراکم خودشان
# بالای ۱۸۰ kg/m³، نه میانگین پروژه.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 REBAR_DENSITY_THRESHOLD, _default_fehrest_db, default_settings,
                 rebar_density, thin_concrete_net)

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


def test_T80_real_project_no_surcharges_fire():
    """روی پروژهٔ نمونه با هر سه تنظیم فعال، فقط ۰۸۰۳۰۴ اضافه می‌شود.

    ۰۸۰۳۱۱: تراکم ≈ ۳۱ kg/m³ < ۱۸۰. ۰۸۰۳۱۰: بالاترین تراکم المانی
    (B04-ST01) = ۱۵۳٫۹۷ < ۱۸۰. ۰۸۰۳۰۴: بتن مگر کف روی زمین (۹٫۹۷ cm).
    """
    off = _pipeline(default_settings())
    on_settings = dict(default_settings(),
                       surcharge_rebar_density=True,
                       surcharge_reinforced_concrete=True,
                       surcharge_thin_concrete=True)
    on = _pipeline(on_settings)
    codes = [l["code"] for l in on["lines"]]
    assert codes.count("080304") == 1
    assert "080310" not in codes
    assert "080311" not in codes
    assert len(on["lines"]) == len(off["lines"]) + 1
    thin = next(l for l in on["lines"] if l["code"] == "080304")
    assert thin["qty"] == pytest.approx(18.65, abs=1e-6)
    assert on["base_total"] == pytest.approx(off["base_total"] + thin["total"], abs=1.0)


def test_T80_thin_net_excludes_joist_and_suspended():
    """پایهٔ ۰۸۰۳۰۴: فقط ردیف دارای حجم+مساحت در جدول خودش (دال روی زمین)."""
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    # بتن مگر: 18.65 m³ بر 125 m² → 14.97 cm ≤ 15 ✓
    assert thin_concrete_net(tables) == pytest.approx(18.65, abs=1e-6)
    # JSL-TOP01 (رویهٔ سقف معلق) مساحت هم‌جدولی ندارد → هرگز ارزیابی نمی‌شود
    joist_sys = TechnicalOfficeEngine._joist_system_refs(tables)
    assert "JSL-TOP01-ST01" in joist_sys


def test_T80_synth_bases_exclude_joist_system():
    """پایهٔ هر سه اضافه‌بها حجم JSL را کسر می‌کند (بند ۳-۵).

    المان‌ها: DENSE-01 (ستون ۱ m³، ۲۰۰ kg → ۲۰۰ > ۱۸۰)، SL-G (دال روی
    زمین ۱ m³ و ۸ m² → ۱۲٫۵ cm ≤ ۱۵ ✓)، JSL-TOP01 (رویهٔ ۲٫۵۸ m³، ۵۰۰ kg
    → ۱۹۳٫۸ > ۱۸۰ اما مستثنی).
    """
    tables = [
        _mktable("structural_concrete", [
            ({"volume": 1.0}, {"mark": "DENSE-01", "category": "Structural Column",
                               "familyType": "Column"}),
            ({"volume": 1.0, "area": 8.0}, {"mark": "SL-G", "category": "Floor",
                                            "familyType": "Slab"}),
            ({"volume": 2.58}, {"mark": "JSL-TOP01", "category": "Floor",
                                "familyType": "Slab"}),
        ]),
        _mktable("joist_floor", [
            ({"length": 5.0, "count": 1}, {"mark": "JSL01-ST01", "level": "L0"}),
        ]),
        _mktable("rebar_detailed", [
            ({"weight": 200.0}, {"hostMark": "DENSE-01"}),
            ({"weight": 500.0}, {"hostMark": "JSL-TOP01"}),
        ]),
    ]
    s = dict(default_settings(),
             surcharge_rebar_density=True,
             surcharge_reinforced_concrete=True,
             surcharge_thin_concrete=True)
    r = TechnicalOfficeEngine(_default_fehrest_db(), s).compute(tables, None)
    by = {l["code"]: l["qty"] for l in r["lines"]}

    # ۰۸۰۳۰۴: فقط SL-G (دال روی زمین)؛ JSL-TOP01 مساحت ندارد ولی حتی
    # اگر داشت مستثنی بود (سقف معلق)
    assert by["080304"] == pytest.approx(1.0, abs=1e-9)
    # ۰۸۰۳۱۰: فقط DENSE-01؛ JSL-TOP01 با وجود تراکم ۱۹۳٫۸ > ۱۸۰ مستثنی است
    assert by["080310"] == pytest.approx(1.0, abs=1e-9)
    # ۰۸۰۳۱۱: پایه = حجم سازه‌ای بدون JSL = ۱ + ۱ = ۲ m³ (رویه مستثنی)
    assert by["080311"] == pytest.approx(2.0, abs=1e-9)
    # تراکمی که اضافه‌بها را روشن می‌کند: ۷۰۰ kg ÷ ۲ m³ = ۳۵۰ > ۱۸۰
    assert rebar_density(700.0, 2.0) > REBAR_DENSITY_THRESHOLD
