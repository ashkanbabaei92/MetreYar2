# -*- coding: utf-8 -*-
# T86 — نگاشت مقاومت فشاری بتن به ردیف فصل ۸ (ایراد ۱ — مرحلهٔ ۱۳).
#
# تقدم رسمی: پارامتر صریح Revit > نام متریال > ورودی دستی.
# در پروژهٔ مرجع، FT* در جدول بتن سازه‌ای متریال «35 MPa» دارند →
# ردیف پی از ۰۸۰۱۰۵ (۲۰ MPa) به ۰۸۰۱۰۸ (۳۵ MPa) تغییر می‌کند:
#   ۱۵۲٫۸۳ × (۲۱٬۴۲۲٬۰۰۰ − ۱۹٬۵۳۵٬۰۰۰) = ۲۸۸٬۳۹۵٬۰۱۰ ریال افزایش پایه.
# جداول بدون ستون متریال (جدول اختصاصی پی) مقاومت را از جدولی دیگر
# برای همان مرجع می‌گیرند.
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings, parse_concrete_strength)

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


# ── تجزیهٔ نام متریال ──
@pytest.mark.parametrize("text,expected", [
    ("Concrete - Cast-in-Place Concrete - 35 MPa", 35),
    ("CONCRETE - 25 Mpa", 25),
    ("۳۰ مگاپاسکال", 30),
    ("C40", 40),
    ("C 30", 30),
    ("f'c=35", 35),
    ("fc35", 35),
    ("CONCRETE", None),
    ("Concrete, Cast-in-Place gray", None),
    ("Column: C 45×45", None),      # ابعاد مقطع، نه مقاومت
    ("C30/37", None),               # دارای خط کسر
])
def test_T86_parse_strength(text, expected):
    assert parse_concrete_strength(text) == expected


def test_T86_real_project_foundation_is_35mpa():
    """متریال Revit پی ۳۵ مگاپاسکال است → ردیف ۰۸۰۱۰۸."""
    r = _pipeline(default_settings())
    line = next(l for l in r["lines"] if l["id"] == "conc-foundation")
    assert line["code"] == "080108"
    assert line["price"] == 21422000.0
    assert line["qty"] == pytest.approx(152.83, abs=1e-6)
    assert line["total"] == pytest.approx(3273924260.0, abs=1.0)
    assert line["strength_mpa"] == 35
    assert line["strength_origin"] == "material"
    # کل افزایش پایه نسبت به حالت ۲۰ مگاپاسکال
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)


def test_T86_base_delta_exactly_288_million():
    """اختلاف پایه دقیقاً ۱۵۲٫۸۳ × (۲۱٬۴۲۲٬۰۰۰ − ۱۹٬۵۳۵٬۰۰۰) = ۲۸۸٬۳۹۰٬۲۱۰ ریال."""
    r = _pipeline(default_settings())
    old_foundation = 152.83 * 19535000.0
    others = r["base_total"] - 3273924260.0    # پایه بدون ردیف پی جدید
    assert r["base_total"] - (others + old_foundation) == \
        pytest.approx(288390210.0, abs=1.0)
    assert 152.83 * (21422000.0 - 19535000.0) == pytest.approx(288390210.0, abs=0.5)


def test_T86_other_groups_use_settings():
    """گروه‌های بدون متریال صریح از تنظیمات کاربر استفاده می‌کنند."""
    r = _pipeline(default_settings())
    by_id = {l["id"]: l for l in r["lines"]}
    assert by_id["conc-col-beam"]["code"] == "080107"      # ۳۰ مگاپاسکال (تنظیم)
    assert by_id["conc-col-beam"]["strength_origin"] == "setting"
    assert by_id["conc-slab"]["code"] == "080106"          # ۲۵ مگاپاسکال (تنظیم)
    assert by_id["conc-stair"]["code"] == "080105"         # ۲۰ مگاپاسکال (تنظیم)


def test_T86_unknown_strength_warns_and_skips():
    """مقاومت خارج از جدول → هشدار خطا و عدم انتخاب ردیف پیش‌فرض."""
    tbl = _mktable("structural_concrete", [
        ({"volume": 10.0}, {"mark": "X01", "category": "Structural Columns",
                            "familyType": "Column: X", "material": "Concrete - 50 MPa"}),
    ])
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    recs = eng._records_from_table(tbl)
    assert recs[0]["strength_mpa"] == 50
    buckets = eng._concrete_buckets("conc-col-beam", recs, [tbl], {})
    assert 50 in buckets and abs(buckets[50]["qty"] - 10.0) < 1e-9
    lines, warns = [], []
    plan = {"id": "conc-col-beam", "target": "080107", "query": "q", "desc": "d",
            "unit": "مترمکعب", "price": 20924000.0}
    eng._emit_concrete_line(plan, 50, buckets[50], 1, set(), lines, warns)
    assert len(lines) == 0                     # ردیف پیش‌فرض انتخاب نمی‌شود
    assert len(warns) == 1 and warns[0]["level"] == "خطا"


def test_T86_mixed_strengths_split_lines():
    """دو مقاومت متفاوت در یک گروه → دو ردیف جداگانه با پسوند @mpa."""
    tbl = _mktable("structural_concrete", [
        ({"volume": 10.0}, {"mark": "A01", "category": "Structural Columns",
                            "familyType": "Column: A", "material": "CONCRETE"}),
        ({"volume": 5.0}, {"mark": "A02", "category": "Structural Columns",
                           "familyType": "Column: A2",
                           "material": "Concrete - 40 MPa"}),
    ])
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    recs = eng._records_from_table(tbl)
    buckets = eng._concrete_buckets("conc-col-beam", recs, [tbl], {})
    assert set(buckets) == {30, 40}            # ۳۰ از تنظیم، ۴۰ از متریال
    lines, warns = [], []
    plan = {"id": "conc-col-beam", "target": "080107", "query": "q", "desc": "d",
            "unit": "مترمکعب", "price": 20924000.0}
    for mpa, b in buckets.items():
        eng._emit_concrete_line(plan, mpa, b, len(buckets), set(), lines, warns)
    assert len(lines) == 2
    ids = {l["id"]: l for l in lines}
    assert ids["conc-col-beam"]["code"] == "080107"       # سطل تنظیم، شناسهٔ ساده
    assert ids["conc-col-beam@40"]["code"] == "080109"    # سطل متریال، شناسهٔ پسونددار


def test_T86_config_json_is_data_source():
    """جدول نگاشت از config/concrete_strength_map.json بارگذاری می‌شود."""
    from app import CONCRETE_STRENGTH_CODES
    assert CONCRETE_STRENGTH_CODES[35] == ("080108", 21422000.0)
    assert CONCRETE_STRENGTH_CODES[20] == ("080105", 19535000.0)
