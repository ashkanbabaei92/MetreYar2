# -*- coding: utf-8 -*-
# T116 — برچسب‌گذاریِ برآورد به‌هنگام (فاز E-8 بخش ۳).
#
# قاعده: هیچ خروجیِ برآوردی (Excel / UI) بدون برچسبِ «دورهٔ It» و
# «وضعیت موقت/قطعی» ساخته نمی‌شود. اگر It موقت (۱۴۰۵Q1) باشد، ضریبِ
# موقت هم باید نمایش داده شود.
#
# این آزمون:
#   ۱) موتور: خروجیِ baravord فیلدهای it_status / prov / prov_manual /
#      prov_trace را دارد (هر دو مسیر: قطعی و موقت)؛
#   ۲) شیتِ Excel «برآورد به‌هنگام»: برچسبِ «دورهٔ انجام کار (It)» و
#      «وضعیت دورهٔ It» همیشه موجودند؛
#   ۳) مسیرِ قطعی (q4): وضعیت = «قطعی» و ردیفِ ضریبِ موقت وجود ندارد؛
#   ۴) مسیرِ موقت (۱۴۰۵Q1): وضعیت = «موقت» و ردیفِ «ضریب موقت (۱۴۰۵Q1)»
#      با عددِ ضریب ساخته می‌شود.
#
# آینهٔ test_T116_baravord_labels.ts.
import io
import os
import sys
import zipfile

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, ExcelExporter, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings,
                 fa_float)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

META = {"report_type": "دوره‌ای", "report_no": "۱", "contract_no": "۱",
        "project_name": "پروژه نمونه", "employer": "کارفرما",
        "contractor": "پیمانکار", "consultant": "مشاور",
        "period_start": "۱۴۰۴/۰۱/۰۱", "period_end": "۱۴۰۴/۰۳/۳۱",
        "location": "گرگان", "contract_date": "۱۴۰۴/۰۱/۰۱"}
PROV_COEF = 1.1530518586507572

_BASE = dict(tadil_enabled=True, baravord_enabled=True,
             proposal_date="۱۴۰۳/۱۲/۲۹",
             work_period_start="۱۴۰۴/۰۱/۰۱",
             work_period_end="۱۴۰۵/۰۲/۱۵",
             provisional_coef_1405q1=PROV_COEF)


def _pipeline(extra):
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r",
                      encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    s = default_settings()
    s.update(_BASE)
    s.update(extra)
    res = TechnicalOfficeEngine(_default_fehrest_db(), s).compute(
        tables, DynamoMappingParser.merge_formats(results))
    return res, s


def _shared_strings(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    return z.read("xl/sharedStrings.xml").decode("utf-8")


# ── ۱) موتور: فیلدهای جدید در خروجیِ برآورد (قطعی) ──

def test_T116_engine_final_has_it_status_and_prov_fields():
    res, _s = _pipeline(dict(baravord_it_period="q4"))
    b = res["adjustment"]["baravord"]
    assert b is not None
    assert b["it_status"] == "قطعی"
    assert b["prov"] is not None      # از ورودیِ دستی خوانده می‌شود
    assert b["prov_manual"] is True   # PROV_COEF از ورودیِ دستی آمده
    assert isinstance(b["prov_trace"], dict)
    # در مسیرِ قطعی، ضریبِ موقت استفاده نمی‌شود (فقط برای It موقت است)


# ─ـ ۲) موتور: فیلدهای جدید در خروجیِ برآورد (موقت) ──

def test_T116_engine_provisional_has_prov_value():
    res, _s = _pipeline(dict(baravord_it_period="1405Q1"))
    b = res["adjustment"]["baravord"]
    assert b is not None
    assert b["it_status"] == "موقت"
    assert b["prov"] == pytest.approx(PROV_COEF)
    assert b["prov_manual"] is True   # PROV_COEF از ورودیِ دستی آمده
    assert isinstance(b["prov_trace"], dict)


# ─ـ ۳) شیتِ Excel: برچسب‌های It همیشه موجودند (مسیرِ قطعی) ──

def test_T116_excel_final_sheet_has_it_labels():
    res, s = _pipeline(dict(baravord_it_period="q4"))
    data = ExcelExporter().export(META, res, s, [])
    shared = _shared_strings(data)
    assert "دورهٔ مبنا (Io)" in shared
    assert "دورهٔ انجام کار (It)" in shared
    assert "وضعیت دورهٔ It" in shared
    assert "قطعی" in shared
    # مسیرِ قطعی ⇒ ردیفِ ضریبِ موقت نباید باشد
    assert "ضریب موقت (۱۴۰۵Q1)" not in shared
    # عددِ برآورد باید برچسبِ It داشته باشد (§۳.۲ — بدون It ممنوع)
    assert "برآورد به‌هنگام‌شده (ریال)" in shared


# ─ـ ۴) شیتِ Excel: مسیرِ موقت ⇒ ضریبِ موقت نمایش داده می‌شود ──

def test_T116_excel_provisional_sheet_shows_prov_coef():
    res, s = _pipeline(dict(baravord_it_period="1405Q1"))
    data = ExcelExporter().export(META, res, s, [])
    shared = _shared_strings(data)
    assert "وضعیت دورهٔ It" in shared
    assert "موقت" in shared
    assert "ضریب موقت (۱۴۰۵Q1)" in shared
    # خودِ عددِ ضریب (۴ رقم اعشار، ارقامِ فارسی) در شیت است
    assert fa_float(PROV_COEF, 4) in shared
    # راهنمایِ معنیِ ضریبِ موقت هم هست
    assert "موقت = این ضریب × آخرین شاخص قطعی" in shared


# ─ـ ۵) شیتِ Excel در هر دو مسیر ساخته می‌شود ──

def test_T116_excel_sheet_present_both_paths():
    for extra, want in ((dict(baravord_it_period="q4"), "قطعی"),
                        (dict(baravord_it_period="1405Q1"), "موقت")):
        res, s = _pipeline(extra)
        data = ExcelExporter().export(META, res, s, [])
        z = zipfile.ZipFile(io.BytesIO(data))
        wbxml = z.read("xl/workbook.xml").decode("utf-8")
        assert "برآورد به‌هنگام" in wbxml
        shared = _shared_strings(data)
        assert want in shared
