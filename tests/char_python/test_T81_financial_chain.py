# -*- coding: utf-8 -*-
# T81 — زنجیرهٔ مالی (مرحلهٔ ۱۱ بخش ۴ — دستورالعمل کاربرد بندهای ۲-۷/۲-۸).
#
# ترتیب: جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای +
# تجهیز و برچیدن کارگاه = ناخالص پرداختی (= مبلغ نهایی).
# • بالاسری: تنظیم کاربر با ۴ پیش‌فرض (عمرانی: مناقصه ۱٫۳ / ترک تشریفات
#   ۱٫۲؛ غیرعمرانی: ۱٫۴ / ۱٫۳).
# • تجهیز و برچیدن: مبلغ واردشده توسط کاربر (نه ضریب خودکار)؛ سقف ۴٪
#   فقط هشدار است و مبلغ کامل محاسبه می‌شود.
# • کسورات قانونی (۲۲٫۸٪) جزو ناخالص نیستند؛ فقط در خروجی جداگانهٔ
#   «خالص پرداختی» محاسبه می‌شوند.
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


def test_T81_default_chain_is_overhead_only():
    """پیش‌فرض: base × ۱ (طبقات ناقص) × ۱٫۳ × ۱٫۰۴ (گرگان، جدول ۹۴/۶۹۴۱۶)."""
    r = _pipeline(default_settings())
    assert r["floors_amount"] == pytest.approx(r["base_total"] * 1.0, rel=1e-9)
    assert r["overhead_amount"] == pytest.approx(r["floors_amount"] * 1.3, rel=1e-9)
    assert r["regional_amount"] == pytest.approx(r["overhead_amount"] * 1.04, rel=1e-9)
    assert r["site_setup"] == 0.0
    assert r["gross_payable"] == pytest.approx(r["regional_amount"], rel=1e-9)
    assert r["grand_total"] == r["gross_payable"]
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


def test_T81_overhead_presets_four_states():
    """۴ حالت بالاسری (نوع پروژه × نوع قرارداد) ضریب درست تولید می‌کنند."""
    presets = {key: val for key, val, _label in OVERHEAD_PRESETS}
    assert presets == {
        "overhead_civil_tender": 1.3,
        "overhead_civil_direct": 1.2,
        "overhead_noncivil_tender": 1.4,
        "overhead_noncivil_direct": 1.3,
    }
    # یک ضریب غیرپیش‌فرض (۱٫۴) سراسر زنجیره را تغییر می‌دهد (ضریب منطقه‌ای ۱٫۰۴)
    base = _pipeline(default_settings())["base_total"]
    r = _pipeline(dict(default_settings(), overhead_coef=1.4))
    assert r["overhead_amount"] == pytest.approx(base * 1.4, rel=1e-9)
    assert r["gross_payable"] == pytest.approx(base * 1.4 * 1.04, rel=1e-9)
    assert r["grand_total"] == pytest.approx(base * 1.4 * 1.04, rel=1e-9)


def test_T81_site_setup_is_an_amount_not_a_coefficient():
    """تجهیز و برچیدن مبلغ مستقیم است و کامل به ناخالص اضافه می‌شود."""
    amount = 500_000_000.0
    r = _pipeline(dict(default_settings(), site_setup_amount=amount))
    base = _pipeline(default_settings())["base_total"]
    assert r["site_setup"] == amount
    assert r["gross_payable"] == pytest.approx(base * 1.3 * 1.04 + amount, rel=1e-9)
    assert r["grand_total"] == r["gross_payable"]


def test_T81_site_setup_over_4pct_is_still_included():
    """سقف ۴٪ تجهیز (دستورالعمل ۲-۸) فقط هشدار است؛ مبلغ کامل محاسبه می‌شود."""
    r0 = _pipeline(default_settings())
    huge = 10 * (0.04 * r0["regional_amount"])  # ده برابر سقف
    r = _pipeline(dict(default_settings(), site_setup_amount=huge))
    assert huge > 0.04 * r0["regional_amount"]
    assert r["gross_payable"] == pytest.approx(r0["regional_amount"] + huge, rel=1e-9)
    assert r["grand_total"] == r["gross_payable"]


def test_T81_floors_and_regional_coefficients():
    """ضرایب طبقات و منطقه‌ای در جای درست زنجیره ضرب می‌شوند.

    ورودی دستی (floors_auto=False، regional_coef) بر محاسبهٔ خودکار تقدم
    دارد. ضریب طبقات فقط روی ردیف‌های مشمول (کار ساختمان) اعمال می‌شود —
    فصل ۲۸ (حمل و نقل) مستثنی است.
    """
    r = _pipeline(dict(default_settings(), floors_auto=False, floors_coef=1.05,
                       regional_coef=1.1))
    base = _pipeline(default_settings())
    fc = base["coefs"]["floors"]
    eligible, excluded = fc["eligible_total"], fc["excluded_total"]
    fa = eligible * 1.05 + excluded
    expected = fa * 1.3 * 1.1
    assert r["floors_amount"] == pytest.approx(fa, rel=1e-9)
    assert r["overhead_amount"] == pytest.approx(fa * 1.3, rel=1e-9)
    assert r["regional_amount"] == pytest.approx(fa * 1.3 * 1.1, rel=1e-9)
    assert r["gross_payable"] == pytest.approx(expected, rel=1e-9)


def test_T81_deductions_do_not_affect_grand_total():
    """کسورات ۲۲٫۸٪ فقط در «خالص پرداختی» هستند؛ بر ناخالص اثر ندارند."""
    plain = _pipeline(default_settings())
    s = dict(default_settings(),
             insurance_pct=7.8, tax_pct=5.0, good_job_pct=10.0,
             advance_payment=1_000_000_000.0)
    r = _pipeline(s)
    assert r["grand_total"] == pytest.approx(plain["grand_total"], rel=1e-12)
    assert r["gross_payable"] == pytest.approx(plain["gross_payable"], rel=1e-12)
    # خالص پرداختی = ناخالص − کسورات
    assert r["insurance"] == pytest.approx(r["gross_payable"] * 0.078, rel=1e-9)
    assert r["tax"] == pytest.approx(r["gross_payable"] * 0.05, rel=1e-9)
    assert r["good_job"] == pytest.approx(r["gross_payable"] * 0.10, rel=1e-9)
    assert r["advance_payment"] == 1_000_000_000.0
    assert r["total_deductions"] == pytest.approx(
        r["insurance"] + r["tax"] + r["good_job"] + r["advance_payment"], rel=1e-6)
    assert r["net_payable"] == pytest.approx(r["gross_payable"] - r["total_deductions"],
                                             rel=1e-6)
    assert r["net_payable"] < r["gross_payable"]
