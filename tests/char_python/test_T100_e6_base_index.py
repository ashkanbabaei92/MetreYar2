# -*- coding: utf-8 -*-
# T100 — فاز E-6 Part C (گام ۲): روش شاخص مبنا (بندهای ۱-۶-۱/۱-۶-۲)،
# پیشنهاد نهاییِ ترک تشریفات (final_offer_date)، و هشدارِ Io بعد از It.
#
# منبع: بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳) — docs/sources/2080_summary.md
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import app
from app import (TechnicalOfficeEngine, _default_fehrest_db, default_settings)

PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"          # ⇒ Io = ۱۴۰۳Q4 (مبنا)


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    return s


def _ctx(chapters=None, base=10_000_000_000.0, setup=0.0):
    return {"chapter_amounts": chapters or {"06": base},
            "floors_amount": base, "base_total": base, "site_setup": setup,
            "advance_payment": 0.0,
            "overhead_coef": 1.3, "regional_coef": 1.04,
            "grand_total": base * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": base, "excluded_total": 0.0}}


def _tadil(settings, ctx=None):
    warns = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._tadil_engine(ctx or _ctx(), warns), warns


# ── ۱-۶-۱ دوم: ترک تشریفات ⇒ ملاک پیشنهاد نهایی کتبی ──

def test_T100_final_offer_date_precedence():
    # بند ۱-۶-۱ دوم: در ترک تشریفات، دورهٔ تسلیم کتبیِ پیشنهاد نهایی ملاک است.
    t, _w = _tadil(_on(proposal_date="۱۴۰۳/۱۲/۲۹",          # ۱۴۰۳Q4
                       proposal_deadline="۱۴۰۴/۰۶/۰۱",       # ۱۴۰۴Q2
                       final_offer_date="۱۴۰۴/۰۹/۰۱"))       # ۱۴۰۴Q3
    assert t.get("error") is None
    assert t["io_q"] == "1404Q3"


def test_T100_deadline_precedence_over_proposal():
    # بدون پیشنهاد نهایی: مهلت تسلیم مقدم بر تاریخ تسلیم است
    t, _w = _tadil(_on(proposal_date="۱۴۰۳/۱۲/۲۹",
                       proposal_deadline="۱۴۰۴/۰۳/۰۱",
                       final_offer_date=""))
    assert t.get("error") is None
    assert t["io_q"] == "1404Q1"


def test_T100_final_offer_date_invalid_stops_engine():
    t, w = _tadil(_on(final_offer_date="بد"))
    assert t.get("error") is not None
    assert any(x["level"] == "خطا" for x in w)


# ── ۱-۶-۲: پیمان بدون فهرست‌بها ──

def test_T100_no_base_list_uses_proposal_period():
    # بند ۱-۶-۲: دورهٔ تسلیم پیشنهاد ملاک است (همان رفتار روش دوم)
    t, _w = _tadil(_on(base_index_method="no_base_list",
                       proposal_date="۱۴۰۴/۰۳/۱۵"))
    assert t.get("error") is None
    assert t["io_q"] == "1404Q1"


# ── ۱-۶-۱ یکم: دورهٔ تهیهٔ فهرست‌بها ──

def test_T100_fehrest_period_without_config_stops(monkeypatch):
    # قاعدهٔ طلایی: دورهٔ قیمت پایهٔ فهرست در config نیست ⇒ توقف +
    # «نیازمند ورود» (هیچ عددی حدس زده نمی‌شود)
    monkeypatch.setattr(app, "FEHREST_BASE_PERIODS", {})
    t, w = _tadil(_on(base_index_method="fehrest_period", fehrest_year="۱۴۰۴"))
    assert t.get("error") is not None
    assert t["incomplete"] is True
    assert any(x["level"] == "خطا" and "proposal_date" == x["item"] for x in w)
    assert "۱۴۰۴" in t["error"]


def test_T100_fehrest_period_null_entry_stops(monkeypatch):
    # مقدار null در config هم به معنای «نیازمند ورود» است
    monkeypatch.setattr(app, "FEHREST_BASE_PERIODS", {"۱۴۰۴": None})
    t, _w = _tadil(_on(base_index_method="fehrest_period", fehrest_year="۱۴۰۴"))
    assert t.get("error") is not None


def test_T100_fehrest_period_with_config_uses_base_quarter(monkeypatch):
    # وقتی دوره در config هست (با منبع)، Io = همان دوره
    monkeypatch.setattr(app, "FEHREST_BASE_PERIODS", {"۱۴۰۴": "1403Q4"})
    t, _w = _tadil(_on(base_index_method="fehrest_period", fehrest_year="۱۴۰۴"))
    assert t.get("error") is None
    assert t["io_q"] == "1403Q4"
    # تاریخ‌های تسلید دیگر ملاک نیستند
    t2, _w2 = _tadil(_on(base_index_method="fehrest_period", fehrest_year="۱۴۰۴",
                         proposal_date="۱۴۰۴/۰۹/۰۱",
                         proposal_deadline="۱۴۰۴/۰۹/۰۱"))
    assert t2["io_q"] == "1403Q4"


def test_T100_fehrest_period_unknown_quarter_stops(monkeypatch):
    # مقدار غیرمجاز در config ⇒ توقف
    monkeypatch.setattr(app, "FEHREST_BASE_PERIODS", {"۱۴۰۴": "1399Q2"})
    t, _w = _tadil(_on(base_index_method="fehrest_period", fehrest_year="۱۴۰۴"))
    assert t.get("error") is not None


def test_T100_fehrest_period_ignores_proposal_dates(monkeypatch):
    # روش اول مستقل از تاریخ‌های تسلیم است
    monkeypatch.setattr(app, "FEHREST_BASE_PERIODS", {"۱۴۰۴": "1403Q4"})
    t, _w = _tadil(_on(base_index_method="fehrest_period", fehrest_year="۱۴۰۴",
                       proposal_date="", proposal_deadline="",
                       final_offer_date=""))
    assert t.get("error") is None
    assert t["io_q"] == "1403Q4"


# ── بند ۱-۷: هشدار Io بعد از It ──

def test_T100_warns_when_io_after_it():
    t, w = _tadil(_on(proposal_date="۱۴۰۴/۰۹/۰۱",   # Io = ۱۴۰۴Q3
                      tadil_it_period="q2"))        # It = ۱۴۰۴Q2
    io_warns = [x for x in w if x["item"] == "io_after_it"]
    assert len(io_warns) == 1
    assert "1404Q3" in io_warns[0]["message"]
    assert "1404Q2" in io_warns[0]["message"]
    assert "۱-۷" in io_warns[0]["ref"]


def test_T100_no_warning_when_io_before_it():
    t, w = _tadil(_on(proposal_date="۱۴۰۳/۱۲/۲۹",   # Io = ۱۴۰۳Q4
                      tadil_it_period="q2"))        # It = ۱۴۰۴Q2
    assert not any(x["item"] == "io_after_it" for x in w)


def test_T100_no_warning_on_reference_defaults():
    # تنظیمات پیش‌فرض: هیچ هشدارِ جدیدی تولید نمی‌شود
    t, w = _tadil(_on())
    assert not any(x["item"] == "io_after_it" for x in w)


# ── مرزهای فصل‌ها (بند ۱-۵: سه‌ماهه‌های منتهی به خرداد/شهریور/آذر/اسفند) ──

@pytest.mark.parametrize("date_text,expected", [
    ("۱۴۰۴/۰۱/۰۱", "1404Q1"),   # ۱ فروردین
    ("۱۴۰۴/۰۳/۳۱", "1404Q1"),   # ۳۱ خرداد — آخر Q1
    ("۱۴۰۴/۰۴/۰۱", "1404Q2"),   # ۱ تیر
    ("۱۴۰۴/۰۶/۳۱", "1404Q2"),   # ۳۱ شهریور — آخر Q2
    ("۱۴۰۴/۰۷/۰۱", "1404Q3"),   # ۱ مهر
    ("۱۴۰۴/۰۹/۳۰", "1404Q3"),   # ۳۰ آذر — آخر Q3
    ("۱۴۰۴/۱۰/۰۱", "1404Q4"),   # ۱ دی
    ("۱۴۰۴/۱۲/۲۹", "1404Q4"),   # ۲۹ اسفند کبیسهٔ ۱۴۰۴ — آخر Q4
    ("۱۴۰۳/۱۲/۲۹", "1403Q4"),
])
def test_T100_quarter_boundaries(date_text, expected):
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    assert eng._date_quarter(date_text) == expected


@pytest.mark.parametrize("bad", ["۱۴۰۴/۱۳/۰۱", "بد", ""])
def test_T100_invalid_dates_rejected(bad):
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    assert eng._date_quarter(bad) is None


def test_T100_month_length_not_validated_but_quarter_correct():
    # یادداشت: تجزیه‌کنندهٔ تاریخ درست‌بودنِ طولِ ماه را بررسی نمی‌کند
    # (۱۴۰۳ کبیسه نیست ولی ۳۰ اسفند را می‌پذیرد). این رفتارِ ازپیش‌وجودداشته
    # است و تغییرش خارج از دامنهٔ فاز E-6 است؛ ولی انتسابِ سه‌ماهه درست است.
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    assert eng._date_quarter("۱۴۰۳/۱۲/۳۰") == "1403Q4"
    assert eng._date_quarter("۱۴۰۴/۱۲/۳۰") == "1404Q4"
    assert eng._date_quarter("۱۴۰۴/۰۱/۳۲") is None
