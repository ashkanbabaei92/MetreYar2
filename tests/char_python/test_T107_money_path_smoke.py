# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# T107 — دودویِ مسیرهای پولیِ پوشش‌نیافته (فاز E-6)
#
# هدف: هر شاخهٔ محاسبهٔ پولیِ موتورها که در پوششِ آزمون‌ها نبود، حداقل
# یک بار اجرا شود تا هیچ NameError/TypeError نهفته‌ای نمانَد. شاخه‌ها:
#   ۱) ردیفِ تجهیز در موتورِ برآورد (setup > 0)
#   ۲) ترکیبِ تجهیز + کار جدید در برآورد
#   ۳) هشدارِ «دورهٔ مبنا ناموجود» در موتورِ برآورد
#   ۴) تأخیرِ تعیین‌نشده (۲-۵-۳) روی ردیفِ تجهیز
#   ۵) تأخیرِ تعیین‌نشده (۲-۵-۳) روی ردیفِ کار جدید
#   ۶) شاخص دستیِ It فصل + تأخیر
#   ۷) ماتریسِ دودویی: هر دو موتور روی ترکیب‌های متنوع بدون خطا + invariant
# آینهٔ tests/char_ts/test_T107_money_path_smoke.ts
# ─────────────────────────────────────────────────────────────
import itertools
import sys

import pytest

