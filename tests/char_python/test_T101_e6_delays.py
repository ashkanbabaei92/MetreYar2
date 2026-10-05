# -*- coding: utf-8 -*-
"""T101 — فاز E-6 Part C گام ۳: تأخیرهای مجاز/غیرمجاز/تعیین‌نشده.

بندهای ۲-۵-۱..۲-۵-۳ بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (docs/sources/2080_summary.md):
  ۲-۵-۱ مجاز       : شاخص همان دورهٔ انجام کار.
  ۲-۵-۲ غیرمجاز    : میانگین شاخص‌های سه‌ماهه‌های داخل مدت پیمان
                     (مدت اولیه + تمدیدها).
  ۲-۵-۳ تعیین‌نشده  : علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمهٔ مدت
                     (یا هر تمدید).

در تمام آزمون‌ها، مقدارِ «منتظرِ» از همان جدولِ شاخصی محاسبه می‌شود که
موتور می‌خواند (_quarter_index/_quarter_discipline) — هیچ عددی حدس زده نمی‌شود.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

# شاخص قطعیِ فصل ۶ در ۱۴۰۴Q4 (پیوست ۳، صفحهٔ ۶) — ثابتِ مرجعٔ آزمون‌ها
CH06_Q4 = 10632.1
BASE = 10_000_000_000.0


def _ctx(setup=0.0):
    return {"chapter_amounts": {"06": BASE}, "floors_amount": BASE,
            "base_total": BASE, "site_setup": setup, "advance_payment": 0.0,
            "overhead_coef": 1.3, "regional_coef": 1.04,
            "grand_total": BASE * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": BASE, "excluded_total": 0.0}}


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = "۱۴۰۳/۱۲/۲۹"          # ⇒ Io = ۱۴۰۳Q4 (مبنا)
    s["work_period_start"] = "۱۴۰۴/۰۱/۰۱"
    s["work_period_end"] = "۱۴۰۴/۱۲/۲۹"
    s.update(extra)
    return s


def _tadil(settings, ctx=None):
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    t = eng._tadil_engine(ctx or _ctx(), w)
    return t, w, eng


def _qmap(t):
    return {q: (v, st) for q, v, st in (t.get("chapters") or [{}])[0].get(
        "quarters") or []}


# ── بند ۲-۵: بدونِ مدتِ پیمان، هیچ بازنویسی‌ای نیست (اعداد مرجع ثابت) ──

def test_T101_no_duration_no_override():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱"))
    assert (t.get("delay_info") or {}).get("override") == {}
    assert (t.get("chapters") or [{}])[0].get("delay_notes") == []
    assert not [x for x in w if x.get("category") == "تأخیر پیمان"]


def test_T101_no_duration_same_as_no_contract():
    """بدونِ مدت، خروجیِ موتور با حالتِ بدونِ تاریخِ پیمان یکسان است."""
    t1, _, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱"))
    t2, _, _ = _tadil(_on())
    assert t1["delta_p"] == pytest.approx(t2["delta_p"])
    assert t1["delta_p_definitive"] == pytest.approx(t2["delta_p_definitive"])


# ── کارکردِ درونِ مدت: بدونِ بازنویسی ──

def test_T101_work_within_term_no_override():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=12))
    di = t["delay_info"]
    assert di["contract_end"] == "1405/01/01"
    assert di["override"] == {}
    assert (t["chapters"][0]["delay_notes"]) == []
    assert not [x for x in w if x.get("category") == "تأخیر پیمان"]


# ── ۲-۵-۱ تأخیر مجاز: شاخص همان دوره ──

def test_T101_mojaz_uses_own_quarter_index():
    ext = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "مجاز",
            "doc_no": "ن۱"}]
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=3,
                         contract_extensions=ext))
    assert t["delay_info"]["override"] == {}
    # همان شاخص‌هایِ حالتِ بدونِ طبقه‌بندی
    t0, _, _ = _tadil(_on())
    assert _qmap(t) == _qmap(t0)
    assert t["delta_p"] == pytest.approx(t0["delta_p"])
    assert t["chapters"][0]["delay_notes"] == []
    assert not [x for x in w if x.get("item") == "delay_uncovered"]


# ── ۲-۵-۲ تأخیر غیرمجاز: میانگین شاخص‌های داخل مدت ──

def test_T101_gh_eir_mojaz_uses_term_average():
    ext = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "غیرمجاز",
            "doc_no": "ن۲"}]
    t, w, eng = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=3,
                           contract_extensions=ext))
    di = t["delay_info"]
    assert di["contract_end"] == "1404/04/01"
    assert di["term_end"] == "1404/10/01"
    assert di["term_quarters"] == ["1404Q1", "1404Q2", "1404Q3", "1404Q4"]
    # سه‌ماهه‌های پس از مدت: Q2, Q3, Q4 (Q1 درونِ مدت است)
    assert set(di["override"]) == {"1404Q2", "1404Q3", "1404Q4"}
    # مقدارِ مورد انتظار: میانگینِ شاخص‌های داخل مدت (از همان جدول)
    _vals = [eng._quarter_index("06", tq, 1.0)[0] for tq in di["term_quarters"]]
    _exp = sum(_vals) / float(len(_vals))
    for q in ("1404Q2", "1404Q3", "1404Q4"):
        v, st = _qmap(t)[q]
        assert v == pytest.approx(_exp, abs=1e-6)
        assert "۲-۵-۲" in st
    # همگی قطعی ⇒ همه‌چیز در سبدِ قطعی
    assert t["delta_p_definitive"] == pytest.approx(t["delta_p"])
    assert t["delta_p_provisional"] == pytest.approx(0.0, abs=1e-6)
    notes = t["chapters"][0]["delay_notes"]
    assert [n["q"] for n in notes] == ["1404Q2", "1404Q3", "1404Q4"]
    assert all(n["rule"] == "غیرمجاز" for n in notes)


# ── ۲-۵-۳ تأخیر تعیین‌نشده: علی‌الحساب با شاخص دورهٔ خاتمه ──

def test_T101_taeen_nashode_is_provisional():
    ext = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "تعیین‌نشده",
            "doc_no": "ن۳"}]
    t, w, eng = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=3,
                           contract_extensions=ext))
    di = t["delay_info"]
    # مبنای علی‌الحساب: سه‌ماههٔ منتهی به تاریخ خاتمهٔ تمدید = 1404Q4
    assert di["override"]["1404Q2"]["basis_q"] == "1404Q4"
    for q in ("1404Q2", "1404Q3", "1404Q4"):
        v, st = _qmap(t)[q]
        assert v == pytest.approx(CH06_Q4, abs=1e-6)
        assert "علی‌الحساب" in st and "۲-۵-۳" in st
    # علی‌الحساب ⇒ در سبدِ موقت، حتی اگر شاخص قطعی است
    assert t["delta_p_provisional"] > 0
    assert t["delta_p_provisional"] == pytest.approx(
        t["delta_p"] - t["delta_p_definitive"])
    # هشدارِ «نیازمندِ تعیین»
    _inf = [x for x in w if x.get("item") == "delay_undefined"]
    assert len(_inf) == 1
    assert "۲-۵-۳" in _inf[0]["ref"]


# ── پس از مدت بدونِ تمدیدِ پوشش‌دهنده ⇒ علی‌الحساب + هشدار ──

def test_T101_uncovered_after_term_warns():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=3))
    di = t["delay_info"]
    # پایانِ مدت = ۱۴۰۴/۰۴/۰۱ ⇒ مبنای علی‌الحساب = 1404Q2
    assert di["term_end"] == "1404/04/01"
    assert di["override"]["1404Q3"]["basis_q"] == "1404Q2"
    v, st = _qmap(t)["1404Q3"]
    assert "علی‌الحساب" in st
    unc = [x for x in w if x.get("item") == "delay_uncovered"]
    _covered = {q for x in unc for q in ("1404Q2", "1404Q3", "1404Q4")
                if "«%s»" % q in x["message"]}
    assert _covered == {"1404Q2", "1404Q3", "1404Q4"}
    assert all("۲-۵-۳" in x["ref"] for x in unc)


# ── تمدید نامعتبر نادیده گرفته می‌شود + خطا ──

def test_T101_invalid_extension_ignored():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=12,
                         contract_extensions=[
                             {"date": "bad", "months": 3, "kind": "مجاز",
                              "doc_no": ""},
                             {"date": "۱۴۰۴/۰۶/۰۱", "months": 0,
                              "kind": "مجاز", "doc_no": ""},
                         ]))
    errs = [x for x in w
            if x.get("item") == "contract_extensions" and x["level"] == "خطا"]
    assert len(errs) == 2
    # چون تمامِ کارکرد درونِ مدت است، بازنویسی‌ای وجود ندارد
    assert t["delay_info"]["override"] == {}
    assert not [x for x in w if x.get("item") == "delay_uncovered"]


# ── مرز: سه‌ماهه‌ای که روی تاریخ خاتمه شروع می‌شود، پس از مدت است ──

def test_T101_quarter_starting_at_term_end_is_after_term():
    # مدت = ۴ ماه ⇒ پایان = ۱۴۰۴/۰۵/۰۱؛ Q2 (شروع ۱۴۰۴/۰۴/۰۱) درونِ مدت
    ext = [{"date": "۱۴۰۴/۰۵/۰۱", "months": 6, "kind": "تعیین‌نشده",
            "doc_no": "ن۴"}]
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=4,
                         contract_extensions=ext))
    assert set(t["delay_info"]["override"]) == {"1404Q3", "1404Q4"}
    t0, _, _ = _tadil(_on())
    # Q2 درونِ مدت است ⇒ شاخصِ خودش
    assert _qmap(t)["1404Q2"] == _qmap(t0)["1404Q2"]


# ── ساختارِ delay_info در خروجی ──

def test_T101_delay_info_present():
    t, _, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=6))
    di = t["delay_info"]
    assert set(di) >= {"contract_end", "term_end", "term_quarters",
                       "override"}
    assert di["contract_end"] == "1404/07/01"
    assert di["term_quarters"] == ["1404Q1", "1404Q2", "1404Q3"]


# ── تجهیز/برچیدن: همان قاعده روی شاخصِ رشته (بند ۴) ──

def test_T101_setup_row_delay_override():
    ext = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "غیرمجاز",
            "doc_no": "ن۵"}]
    t, w, eng = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=3,
                           contract_extensions=ext),
                       ctx=_ctx(setup=BASE))
    sr = t.get("setup_row")
    assert sr is not None
    _term = t["delay_info"]["term_quarters"]
    _avg = (sum(eng._quarter_discipline(tq, 1.0)[0] for tq in _term)
            / float(len(_term)))
    # مجموعِ وزن‌دار: Q1 شاخصِ خودش، بقیه میانگینِ داخلِ مدت
    _w = {q: f for q, f in t["split"]}
    _exp_it = (_w["1404Q1"] * eng._quarter_discipline("1404Q1", 1.0)[0]
               + sum(_w[q] for q in ("1404Q2", "1404Q3", "1404Q4")) * _avg)
    assert sr["it"] == pytest.approx(_exp_it, abs=1e-6)
    assert [n["rule"] for n in sr["delay_notes"]] == ["غیرمجاز"] * 3
    assert all("۲-۵-۲" in n["note"] for n in sr["delay_notes"])


# ── کمک‌آینِ اضافه‌کردنِ ماه به تاریخ شمسی ──

@pytest.mark.parametrize("d,m,exp", [
    ("۱۴۰۴/۰۱/۰۱", 6, "1404/07/01"),
    ("۱۴۰۴/۰۶/۳۱", 1, "1404/07/30"),
    ("۱۴۰۴/۱۲/۲۹", 2, "1405/02/29"),
    ("۱۴۰۴/۰۶/۳۱", 12, "1405/06/31"),
    ("۱۴۰۳/۱۲/۳۰", 1, "1404/01/30"),
    ("۱۴۰۴/۰۱/۰۱", 0, None),
    ("bad", 3, None),
    ("", 3, None),
])
def test_T101_add_months_jalali(d, m, exp):
    assert TechnicalOfficeEngine._add_months_jalali(d, m) == exp
