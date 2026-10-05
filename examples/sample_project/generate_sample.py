# -*- coding: utf-8 -*-
# generate_sample.py — تولیدِ پروژهٔ نمونهٔ ناشناس (پروفایل + Excel).
#
# این اسکریپت کل خطِ لوله را با دادهٔ نمایشیِ پروژهٔ مرجع اجرا می‌کند و
# دو فایل می‌سازد:
#   project_profile.json — پروفایل کامل پروژه (مشخصات + تنظیمات)
#   sample_output.xlsx  — خروجی Excel شش‌برگه
#
# تمامِ مشخصاتِ شناسایی‌کننده (نام پروژه، کارفرما، پیمانکار) ناشناس‌اند.
# اعدادِ خروجی دقیقاً همان اعدادِ خطِ لولهٔ پروژهٔ مرجع هستند (تست T113).
#
# اجرا:  python examples/sample_project/generate_sample.py
import json
import logging
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

# خروجیِ کنسولِ ویندوز cp1252 است؛ خروجی را UTF-8 می‌کنیم و هشدارهای
# بی‌اهمیتِ Streamlit (import در حالت bare) را خاموش می‌کنیم.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
logging.disable(logging.WARNING)

from app import (DynamoMappingParser, ExcelExporter, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, _default_meta,
                 default_settings, save_profile)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


def build_tables():
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r",
                      encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    return tables


def build_map():
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    return DynamoMappingParser.merge_formats(results)


def sample_meta():
    """مشخصاتِ ناشناسِ پروژهٔ نمونه."""
    m = _default_meta()
    m.update({
        "project_name": "پروژهٔ نمونهٔ نمایشی",
        "employer": "کارفرمای نمونه",
        "contractor": "پیمانکار نمونه",
        "consultant": "مشاور نمونه",
        "contract_no": "نمونه-۱۴۰۴-۰۱",
        "contract_date": "۱۴۰۴/۰۱/۱۵",
        "location": "گرگان",
        "report_no": "۱",
        "report_type": "موقت",
        "period_start": "۱۴۰۴/۰۱/۰۱",
        "period_end": "۱۴۰۴/۰۳/۳۱",
    })
    return m


def sample_settings():
    """تنظیماتِ پروژهٔ نمونه — هر دو موتور فعال، دورهٔ هدف ۱۴۰۴Q4."""
    s = default_settings()
    s.update({
        "baravord_enabled": True,      # موتور برآورد به‌هنگام
        "baravord_approved": True,
        "tadil_enabled": True,         # موتور تعدیل پیمان
        "tadil_approved": True,
        "baravord_it_period": "q4",    # ۱۴۰۴Q4 قطعی (پیش‌فرض)
    })
    return s


def main():
    print("ساختِ جداول از data/export revit ...")
    tables = build_tables()
    print("  %d جدول" % len(tables))
    print("ساختِ نگاشت Dynamo ...")
    map_df = build_map()
    print("اجرای موتور دفتر فنی ...")
    result = TechnicalOfficeEngine(
        _default_fehrest_db(), sample_settings()).compute(tables, map_df)

    meta = sample_meta()
    settings = sample_settings()

    prof_path = os.path.join(OUT_DIR, "project_profile.json")
    save_profile(prof_path, settings, meta)
    print("نوشته شد: %s" % prof_path)

    xlsx = ExcelExporter().export(meta, result, settings, [])
    xlsx_path = os.path.join(OUT_DIR, "sample_output.xlsx")
    with open(xlsx_path, "wb") as f:
        f.write(xlsx)
    print("نوشته شد: %s (%d بایت)" % (xlsx_path, len(xlsx)))

    print("")
    print("baseTotal  = %.2f ریال" % result["base_total"])
    print("grandTotal = %.2f ریال" % result["grand_total"])
    bar = (result.get("adjustment") or {}).get("baravord")
    if bar:
        print("baravord   = %.2f ریال (It = %s)" % (bar["result_amount"],
                                                    bar["it_q"]))


if __name__ == "__main__":
    main()
