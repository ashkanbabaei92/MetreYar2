# -*- coding: utf-8 -*-
# T70 - فرض‌های فنی پروژه به‌عنوان تنظیمات رابط کاربری (مرحلهٔ ۷).
#
# مقاومت فشاری بتن به تفکیک گروه، عیار سیمان بتن مگر و ضخامت سقف
# تیرچه‌بلوک دیگر در _plans() ثابت نیستند؛ از تنظیمات خوانده می‌شوند و
# کد فهرست‌بها از جداول نگاشتِ ماژول انتخاب می‌شود:
#   MPa:  ۱۲→۰۸۰۱۰۳  ۱۶→۰۸۰۱۰۴  ۲۰→۰۸۰۱۰۵  ۲۵→۰۸۰۱۰۶  ۳۰→۰۸۰۱۰۷  ۳۵→۰۸۰۱۰۸  ۴۰→۰۸۰۱۰۹
#   مگر:  ۱۰۰→۰۸۰۱۰۱  ۱۵۰→۰۸۰۱۰۲
#   سقف:  ۲۵→۱۰۰۳۰۵  ۳۰→۱۰۰۳۰۶
# قیمت ردیف از فایل رسمی ۱۴۰۴ خوانده می‌شود (method=rule-exact).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (CONCRETE_STRENGTH_CODES, JOIST_BLOCK_THICKNESS_CODES,
                 LEAN_CEMENT_CODES, DynamoMappingParser, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

CONC_IDS = ["conc-foundation", "conc-col-beam", "conc-slab", "conc-stair"]


def _pipeline(settings):
    """اجرای پایپ‌لاین واقعی (۱۰ جدول Revit + نگاشت Dynamo) با تنظیمات داده‌شده."""
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


def _line(result, plan_id):
    return next(l for l in result["lines"] if l["id"] == plan_id)


def test_T70_defaults_match_reference():
    """پیش‌فرض‌های فنی روی دادهٔ مرجع → اعداد مرجع مرحلهٔ ۱۱."""
    s = default_settings()
    assert s["concrete_strength_mpa"] == {"foundation": 20, "column_beam": 30,
                                          "slab": 25, "stair": 20}
    assert s["lean_cement_kg"] == 150
    assert s["joist_block_thickness_cm"] == 25

    r = _pipeline(s)
    assert len(r["lines"]) == 17
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)
    # کدهای پیش‌فرض روی دادهٔ مرجع — پی از نام متریال Revit: ۳۵ مگاپاسکال (ایراد ۱)
    assert _line(r, "lean")["code"] == "080102"
    assert _line(r, "conc-foundation")["code"] == "080108"
    assert _line(r, "conc-col-beam")["code"] == "080107"
    assert _line(r, "conc-slab")["code"] == "080106"
    assert _line(r, "conc-stair")["code"] == "080105"
    assert _line(r, "joist-block")["code"] == "100305"


def test_T70_mapping_tables_are_canonical():
    """جداول نگاشت تنها منبع انتخاب کد هستند و مقادیر رسمی ۱۴۰۴ را پوشش می‌دهند."""
    assert CONCRETE_STRENGTH_CODES == {12: ("080103", 17996000.0), 16: ("080104", 18904000.0),
                                       20: ("080105", 19535000.0), 25: ("080106", 20162000.0),
                                       30: ("080107", 20924000.0), 35: ("080108", 21422000.0),
                                       40: ("080109", 22200000.0)}
    assert LEAN_CEMENT_CODES == {100: ("080101", 16039000.0), 150: ("080102", 17152000.0)}
    assert JOIST_BLOCK_THICKNESS_CODES == {25: ("100305", 8391000.0), 30: ("100306", 9101000.0)}


