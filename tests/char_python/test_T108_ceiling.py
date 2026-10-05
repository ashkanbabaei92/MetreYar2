# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# T108 — سقفِ قیمت قابل قبول ۱۰٪ (فاز E-6 Part C گام ۷ — نامه-۶)
#
# «در کارهایی که شاخص مبنایشان طبق ۱-۶-۱ یکم است، سقف قیمت قابل قبول
#  حداکثر ۱۰٪ بالاتر از مبلغ برآورد بر اساس قیمت‌های پایه است و انعقاد
#  قرارداد بیش از آن مجاز نیست.»
# بررسی فقط وقتی روش ۱-۶-۱ یکم (fehrest_period) انتخاب شده باشد.
# مبلغ برآورد بر اساس قیمت‌های پایه = ctx["base_total"] (تفسیر ۱۸).
# آینهٔ tests/char_ts/test_T108_ceiling.ts
# ─────────────────────────────────────────────────────────────
import sys

import pytest

sys.path.insert(0, r"C:\Users\AriAfar\Desktop\MetreYar2")
from app import (TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

BASE = 10_000_000_000.0


def _ctx(base_total=BASE):
    return {"chapter_amounts": {"06": BASE}, "floors_amount": BASE,
            "base_total": base_total, "site_setup": 0.0,
            "advance_payment": 0.0, "overhead_coef": 1.3,
            "regional_coef": 1.04, "grand_total": BASE * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": BASE, "excluded_total": 0.0}}


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = "۱۴۰۳/۱۲/۲۹"
    s["work_period_start"] = "۱۴۰۴/۰۱/۰۱"
    s["work_period_end"] = "۱۴۰۴/۱۲/۲۹"
    s["fehrest_year"] = "1403"
    s.update(extra)
    return s


def _ceiling_warns(settings, ctx=None):
    w = []
    TechnicalOfficeEngine(_default_fehrest_db(),
                          settings)._tadil_engine(ctx or _ctx(), w)
    return [x for x in w if x["item"] == "contract_price_ceiling_110"]


# ── ۱) قیمت ۱۲۰٪ ⇒ هشدار ──

def test_T108_price_120_pct_warns():
    ws = _ceiling_warns(_on(base_index_method="fehrest_period",
                            contract_initial_amount=1.2e10))
    assert len(ws) == 1
    assert ws[0]["level"] == "هشدار"
    assert ws[0]["category"] == "موتور تعدیل"
    assert ws[0]["ref"] == "نامه-۶"


# ── ۲) قیمت ۱۰۵٪ ⇒ بدون هشدار ──

def test_T108_price_105_pct_no_warn():
    assert _ceiling_warns(_on(base_index_method="fehrest_period",
                              contract_initial_amount=1.05e10)) == []


# ── ۳) دقیقاً ۱۱۰٪ ⇒ بدون هشدار (مرزِ باز) ──

def test_T108_exactly_110_pct_no_warn():
    assert _ceiling_warns(_on(base_index_method="fehrest_period",
                              contract_initial_amount=1.10e10)) == []


# ── ۴) کمی بالاتر از ۱۱۰٪ ⇒ هشدار ──

def test_T108_just_over_110_pct_warns():
    assert len(_ceiling_warns(
        _on(base_index_method="fehrest_period",
            contract_initial_amount=1.1000001e10))) == 1


# ── ۵) روش proposal_period ⇒ بدون بررسی حتی با قیمت ۱۵۰٪ ──

def test_T108_proposal_period_no_check():
    assert _ceiling_warns(_on(base_index_method="proposal_period",
                              contract_initial_amount=1.5e10)) == []


# ── ۶) قیمت خالی ⇒ بدون هشدار ──

def test_T108_no_amount_no_warn():
    assert _ceiling_warns(_on(base_index_method="fehrest_period")) == []


# ── ۷) پیامِ هشدار اعداد را درست نمایش می‌دهد ──

def test_T108_warning_message_shows_amounts():
    ws = _ceiling_warns(_on(base_index_method="fehrest_period",
                            contract_initial_amount=1.2e10))
    msg = ws[0]["message"]
    # fa_float ارقامِ فارسی با جداکنندهٔ هزارگان (کاما) می‌نویسد
    assert "۱۲,۰۰۰,۰۰۰,۰۰۰" in msg
    assert "۱۱,۰۰۰,۰۰۰,۰۰۰" in msg
    assert "۱۰,۰۰۰,۰۰۰,۰۰۰" in msg
    assert "۱۰%" in msg
