# -*- coding: utf-8 -*-
# T78 — حذف کامل ضریب پرت مصالح (مرحلهٔ ۱۱ بخش ۱).
#
# کلیات فهرست‌بهای ۱۴۰۴ (بند ۳ و بند ۱۴) و فصل ۸ بند ۴: افت تراکم کارگاهی،
# اتلاف ناشی از حمل و تخلیه و پرت مصالح، در بهای واحد ردیف‌های فهرست‌بها
# لحاظ شده است. بنابراین هیچ ضریب پرت جداگانه‌ای روی کمیت اعمال نمی‌شود
# و «مقدار نهایی» وجود ندارد: کمیت واحد است و مبلغ = کمیت × بها.
#
# مکانیزم پرت به‌طور کامل حذف شده است — حتی تنظیم پنهانی در UI باقی نمانده
# (شناسهٔ waste/پرت در تنظیمات وجود ندارد). اضافه‌بهای مقاومت سقف تیرچه‌بلوک
# (100701/100702) روی همان مساحت ۱۰۰۳۰۵ محاسبه می‌شود — بدون ضریب ۱٫۰۳.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 OVERHEAD_PRESETS, _default_fehrest_db, default_settings)

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


def test_T78_no_waste_mechanism_anywhere():
    """هیچ ردیفی ضریب پرت یا مقدار نهایی ندارد؛ کمیت و مبلغ one-to-one هستند."""
    r = _pipeline(default_settings())
    assert len(r["lines"]) == 17
    for l in r["lines"]:
        assert "waste_pct" not in l, l["id"]
        assert "qty_final" not in l, l["id"]
        assert "waste" not in l, l["id"]
        # مبلغ = کمیت × بها (هیچ ضریب اضافی روی مقدار نیست)
        assert l["total"] == pytest.approx(l["qty"] * l["price"], rel=1e-9)
        assert l.get("total_indexed", l["total"]) == pytest.approx(l["total"], rel=1e-12)


def test_T78_settings_have_no_waste_key():
    """تنظیمات پیش‌فرض هیچ کلید پرتی ندارد (حتی خاموش)."""
    s = default_settings()
    for k in s:
        assert "waste" not in k.lower(), k
        assert "پرت" not in k, k
    # presets بالاسری هم ضریب پرت نیستند — ضرایب زنجیرهٔ مالی هستند
    assert len(OVERHEAD_PRESETS) == 4
    for _key, val, _label in OVERHEAD_PRESETS:
        assert val in (1.2, 1.3, 1.4)


def test_T78_joist_surcharge_uses_net_area():
    """اضافه‌بهای مقاومت بتن سقف تیرچه‌بلوک روی مساحت خالص ۱۰۰۳۰۵ است.
    مقدار قبلی با ضریب ۱٫۰۳ (پرت ۳٪) محاسبه می‌شد؛ اکنون دقیقاً همان مساحت.
    """
    r = _pipeline(default_settings())
    jb = next(l for l in r["lines"] if l["id"] == "joist-block")
    sc = next(l for l in r["lines"] if l["id"] == "joist-strength-surcharge")
    # مساحت خالص = طول تیرچه × فاصلهٔ محوری = 74.48456 × 0.55
    assert jb["qty"] == pytest.approx(40.966508, abs=1e-6)
    assert sc["qty"] == jb["qty"]  # بدون هیچ ضریبی
    assert sc["code"] == "100701"
    assert sc["total"] == pytest.approx(sc["qty"] * sc["price"], rel=1e-9)
    # ردیف ۱۰۰۷۰۲ (مقاومت بتن ۳۰MPa) هم روی همان مساحت است
    s30 = dict(default_settings(), joist_block_concrete_mpa=30)
    r30 = _pipeline(s30)
    sc30 = next(l for l in r30["lines"] if l["id"] == "joist-strength-surcharge")
    jb30 = next(l for l in r30["lines"] if l["id"] == "joist-block")
    assert sc30["code"] == "100702"
    assert sc30["qty"] == pytest.approx(jb30["qty"], abs=1e-9)


def test_T78_quantities_are_net_of_nothing():
    """کمیت‌های اصلی مساوی جمع خام رکوردهای Revit/mapping هستند (بدون ۵٪)."""
    r = _pipeline(default_settings())
    by = {l["code"]: l["qty"] for l in r["lines"]}
    # آرماتور خام پروژه: ۱۱۵۵۰٫۵۵۵۳۰۳ kg (بدون ×۱٫۰۵)
    assert by["070202"] == pytest.approx(11550.555303, abs=1e-3)
    # بتن ستون/تیر خالص: ۲۴۱٫۹۴ m³ (بدون ×۱٫۰۵)
    assert by["080107"] == pytest.approx(241.94, abs=1e-6)
    # بتن مگر خالص: ۱۸٫۶۵ m³ (بدون ×۱٫۰۵)
    assert by["080102"] == pytest.approx(18.65, abs=1e-6)