def test_T70_plans_follow_settings():
    """هر مقدار مجاز → کد و بهای درست از فایل ۱۴۰۴ (rule-exact)."""
    db = _default_fehrest_db()
    for mpa, (code, price) in CONCRETE_STRENGTH_CODES.items():
        s = default_settings()
        s["concrete_strength_mpa"].update(foundation=mpa, column_beam=mpa,
                                          slab=mpa, stair=mpa)
        eng = TechnicalOfficeEngine(db, s)
        for pid in CONC_IDS:
            sp = next(p for p in eng._plans() if p["id"] == pid)
            assert sp["target"] == code, (pid, mpa)
            assert sp["price"] == pytest.approx(price, abs=0.5)
            # کد واقعاً در فهرست‌بها موجود است و قیمتش می‌خواند
            row = next((r for r in db if r["code"] == code), None)
            assert row is not None
            assert row["price"] == pytest.approx(price, abs=0.5)
    for kg, (code, price) in LEAN_CEMENT_CODES.items():
        s = default_settings()
        s["lean_cement_kg"] = kg
        sp = next(p for p in TechnicalOfficeEngine(db, s)._plans() if p["id"] == "lean")
        assert sp["target"] == code
        assert sp["price"] == pytest.approx(price, abs=0.5)
    for cm, (code, price) in JOIST_BLOCK_THICKNESS_CODES.items():
        s = default_settings()
        s["joist_block_thickness_cm"] = cm
        sp = next(p for p in TechnicalOfficeEngine(db, s)._plans() if p["id"] == "joist-block")
        assert sp["target"] == code
        assert sp["price"] == pytest.approx(price, abs=0.5)


def test_T70_all_30_mpa():
    """سناریو ۱: همهٔ بتن‌ها ۳۰ مگاپاسکال → ۰۸۰۱۰۷ (۲۰٬۹۲۴٬۰۰۰).

    استثنا (ایراد ۱): پی از نام متریال Revit (۳۵ مگاپاسکال) مشخص شده است و
    تقدم متریال > تنظیمات دارد → ۰۸۰۱۰۸ می‌ماند.
    """
    s = default_settings()
    s["concrete_strength_mpa"].update(foundation=30, column_beam=30, slab=30, stair=30)
    r = _pipeline(s)
    assert len(r["lines"]) == 17
    for pid in CONC_IDS:
        l = _line(r, pid)
        if pid == "conc-foundation":
            assert l["code"] == "080108"                 # متریال Revit تقدم دارد
            assert l["strength_origin"] == "material"
        else:
            assert l["code"] == "080107"
        assert l["price"] == pytest.approx(20924000.0 if pid != "conc-foundation"
                                           else 21422000.0, abs=0.5)
        assert l["method"] == "rule-exact"
    # بتن مگر و سقف تیرچه‌بلوک دست‌نخورده
    assert _line(r, "lean")["code"] == "080102"
    assert _line(r, "joist-block")["code"] == "100305"
    assert r["base_total"] == pytest.approx(23230359693.06, abs=1.0)
    assert r["grand_total"] == pytest.approx(31407446305.01, abs=1.0)


def test_T70_joist_30cm_and_lean_100():
    """سناریو ۲ و ۳: سقف ۳۰cm → ۱۰۰۳۰۶ (۹٬۱۰۱٬۰۰۰)؛ مگر ۱۰۰ → ۰۸۰۱۰۱ (۱۶٬۰۳۹٬۰۰۰)."""
    s = default_settings()
    s["joist_block_thickness_cm"] = 30
    s["lean_cement_kg"] = 100
    r = _pipeline(s)
    jb, lean = _line(r, "joist-block"), _line(r, "lean")
    assert jb["code"] == "100306"
    assert jb["price"] == pytest.approx(9101000.0, abs=0.5)
    assert lean["code"] == "080101"
    assert lean["price"] == pytest.approx(16039000.0, abs=0.5)
    # بقیهٔ ردیف‌های بتن سر جای خودشان (پی از متریال Revit = ۰۸۰۱۰۸، ایراد ۱)
    assert _line(r, "conc-foundation")["code"] == "080108"
    assert _line(r, "conc-col-beam")["code"] == "080107"
    assert _line(r, "conc-slab")["code"] == "080106"
    assert _line(r, "conc-stair")["code"] == "080105"
    assert r["base_total"] == pytest.approx(23226710107.69, abs=1.0)
    assert r["grand_total"] == pytest.approx(31402512065.60, abs=1.0)


if __name__ == "__main__":
    test_T70_defaults_match_reference()
    test_T70_mapping_tables_are_canonical()
    test_T70_plans_follow_settings()
    test_T70_all_30_mpa()
    test_T70_joist_30cm_and_lean_100()
    print("T70 ok")
