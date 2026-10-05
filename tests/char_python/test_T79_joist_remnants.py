# -*- coding: utf-8 -*-
# T79 — بقایای سقف تیرچه‌بلوک در ردیف بتن (مرحلهٔ ۱۱ بخش ۲).
#
# فصل ۱۰ بند ۳ (الزامات عمومی): نرخ ۱۰۰۳۰۵ (سقف تیرچه‌بلوک) شامل تمام
# مصالح سقف به‌جز میلگرد است → بتن پاشنهٔ تیرچه (joist_materials) دیگر
# به ردیف ۰۸۰۱۰۶ اضافه نمی‌شود؛ پاشنه کلاً حذف می‌شود.
#
# فصل ۱۰ بند ۹: بتن تا ۵ cm روی بلوک داخل نرخ ۱۰۰۳۰۵ است → معادل
# ۰٫۰۵ × مساحت ۱۰۰۳۰۵ از حجم رویهٔ JSL-TOP* کسر می‌شود و فقط مازاد بر آن
# در ردیف ۰۸۰۱۰۶ می‌ماند:
#     مساحت ۱۰۰۳۰۵ = 74.48456 × 0.55 = 40.966508 m²
#     سهم داخل نرخ = 0.05 × 40.966508 = 2.048325 m³
#     حجم رویهٔ JSL-TOP01 = 2.58 m³ → باقی‌مانده = 0.531675 m³
# دال ساده (SL01) سراسر محاسبه می‌شود (تغییری نمی‌یابد).
import os
import sys

import pytest

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
    """جدول مینیمال ساختگی برای آزمایش مستقیم قاعدهٔ بقایای رویه."""
    return {"file_name": "t.txt", "title": "T", "headers": [],
            "kind": kind, "kind_conf": 0.9, "col_map": {}, "warnings": [],
            "grand_total": {},
            "rows": [{"cells": [], "values": v, "texts": t, "is_subtotal": False}
                     for v, t in rows]}


def test_T79_heel_removed_from_concrete_rows():
    """پاشنهٔ تیرچه (JSL01-ST01، ۰٫۳۴ m³، kind=joist_materials) حذف می‌شود.

    هیچ ردیف فهرست‌بهایی از رکوردهای joist_materials تغذیه نمی‌کند؛
    جدول «بتن پاشنه و یونولیت» در پروژهٔ نمونه اکنون صفر خط تولید می‌کند.
    """
    r = _pipeline(default_settings())
    for l in r["lines"]:
        for src in l.get("sources", []):
            assert src.get("kind") != "joist_materials", (l["id"], src)
    # ردیف ۰۸۰۱۰۶ شامل دال ساده + باقی‌ماندهٔ رویه است؛ پاشنه در آن نیست
    slab = next(l for l in r["lines"] if l["id"] == "conc-slab")
    refs = {src.get("ref") for src in slab["sources"]}
    assert "SL01-ST01" in refs
    assert "JSL-TOP01-ST01" in refs
    # هیچ منبعی مقدار ۰٫۳۴ (پاشنه) ندارد
    assert not any(abs((src.get("qty") or 0) - 0.34) < 1e-9
                   for l in r["lines"] for src in l.get("sources", []))


def test_T79_topping_residual_values():
    """مقادیر دقیق: مساحت، سهم داخل نرخ، باقی‌مانده و کمیت نهایی سقف."""
    r = _pipeline(default_settings())
    slab = next(l for l in r["lines"] if l["id"] == "conc-slab")
    jb = next(l for l in r["lines"] if l["id"] == "joist-block")
    area = jb["qty"]
    assert area == pytest.approx(40.966508, abs=1e-6)
    # سهم داخل نرخ ۱۰۰۳۰۵
    allowance = 0.05 * area
    assert allowance == pytest.approx(2.0483254, abs=1e-6)
    # باقی‌ماندهٔ رویه = ۲٫۵۸ − ۲٫۰۴۸۳۲۵
    topping_srcs = [src for src in slab["sources"]
                    if (src.get("ref") or "").startswith("JSL-TOP")]
    residual = sum(src["qty"] for src in topping_srcs)
    assert residual == pytest.approx(2.58 - allowance, abs=1e-6)
    assert residual == pytest.approx(0.531675, abs=1e-6)
    # دال ساده سراسر + باقی‌مانده
    plain = [src for src in slab["sources"]
             if not (src.get("ref") or "").startswith("JSL-TOP")]
    assert sum(s["qty"] for s in plain) == pytest.approx(2.1, abs=1e-6)
    assert slab["qty"] == pytest.approx(2.1 + residual, abs=1e-6)
    assert slab["qty"] == pytest.approx(2.631675, abs=1e-6)


def test_T79_sl01_unchanged_and_note_documents_deduction():
    """SL01 تغییر نمی‌کند و یادداشت ردیف کسر را مستند می‌کند."""
    r = _pipeline(default_settings())
    slab = next(l for l in r["lines"] if l["id"] == "conc-slab")
    sl01 = [src for src in slab["sources"] if src.get("ref") == "SL01-ST01"]
    assert len(sl01) == 1
    assert sl01[0]["qty"] == pytest.approx(2.1, abs=1e-6)
    note = slab.get("note") or ""
    assert "۱۰۰۳۰۵" in note
    assert "بند ۹" in note


def test_T79_general_logic_multiple_topping_marks():
    """قاعدهٔ عام برای هر تعداد علامت JSL-TOP*: کسر متناسب با حجم هر کدام.

    دو رویهٔ ۱ m³ هر کدام + یک دال ۲٫۵ m³ + ۱۰ m تیرچه → مساحت ۵٫۵ m²،
    سهم داخل نرخ ۰٫۲۷۵ m³، سهم هر رویه ۰٫۱۳۷۵ m³ → باقی‌ماندهٔ هر کدام
    ۰٫۸۶۲۵ m³؛ کمیت سقف = ۲٫۵ + ۱٫۷۲۵ = ۴٫۲۲۵ m³.
    """
    tables = [
        _mktable("structural_concrete", [
            ({"volume": 1.0}, {"mark": "JSL-TOP01", "category": "Floor",
                               "familyType": "Slab"}),
            ({"volume": 1.0}, {"mark": "JSL-TOP02", "category": "Floor",
                               "familyType": "Slab"}),
            ({"volume": 2.5}, {"mark": "SL01", "category": "Floor",
                               "familyType": "Slab"}),
        ]),
        _mktable("joist_floor", [
            ({"length": 10.0, "count": 1}, {"mark": "JSL01-ST01", "level": "L0"}),
        ]),
    ]
    r = TechnicalOfficeEngine(_default_fehrest_db(), default_settings()).compute(tables, None)
    slab = next(l for l in r["lines"] if l["id"] == "conc-slab")
    assert slab["qty"] == pytest.approx(4.225, abs=1e-9)
    jb = next(l for l in r["lines"] if l["id"] == "joist-block")
    assert jb["qty"] == pytest.approx(5.5, abs=1e-9)
    # هر دو علامت رویه با کسر متناسب
    by_ref = {src["ref"]: src["qty"] for src in slab["sources"]}
    assert by_ref["JSL-TOP01"] == pytest.approx(0.8625, abs=1e-9)
    assert by_ref["JSL-TOP02"] == pytest.approx(0.8625, abs=1e-9)
    assert by_ref["SL01"] == pytest.approx(2.5, abs=1e-9)
