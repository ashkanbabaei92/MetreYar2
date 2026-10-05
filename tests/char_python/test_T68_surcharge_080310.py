# -*- coding: utf-8 -*-
# T68 - اضافه‌بهای بتن مسلح (ردیف ۰۸۰۳۱۰ فهرست‌بهای ۱۴۰۴).
#
# شرط رسمی (فصل ۸ بند ۳-۶): «اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت مصرف
# بتن در بتن مسلح» (۱۴۵٬۵۰۰ ریال/m³). مدرک «مسلح بودن» ستون «Host Mark»
# جدول آرماتور است: تراکم میلگرد هر المان = وزن آرماتورِ میزبانِ همان
# مارک ÷ حجم همان المان. برخلاف گذشته، فقط المان‌هایی که **تراکم خودشان**
# > ۱۸۰ kg/m³ است مشمول می‌شوند (نه میانگین پروژه). حجم سیستم سقف
# تیرچه‌بلوک (تیرچه + رویهٔ JSL-TOP*) از مبنای اضافه‌بها کسر می‌شود
# (بند ۳-۵: به سقف تیرچه‌بلوک تعلق نمی‌گیرد) و بتن مگر (lean) هرگز مسلح
# نیست. مقدار خالص است (بدون ضریب پرت — مرحلهٔ ۱۱ بخش ۱).
#
# نکتهٔ مهم: در پروژهٔ نمونه، متراکم‌ترین المان B04-ST01 با ۴۹۱٫۱۶ kg بر
# ۳٫۱۹ m³ = ۱۵۳٫۹۷ kg/m³ است — زیر آستانه. بنابراین فعال کردن این تنظیم
# روی دادهٔ واقعی هیچ ردیفی اضافه نمی‌کند (قانون per-element، برخلاف
# میانگین پروژه) و همان رفتار آزمون می‌شود. بخشی از وزن آرماتور
# (۲٬۴۹۱٫۷۸ kg ≈ ۲۱٪) در دستهٔ «<varies>» قرار دارد که به هیچ المانی
# قابل انتساب نیست.
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings, structural_group,
                 REBAR_DENSITY_THRESHOLD)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


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


def _mktable(kind, rows):
    """جدول مینیمال ساختگی برای آزمایش مستقیم قاعدهٔ per-element."""
    return {"file_name": "t.txt", "title": "T", "headers": [],
            "kind": kind, "kind_conf": 0.9, "col_map": {}, "warnings": [],
            "grand_total": {},
            "rows": [{"cells": [], "values": v, "texts": t, "is_subtotal": False}
                     for v, t in rows]}


def test_T68_host_category_retained():
    """پارسر ستون‌های «Host Category» و «Host Mark» جدول آرماتور را نگه می‌دارد.

    مقدار خام این ستون‌ها برای ردیف‌های واقعی خوانده می‌شود. هیچ ستون
    دیگری حذف یا تغییر نام نمی‌یابد.
    """
    path = os.path.join(REVIT_DIR, "جدول ریزمتره آرماتورها - Structural Rebar Schedule.txt")
    with open(path, "r", encoding="utf-8-sig") as fh:
        t = RevitScheduleParser.parse(os.path.basename(path), fh.read())
    assert t["kind"] == "rebar_detailed"

    cats, total = {}, 0.0
    for r in t["rows"]:
        c = (r["texts"].get("hostCategory") or "").strip()
        assert c  # هر ردیف آرماتور واقعی دارای Host Category است
        cats[c] = cats.get(c, 0) + (r["values"].get("weight", 0) or 0)
        total += r["values"].get("weight", 0) or 0

    # دسته‌های میزبان موجود در پروژهٔ نمونه
    assert set(cats) == {"Structural Foundation", "Structural Column", "Structural Framing",
                         "Stairs", "Floor", "Wall", "<varies>"}
    # بیشترین وزن متعلق به پی است (۱۰٬۳۹۲٫۴ kg)
    assert cats["Structural Foundation"] == pytest.approx(10392.40, abs=0.5)
    assert total == pytest.approx(12103.46, abs=0.5)

    # پل نگاشت Host Category → گروه سازه‌ای (مبنای تشخیص بتن مسلح)
    assert structural_group("Structural Framing") == "تیر"
    assert structural_group("Structural Column") == "ستون"
    assert structural_group("Structural Foundation") == "پی"
    assert structural_group("Floor") == "سقف"
    assert structural_group("Stairs") == "پله"
    assert structural_group("Wall") == "دیوار"
    assert structural_group("<varies>") == "سایر"  # نامعلوم → مدرک نمی‌شود


def test_T68_surcharge_off_by_default():
    """پیش‌فرض: تنظیم خاموش است و ردیف ۰۸۰۳۱۰ وجود ندارد و totals مرجع است."""
    assert default_settings()["surcharge_reinforced_concrete"] is False
    r = _pipeline(default_settings())
    assert len(r["lines"]) == 17
    assert not any(l["code"] == "080310" for l in r["lines"])
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


