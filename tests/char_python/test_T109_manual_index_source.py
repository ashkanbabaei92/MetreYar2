# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# T109 — شاخص‌های دستی با منبعِ اجباری + هشدار اختلاف (گام ۸)
#
# گام ۸ (حرف e):
#   - فیلد src برای شاخص دستی (فصل و رشته) اجباری است؛ اگر نباشد
#     هشدارِ خطای manual_index_source_required داده می‌شود.
#   - اگر شاخص دستی بیش از ۲۰٪ با شاخص config اختلاف داشته باشد
#     هشدارِ manual_index_deviation_20 داده می‌شود (آستانه در config).
#   - برچسبِ src شاملِ منبع می‌شود: «دستی (پیوست ۳)».
# آینهٔ tests/char_ts/test_T109_manual_index_source.ts
# ─────────────────────────────────────────────────────────────
import sys

import pytest

sys.path.insert(0, r"C:\Users\AriAfar\Desktop\MetreYar2")
from app import (TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

BASE = 10_000_000_000.0
IO_CH06 = 7273.8  # شاخصِ گروهیِ فصل ۰۶ در config


def _ctx():
    return {"chapter_amounts": {"06": BASE}, "floors_amount": BASE,
            "base_total": BASE, "site_setup": 0.0, "advance_payment": 0.0,
            "overhead_coef": 1.3, "regional_coef": 1.04,
            "grand_total": BASE * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": BASE, "excluded_total": 0.0}}


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = "۱۴۰۳/۱۲/۲۹"
    s["work_period_start"] = "۱۴۰۴/۰۱/۰۱"
    s["work_period_end"] = "۱۴۰۴/۱۲/۲۹"
    s.update(extra)
    return s


def _tadil(settings):
    w = []
    t = TechnicalOfficeEngine(_default_fehrest_db(),
                              settings)._tadil_engine(_ctx(), w)
    return t, w


# ── ۱) شاخص دستیِ فصل بدون src ⇒ خطای manual_index_source_required ──

def test_T109_chapter_manual_without_src_warns():
    t, w = _tadil(_on(chapter_index_manual={"06": {"io": 7000.0, "it": 12000.0}}))
    req = [x for x in w if x["item"] == "manual_index_source_required"]
    assert len(req) == 1
    assert req[0]["level"] == "خطا"
    assert req[0]["category"] == "موتور تعدیل"
    assert "فصل 06" in req[0]["message"]
    assert req[0]["ref"] == "بخشنامهٔ ۲۰۸۰ — گام ۸"
    # موتور همچنان اجرا می‌شود
    assert len(t["chapters"]) == 1


# ── ۲) شاخص دستیِ فصل با src ⇒ بدون هشدار ──

def test_T109_chapter_manual_with_src_no_warn():
    _t, w = _tadil(_on(chapter_index_manual={"06": {"io": 7000.0, "it": 12000.0,
                                                    "src": "پیوست ۳"}}))
    assert not any(x["item"] == "manual_index_source_required" for x in w)


# ── ۳) برچسب src شاملِ منبع می‌شود ──

def test_T109_chapter_src_label_includes_source():
    t, _w = _tadil(_on(chapter_index_manual={"06": {"io": 7000.0, "it": 12000.0,
                                                    "src": "نامهٔ کارفرما"}}))
    assert t["chapters"][0]["src"] == "دستی (نامهٔ کارفرما)"


# ── ۴) شاخص دستیِ رشته بدون src ⇒ خطا ──

def test_T109_discipline_manual_without_src_warns():
    _t, w = _tadil(_on(discipline_index_manual={"io": 9500.0, "it": 15000.0}))
    req = [x for x in w if x["item"] == "manual_index_source_required"]
    assert len(req) == 1
    assert "رشتهٔ ابنیه" in req[0]["message"]


# ── ۵) شاخص دستیِ رشته با src ⇒ بدون هشدار ──

def test_T109_discipline_manual_with_src_no_warn():
    _t, w = _tadil(_on(discipline_index_manual={"io": 9500.0, "it": 15000.0,
                                                "src": "پیوست ۳"}))
    assert not any(x["item"] == "manual_index_source_required" for x in w)


# ── ۶) اختلاف > ۲۰٪ با config ⇒ هشدارِ manual_index_deviation_20 ──

def test_T109_deviation_over_threshold_warns():
    # شاخص config فصل ۰۶ = ۷۲۷۳٫۸؛ ۱۲۰۰۰ ⇒ اختلاف ~۶۵٪
    _t, w = _tadil(_on(chapter_index_manual={"06": {"io": 12000.0,
                                                    "src": "پیوست ۳"}}))
    dev = [x for x in w if x["item"] == "manual_index_deviation_20"]
    assert len(dev) == 1
    assert dev[0]["level"] == "هشدار"
    assert "فصل 06" in dev[0]["message"]
    assert "۲۰٪" in dev[0]["message"]


# ── ۷) اختلاف < ۲۰٪ ⇒ بدون هشدار ──

def test_T109_deviation_under_threshold_no_warn():
    # ۷۰۰۰ ÷ ۷۲۷۳٫۸ ≈ ۰٫۹۶ ⇒ اختلاف ~۳٫۸٪
    _t, w = _tadil(_on(chapter_index_manual={"06": {"io": 7000.0,
                                                    "src": "پیوست ۳"}}))
    assert not any(x["item"] == "manual_index_deviation_20" for x in w)


# ── ۸) dedup: دو فصلِ ناموجود فقط یک هشدار می‌دهند ──

def test_T109_dedup_across_chapters():
    _t, w = _tadil(_on(
        chapter_index_manual={"06": {"io": 12000.0, "src": "پیوست ۳"},
                             "07": {"io": 13000.0, "src": "پیوست ۳"}},
        chapter_amounts={"06": BASE}))
    dev = [x for x in w if x["item"] == "manual_index_deviation_20"]
    # فقط فصل‌های فعال (موجود در ctx) بررسی می‌شوند ⇒ ۰۷ نادیده
    assert len(dev) == 1
    assert dev[0]["_code"] == "06"


# ── ۹) فصل بدون شاخص دستی ⇒ هیچ‌کدام از هشدارها ──

def test_T109_no_manual_no_warns():
    _t, w = _tadil(_on())
    assert not any(x["item"] == "manual_index_source_required" for x in w)
    assert not any(x["item"] == "manual_index_deviation_20" for x in w)


# ── ۱۰) موتور برآورد هم همین بررسی‌ها را دارد ──

def test_T109_baravord_chapter_manual_without_src_warns():
    s = _on(baravord_enabled=True,
            chapter_index_manual={"06": {"io": 7000.0, "it": 12000.0}})
    w = []
    TechnicalOfficeEngine(_default_fehrest_db(),
                          s)._baravord_engine(_ctx(), w)
    assert any(x["item"] == "manual_index_source_required" for x in w)