sys.path.insert(0, r"C:\Users\AriAfar\Desktop\MetreYar2")
from app import (TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

BASE = 10_000_000_000.0
SETUP = 100_000_000.0
# شاخصِ گروهیِ فصل ۰۶ و شاخصِ رشتهٔ ابنیه (config)
IO_CH06 = 7273.8
IO_DISC = 9744.7


def _ctx(setup=0.0, chapters=None):
    return {"chapter_amounts": chapters or {"06": BASE}, "floors_amount": BASE,
            "base_total": BASE, "site_setup": setup, "advance_payment": 0.0,
            "overhead_coef": 1.3, "regional_coef": 1.04,
            "grand_total": BASE * 1.352,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": BASE, "excluded_total": 0.0}}


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["baravord_enabled"] = True
    s["proposal_date"] = "۱۴۰۳/۱۲/۲۹"
    s["work_period_start"] = "۱۴۰۴/۰۱/۰۱"
    s["work_period_end"] = "۱۴۰۴/۱۲/۲۹"
    s.update(extra)
    return s


def _tadil(settings, ctx=None):
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._tadil_engine(ctx or _ctx(), w), w, eng


def _baravord(settings, ctx=None):
    w = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._baravord_engine(ctx or _ctx(), w), w, eng


_EXT_UNDEF = [{"date": "۱۴۰۴/۰۴/۰۱", "months": 6, "kind": "تعیین‌نشده",
               "doc_no": "ن۳"}]


# ── ۱) برآورد: ردیف تجهیز ──

def test_T107_baravord_setup_row():
    b, _, _ = _baravord(_on(), _ctx(setup=SETUP))
    sr = b["setup_row"]
    assert sr is not None
    assert sr["amount"] == pytest.approx(SETUP)
    assert sr["io"] == pytest.approx(IO_DISC)
    assert sr["it"] == pytest.approx(14333.1)
    assert sr["ratio"] == pytest.approx(1.470861083460753)
    assert sr["value"] == pytest.approx(147086108.3460753)
    assert b["result_amount"] == pytest.approx(19909245089.896297)
    assert b["base_amount"] == pytest.approx(13620000000.0)
    assert b["grand_updated"] == pytest.approx(b["result_amount"])


# ── ۲) برآورد: تجهیز + کار جدید ۳-۱ ──

def test_T107_baravord_setup_and_new_work():
    b, _, _ = _baravord(
        _on(new_item_method="فهرست پیمان",
            new_item_amount=1_000_000_000.0), _ctx(setup=SETUP))
    assert b["setup_row"]["value"] == pytest.approx(147086108.3460753)
    assert b["new_work_row"]["value"] == pytest.approx(1470861083.460753)
    assert b["result_amount"] == pytest.approx(21380106173.35705)


# ── ۳) برآورد: کار جدید بدونِ دورهٔ مبنا ⇒ هشدار ──

def test_T107_baravord_new_work_missing_period():
    b, w, _ = _baravord(
        _on(new_item_method="فهرست پایه",
            new_item_amount=1_000_000_000.0), _ctx())
    assert b["new_work_row"] is None
    f = [x for x in w if x.get("item") == "new_item_base_period_missing"]
    assert len(f) == 1
    assert f[0]["level"] == "خطا"
    assert f[0]["category"] == "موتور برآورد"
    assert f[0]["ref"] == "بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳"


# ── ۴) تعدیل: تأخیرِ تعیین‌نشده روی ردیفِ تجهیز (۲-۵-۳) ──

def test_T107_tadil_setup_delay_undefined():
    t, _, _ = _tadil(
        _on(contract_date="۱۴۰۴/۰۱/۰۱",
            contract_duration_months=3,
            contract_extensions=list(_EXT_UNDEF)),
        _ctx(setup=SETUP))
    sr = t["setup_row"]
    assert sr is not None
    # هر سه سه‌ماههٔ پس از مدت ⇒ علی‌الحساب با شاخصِ دورهٔ خاتمه
    assert [n["rule"] for n in sr["delay_notes"]] == ["تعیین‌نشده"] * 3
    assert all("۲-۵-۳" in n["note"] for n in sr["delay_notes"])
    assert sr["it"] == pytest.approx(13563.977260273972)
    assert sr["delta"] == pytest.approx(37356164.38356164)
    # Q1 ضریبِ خودش، بقیه ضریبِ دورهٔ خاتمه
    assert [x[2] for x in sr["coef_rows"]] == pytest.approx(
        [0.15, 0.45, 0.45, 0.45])
    # invariant
    assert t["delta_p"] == pytest.approx(
        t["delta_p_definitive"] + t["delta_p_provisional"])


# ── ۵) تعدیل: تأخیرِ تعیین‌نشده روی ردیفِ کار جدید ──

def test_T107_tadil_new_work_delay_undefined():
    t, _, _ = _tadil(
        _on(contract_date="۱۴۰۴/۰۱/۰۱",
            contract_duration_months=3,
            contract_extensions=list(_EXT_UNDEF),
            new_item_method="فهرست پیمان",
            new_item_amount=1_000_000_000.0),
        _ctx(setup=SETUP))
    nr = t["new_work_row"]
    assert nr is not None
    assert [n["rule"] for n in nr["delay_notes"]] == ["تعیین‌نشده"] * 3
    assert nr["it"] == pytest.approx(13563.977260273972)
    assert nr["delta"] == pytest.approx(373561643.83561647)
    assert t["delta_p"] == pytest.approx(5636305205.479452)
    assert t["delta_p"] == pytest.approx(
        t["delta_p_definitive"] + t["delta_p_provisional"])


# ── ۶) شاخص دستیِ It فصل + تأخیر ──

def test_T107_manual_chapter_it_with_delay():
    t, _, _ = _tadil(
        _on(contract_date="۱۴۰۴/۰۱/۰۱",
            contract_duration_months=3,
            contract_extensions=list(_EXT_UNDEF),
            chapter_index_manual={"06": {"it": 13000.0, "src": "دستی"}}),
        _ctx())
    c0 = t["chapters"][0]
    assert c0["io"] == pytest.approx(IO_CH06)
    assert c0["it"] == pytest.approx(13000.0)
    assert "دستی" in c0["status"] and "۲-۵-۳" in c0["status"]
    # ۰٫۹۵ × (13000/7273.8 − 1) = ۰٫۷۴۷۸۷… ⇒ گردشده ۰٫۷۵
    assert [x[2] for x in c0["coef_rows"]] == pytest.approx([0.75] * 4)
    assert t["delta_p"] == pytest.approx(10140000000.0)
    # علی‌الحساب ⇒ همهٔ ΔP موقت
    assert t["delta_p_definitive"] == pytest.approx(0.0, abs=1e-6)
    assert t["delta_p_provisional"] == pytest.approx(t["delta_p"])


# ── ۸) شاخص دستیِ رشته (Io) روی ردیفِ تجهیز ──

def test_T107_manual_discipline_io_on_setup():
    t, _, _ = _tadil(
        _on(discipline_index_manual={"io": 9500.0, "src": "دستی"}),
        _ctx(setup=SETUP))
    sr = t["setup_row"]
    assert sr is not None
    assert sr["io"] == pytest.approx(9500.0)
    assert "دستی" in sr["src"]
    assert sr["value"] == pytest.approx(29531506.84931507)
    # فصلی که شاخصِ گروهی دارد همچنان از شاخصِ گروهی استفاده می‌کند
    assert t["chapters"][0]["io"] == pytest.approx(IO_CH06)
    assert t["delta_p"] == pytest.approx(4302592328.767123)


# ── ۹) فصلِ صغیر نادیده گرفته می‌شود ──

def test_T107_tiny_chapter_skipped():
    t, _, _ = _tadil(_on(), _ctx(chapters={"06": BASE, "07": 0.001}))
    assert [(c["chapter"], c["amount"]) for c in t["chapters"]] == [
        ("06", pytest.approx(13520000000.0))]


# ── ۱۰) برآورد: شاخص دستیِ رشته (Io/It) روی تجهیز و کار جدید ──

def test_T107_baravord_manual_discipline_indices():
    b, _, _ = _baravord(
        _on(discipline_index_manual={"io": 9500.0, "it": 15000.0},
            new_item_method="فهرست پیمان", new_item_amount=1_000_000_000.0),
        _ctx(setup=SETUP))
    assert b["setup_row"]["io"] == pytest.approx(9500.0)
    assert b["setup_row"]["it"] == pytest.approx(15000.0)
    assert b["new_work_row"]["io"] == pytest.approx(9500.0)
    assert b["new_work_row"]["it"] == pytest.approx(15000.0)
    assert b["new_work_row"]["value"] == pytest.approx(1578947368.4210527)
    assert b["result_amount"] == pytest.approx(21499001086.813377)


# ── ۱۱) برآورد: شاخص دستیِ فصل ──

def test_T107_baravord_manual_chapter_indices():
    b, _, _ = _baravord(
        _on(chapter_index_manual={"06": {"io": 7000.0, "it": 12000.0,
                                         "src": "پیوست ۳"}}), _ctx())
    c = b["chapters"][0]
    assert c["io"] == pytest.approx(7000.0)
    assert c["it"] == pytest.approx(12000.0)
    assert c["src"] == "دستی (پیوست ۳)"
    assert c["status"] == "دستی"
    assert c["value"] == pytest.approx(23177142857.142857)
    assert b["result_amount"] == pytest.approx(23177142857.142857)


# ── ۱۲) برآورد: فصلِ صغیر نادیده گرفته می‌شود ──

def test_T107_baravord_tiny_chapter_skipped():
    b, _, _ = _baravord(
        _on(), _ctx(chapters={"06": BASE, "07": 0.001}))
    assert [(c["chapter"], c["amount"]) for c in b["chapters"]] == [
        ("06", pytest.approx(13520000000.0))]


# ─ـ ۱۳) تعدیل: مسیر رشته‌ای + تأخیرِ تعیین‌نشده (useDisc در ۲-۵-۳) ──

def test_T107_tadil_rail_method_with_undefined_delay():
    t, _, _ = _tadil(
        _on(contract_date="۱۴۰۴/۰۱/۰۱", contract_duration_months=3,
            contract_extensions=_EXT_UNDEF, index_method="رشته‌ای"), _ctx())
    c = t["chapters"][0]
    # مسیر رشته‌ای ⇒ شاخص رشتهٔ ابنیه
    assert c["io"] == pytest.approx(IO_DISC)
    assert c["it"] == pytest.approx(13563.977260273972)
    assert "۲-۵-۳" in c["status"]
    assert [n["rule"] for n in c["delay_notes"]] == [
        "تعیین‌نشده", "تعیین‌نشده", "تعیین‌نشده"]
    assert t["delta_p"] == pytest.approx(5050553424.657535)
    assert t["delta_p"] == pytest.approx(
        t["delta_p_definitive"] + t["delta_p_provisional"])


# ─ـ ۱۴) تعدیل: ۲-۵-۲ (غیرمجاز) + شاخص دستیِ It فصل ──

def test_T107_tadil_unauth_delay_with_manual_it():
    t, _, _ = _tadil(
        _on(contract_date="۱۴۰۴/۰۱/۰۱", contract_duration_months=3,
            contract_extensions=[{"date": "۱۴۰۴/۰۴/۰۱", "months": 6,
                                  "kind": "غیرمجاز", "doc_no": "ن۲"}],
            chapter_index_manual={"06": {"io": 7273.8, "it": 11900.0,
                                             "src": "پیوست ۳"}}),
        _ctx())
    c = t["chapters"][0]
    assert c["io"] == pytest.approx(7273.8)
    assert c["it"] == pytest.approx(11900.0)
    assert "۲-۵-۲" in c["status"]
    # شاخص دستی ⇒ میانگین مدت همان مقدار دستی است
    assert [n["rule"] for n in c["delay_notes"]] == [
        "غیرمجاز", "غیرمجاز", "غیرمجاز"]
    assert [r[2] for r in c["coef_rows"]] == [pytest.approx(0.6)] * 4
    assert t["delta_p"] == pytest.approx(8112000000.0)
    assert t["delta_p_definitive"] == pytest.approx(0.0)
    assert t["delta_p_provisional"] == pytest.approx(t["delta_p"])


# ─ـ ۱۵) تعدیل: ۲-۶ (آخرین موقت) + شاخص دستیِ It فصل ──

def test_T107_tadil_26_average_with_manual_it():
    t, _, _ = _tadil(
        _on(contract_date="۱۴۰۴/۰۱/۰۱", contract_duration_months=12,
            last_provisional_date="۱۴۰۴/۰۶/۳۰",
            chapter_index_manual={"06": {"io": 7273.8, "it": 11900.0,
                                             "src": "پیوست ۳"}}),
        _ctx())
    c = t["chapters"][0]
    assert c["io"] == pytest.approx(7273.8)
    assert c["it"] == pytest.approx(11900.0)
    assert "۲-۶" in c["status"]
    # فقط فصل‌های پس از آخرین موقت درونِ مدت
    assert [n["q"] for n in c["delay_notes"]] == ["1404Q3", "1404Q4"]
    assert all(n["rule"] == "۲-۶" for n in c["delay_notes"])
    assert [r[2] for r in c["coef_rows"]] == [pytest.approx(0.6)] * 4
    assert t["delta_p"] == pytest.approx(8112000000.0)
    assert t["delta_p_provisional"] == pytest.approx(t["delta_p"])


# ── ۷) ماتریسِ دودویی: هیچ خطایی نهفته نیست + invariant ──

@pytest.mark.parametrize("index_method,cwt,do_round,setup,method,status,"
                         "pdm", [
    (im, cwt, rnd, setup, method, status, pdm)
    for im in ("گروهی", "رشته‌ای")
    for cwt in (None, True)
    for rnd in (True, False)
    for setup in (0.0, SETUP)
    for method in ("فهرست پیمان", "فهرست پایه", "ترکیب")
    for status in ("عادی", "فسخ با قصور")
    for pdm in ("average", "last")
])
def test_T107_smoke_matrix(index_method, cwt, do_round, setup, method,
                           status, pdm):
    extra = {
        "index_method": index_method,
        "completed_within_term": cwt,
        "coef_rounding_2080": do_round,
        "contract_status": status,
        "provisional_diff_method": pdm,
        "new_item_method": method,
        "new_item_amount": 500_000_000.0,
    }
    if method in ("فهرست پایه", "ترکیب"):
        extra["new_item_base_period"] = "1404Q2"
        if method == "ترکیب":
            extra["new_item_amount_attached"] = 300_000_000.0
    t, _, _ = _tadil(_on(**extra), _ctx(setup=setup))
    # invariantِ همیشگی
    assert t["delta_p"] == pytest.approx(
        t["delta_p_definitive"] + t["delta_p_provisional"], abs=1e-3)
    # ردیفِ تجهیز فقط وقتی setup > 0 است
    assert (t["setup_row"] is None) == (setup <= 0)
    # کار جدید همیشه ردیف دارد (روش و دوره معتبرند)
    assert t["new_work_row"] is not None

    b, _, _ = _baravord(_on(**extra), _ctx(setup=setup))
    assert (b["setup_row"] is None) == (setup <= 0)
    assert b["new_work_row"] is not None
    assert b["result_amount"] > 0
