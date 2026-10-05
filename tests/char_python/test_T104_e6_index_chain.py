# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# T104 — فاز E-6 Part C گام ۶ (حرف b): مسیر شاخص — بندهای ۲-۱/۲-۲
#
# بند ۲-۱: پیمان‌های با مبلغ اولیهٔ کمتر از آستانه با شاخص رشته‌ای تعدیل
# می‌شوند. بند ۲-۲: آستانه و بیشتر با شاخص‌های گروهی (هر فصل).
# آستانه از config/index_bulletins.json → bulletin_2080.threshold_rail.
# آینهٔ tests/char_ts/test_T104_e6_index_chain.ts — اعداد از همان جدولی
# محاسبه می‌شوند که موتور می‌خواند (indexValue/quarterDiscipline).
# ─────────────────────────────────────────────────────────────
import sys

import pytest

sys.path.insert(0, r"C:\Users\AriAfar\Desktop\MetreYar2")
from app import (TechnicalOfficeEngine, _default_fehrest_db, copy_project,
                 default_settings)

BASE = 10_000_000_000.0
# ΔP مرجعِ این تنظیمات (گروهی، setup=۰) — از موتور استخراج شده تا
# تغییرِ ناخواستهٔ مسیرِ گروهی فوراً خودش را نشان دهد.
REF_DELTA_P_GROUP = 4273060821.9178085


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


def _ch(t):
    return (t.get("chapters") or [{}])[0]


def _warn(w, item):
    return [x for x in w if x.get("item") == item]


# ── ۱) پیش‌فرض: مسیر گروهی، بدون تغییر، بدون هشدار ──

def test_T104_default_is_group():
    t, w, _ = _tadil(_on())
    assert t["index_method_resolved"] == {"method": "گروهی",
                                          "source": "دستی"}
    assert t["delta_p"] == pytest.approx(REF_DELTA_P_GROUP)
    assert _warn(w, "index_method_threshold_1370") == []
    assert _warn(w, "index_method_no_amount") == []


# ── ۲) خودکار + مبلغِ کمتر از آستانه ⇒ رشته‌ای + هشدارِ آستانه ──

def test_T104_auto_below_threshold_is_reshteh():
    t, w, _ = _tadil(_on(index_method="خودکار",
                         contract_initial_amount=200_000_000))
    assert t["index_method_resolved"]["method"] == "رشته‌ای"
    assert t["index_method_resolved"]["source"] == \
        "خودکار: مبلغ اولیه < آستانه (بند ۲-۱)"
    f = _warn(w, "index_method_threshold_1370")
    assert len(f) == 1
    assert f[0]["level"] == "اطلاع"
    assert f[0]["category"] == "موتور تعدیل"
    assert f[0]["message"].startswith("آستانهٔ ۳۰۰,۰۰۰,۰۰۰ ریال")
    assert f[0]["action"] == "آستانه و مبلغ اولیهٔ پیمان را بررسی کنید."
    assert f[0]["ref"] == "بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲"


# ── ۳) خودکار + مبلغِ آستانه و بیشتر ⇒ گروهی، مثلِ پیش‌فرض ──

def test_T104_auto_above_threshold_is_group():
    t0, _, _ = _tadil(_on())
    t, _, _ = _tadil(_on(index_method="خودکار",
                         contract_initial_amount=400_000_000))
    assert t["index_method_resolved"]["method"] == "گروهی"
    assert t["delta_p"] == pytest.approx(t0["delta_p"])


# ── ۴) خودکار بدون مبلغ ⇒ گروهی + هشدار ──

def test_T104_auto_without_amount_is_group():
    t, w, _ = _tadil(_on(index_method="خودکار",
                         contract_initial_amount=None))
    assert t["index_method_resolved"]["method"] == "گروهی"
    f = _warn(w, "index_method_no_amount")
    assert len(f) == 1
    assert f[0]["level"] == "هشدار"
    assert f[0]["category"] == "موتور تعدیل"
    assert f[0]["message"] == (
        "مسیر شاخص «خودکار» است ولی مبلغ اولیهٔ پیمان وارد نشده؛ "
        "مسیر گروهی (۲-۲) فرض می‌شود.")
    assert f[0]["action"] == (
        "مبلغ اولیهٔ پیمان را در بخش «ورودی‌های قرارداد» وارد کنید.")
    assert f[0]["ref"] == "بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲"


