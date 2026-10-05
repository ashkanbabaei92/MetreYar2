# -*- coding: utf-8 -*-
# T121 — فاز E-9 §۴: D-01 به‌عنوانِ «دادهٔ ورودیِ الزامی».
#
# قاعدهٔ k (بخشنامهٔ ۲۰۸۰ — بند ۱-۸، تبصرهٔ ۲ و بند ۸-۴) با ورودیِ کاربر
# کاملاً تعیین می‌شود؛ گزینه‌ای برای تصمیم باقی نمانده. تا وقتی کاربر
# وضعیتِ اتمام را مشخص نکرده، خروجی علی‌الحساب است و یک هشدارِ مرکزی او را
# به فیلد هدایت می‌کند.
#
# همتایِ TypeScript این آزمون: tests/char_ts/test_T121_d01_required_input.ts
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (TechnicalOfficeEngine, _default_fehrest_db,  # noqa: E402
                 _tadil_k, default_settings)

A_TEST = 10_000_000_000.0
OH, REG, PROP = 1.3, 1.04, 1.0
PRICE_MULT = OH * REG * PROP
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"
K_2080, K_COMPLETED = 0.95, 1.0


def _ctx(base=A_TEST):
    return {"chapter_amounts": {"06": base},
            "floors_amount": base, "base_total": base, "site_setup": 0.0,
            "advance_payment": 0.0,
            "overhead_coef": OH, "regional_coef": REG,
            "grand_total": base * PRICE_MULT,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": base, "excluded_total": 0.0}}


def _eng(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["tadil_approved"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    return TechnicalOfficeEngine(_default_fehrest_db(), s)


# ═════════ مشتق‌شدنِ k از ورودی ═════════

def test_T121_k_from_input():
    assert _tadil_k({"completed_within_term": True})[0] == K_COMPLETED
    assert _tadil_k({"completed_within_term": False})[0] == K_2080
    k, st, _src = _tadil_k({"completed_within_term": None})
    assert k == K_2080
    assert "علی‌الحساب" in st


# ═════════ هشدارِ ورودیِ الزامی ═════════

def test_T121_required_input_warning_when_null():
    eng = _eng()                                     # پیش‌فرض = نامشخص
    warns = []
    t = eng._tadil_engine(_ctx(), warns)
    assert not t.get("error")
    w = [x for x in warns
         if x.get("item") == "completed_within_term_required"]
    assert len(w) == 1
    assert w[0]["level"] == "اطلاع"
    assert "۰٫۹۵" in w[0]["message"]
    assert w[0]["ref"] == "بخشنامهٔ ۲۰۸۰ — بند ۱-۸، تبصرهٔ ۲ و بند ۸-۴"
    # خروجی علی‌الحساب و بدونِ k_diff
    assert t["coef"] == K_2080
    assert t["k_diff"] == 0.0


def test_T121_no_warning_when_true():
    eng = _eng(completed_within_term=True)
    warns = []
    t = eng._tadil_engine(_ctx(), warns)
    assert not t.get("error")
    assert not [x for x in warns
                if x.get("item") == "completed_within_term_required"]
    assert t["coef"] == K_COMPLETED
    # مابه‌التفاوتِ بند ۸-۴ جدا نمایش داده می‌شود
    assert t["k_diff"] > 0.0
    assert t["completed_within_term"] is True


def test_T121_no_warning_when_false():
    eng = _eng(completed_within_term=False)
    warns = []
    t = eng._tadil_engine(_ctx(), warns)
    assert not t.get("error")
    assert not [x for x in warns
                if x.get("item") == "completed_within_term_required"]
    assert t["coef"] == K_2080
    assert t["completed_within_term"] is False


def test_T121_null_and_true_differ_by_k_diff_only():
    """اختلافِ دو خروجی دقیقاً همان مابه‌التفاوتِ بند ۸-۴ است."""
    t_null = _eng()._tadil_engine(_ctx(), [])
    t_true = _eng(completed_within_term=True)._tadil_engine(_ctx(), [])
    assert abs((t_true["result_amount"] - t_null["result_amount"])
               - t_true["k_diff"]) < 1e-6


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
