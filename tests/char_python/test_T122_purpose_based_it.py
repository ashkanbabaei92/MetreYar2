# -*- coding: utf-8 -*-
# T122 — فاز E-9 §۵: پیش‌فرضِ هدف‌محورِ It (تعدیل صورت‌وضعیت vs برآورد به‌هنگام).
#
# موتورِ تعدیلِ صورت‌وضعیت باید شاخص را از دورهٔ واقعیِ انجامِ کار بخواند.
# وقتی دوره خالی است، تمامِ کارکرد به آخرین شاخصِ قطعی (۱۴۰۴Q4) منتسب
# می‌شود و ΔP متفاوتی می‌دهد. موتور باید هشدار دهد و کاربر را به فیلد
# مربوطه هدایت کند (قاعدهٔ طلایی).
#
# مرورِ پیش‌فرضِ q4 در موتورِ برآورد به‌هنگام (E-8 §۱۸-۱۰-۶ §۳.۳): تأیید
# شد — هدفِ برآورد به‌هنگام، به‌روزرسانی به یک سطحِ قیمتِ هدف است و q4
# (آخرین شاخصِ قطعی) پیش‌فرضِ درست است. تغییرِ کد لازم نیست.
#
# همتایِ TypeScript این آزمون: tests/char_ts/test_T122_purpose_based_it.py.ts
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (TechnicalOfficeEngine, _default_fehrest_db,  # noqa: E402
                 default_settings)

A_TEST = 10_000_000_000.0
OH, REG, PROP = 1.3, 1.04, 1.0
PRICE_MULT = OH * REG * PROP
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"


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


# ═════════ هشدارِ دورهٔ انجام کار ═════════

def test_T122_warns_when_work_period_missing():
    eng = _eng()                                     # پیش‌فرض: دوره خالی
    warns = []
    t = eng._tadil_engine(_ctx(), warns)
    assert not t.get("error")
    w = [x for x in warns
         if x.get("item") == "work_period_missing_for_it"]
    assert len(w) == 1
    assert w[0]["level"] == "هشدار"
    assert w[0]["category"] == "موتور تعدیل"
    assert "1404Q4" in w[0]["message"]
    assert w[0]["ref"] == "فاز E-9 §۵ — بند ۱-۷ بخشنامهٔ ۲۰۸۰"


def test_T122_no_warning_when_work_period_set():
    eng = _eng(work_period_start="۱۴۰۴/۰۱/۰۱",
               work_period_end="۱۴۰۵/۰۲/۱۵")
    warns = []
    t = eng._tadil_engine(_ctx(), warns)
    assert not t.get("error")
    assert not [x for x in warns
                if x.get("item") == "work_period_missing_for_it"]
    # شاخصِ هر سه‌ماهه اعمال می‌شود
    qs = set()
    for row in (t.get("chapters") or []):
        for q, _v, _st in (row.get("quarters") or []):
            qs.add(q)
    assert qs == {"1404Q1", "1404Q2", "1404Q3", "1404Q4", "1405Q1"}


def test_T122_missing_work_period_changes_delta_p():
    """بدونِ دوره، تمامِ کارکرد به ۱۴۰۴Q4 منتسب می‌شود → ΔP متفاوت."""
    t_fb = _eng()._tadil_engine(_ctx(), [])
    t_sp = _eng(work_period_start="۱۴۰۴/۰۱/۰۱",
                work_period_end="۱۴۰۵/۰۲/۱۵")._tadil_engine(_ctx(), [])
    assert abs(t_fb["delta_p"] - t_sp["delta_p"]) > 1_000_000.0


def test_T122_explicit_it_period_used_in_fallback():
    """اگر کاربر tadil_it_period را تغییر دهد، fallback از همان استفاده می‌کند."""
    eng = _eng(tadil_it_period="q2")
    warns = []
    t = eng._tadil_engine(_ctx(), warns)
    assert not t.get("error")
    w = [x for x in warns
         if x.get("item") == "work_period_missing_for_it"]
    assert len(w) == 1 and "1404Q2" in w[0]["message"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