# ── ۵) مرزِ دقیقِ آستانه ⇒ گروهی (آستانه مشمولِ ۲-۲ است) ──

def test_T104_boundary_exact_threshold_is_group():
    t, _, _ = _tadil(_on(index_method="خودکار",
                         contract_initial_amount=300_000_000))
    assert t["index_method_resolved"]["method"] == "گروهی"


# ── ۶) رشته‌ایِ دستی: شاخصِ رشته برای Io و Itِ هر سه‌ماهه ──

def test_T104_manual_reshteh_uses_discipline():
    t, _, eng = _tadil(_on(index_method="رشته‌ای"))
    ch = _ch(t)
    # Io = شاخص رشتهٔ ابنیه در دورهٔ مبنا
    d_io, _ = eng._index_value("base", "ابنیه")
    assert ch["io"] == pytest.approx(d_io)
    assert ch["src"] == "شاخص رشته (مسیر ۲-۱)"
    # Itِ هر سه‌ماهه = شاخص رشته (نه شاخصِ فصل)
    for q, v, _st in (ch.get("quarters") or []):
        dv, _ = eng._quarter_discipline(q, 1.0, "ابنیه")
        assert v == pytest.approx(dv)
    # نسبتِ وزن‌دار: Σ f_q × it_q ÷ io
    _exp = 0.0
    for q, f in eng._work_split("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۱۲/۲۹"):
        dv, _ = eng._quarter_discipline(q, 1.0, "ابنیه")
        _exp += f * dv
    assert ch["ratio"] == pytest.approx(_exp / d_io, rel=1e-12)


# ── ۷) رشته‌ای + ۲-۶: میانگینِ شاخص‌های رشته تا آخرین موقت ──

def test_T104_reshteh_26_average_uses_discipline():
    t, _, eng = _tadil(_on(index_method="رشته‌ای",
                           contract_date="۱۴۰۴/۰۱/۰۱",
                           contract_duration_months=12,
                           last_provisional_date="۱۴۰۴/۰۶/۳۰"))
    ch = _ch(t)
    # سه‌ماهه‌های بعد از موقت باید با میانگینِ شاخصِ رشته روی span26
    # محاسبه شوند (موتور خودش span26 را از همان جدول می‌سازد)
    _span = [q for q, _f in eng._work_split("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۰۶/۳۰")]
    _vals = []
    for q in _span:
        dv, _ = eng._quarter_discipline(q, 1.0, "ابنیه")
        _vals.append(dv)
    _avg = sum(_vals) / float(len(_vals))
    _notes = {n["q"]: n for n in (ch.get("delay_notes") or [])}
    _checked = 0
    for q, v, _st in (ch.get("quarters") or []):
        if q in _notes and _notes[q]["rule"] == "۲-۶":
            assert v == pytest.approx(_avg)
            _checked += 1
    assert _checked > 0


# ── ۸) هشدارها وقتی هر دو موتور روشن‌اند یکبار ساطع می‌شوند ──

def test_T104_warnings_deduped_across_engines():
    s = _on(index_method="خودکار", baravord_enabled=True)
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), s)
    eng._tadil_engine(_ctx(), w)
    eng._baravord_engine(_ctx(), w)
    assert len(_warn(w, "index_method_threshold_1370")) == 1
    assert len(_warn(w, "index_method_no_amount")) == 1


# ─ـ ۹) هر دو موتور مسیرِ حل‌شده را برمی‌گردانند ──

def test_T104_resolved_in_both_engines():
    s = _on(index_method="خودکار", contract_initial_amount=200_000_000,
            baravord_enabled=True)
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), s)
    t = eng._tadil_engine(_ctx(), w)
    b = eng._baravord_engine(_ctx(), w)
    assert t["index_method_resolved"]["method"] == \
        b["index_method_resolved"]["method"] == "رشته‌ای"
    assert t["index_method_resolved"]["source"] == \
        b["index_method_resolved"]["source"]


# ── ۱۰) copy_project مسیر و مبلغ اولیه را نگه می‌دارد ──

def test_T104_copy_project_keeps_index_method():
    s = _on(index_method="خودکار", contract_initial_amount=200_000_000)
    _meta, new_s = copy_project(s, {"project_name": "پروژه"})
    assert new_s["index_method"] == "خودکار"
    assert new_s["contract_initial_amount"] == 200_000_000