def test_T68_surcharge_on_but_below_threshold_no_line():
    """فعال‌سازی روی دادهٔ نمونه: متراکم‌ترین المان ۱۵۳٫۹۷ < ۱۸۰ → ردیفی نیست.

    قانون per-element (بند ۳-۶) برخلاف میانگین پروژه است: حتی اگر میانگین
    پروژه > ۱۸۰ باشد، فقط المان‌های تراکم بالای آستانه مشمول می‌شوند. در
    پروژهٔ نمونه هیچ المانی از آستانه عبور نمی‌کند، پس totals بی‌تغییر
    می‌مانند (و چون سمت TS همین محاسبات را می‌کند، برابری دو زبان حفظ
    می‌شود).
    """
    off = _pipeline(default_settings())
    s = default_settings()
    s["surcharge_reinforced_concrete"] = True
    on = _pipeline(s)

    assert len(on["lines"]) == len(off["lines"]) == 17
    assert not any(l["code"] == "080310" for l in on["lines"])
    assert on["base_total"] == off["base_total"]
    assert on["grand_total"] == off["grand_total"]
    assert on["base_total"] == pytest.approx(23218381337.01, abs=1.0)


def test_T68_per_element_rule():
    """قاعدهٔ per-element روی دادهٔ ساختگی: فقط المان با تراکم خودش > ۱۸۰.

    DENSE-01: ۲۰۰ kg / ۱٫۰ m³ = 200 > 180 → مشمول.
    LIGHT-01: ۱۰۰ kg / ۱۰٫۰ m³ = 10 → مشمول نیست.
    EDGE-01:   ۳۶۰ kg / ۲٫۰ m³ = 180 → دقیقاً برابر آستانه، مشمول نیست.
    JSL-TOP01: ۵۰۰ kg / ۱٫۰ m³ = 500 → رویهٔ تیرچه‌بلوک → مستثنی (بند ۳-۵).
    دستهٔ «<varies>» → به هیچ المانی انتساب ندارد → مستثنی.
    """
    db = [
        {"code": "080107", "chapter": "08", "desc": "بتن درجای ستون‌ها و تیرها",
         "unit": "مترمکعب", "price": 1000000, "estimated": False},
        {"code": "080310", "chapter": "08",
         "desc": "اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت مصرف بتن در بتن مسلح",
         "unit": "مترمکعب", "price": 145500, "estimated": False},
    ]
    tables = [
        _mktable("structural_concrete", [
            ({"volume": 1.0}, {"mark": "DENSE-01", "category": "Structural Column",
                               "familyType": "Column", "level": "L0"}),
            ({"volume": 10.0}, {"mark": "LIGHT-01", "category": "Structural Column",
                                "familyType": "Column", "level": "L0"}),
            ({"volume": 2.0}, {"mark": "EDGE-01", "category": "Structural Column",
                               "familyType": "Column", "level": "L0"}),
            ({"volume": 1.0}, {"mark": "JSL-TOP01-ST01", "category": "Floor",
                               "familyType": "Slab", "level": "L0"}),
        ]),
        _mktable("rebar_detailed", [
            ({"weight": 200.0}, {"hostMark": "DENSE-01"}),
            ({"weight": 100.0}, {"hostMark": "LIGHT-01"}),
            ({"weight": 360.0}, {"hostMark": "EDGE-01"}),
            ({"weight": 500.0}, {"hostMark": "JSL-TOP01-ST01"}),
            ({"weight": 999.0}, {"hostMark": "<varies>"}),
        ]),
    ]
    s = default_settings()
    s["surcharge_reinforced_concrete"] = True
    eng = TechnicalOfficeEngine(db, s)
    res = eng.compute(tables, None)

    sc = [l for l in res["lines"] if l["code"] == "080310"]
    assert len(sc) == 1
    line = sc[0]
    assert line["id"] == "surcharge-080310"
    assert line["unit"] == "مترمکعب"
    assert line["price"] == pytest.approx(145500.0, abs=0.5)
    # فقط DENSE-01 (۱٫۰ m³)؛ EDGE-01 دقیقاً ۱۸۰ است و مشمول نمی‌شود
    assert line["qty"] == pytest.approx(1.0, abs=1e-9)
    assert line["total"] == pytest.approx(1.0 * 145500.0, abs=1.0)
    assert line["method"] == "rule-exact"
    assert "DENSE-01" in line["note"]
    assert "EDGE-01" not in line["note"]


if __name__ == "__main__":
    test_T68_host_category_retained()
    test_T68_surcharge_off_by_default()
    test_T68_surcharge_on_but_below_threshold_no_line()
    test_T68_per_element_rule()
    print("T68 ok")
