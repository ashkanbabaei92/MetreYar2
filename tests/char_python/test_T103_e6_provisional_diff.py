# -*- coding: utf-8 -*-
"""T103 — فاز E-6 Part C گام ۹ (حرف a): بند ۲-۶ — مابه‌التفاوتِ آخرین
صورت‌وضعیتِ موقت و صورت‌وضعیتِ قطعی.

بند ۲-۶ بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (docs/sources/2080_summary.md):
  مابه‌التفاوت آخرین صورت‌وضعیت موقت و صورت‌وضعیت قطعی: اگر در مدت پیمان
  انجام شده، با میانگین شاخص‌های دوره‌های سه‌ماههٔ بین تاریخ شروع پیمان و
  تاریخ آخرین صورت‌وضعیت موقت.
  تبصرهٔ ۱: اگر دورهٔ انجام بخشی از آن قابل تشخیص است، با شاخص همان دوره.
  تبصرهٔ ۲: اگر تمام یا بخشی از آن در تأخیر غیرمجاز انجام شده، طبق ۲-۵-۲.

آینهٔ test_T103_e6_provisional_diff.ts — مقدارِ «منتظر» از همان جدولی
محاسبه می‌شود که موتور می‌خواند (_quarter_index) — هیچ عددی حدس زده نمی‌شود.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

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


def _notes(t):
    return (t.get("chapters") or [{}])[0].get("delay_notes") or []


def _lpd_warns(w):
    return [x for x in w if x.get("item") == "last_provisional_date"]


# ── بدونِ آخرین موقت: هیچ بازنویسی‌ای نیست (اعداد مرجع ثابت) ──

def test_T103_no_lpd_no_override():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=12))
    assert _notes(t) == []
    assert _lpd_warns(w) == []
    t0, _, _ = _tadil(_on())
    assert t["delta_p"] == pytest.approx(t0["delta_p"])


# ── متنِ اصلیِ بند: میانگین شاخص‌های شروع تا آخرین موقت ──

def test_T103_lpd_mid_average():
    """lpd = ۱۴۰۴/۰۶/۳۰ ⇒ span26 = Q1+Q2؛ Q3 و Q4 میانگین می‌گیرند."""
    t, w, eng = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=12,
                           last_provisional_date="۱۴۰۴/۰۶/۳۰"))
    assert _lpd_warns(w) == []
    _span = ["1404Q1", "1404Q2"]       # workSplit(شروع، lpd)
    _vals = [eng._quarter_index("06", tq, 1.0)[0] for tq in _span]
    _exp = sum(_vals) / float(len(_vals))
    m = _qmap(t)
    # Q1 و Q2 شاخصِ خودشان را نگه می‌دارند
    for q in ("1404Q1", "1404Q2"):
        assert m[q][0] == pytest.approx(
            eng._quarter_index("06", q, 1.0)[0], abs=1e-6)
        assert "۲-۶" not in m[q][1]
    # Q3 و Q4 میانگینِ ۲-۶ را می‌گیرند
    for q in ("1404Q3", "1404Q4"):
        assert m[q][0] == pytest.approx(_exp, abs=1e-6)
        assert "۲-۶" in m[q][1]
    notes = _notes(t)
    assert [n["q"] for n in notes] == ["1404Q3", "1404Q4"]
    assert all(n["rule"] == "۲-۶" for n in notes)


# ── تبصرهٔ ۱: شاخصِ همان دوره (بدونِ بازنویسی) ──

def test_T103_own_period_no_override():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=12,
                         last_provisional_date="۱۴۰۴/۰۶/۳۰",
                         provisional_diff_method="own_period"))
    t0, _, _ = _tadil(_on())
    assert _qmap(t) == _qmap(t0)
    assert _notes(t) == []
    assert t["delta_p"] == pytest.approx(t0["delta_p"])


# ── lpd قبل از شروعِ پیمان: هشدار + بدونِ بازنویسی ──

def test_T103_lpd_before_contract_warns():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۶/۰۱",
                         contract_duration_months=12,
                         last_provisional_date="۱۴۰۴/۰۱/۰۱"))
    f = _lpd_warns(w)
    assert len(f) == 1
    assert "قبل از شروع" in f[0]["message"]
    assert "۲-۶" in f[0]["ref"]
    assert _notes(t) == []
    t0, _, _ = _tadil(_on())
    assert t["delta_p"] == pytest.approx(t0["delta_p"])


# ── بدونِ تاریخِ شروع: هشدار + بدونِ بازنویسی ──

def test_T103_no_contract_date_warns():
    t, w, _ = _tadil(_on(contract_duration_months=12,
                         last_provisional_date="۱۴۰۴/۰۶/۳۰"))
    f = _lpd_warns(w)
    assert len(f) == 1
    assert "شروع پیمان" in f[0]["message"]
    assert _notes(t) == []
    t0, _, _ = _tadil(_on())
    assert t["delta_p"] == pytest.approx(t0["delta_p"])


# ── lpd نامعتبر: هشدار ──

def test_T103_invalid_lpd_warns():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=12,
                         last_provisional_date="نامعتبر"))
    f = _lpd_warns(w)
    assert len(f) == 1
    assert "نامعتبر" in f[0]["message"]
    assert _notes(t) == []


# ── lpd بعد از پایانِ کار: بدونِ بازنویسی ──

def test_T103_lpd_after_work_noop():
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=12,
                         last_provisional_date="۱۴۰۵/۰۶/۳۰"))
    assert _lpd_warns(w) == []
    assert _notes(t) == []
    t0, _, _ = _tadil(_on())
    assert t["delta_p"] == pytest.approx(t0["delta_p"])


# ── تبصرهٔ ۲: تأخیر غیرمجاز → ۲-۵-۲ (اولویت) ──

def test_T103_unauthorized_delay_wins():
    ext = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "غیرمجاز",
            "doc_no": "ن۲"}]
    t, w, _ = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                         contract_duration_months=3,
                         contract_extensions=ext,
                         last_provisional_date="۱۴۰۴/۰۶/۳۰"))
    notes = _notes(t)
    # همهٔ یادداشت‌ها ۲-۵-۲ هستند؛ هیچکدام ۲-۶ نیست
    assert notes
    assert all(n["rule"] == "غیرمجاز" for n in notes)
    assert not [n for n in notes if n["rule"] == "۲-۶"]
    m = _qmap(t)
    assert all("۲-۶" not in m[q][1] for q in m)


# ── تمدیدِ مجاز: کارِ پوشش‌شده جزوِ مدت است ⇒ ۲-۶ (تفسیر — §۱۸-۳) ──

def test_T103_allowed_extension_covered_by_26():
    """تمدیدِ مجاز، مدت را طولانی می‌کند؛ کارِ بینِ contract_end و
    term_end که بعد از lpd است، میانگینِ ۲-۶ را می‌گیرد."""
    ext = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "مجاز",
            "doc_no": "ن۱"}]
    t, w, eng = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=3,
                           contract_extensions=ext,
                           last_provisional_date="۱۴۰۴/۰۶/۳۰"))
    di = t["delay_info"]
    assert di["term_end"] == "1404/10/01"
    assert di["override"] == {}
    _span = ["1404Q1", "1404Q2"]
    _vals = [eng._quarter_index("06", tq, 1.0)[0] for tq in _span]
    _exp = sum(_vals) / float(len(_vals))
    m = _qmap(t)
    # Q3 (شروع ۱۴۰۴/۰۷/۰۱): بعد از lpd، قبل از term_end، بدون override
    assert m["1404Q3"][0] == pytest.approx(_exp, abs=1e-6)
    assert "۲-۶" in m["1404Q3"][1]
    # Q4 (شروع ۱۴۰۴/۱۰/۰۱ = term_end): بعد از مدت ⇒ شاخصِ خودش (۲-۵-۱)
    assert m["1404Q4"][0] == pytest.approx(
        eng._quarter_index("06", "1404Q4", 1.0)[0], abs=1e-6)
    assert "۲-۶" not in m["1404Q4"][1]
    notes = _notes(t)
    assert [n["q"] for n in notes] == ["1404Q3"]
    assert notes[0]["rule"] == "۲-۶"


# ── تجهیز و برچیدن: همان منطق (شاخص رشته‌ای) ──

def test_T103_setup_uses_discipline_average():
    t, w, eng = _tadil(_on(contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=12,
                           last_provisional_date="۱۴۰۴/۰۶/۳۰"),
                       _ctx(setup=BASE))
    _span = ["1404Q1", "1404Q2"]
    _vals = [eng._quarter_discipline(tq, 1.0)[0] for tq in _span]
    _avg26 = sum(_vals) / float(len(_vals))
    # it تجهیز = Σ(f_q × it_q) — Q3 و Q4 میانگینِ ۲-۶ را می‌گیرند
    _exp_it = 0.0
    for _q, _f in eng._work_split("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۱۲/۲۹"):
        _iv = _avg26 if _q in ("1404Q3", "1404Q4") \
            else eng._quarter_discipline(_q, 1.0)[0]
        _exp_it += float(_f) * float(_iv)
    row = t.get("setup_row") or {}
    assert row["it"] == pytest.approx(_exp_it, abs=1e-6)
    sn = row.get("delay_notes") or []
    assert [n["q"] for n in sn] == ["1404Q3", "1404Q4"]
    assert all(n["rule"] == "۲-۶" for n in sn)
