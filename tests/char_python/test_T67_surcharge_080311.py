# -*- coding: utf-8 -*-
# T67 - اضافه‌بهای سختی ارتعاش بتن (ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴).
#
# شرط رسمی: «اضافه‌بها به ردیف‌های بتن‌ریزی برای سختی ارتعاش بتن، در صورتی
# که میلگرد به کار رفته بیش از ۱۸۰ کیلوگرم در مترمکعب بتن باشد» (۳۶۳٬۵۰۰
# ریال/m³). پیاده‌سازی: تراکم = مجموع وزن آرماتور ÷ حجم بتن‌های سازه‌ای
# (بدون بتن‌مگر)؛ چون از ۱۸۰ بیشتر شود، ردیفی به ازای مقدار بتن سازه‌ای
# (به‌جز سیستم سقف تیرچه‌بلوک — بند ۳-۵ فصل ۸) افزوده می‌شود. این ردیف
# **اختیاری** است و تنظیم بولین
# `surcharge_rebar_density` (پیش‌فرض False) آن را فعال می‌کند.
#
# نکتهٔ مهم: جدول آرماتورِ پروژهٔ نمونه یک استخراج نمونه است؛ تراکم واقعی
# پروژه ≈ ۳۱ kg/m³ است و زیر آستانه می‌ماند. بنابراین در دادهٔ واقعی،
# فعال کردن این تنظیم هیچ ردیفی اضافه نمی‌کند و totals بی‌تغییر می‌مانند —
# همین رفتار آزمون می‌شود (و در سمت TS نیز دقیقاً همین خروجی به دست
# می‌آید → برابری دو زبان).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings, rebar_density,
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


def test_T67_rebar_density_helper():
    """تابع تراکم: تقسیم ساده، بازگشت صفر برای حجم صفر، عبور از آستانه."""
    # مقادیر واقعی پروژهٔ نمونه: ۱۲٬۵۳۶٫۳۷ کیلوگرم آرماتور بر ۴۰۴٫۵۸ m³ بتن سازه‌ای
    d = rebar_density(12536.368737, 404.581675)
    assert d == pytest.approx(30.99, abs=0.01)
    assert d < REBAR_DENSITY_THRESHOLD
    # تراکم فرضی بالای آستانه (مثلاً پروژهٔ دیوار برشی متراکم)
    assert rebar_density(75000.0, 404.581675) > REBAR_DENSITY_THRESHOLD
    # حجم صفر → تراکم صفر (تقسیم بر صفر ممنوع)
    assert rebar_density(1000.0, 0.0) == 0.0


def test_T67_surcharge_off_by_default():
    """پیش‌فرض: تنظیم خاموش است و ردیف ۰۸۰۳۱۱ وجود ندارد و totals مرجع است."""
    assert default_settings()["surcharge_rebar_density"] is False
    r = _pipeline(default_settings())
    assert len(r["lines"]) == 17
    assert not any(l["code"] == "080311" for l in r["lines"])
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


def test_T67_surcharge_on_but_below_threshold_no_line():
    """فعال‌سازی روی دادهٔ نمونه: تراکم ≈ ۳۱ < ۱۸۰ → ردیفی افزوده نمی‌شود.

    totals و شمارش ردیف‌ها دقیقاً برابر حالت خاموش می‌مانند (و چون سمت TS
    همین محاسبات را می‌کند، برابری دو زبان حفظ می‌شود).
    """
    off = _pipeline(default_settings())
    s = default_settings()
    s["surcharge_rebar_density"] = True
    on = _pipeline(s)

    # تراکم از روی ردیف‌های واقعی محاسبه می‌شود تا شرط اثبات گردد
    rebar_net = sum(l["qty"] for l in on["lines"] if l["id"].startswith("rebar-"))
    conc_net = sum(l["qty"] for l in on["lines"] if l["id"].startswith("conc-"))
    assert rebar_density(rebar_net, conc_net) < REBAR_DENSITY_THRESHOLD

    assert len(on["lines"]) == len(off["lines"]) == 17
    assert not any(l["code"] == "080311" for l in on["lines"])
    assert on["base_total"] == off["base_total"]
    assert on["grand_total"] == off["grand_total"]
    assert on["base_total"] == pytest.approx(23218381337.01, abs=1.0)


if __name__ == "__main__":
    test_T67_rebar_density_helper()
    test_T67_surcharge_off_by_default()
    test_T67_surcharge_on_but_below_threshold_no_line()
    print("T67 ok")
