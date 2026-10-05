# -*- coding: utf-8 -*-
# T69 - اضافه‌بهای ضخامت کم بتن (ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴).
#
# شرط رسمی (فصل ۸ بند ۳-۳): «اضافه‌بها به ردیف‌های بتن‌ریزی، هرگاه ضخامت
# بتن برابر ۱۵ سانتی‌متر یا کمتر باشد» (۳۰۴٬۰۰۰ ریال/m³). این اضافه‌بها
# مختص **دال روی زمین** (بتن‌ریزی کف روی خاک) است و سقف‌های معلق شامل
# نمی‌شوند. ضخامت **فقط از داده‌های خود پروژه** استخراج می‌شود:
#   فقط ردیفی که در **جدول خودش** هم «حجم» و هم «مساحت» دارد ارزیابی
#   می‌شود → ضخامت = حجم ÷ مساحت. ردیف‌های فاقد مساحتِ هم‌جدولی (دال‌های
#   سقف، پله، تیر، ستون) هرگز ارزیابی نمی‌شوند؛ جفت‌سازی با مساحت
#   قالب‌بندی مجاز نیست چون کناره‌ها/پاها را شامل می‌شود و دیگر نشانگر
#   دال روی زمین نیست.
# این ردیف **اختیاری** است و تنظیم بولین `surcharge_thin_concrete`
# (پیش‌فرض False) آن را فعال می‌کند. مقدار نهایی برابر مقدار خالص است
# (ضریب پرت وجود ندارد — مرحلهٔ ۱۱ بخش ۱).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings, thin_concrete_net,
                 THIN_CONCRETE_THRESHOLD_M)

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
    """جدول مینیمال ساختگی برای آزمایش مستقیم قاعدهٔ ضخامت."""
    return {"file_name": "t.txt", "title": "T", "headers": [],
            "kind": kind, "kind_conf": 0.9, "col_map": {}, "warnings": [],
            "grand_total": {},
            "rows": [{"cells": [], "values": v, "texts": t, "is_subtotal": False}
                     for v, t in rows]}


def test_T69_thin_concrete_rule():
    """قاعدهٔ استخراج ضخامت روی دادهٔ ساختگی: هر چهار شاخص رفتار.

    ۱) بتن مگر (همان‌جدولی): ۱۰ m³ بر ۱۰۰ m² = ۱۰ cm ≤ ۱۵ → نازک.
    ۲) پی (همان‌جدولی): ۲۰ m³ بر ۲۲٫۲ m² = ۹۰ cm > ۱۵ → نازک نیست.
    ۳) دال بدون مساحت در جدول خودش: ارزیابی نمی‌شود (جفت‌سازی با
       قالب‌بندی مجاز نیست — فقط دال روی زمین).
    ۴) پله و تیر: ارزیابی نمی‌شوند.
    ۵) دال ضخیم (۳ m³ بر ۱۰ m² = ۳۰ cm) → نازک نیست.
    """
    tables = [
        _mktable("lean_concrete", [({"volume": 10.0, "area": 100.0},
                                    {"mark": "LC-01", "familyType": "Lean Concrete - 100mm"})]),
        _mktable("structural_concrete", [
            # پی با مساحت همان جدول
            ({"volume": 20.0, "area": 22.2}, {"mark": "FT-1", "familyType": "Wall Foundation: WF_A_1800x900"}),
            # دال نازک بدون مساحت در جدول خودش → ارزیابی نمی‌شود
            ({"volume": 2.0}, {"mark": "SL01", "familyType": "Slab", "category": "Floors"}),
            # دال ضخیم با مساحت همان جدول
            ({"volume": 3.0, "area": 10.0}, {"mark": "SL02", "familyType": "Slab", "category": "Floors"}),
            # پله: ارزیابی نمی‌شود
            ({"volume": 5.0}, {"mark": "STR01", "familyType": "Stair", "category": "Stairs"}),
            # تیر: ارزیابی نمی‌شود
            ({"volume": 3.0}, {"mark": "B01", "familyType": "Beam", "category": "Structural Framing"}),
        ]),
        # مساحت قالب‌بندی دیگر برای جفت‌سازی استفاده نمی‌شود
        _mktable("formwork_super", [
            ({"area": 40.0}, {"mark": "SL01", "category": "Floors"}),
            ({"area": 50.0}, {"mark": "STR01", "category": "Stairs"}),
            ({"area": 100.0}, {"mark": "B01", "category": "Structural Framing"}),
        ]),
    ]
    assert thin_concrete_net(tables) == pytest.approx(10.0, abs=1e-9)
    assert THIN_CONCRETE_THRESHOLD_M == 0.15


def test_T69_thin_concrete_real_data():
    """دادهٔ واقعی: فقط بتن مگر (۹٫۹۷ cm) = ۱۸٫۶۵ m³ نازک.

    بتن مگر: ۱۸٫۶۵ m³ بر ۱۸۷ m² ≈ ۱۰ cm ≤ ۱۵ → نازک. دال‌های سقف (SL01-ST01
    و JSL-TOP01) مساحتِ هم‌جدولی ندارند و طبق فصل ۸ بند ۳-۳ فقط «دال روی
    زمین» مشمول اضافه‌بهای ضخامت می‌شود، بنابراین ارزیابی نمی‌شوند. پی‌ها
    (۹۰ cm) هم ضخیم‌اند. پله‌ها ارزیابی نمی‌شوند.
    """
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    thin = thin_concrete_net(tables)
    assert thin == pytest.approx(18.65, abs=1e-3)


def test_T69_surcharge_off_by_default():
    """پیش‌فرض: تنظیم خاموش است و ردیف ۰۸۰۳۰۴ وجود ندارد و totals مرجع است."""
    assert default_settings()["surcharge_thin_concrete"] is False
    r = _pipeline(default_settings())
    assert len(r["lines"]) == 17
    assert not any(l["code"] == "080304" for l in r["lines"])
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


def test_T69_surcharge_on_adds_line():
    """فعال‌سازی روی دادهٔ نمونه: ۱۸٫۶۵ m³ نازک × ۳۰۴٬۰۰۰ ریال = ۵٬۶۶۹٬۶۰۰ ریال.

    totals دقیقاً برابر مرجع + مقدار این ردیف می‌شود (و چون سمت TS همین
    محاسبات را می‌کند، برابری دو زبان حفظ می‌شود). مقدار خالص است (بدون
    ضریب پرت — مرحلهٔ ۱۱ بخش ۱).
    """
    off = _pipeline(default_settings())
    s = default_settings()
    s["surcharge_thin_concrete"] = True
    on = _pipeline(s)

    assert len(on["lines"]) == 18
    sc = [l for l in on["lines"] if l["code"] == "080304"]
    assert len(sc) == 1
    line = sc[0]
    assert line["id"] == "surcharge-080304"
    assert line["unit"] == "مترمکعب"
    assert line["price"] == pytest.approx(304000.0, abs=0.5)
    assert line["qty"] == pytest.approx(18.65, abs=1e-3)
    assert line["total"] == pytest.approx(18.65 * 304000.0, abs=1.0)
    assert line["method"] == "rule-exact"

    assert on["base_total"] == pytest.approx(off["base_total"] + line["total"], abs=1.0)
    assert on["base_total"] == pytest.approx(23218381337.01 + 18.65 * 304000.0, abs=1.0)


if __name__ == "__main__":
    test_T69_thin_concrete_rule()
    test_T69_thin_concrete_real_data()
    test_T69_surcharge_off_by_default()
    test_T69_surcharge_on_adds_line()
    print("T69 ok")
