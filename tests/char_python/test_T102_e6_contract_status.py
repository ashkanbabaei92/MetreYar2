# -*- coding: utf-8 -*-
"""T102 — فاز E-6 Part C گام ۴: وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷).

بند ۶: پیمان‌هایی که بدون قصور پیمانکار خاتمه داده شوند — طبق همین
دستورالعمل (بدون تغییر).
بند ۷: پیمان‌هایی که به علت قصور پیمانکار فسخ شوند — ۵٪ از مبلغ تعدیل
کسر می‌شود (ردیفِ جداگانه در خروجی و Excel).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

BASE = 10_000_000_000.0


def _ctx():
    return {"chapter_amounts": {"06": BASE}, "floors_amount": BASE,
            "base_total": BASE, "site_setup": 0.0, "advance_payment": 0.0,
            "overhead_coef": 1.3, "regional_coef": 1.04,
            "grand_total": BASE * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": BASE, "excluded_total": 0.0}}


def _tadil(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = "۱۴۰۳/۱۲/۲۹"          # ⇒ Io = ۱۴۰۳Q4 (مبنا)
    s.update(extra)
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), s)
    return eng._tadil_engine(_ctx(), w), w


# ── پیش‌فرض: فعال ⇒ هیچ کسری نیست (اعداد مرجع ثابت) ──

def test_T102_default_active_no_deduction():
    t, w = _tadil()
    assert t["contract_status"] == "فعال"
    assert t["deduction_fault"] == 0.0
    assert not [x for x in w
                if x.get("category") == "موتور تعدیل"
                and "بند ۷" in (x.get("ref") or "")]


# ── بند ۶: خاتمهٔ بدون قصور ⇒ مثلِ حالتِ عادی ──

def test_T102_completed_without_fault_unchanged():
    t, w = _tadil(contract_status="خاتمه بدون قصور")
    assert t["contract_status"] == "خاتمه بدون قصور"
    assert t["deduction_fault"] == 0.0
    t0, _ = _tadil()
    assert t["delta_p"] == pytest.approx(t0["delta_p"])
    assert t["result_amount"] == pytest.approx(t0["result_amount"])


# ── بند ۷: فسخ با قصور ⇒ ۵٪ از مبلغ تعدیل کسر می‌شود ──

def test_T102_fasx_deducts_5_percent():
    t, w = _tadil(contract_status="فسخ با قصور")
    assert t["contract_status"] == "فسخ با قصور"
    # کسر = ۵٪ از مبلغ تعدیل (عددِ منفی)
    assert t["deduction_fault"] == pytest.approx(-0.05 * t["delta_p"])
    # مبلغ نهایی شامل کسر است
    assert t["result_amount"] == pytest.approx(
        t["base_amount"] + t["delta_p"] + t["deduction_fault"])
    # خودِ مبلغ تعدیل تغییر نمی‌کند — فقط پرداختِ نهایی
    t0, _ = _tadil()
    assert t["delta_p"] == pytest.approx(t0["delta_p"])
    assert t["delta_p_definitive"] == pytest.approx(t0["delta_p_definitive"])


def test_T102_fasx_warning_and_fields():
    t, w = _tadil(contract_status="فسخ با قصور")
    _f = [x for x in w
          if x.get("category") == "موتور تعدیل"
          and "بند ۷" in (x.get("ref") or "")]
    assert len(_f) == 1
    assert _f[0]["level"] == "هشدار"
    assert "فسخ با قصور" in _f[0]["message"]
    # فیلدهای جدید در خروجی موجودند
    assert "contract_status" in t and "deduction_fault" in t


def test_T102_fasx_deduction_is_separate_amount():
    """مقدارِ دقیقِ کسر = ۵٪ از ΔP گردشدهٔ همان اجرا."""
    t, _ = _tadil(contract_status="فسخ با قصور")
    _dp = t["delta_p"]
    assert t["deduction_fault"] == pytest.approx(-0.05 * _dp, abs=1e-6)
    assert t["result_amount"] < t["base_amount"] + t["delta_p"]


# ── ΔP منفی: کسر فقط با فلگ اعمال می‌شود (تفسیر — §۱۸-۳) ──

def test_T102_negative_dp_no_flag_no_deduction():
    t, w = _tadil(contract_status="فسخ با قصور",
                  proposal_date="۱۴۰۴/۱۲/۲۹",
                  tadil_it_period="base",
                  tadil_allow_negative=True)
    assert t["delta_p"] < 0
    assert t["deduction_fault"] == 0.0
    assert t["result_amount"] == pytest.approx(
        t["base_amount"] + t["delta_p"])
    _f = [x for x in w
          if x.get("category") == "موتور تعدیل"
          and "بند ۷" in (x.get("ref") or "")]
    assert len(_f) == 1
    assert "اعمال نشد" in _f[0]["message"]


def test_T102_negative_dp_with_flag_deduction_applied():
    t, w = _tadil(contract_status="فسخ با قصور",
                  proposal_date="۱۴۰۴/۱۲/۲۹",
                  tadil_it_period="base",
                  tadil_allow_negative=True,
                  fault_deduction_on_negative=True)
    assert t["delta_p"] < 0
    assert t["deduction_fault"] == pytest.approx(-0.05 * t["delta_p"])
    # کسرِ تعدیلِ منفی ⇒ عددِ مثبت (افزایشِ مبلغ نهایی)
    assert t["deduction_fault"] > 0
    assert t["result_amount"] == pytest.approx(
        t["base_amount"] + t["delta_p"] + t["deduction_fault"])
    _f = [x for x in w
          if x.get("category") == "موتور تعدیل"
          and "بند ۷" in (x.get("ref") or "")]
    assert len(_f) == 1
    assert "فسخ با قصور" in _f[0]["message"]


def test_T102_zero_dp_no_deduction_but_warning():
    # Io = It = ۱۴۰۳Q4 ⇒ ΔP = 0
    t, w = _tadil(contract_status="فسخ با قصور",
                  tadil_it_period="base")
    assert t["delta_p"] == 0.0
    assert t["deduction_fault"] == pytest.approx(0.0)
    assert t["result_amount"] == pytest.approx(t["base_amount"])
    _f = [x for x in w
          if x.get("category") == "موتور تعدیل"
          and "بند ۷" in (x.get("ref") or "")]
    assert len(_f) == 1


def test_T102_fasx_with_cwt_k1():
    t, w = _tadil(contract_status="فسخ با قصور",
                  completed_within_term=True)
    t0, _ = _tadil(completed_within_term=True)
    assert t["delta_p"] == pytest.approx(t0["delta_p"])
    assert t["delta_p_definitive"] == pytest.approx(
        t0["delta_p_definitive"])
    assert t["deduction_fault"] == pytest.approx(-0.05 * t0["delta_p"])
    assert t["result_amount"] == pytest.approx(
        t0["result_amount"] + t["deduction_fault"])
    # k_diff هنوز در بخش قطعی است (تبصرهٔ ۲) و کسر جداگانه است
    assert "k_diff" in t


def test_T102_copy_project_resets_status():
    from app import copy_project
    s = default_settings()
    s["contract_status"] = "فسخ با قصور"
    s["fault_deduction_on_negative"] = True
    _nm, ns = copy_project(s, {"project_name": "P"})
    assert ns["contract_status"] == "فعال"
    # فلگ به‌عنوان یک تنظیمِ فنی نگه داشته می‌شود
    assert ns["fault_deduction_on_negative"] is True
