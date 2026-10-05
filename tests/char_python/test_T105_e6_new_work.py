# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# T105 — فاز E-6 Part C گام ۵ (حرف c): کارهای جدید — بندهای ۳-۱..۳-۵
#
# ۳-۱: قیمت از فهرستِ ضمیمهٔ پیمان (شاخص مبنا = مبنای پیمان).
# ۳-۲: فهرستِ پایه / ۳-۳: قیمت روز (شاخص مبنا = دورهٔ آن قیمت‌ها).
# ۳-۴: ترکیب — هر بخش طبق روشِ همان بخش.
# ۳-۵: قیمت بر ۰٫۹۵ تقسیم، سپس × (Io پیمان ÷ Io کار جدید).
# آینهٔ tests/char_ts/test_T105_e6_new_work.ts — اعداد از همان
# جدولی محاسبه می‌شوند که موتور می‌خواند (quarterDiscipline).
# ─────────────────────────────────────────────────────────────
import sys

import pytest

sys.path.insert(0, r"C:\Users\AriAfar\Desktop\MetreYar2")
from app import (TechnicalOfficeEngine, _default_fehrest_db, copy_project,
                 default_settings)

BASE = 10_000_000_000.0
# ΔP و base_amount مرجعِ این تنظیمات (گروهی، setup=۰، بدون کار جدید)
REF_DELTA_P = 4273060821.9178085
REF_BASE_AMT = 13520000000.0
# شاخص‌های رشتهٔ ابنیه (config/index_bulletins.json)
IO_BASE = 9744.7      # اسفند ۱۴۰۳
IO_Q2 = 11608.0       # سه‌ماههٔ دوم ۱۴۰۴


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
    s["baravord_enabled"] = True
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


def _baravord(settings, ctx=None):
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    b = eng._baravord_engine(ctx or _ctx(), w)
    return b, w, eng


def _warn(w, item):
    return [x for x in w if x.get("item") == item]


# ── ۱) پیش‌فرض: کار جدیدی نیست، ردیفی هم نیست ──

def test_T105_default_is_noop():
    t, w, _ = _tadil(_on())
    assert t["new_work_row"] is None
    assert t["delta_p"] == pytest.approx(REF_DELTA_P)
    assert t["base_amount"] == pytest.approx(REF_BASE_AMT)
    assert _warn(w, "new_item_base_period_missing") == []
    assert _warn(w, "new_item_095_conversion") == []


# ── ۲) ۳-۱ فهرست پیمان: شاخص مبنا همان مبنای پیمان ──

def test_T105_31_fehrest_peman():
    t, w, _ = _tadil(_on(new_item_method="فهرست پیمان",
                         new_item_amount=1_000_000_000.0))
    r = t["new_work_row"]
    assert r is not None
    assert r["method"] == "فهرست پیمان"
    assert r["amount"] == pytest.approx(1_000_000_000.0)
    assert r["io"] == pytest.approx(IO_BASE)
    assert r["io_new"] == pytest.approx(IO_BASE)   # ۳-۱ ⇒ همان Io
    assert r["conv"] == pytest.approx(1.0)
    assert r["ratio"] == pytest.approx(1.2786616005244016)
    assert r["it"] == pytest.approx(12460.173698630137)
    assert r["delta"] == pytest.approx(265315068.49315068)
    assert r["delta"] == pytest.approx(r["value"])
    assert r["delta_definitive"] == pytest.approx(r["delta"])
    assert r["delta_k095"] == pytest.approx(r["delta"])
    # جمع‌ها
    assert t["delta_p"] == pytest.approx(4538375890.410959)
    assert t["delta_p_definitive"] == pytest.approx(4538375890.410959)
    assert t["delta_p_provisional"] == pytest.approx(0.0, abs=1e-6)
    # مبلغ پایه به اندازهٔ کار جدید زیاد می‌شود
    assert t["base_amount"] == pytest.approx(REF_BASE_AMT + 1_000_000_000.0)
    # ضریبِ هر سه‌ماهه گرد شده (بند ۸-۲)
    assert [x[2] for x in r["coef_rows"]] == pytest.approx(
        [0.15, 0.18, 0.29, 0.45])
    assert _warn(w, "new_item_base_period_missing") == []


# ── ۳) ۳-۲ فهرست پایه: شاخص مبنا = دورهٔ فهرست پایه ──

