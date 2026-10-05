# -*- coding: utf-8 -*-
# T115 — ابزارِ اعتبارسنجیِ مرجع (فاز E-۷ بخش ۵).
#
# tests/tools/validate_against_reference.py را در دو سطح می‌آزماید:
#   ۱) منطقِ مقایسه (check_number / validate_numbers) با ورودی‌های ساختگی؛
#   ۲) خواندنِ Excel (validate_xlsx) با کاربرگِ ساختگی؛
#   ۳) [slow] اجرای واقعیِ موتور روی پروژهٔ مرجع.
#
# بخش‌های ۱ و ۲ سریع‌اند و در run_fast_tests.ps1 اجرا می‌شوند؛ بخش ۳ slow
# است چون خطِ لولهٔ کامل را می‌دوند.
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from validate_against_reference import (DEFAULT_TOLERANCE, EXPECTED,
                                        check_number, validate_numbers,
                                        validate_xlsx)

# ── ۱) منطقِ مقایسه ──


def test_T115_check_number_exact():
    assert check_number("x", 100.0, 100.0) is None


def test_T115_check_number_within_tolerance():
    # ۰٫۵ ریال اختلاف در تلرانسِ پیش‌فرض (۱ ریال)
    assert check_number("x", 100.5, 100.0) is None


def test_T115_check_number_outside_tolerance():
    msg = check_number("x", 102.0, 100.0, tolerance=1.0)
    assert msg is not None
    assert "102.00" in msg and "100.00" in msg


def test_T115_check_number_missing_is_error():
    msg = check_number("x", None, 100.0)
    assert msg is not None
    assert "موجود نیست" in msg


def test_T115_validate_numbers_all_ok():
    actuals = {k: v for k, v in EXPECTED.items()}
    assert validate_numbers(actuals) == []


def test_T115_validate_numbers_reports_each_failure():
    actuals = {k: v + 1000 for k, v in EXPECTED.items()}
    issues = validate_numbers(actuals)
    assert len(issues) == len(EXPECTED)
    for name in EXPECTED:
        assert any(name in i for i in issues)


def test_T115_expected_has_three_reference_numbers():
    assert set(EXPECTED) == {"base_total", "grand_total", "baravord_q4"}
    assert DEFAULT_TOLERANCE == 1.0


# ─ـ ۲) خواندنِ Excel با کاربرگِ ساختگی ──

def _write_xlsx(path, numbers, extra=1234.5):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "خلاصه"
    ws["A1"] = "شرح"
    ws["B1"] = "مبلغ (ریال)"
    for i, n in enumerate(numbers, start=2):
        ws.cell(row=i, column=1, value="ردیف %d" % i)
        ws.cell(row=i, column=2, value=n)
    # یک عددِ نامرتبط
    ws["A20"] = "مبلغ نامرتبط"
    ws["B20"] = extra
    wb.save(path)
    wb.close()


def test_T115_validate_xlsx_accepts_matching(tmp_path):
    p = tmp_path / "ok.xlsx"
    _write_xlsx(str(p), list(EXPECTED.values()))
    assert validate_xlsx(str(p)) == []


def test_T115_validate_xlsx_accepts_persian_string_cells(tmp_path):
    # شیتِ «برآورد به‌هنگام» مبالغ را رشتهٔ فارسی می‌نویسد (۴۵,۴۳۷,۷۴۲,۸۲۰).
    from openpyxl import Workbook
    p = tmp_path / "persian.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "برآورد به‌هنگام‌شده (ریال)"
    ws["B1"] = "۴۵,۴۳۷,۷۴۲,۸۲۰"
    ws["A2"] = "جمع کل"
    ws["B2"] = "۳۱,۳۹۱,۲۵۱,۵۶۸"
    ws["A3"] = "پایه"
    ws["B3"] = "۲۳,۲۱۸,۳۸۱,۳۳۷"
    wb.save(str(p))
    wb.close()
    assert validate_xlsx(str(p)) == []


def test_T115_validate_xlsx_rejects_missing(tmp_path):
    p = tmp_path / "missing.xlsx"
    _write_xlsx(str(p), [1.0, 2.0, 3.0])
    issues = validate_xlsx(str(p))
    assert len(issues) == len(EXPECTED)
    for name in EXPECTED:
        assert any(name in i for i in issues)


def test_T115_validate_xlsx_tolerance(tmp_path):
    p = tmp_path / "tol.xlsx"
    _write_xlsx(str(p), [v + 0.5 for v in EXPECTED.values()])
    assert validate_xlsx(str(p), tolerance=1.0) == []
    issues = validate_xlsx(str(p), tolerance=0.1)
    assert len(issues) == len(EXPECTED)


# ─ـ ۳) اجرای واقعیِ موتور روی پروژهٔ مرجع (slow) ──

@pytest.mark.slow
def test_T115_engine_matches_reference():
    from validate_against_reference import run_engine
    actuals = run_engine()
    issues = validate_numbers(actuals)
    assert issues == [], "; ".join(issues)
