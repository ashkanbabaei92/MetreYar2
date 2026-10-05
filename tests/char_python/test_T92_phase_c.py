# -*- coding: utf-8 -*-
# T92 — فاز C: ایراد ۱۲ (برچسب‌ها و اعتبارسنجی تاریخ‌ها).
#
# سه تاریخ متمایز و هرگز ادغام‌نشدنی (ایراد ۱۲):
#   - «تاریخ شروع پیمان»            ← contract_date
#   - «تاریخ شروع دورهٔ صورت‌وضعیت»  ← period_start
#   - «تاریخ پایان دورهٔ صورت‌وضعیت» ← period_end
# قاعده: شروع پیمان ≤ شروع دوره ≤ پایان دوره. در صورت نقض، خطا و
# جلوگیری از محاسبه/خروجی.
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (ExcelExporter, TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

META = {"project_name": "T92", "employer": "کارفرما", "contractor": "پیمانکار",
        "consultant": "مشاور", "contract_no": "۱", "location": "گرگان",
        "report_no": "۱", "report_type": "دوره‌ای",
        "period_start": "۱۴۰۴/۰۱/۰۱", "period_end": "۱۴۰۴/۰۳/۳۱",
        "contract_date": "۱۴۰۳/۱۲/۲۹"}


def _errs(**over):
    m = dict(META)
    m.update(over)
    return TechnicalOfficeEngine.validate_meta(m)


# ── ترتیب معتبر ──

def test_T92_valid_ordering_no_errors():
    assert _errs() == []
    # مساوی هم مجاز است
    assert _errs(contract_date="۱۴۰۴/۰۱/۰۱") == []
    assert _errs(contract_date="۱۴۰۴/۰۱/۰۱",
                 period_start="۱۴۰۴/۰۱/۰۱",
                 period_end="۱۴۰۴/۰۱/۰۱") == []


def test_T92_empty_dates_skipped():
    assert _errs(contract_date="", period_start="", period_end="") == []
    # فقط یک تاریخ پرشده → بررسی ترتیب ممکن نیست
    assert _errs(contract_date="", period_start="", period_end="۱۴۰۴/۰۱/۰۱") == []


# ── نقض ترتیب ──

def test_T92_contract_after_period_start():
    # period_end بعد از contract_date تا فقط یک خطا تولید شود
    e = _errs(contract_date="۱۴۰۴/۰۶/۰۱", period_end="۱۴۰۴/۱۲/۲۹")
    assert len(e) == 1
    assert e[0]["level"] == "خطا"
    assert e[0]["category"] == "تاریخ‌ها"
    assert "شروع پیمان" in e[0]["message"]
    assert e[0]["ref"].startswith("ایراد ۱۲")


def test_T92_period_start_after_end():
    e = _errs(period_start="۱۴۰۴/۰۶/۰۱", period_end="۱۴۰۴/۰۳/۳۱")
    assert len(e) == 1
    assert e[0]["level"] == "خطا"
    assert "شروع دوره" in e[0]["message"]


def test_T92_contract_after_period_end():
    e = _errs(contract_date="۱۴۰۴/۰۹/۰۱", period_end="۱۴۰۴/۰۳/۳۱")
    # شروع پیمان بعد از هر دو تاریخ دوره است → دو خطا
    assert len(e) == 2
    assert all(x["level"] == "خطا" for x in e)
    assert any("شروع پیمان" in x["message"] for x in e)


def test_T92_multiple_violations():
    e = _errs(contract_date="۱۴۰۵/۰۱/۰۱", period_start="۱۴۰۴/۰۶/۰۱",
              period_end="۱۴۰۴/۰۳/۳۱")
    # شروع پیمان > شروع دوره + شروع دوره > پایان دوره (شروع پیمان > پایان
    # دوره با یکی از این‌ها پوشش داده نمی‌شود → ۳ خطا)
    assert len(e) == 3
    assert all(x["level"] == "خطا" for x in e)


# ── تاریخ نامعتبر ──

def test_T92_invalid_jalali_date():
    e = _errs(period_end="۱۴۰۴/۱۳/۰۱")
    assert len(e) == 1
    assert "معتبر نیست" in e[0]["message"]
    assert e[0]["item"] == "تاریخ پایان دورهٔ صورت‌وضعیت"


def test_T92_invalid_dates_and_order():
    # period_start نامعتبر + ترتیب نقض‌شده (با مقایسهٔ null skip می‌شود)
    e = _errs(contract_date="۱۴۰۴/۰۶/۰۱", period_start="bad")
    assert len(e) == 2
    assert any("معتبر نیست" in x["message"] for x in e)
    assert any("شروع پیمان" in x["message"] for x in e)


def test_T92_persian_and_latin_digits_both_ok():
    # ارقام فارسی و لاتین هر دو پذیرفته می‌شوند (ایراد ۱۳)
    assert _errs(contract_date="1403/12/29") == []
    assert _errs(contract_date="۱۴۰۳/۱۲/۲۹") == []


# ── خروجی Excel: بنر خطا + برچسب‌های جدید ──

def _export(meta):
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    res = eng.compute([], None)
    data = ExcelExporter().export(meta, res, default_settings(), [])
    zf = zipfile.ZipFile(io.BytesIO(data))
    return zf


def test_T92_excel_labels_updated():
    zf = _export(META)
    shared = zf.read("xl/sharedStrings.xml").decode("utf-8")
    # برچسب‌های جدید ایراد ۱۲
    assert "دورهٔ صورت‌وضعیت" in shared
    assert "شروع پیمان" in shared
    # برچسب‌های قدیمی حذف شده‌اند
    assert "شروع قرارداد" not in shared


def test_T92_excel_error_banner_on_invalid_dates():
    bad = dict(META)
    bad["contract_date"] = "۱۴۰۵/۰۱/۰۱"  # بعد از شروع دوره
    zf = _export(bad)
    shared = zf.read("xl/sharedStrings.xml").decode("utf-8")
    assert "خطا — تاریخ‌های پروژه نامعتبر است" in shared
    assert "پیش‌نویس" in shared


def test_T92_excel_no_banner_on_valid_dates():
    zf = _export(META)
    shared = zf.read("xl/sharedStrings.xml").decode("utf-8")
    assert "خطا — تاریخ‌های پروژه نامعتبر است" not in shared