def test_T105_32_fehrest_payeh():
    t, w, _ = _tadil(_on(new_item_method="فهرست پایه",
                         new_item_amount=1_000_000_000.0,
                         new_item_base_period="1404Q2"))
    r = t["new_work_row"]
    assert r["method"] == "فهرست پایه"
    assert r["io_new"] == pytest.approx(IO_Q2)
    # ۳-۵: تبدیل = (Io پیمان ÷ Io کار جدید) / ۰٫۹۵
    assert r["conv"] == pytest.approx((IO_BASE / IO_Q2) / 0.95)
    assert r["conv"] == pytest.approx(0.883664623308789)
    assert r["amount"] == pytest.approx(883664623.308789)
    assert r["delta"] == pytest.approx(234449540.05814552)
    assert t["delta_p"] == pytest.approx(4507510361.975954)
    # هشدارِ اطلاعاتیِ ۳-۵
    f = _warn(w, "new_item_095_conversion")
    assert len(f) == 1 and f[0]["level"] == "اطلاع"
    assert f[0]["ref"] == "بخشنامهٔ ۲۰۸۰، بند ۳-۵"


# ── ۴) ۳-۳ قیمت روز: همان مسیرِ ۳-۲ ──

def test_T105_33_gheymat_rooz():
    t, _, _ = _tadil(_on(new_item_method="قیمت روز",
                         new_item_amount=1_000_000_000.0,
                         new_item_base_period="1404Q2"))
    r = t["new_work_row"]
    assert r["method"] == "قیمت روز"
    assert r["conv"] == pytest.approx(0.883664623308789)
    assert r["amount"] == pytest.approx(883664623.308789)
    assert r["delta"] == pytest.approx(234449540.05814552)


# ── ۵) ۳-۴ ترکیب: هر بخش طبق روشِ خودش ──

def test_T105_34_tarkib():
    t, _, _ = _tadil(_on(new_item_method="ترکیب",
                         new_item_amount=600_000_000.0,
                         new_item_amount_attached=400_000_000.0,
                         new_item_base_period="1404Q2"))
    r = t["new_work_row"]
    assert r["method"] == "ترکیب"
    assert r["amount_own"] == pytest.approx(400_000_000.0)
    assert r["amount_new"] == pytest.approx(600_000_000.0)
    # ۴e8 + ۶e8 × conv
    assert r["amount"] == pytest.approx(
        400_000_000.0 + 600_000_000.0 * 0.883664623308789)
    assert r["amount"] == pytest.approx(930198773.9852734)
    assert r["delta"] == pytest.approx(246795751.4321476)


# ── ۶) دورهٔ مبنا ناموجود ⇒ خطا و بدونِ ردیف ──

def test_T105_missing_base_period_is_error():
    t, w, _ = _tadil(_on(new_item_method="فهرست پایه",
                         new_item_amount=1_000_000_000.0))
    assert t["new_work_row"] is None
    assert t["delta_p"] == pytest.approx(REF_DELTA_P)   # بدون تغییر
    f = _warn(w, "new_item_base_period_missing")
    assert len(f) == 1
    assert f[0]["level"] == "خطا"
    assert f[0]["ref"] == "بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳"


# ── ۷) روشِ نامعتبر ⇒ برگشت به فهرست پیمان ──

def test_T105_invalid_method_falls_back():
    t, _, _ = _tadil(_on(new_item_method="نامعتبر",
                         new_item_amount=1_000_000_000.0))
    r = t["new_work_row"]
    assert r["method"] == "فهرست پیمان"
    assert r["amount_own"] == pytest.approx(1_000_000_000.0)
    assert r["amount_new"] == pytest.approx(0.0)
    assert r["delta"] == pytest.approx(265315068.49315068)


# ── ۸) برآورد به‌هنگام: ۳-۲ در result_amount / base_amount ──

def test_T105_baravord_32():
    b, _, _ = _baravord(_on(new_item_method="فهرست پایه",
                            new_item_amount=1_000_000_000.0,
                            new_item_base_period="1404Q2"))
    r = b["new_work_row"]
    assert r is not None
    assert r["value"] == pytest.approx(1299747905.2559035)
    assert b["result_amount"] == pytest.approx(21061906886.806126)
    assert b["grand_updated"] == pytest.approx(21061906886.806126)
    assert b["base_amount"] == pytest.approx(14403664623.308788)


# ── ۹) برآورد به‌هنگام: ۳-۱ ──

def test_T105_baravord_31():
    b, _, _ = _baravord(_on(new_item_method="فهرست پیمان",
                            new_item_amount=1_000_000_000.0))
    r = b["new_work_row"]
    assert r["value"] == pytest.approx(1470861083.460753)
    assert r["io"] == pytest.approx(IO_BASE)
    assert r["it"] == pytest.approx(14333.1)
    assert r["ratio"] == pytest.approx(1.470861083460753)
    assert b["result_amount"] == pytest.approx(21233020065.010975)
    assert b["base_amount"] == pytest.approx(REF_BASE_AMT + 1_000_000_000.0)


# ── ۱۰) گردکردنِ بند ۸-۲: روشن/خاموش ──

def test_T105_coef_rounding():
    t_on, _, _ = _tadil(_on(new_item_method="فهرست پایه",
                            new_item_amount=1_000_000_000.0,
                            new_item_base_period="1404Q2"))
    t_off, _, _ = _tadil(_on(new_item_method="فهرست پایه",
                             new_item_amount=1_000_000_000.0,
                             new_item_base_period="1404Q2",
                             coef_rounding_2080=False))
    r_on = t_on["new_work_row"]
    r_off = t_off["new_work_row"]
    # ضرایبِ خام یکسان هستند
    assert [x[1] for x in r_on["coef_rows"]] == pytest.approx(
        [x[1] for x in r_off["coef_rows"]])
    # گردکردن مقدارِ delta را عوض می‌کند
    assert r_on["delta"] == pytest.approx(234449540.05814552)
    assert r_off["delta"] == pytest.approx(233931228.34511858)
    assert r_on["delta"] != pytest.approx(r_off["delta"])
    assert t_off["delta_p"] == pytest.approx(4467042058.620941)


# ── ۱۱) تبصرهٔ ۲: k_diff شاملِ بخشِ ۰٫۹۵ِ کار جدید است ──

def test_T105_cwt_k_diff_includes_new_work():
    t_new, _, _ = _tadil(_on(new_item_method="فهرست پایه",
                             new_item_amount=1_000_000_000.0,
                             new_item_base_period="1404Q2",
                             completed_within_term=True))
    t_no, _, _ = _tadil(_on(completed_within_term=True))
    assert t_new["k_diff"] == pytest.approx(179157910.65704632)
    assert t_no["k_diff"] == pytest.approx(168166575.3424654)
    # کار جدید k_diff را بیشتر می‌کند (dpNew(k) > dpNew095)
    assert t_new["k_diff"] > t_no["k_diff"]
    # نامتغیرِ همیشگی
    assert t_new["delta_p"] == pytest.approx(
        t_new["delta_p_definitive"] + t_new["delta_p_provisional"])
    # بدونِ تکمیل، k_diff صفر است
    t_nc, _, _ = _tadil(_on(new_item_method="فهرست پایه",
                            new_item_amount=1_000_000_000.0,
                            new_item_base_period="1404Q2"))
    assert t_nc["k_diff"] == pytest.approx(0.0)


# ── ۱۲) copyProject فیلدها را نگه می‌دارد + ددآپِ هشدار ──

def test_T105_copy_project_and_dedup():
    s = _on(new_item_method="ترکیب", new_item_amount=6e8,
            new_item_amount_attached=4e8, new_item_base_period="1404Q2")
    _meta, new_p = copy_project({"settings": s}, {"project_name": "کپی"})
    ns = new_p["settings"]
    assert ns["new_item_method"] == "ترکیب"
    assert ns["new_item_amount"] == pytest.approx(6e8)
    assert ns["new_item_amount_attached"] == pytest.approx(4e8)
    assert ns["new_item_base_period"] == "1404Q2"

    # هشدارِ «دورهٔ مبنا ناموجود» بین دو موتور ددآپ می‌شود
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(),
                                _on(new_item_method="فهرست پایه",
                                    new_item_amount=1_000_000_000.0))
    eng._tadil_engine(_ctx(), w)
    eng._baravord_engine(_ctx(), w)
    miss = _warn(w, "new_item_base_period_missing")
    assert len(miss) == 1
    assert miss[0]["level"] == "خطا"
