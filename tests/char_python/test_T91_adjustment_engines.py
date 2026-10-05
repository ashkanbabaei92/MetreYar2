# -*- coding: utf-8 -*-
# T91 — موتورهای تعدیل فاز B (مرحلهٔ ۱۳ — نسخهٔ ۳).
#
# دو موتور کاملاً مجزا که هرگز ادغام نمی‌شوند (قاعدهٔ طلایی ۵):
#   ۱) تعدیل پیمان      : ΔP = k × Σ_c (It_c/Io_c − 1) × A_c   (شاخص هر فصل)
#   ۲) برآورد به‌هنگام   : A_new = Σ_c A_c × It_c/Io_c
# هر دو موتور می‌توانند همزمان فعال شوند (دو شیت و دو کارت مجزا).
#
# nouveautés نسخهٔ ۳:
#   - A = مبلغ کارکرد به قیمت پیمان (A۰ × بالاسری × منطقه‌ای × ضریب پیشنهادی
#     پیمانکار) با تنظیم A_basis (با/بدون ضرایب)؛ ضرایب روی مبالغ فصل‌ها هم
#     اعمال می‌شوند تا Σ A_c = A.
#   - برآورد به‌هنگام: grand به‌هنگام‌شده (شامل ضرایب) کنار grand فعلی.
#   - موتور تعدیل: تاریخ تسلیم پیشنهاد الزامی است (خالی/نامعتبر ⇒ خطا و توقف).
#   - جدول فصل × سه‌ماهه (It هر سه‌ماهه؛ ۱۴۰۵Q1 موقت) در شیت و رابط.
#   - فصل‌های فاقد شاخص (مثل ۱۵) که با شاخص رشته‌ای محاسبه می‌شوند در
#     «مقادیر منتظر تأیید» هر دو موتور ثبت می‌شوند.
#
# شاخص‌ها از config/index_bulletins.json (بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳، پیوست ۳،
# صفحه‌های ۶–۷) خوانده می‌شوند. تجهیز/برچیدن و ردیف‌های بدون شاخص فصل با
# شاخص رشته‌ای تعدیل می‌شوند (بند ۴). Io از تاریخ تسلیم پیشنهاد (بند ۱-۲).
# k = ۰٫۹۵ از بخشنامه ۲۰۸۰ (PDF تصویری) ⇒ پیش‌فرض اپ، نیازمند تأیید؛
# تا تأیید کاربر خروجی «پیش‌نویس» است.
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, ExcelExporter, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

META = {"report_type": "دوره‌ای", "report_no": "۱", "contract_no": "۱",
        "project_name": "پروژه نمونه", "employer": "کارفرما", "contractor": "پیمانکار",
        "consultant": "مشاور", "period_start": "۱۴۰۴/۰۱/۰۱", "period_end": "۱۴۰۴/۰۳/۳۱",
        "location": "گرگان", "contract_date": "۱۴۰۴/۰۱/۰۱"}

# شاخص‌های قطعی استخراج‌شده از پیوست ۳ (بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳)
IO_BASE, IT_Q4 = 9744.7, 14333.1                   # ردیف ۱ (شاخص رشته ابنیه) — صفحهٔ ۴
CH06 = (7273.8, 10632.1)                           # فصل ۶ قالب‌بندی — صفحهٔ ۶
CH08 = (9787.4, 14154.7)                           # فصل ۸ بتن درجا — صفحهٔ ۶
CH28 = (13243.1, 18897.9)                          # فصل ۲۸ حمل‌ونقل — صفحهٔ ۷
A_TEST = 10_000_000_000.0
# ضریب موقت ۱۴۰۵Q1 محاسبه‌شده از CPI + m برای ابنیه (m=۰٫۷):
#   ۱ + ۰٫۷ × (۶۱۹٫۶ ÷ میانگین(۴۶۹٫۴، ۵۱۳٫۶، ۵۴۲٫۳) − ۱) = ۱٫۱۵۳۰۵۱۹…
# (config/cpi_monthly.json + config/provisional_m.json — بخشنامهٔ ۱۴۴۳۷۳)
PROV_COEF = 1.1530518586507572
# ضرایب قیمت پیمان در ctx آزمون‌ها
OH, REG, PROP = 1.3, 1.04, 1.0
PRICE_MULT = OH * REG * PROP                        # ۱٫۳۵۲

# تاریخ تسلیم پیشنهاد پیش‌فرض برای آزمون‌های موتور تعدیل (الزامی در v3)
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"                        # ⇒ Io = اسفند ۱۴۰۳ (مبنا)


def _pipeline(settings):
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    map_df = DynamoMappingParser.merge_formats(results)
    return TechnicalOfficeEngine(_default_fehrest_db(), settings).compute(tables, map_df)


def _ctx(chapters=None, base=A_TEST, setup=0.0, advance=0.0):
    return {"chapter_amounts": chapters or {"06": base},
            "floors_amount": base, "base_total": base, "site_setup": setup,
            "advance_payment": advance,
            "overhead_coef": OH, "regional_coef": REG,
            "grand_total": base * PRICE_MULT,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": base, "excluded_total": 0.0}}


def _tadil(settings, ctx=None, warns=None):
    warns = warns if warns is not None else []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._tadil_engine(ctx or _ctx(), warns), warns


def _baravord(settings, ctx=None, warns=None):
    warns = warns if warns is not None else []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._baravord_engine(ctx or _ctx(), warns), warns


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    return s


# ── فعال‌نبودن پیش‌فرض و استقلال موتورها ──

def test_T91_default_disabled():
    res = _pipeline(default_settings())
    adj = res["adjustment"]
    assert adj == {"tadil": None, "baravord": None}


def test_T91_both_engines_simultaneous():
    res = _pipeline(_on(baravord_enabled=True))
    adj = res["adjustment"]
    assert adj["tadil"] is not None and adj["baravord"] is not None
    assert adj["tadil"]["mode"] == "تعدیل پیمان"
    assert adj["baravord"]["mode"] == "برآورد به‌هنگام"
    # فرمول‌ها و خروجی‌ها مستقل‌اند
    assert "Σ_c" in adj["tadil"]["formula"]
    assert "It_c/Io_c" in adj["baravord"]["formula"]


def test_T91_chain_untouched_by_engines():
    base = _pipeline(default_settings())
    on = _pipeline(_on(baravord_enabled=True))
    for key in ("base_total", "floors_amount", "gross_payable", "grand_total",
                "net_payable"):
        assert base[key] == on[key], key


# ── شاخص فصل به فصل (پیوست ۳) ──

def test_T91_chapter_index_int_and_string_codes():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    v_int, _p = eng._chapter_index(6, "base")
    v_str, _p2 = eng._chapter_index("06", "base")
    assert v_int == v_str == CH06[0]
    v28, _p3 = eng._chapter_index("28", "q4")
    assert v28 == CH28[1]


def test_T91_chapter_indices_used_per_chapter():
    res = _pipeline(_on())
    rows = {r["chapter"]: r for r in res["adjustment"]["tadil"]["chapters"]}
    if "06" in rows:
        assert rows["06"]["io"] == CH06[0] and rows["06"]["it"] == CH06[1]
    if "08" in rows:
        assert rows["08"]["io"] == CH08[0] and rows["08"]["it"] == CH08[1]
    if "28" in rows:
        assert rows["28"]["io"] == CH28[0] and rows["28"]["it"] == CH28[1]


def test_T91_tadil_math_matches_independent_computation():
    # فاز E-6: فرمول خام، با گردکردن بند ۸-۲ خاموش
    res = _pipeline(_on(coef_rounding_2080=False))
    t = res["adjustment"]["tadil"]
    expect = 0.0
    for r in t["chapters"]:
        expect += t["coef"] * (r["ratio"] - 1.0) * r["amount"]
    sr = t.get("setup_row")
    if sr:
        expect += t["coef"] * (sr["ratio"] - 1.0) * sr["amount"]
    assert t["delta_p"] == pytest.approx(expect, rel=1e-9)
    assert t["result_amount"] == pytest.approx(t["base_amount"] + t["delta_p"],
                                               rel=1e-9)


def test_T91_exact_rials_not_rounded():
    res = _pipeline(_on())
    t = res["adjustment"]["tadil"]
    assert abs(t["result_amount"] - round(t["result_amount"] / 1000) * 1000) > 1.0
    assert t["delta_p"] != round(t["delta_p"] / 1000) * 1000


def test_T91_manual_chapter_override_takes_precedence():
    t, _w = _tadil(_on(chapter_index_manual={"06": {"io": 7000.0, "it": 14000.0,
                                                     "src": "پیوست ۳"}}))
    r = [x for x in t["chapters"] if x["chapter"] == "06"][0]
    assert r["io"] == 7000.0 and r["it"] == 14000.0
    assert r["ratio"] == pytest.approx(2.0)
    assert r["src"] == "دستی (پیوست ۳)"


def test_T91_missing_chapter_falls_back_to_discipline():
    t, warns = _tadil(_on(), _ctx(chapters={"15": 1_000_000.0}))
    r = [x for x in t["chapters"] if x["chapter"] == "15"][0]
    assert r["io"] == IO_BASE                       # شاخص رشته (بند ۴)
    assert "بدون شاخص فصل" in r["src"]
    assert not t["incomplete"]
    assert any("شاخص فصل" in p["item"] for p in t["pending"])


def test_T91_setup_uses_discipline_index_clause4():
    # فاز E-6: فرمول خام با گردکردن بند ۸-۲ خاموش
    t, _w = _tadil(_on(coef_rounding_2080=False), _ctx(chapters={"06": 5e9}, setup=1e9))
    sr = t["setup_row"]
    assert sr is not None
    assert sr["io"] == IO_BASE
    assert sr["delta"] == pytest.approx(0.95 * (sr["it"] / IO_BASE - 1.0) * 1e9)


# ── v3: A = مبلغ کارکرد به قیمت پیمان (A_basis) ──

def test_T91_A_at_contract_price_with_coefficients():
    t, _w = _tadil(_on())
    labels = [x[0] for x in t["chain"]]
    assert "× ضریب بالاسری" in labels
    assert "× ضریب منطقه‌ای" in labels
    assert "× ضریب پیشنهادی پیمانکار" in labels
    # A = A۰ × ۱٫۳ × ۱٫۰۴ × ۱
    assert t["work_base"] == pytest.approx(A_TEST * PRICE_MULT)
    # ضرایب روی مبالغ فصل‌ها هم اعمال شده‌اند تا Σ A_c = A
    assert sum(r["amount"] for r in t["chapters"]) == pytest.approx(
        t["work_base"], rel=1e-9)


def test_T91_A_basis_without_coefficients():
    t, _w = _tadil(_on(A_basis="بدون ضرایب"))
    labels = [x[0] for x in t["chain"]]
    assert "× ضریب بالاسری" not in labels
    assert t["work_base"] == pytest.approx(A_TEST)
    assert sum(r["amount"] for r in t["chapters"]) == pytest.approx(
        t["work_base"], rel=1e-9)


def test_T91_proposal_coef_applied_and_pending():
    t, _w = _tadil(_on(proposal_coef=1.1))
    assert t["work_base"] == pytest.approx(A_TEST * PRICE_MULT * 1.1)
    assert any("ضریب پیشنهادی پیمانکار" in p["item"] and p["value"] == 1.1
               for p in t["pending"])


# ── v3: Io از تاریخ تسلیم پیشنهاد (الزامی در موتور تعدیل) ──

def test_T91_proposal_date_sets_io_quarter():
    t, _w = _tadil(_on(proposal_date="۱۴۰۴/۰۵/۱۰"))
    assert t["io_q"] == "1404Q2"


def test_T91_proposal_date_q4_1403_is_base():
    t, _w = _tadil(_on(proposal_date="۱۴۰۳/۱۲/۲۹"))
    assert t["io_q"] == "1403Q4"


def test_T91_missing_proposal_date_stops_engine():
    res = _pipeline(_on(proposal_date=""))
    t = res["adjustment"]["tadil"]
    assert t["error"]
    assert t["incomplete"] is True
    assert t["chapters"] == []
    assert t["delta_p"] == 0.0
    assert any(w["level"] == "خطا" and w["item"] == "proposal_date"
               for w in res["warnings"])


def test_T91_invalid_proposal_date_stops_engine():
    t, warns = _tadil(_on(proposal_date="نامعتبر"))
    assert t["error"]
    assert t["incomplete"] is True
    assert t["chapters"] == []
    assert any(w["level"] == "خطا" and w["item"] == "proposal_date" for w in warns)


def test_T91_baravord_does_not_need_proposal_date():
    # پیش‌فرض اسفند ۱۴۰۳ فقط برای برآورد به‌هنگام می‌ماند (قاعدهٔ کاربر ۳)
    b, warns = _baravord(_on(baravord_enabled=True, proposal_date=""))
    assert b["io_q"] == "1403Q4"
    assert not any(w["item"] == "proposal_date" for w in warns)


# ── تقسیم کارکرد بین سه‌ماهه‌ها ──

def test_T91_work_split_single_quarter():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    sp = eng._work_split("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۰۳/۳۱")
    assert sp == [("1404Q1", 1.0)]


def test_T91_work_split_multi_quarter_sums_to_one():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    sp = eng._work_split("۱۴۰۴/۰۱/۰۱", "۱۴۰۵/۰۲/۱۵")
    assert len(sp) >= 5
    assert sum(f for _q, f in sp) == pytest.approx(1.0)
    assert sp[0][0] == "1404Q1" and sp[-1][0] == "1405Q1"


def test_T91_work_split_delay_exclusion():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    sp = eng._work_split("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۰۶/۳۰",
                         delay_text="۱۴۰۴/۰۴/۰۱")
    qs = [q for q, _f in sp]
    assert "1404Q1" not in qs
    assert "1404Q2" in qs


def test_T91_split_used_when_work_period_set():
    res = _pipeline(_on(work_period_start="۱۴۰۴/۰۱/۰۱",
                        work_period_end="۱۴۰۴/۰۶/۳۰"))
    sp = res["adjustment"]["tadil"]["split"]
    assert [q for q, _f in sp] == ["1404Q1", "1404Q2"]


# ── v3: جدول فصل × سه‌ماهه (It هر سه‌ماهه) ──

def test_T91_quarter_table_per_chapter():
    t, _w = _tadil(_on(provisional_coef_1405q1=PROV_COEF,
                       work_period_start="۱۴۰۴/۰۱/۰۱",
                       work_period_end="۱۴۰۵/۰۲/۱۵"))
    assert len(t["split"]) == 5
    for r in t["chapters"]:
        qs = r.get("quarters") or []
        assert len(qs) == 5
        assert [q for q, _v, _s in qs] == [q for q, _f in t["split"]]
        # آخرین سه‌ماهه (۱۴۰۵Q1) موقت است
        assert qs[-1][0] == "1405Q1"
        assert qs[-1][2] == "موقت"
        # بقیه قطعی
        assert all(st == "قطعی" for _q, _v, st in qs[:-1])


def test_T91_quarter_table_single_entry_in_single_quarter():
    t, _w = _tadil(_on())
    for r in t["chapters"]:
        qs = r.get("quarters") or []
        # بدون دورهٔ کارکرد فقط یک سه‌ماهه (It انتخابی) در جدول هست
        assert len(qs) == 1
        assert qs[0][0] == t["split"][0][0]


# ── شاخص موقت ۱۴۰۵Q1 = ضریب × آخرین قطعی ──

def test_T91_provisional_index_applied_to_1405q1():
    t, _w = _tadil(_on(provisional_coef_1405q1=PROV_COEF,
                       work_period_start="۱۴۰۵/۰۱/۰۱",
                       work_period_end="۱۴۰۵/۰۳/۳۱"))
    r = t["chapters"][0]
    assert t["split"][0][0] == "1405Q1"
    assert r["it"] == pytest.approx(CH06[1] * PROV_COEF)
    assert r["status"] == "موقت"
    assert t["delta_p"] > t["delta_p_definitive"]


def test_T91_provisional_pending_registry_entry():
    t, _w = _tadil(_on(provisional_coef_1405q1=PROV_COEF))
    assert any("موقت" in p["item"] and p["value"] == PROV_COEF for p in t["pending"])


# ── کسورات ──

def test_T91_advance_deducted_from_base():
    t, _w = _tadil(_on(tadil_advance_mode="کسر پیش‌پرداخت"),
                   _ctx(advance=2e9))
    # کسر پیش‌پرداخت پس از اعمال ضرایب قیمت پیمان
    assert t["work_base"] == pytest.approx(A_TEST * PRICE_MULT - 2e9)
    assert any("پیش‌پرداخت" in x[0] for x in t["chain"])


def test_T91_advance_not_deducted_for_baravord():
    b, _w = _baravord(_on(tadil_advance_mode="کسر پیش‌پرداخت"),
                      _ctx(advance=2e9))
    assert b["work_base"] == pytest.approx(A_TEST * PRICE_MULT)


def test_T91_negative_delta_clamped():
    # Io = شاخص q4 (بالا) و It = base (پایین) ⇒ تعدیل منفی
    t, warns = _tadil(_on(proposal_date="۱۴۰۴/۱۲/۲۹",
                          tadil_it_period="base",
                          tadil_allow_negative=False))
    assert t["delta_p"] == 0.0
    assert any(w["level"] == "هشدار" for w in warns)


def test_T91_negative_delta_allowed():
    t, _w = _tadil(_on(proposal_date="۱۴۰۴/۱۲/۲۹",
                       tadil_it_period="base",
                       tadil_allow_negative=True))
    assert t["delta_p"] < 0


# ── موتور ۲: برآورد به‌هنگام ──

def test_T91_baravord_math():
    b, _w = _baravord(_on(baravord_enabled=True),
                      _ctx(chapters={"06": 6e9, "28": 4e9}))
    expect = 0.0
    for r in b["chapters"]:
        expect += r["amount"] * r["ratio"]
    assert b["result_amount"] == pytest.approx(expect, rel=1e-9)


def test_T91_baravord_no_k_and_no_rounding():
    b, _w = _baravord(_on(baravord_enabled=True))
    assert abs(b["result_amount"] - round(b["result_amount"])) > 0


# ── v3: grand به‌هنگام‌شده (اعمال ضرایب پس از It/Io) ──

def test_T91_baravord_grand_updated_with_coefficients():
    b, _w = _baravord(_on(baravord_enabled=True),
                      _ctx(chapters={"06": 6e9, "28": 4e9}))
    # A_basis = با ضرایب ⇒ ضرایب داخل A_c هستند ⇒ grand_updated = result
    assert b["grand_updated"] == pytest.approx(b["result_amount"], rel=1e-9)
    assert b["grand_current"] == pytest.approx(A_TEST * PRICE_MULT)
    assert b["applied_mult"] == pytest.approx(PRICE_MULT)


def test_T91_baravord_grand_updated_without_coefficients():
    b, _w = _baravord(_on(baravord_enabled=True, A_basis="بدون ضرایب"),
                      _ctx(chapters={"06": 6e9, "28": 4e9}))
    # ضرایب پس از It/Io اعمال می‌شوند تا grand به قیمت پیمان به‌دست آید
    assert b["applied_mult"] == 1.0
    assert b["grand_updated"] == pytest.approx(b["result_amount"] * PRICE_MULT,
                                               rel=1e-9)


def test_T91_baravord_grand_updated_matches_pipeline():
    res = _pipeline(_on(baravord_enabled=True))
    b = res["adjustment"]["baravord"]
    assert b["grand_current"] == pytest.approx(res["grand_total"], rel=1e-9)
    # روی پروژهٔ مرجع، grand به‌هنگام‌شده باید از grand فعلی بیشتر باشد
    assert b["grand_updated"] > res["grand_total"]


# ── v3: fallback شاخص رشته‌ای در رجیستری هر دو موتور ──

def test_T91_chapter15_fallback_in_both_pending_registries():
    ctx = _ctx(chapters={"15": 1_000_000.0, "06": 5e9})
    t, _w = _tadil(_on(), ctx)
    b, _w2 = _baravord(_on(baravord_enabled=True), ctx)
    assert any(p["item"] == "شاخص فصل 15 — Io" for p in t["pending"])
    assert any(p["item"] == "شاخص فصل 15 — Io" for p in b["pending"])


# ── پیش‌نویس و رجیستری مقادیر منتظر تأیید ──

def test_T91_draft_until_approved():
    t, _w = _tadil(_on())
    assert t["draft"] is True
    t2, _w2 = _tadil(_on(tadil_approved=True))
    assert t2["draft"] is False


def test_T91_pending_has_k_with_bulletin_2080_source():
    t, _w = _tadil(_on())
    k_row = [p for p in t["pending"] if "ضریب قانونی" in p["item"]]
    assert k_row and k_row[0]["value"] == 0.95
    assert "۲۰۸۰" in k_row[0]["source"]
    assert "بند ۱-۸" in k_row[0]["page"]


def test_T91_k_derived_not_user_input():
    """فاز E-6 (بخشنامهٔ ۲۰۸۰): k ورودی کاربر نیست، از
    completed_within_term مشتق می‌شود (بند ۱-۸ و تبصرهٔ ۲)."""
    t_none, w_none = _tadil(_on())
    assert t_none["coef"] == 0.95
    assert t_none["completed_within_term"] is False
    t_true, w_true = _tadil(_on(completed_within_term=True))
    assert t_true["coef"] == 1.0
    assert t_true["completed_within_term"] is True
    t_false, w_false = _tadil(_on(completed_within_term=False))
    assert t_false["coef"] == 0.95
    # tadil_coef قدیمی دیگر در موتور اثری ندارد
    t_legacy, w_legacy = _tadil(_on(tadil_coef=5.0))
    assert t_legacy["coef"] == 0.95
    assert not any(w["item"] == "tadil_coef" for w in w_legacy)


# ── کمکّی‌های تاریخ شمسی ──

def test_T91_split_rounded_sums_exactly():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    # اعداد دقیق سناریوی مرجع §۱۴-۶
    r, a, b = eng._split_rounded(9937407877.639488220, 7709893479.404506, 2)
    assert r == pytest.approx(9937407877.64)
    assert a == pytest.approx(7709893479.40)
    # نامساویِ کلیدی: قطعی + علی‌الحساب ≡ ΔP (دقیق)
    assert a + b == r
    assert b == pytest.approx(2227514398.24)
    # بدون رقم اعشار
    r0, a0, b0 = eng._split_rounded(9937407877.639488220, 7709893479.404506)
    assert r0 == 9937407878 and a0 + b0 == r0
    # مقادیر منفی و صفر
    rn, an, bn = eng._split_rounded(-1000000.006, -600000.004, 2)
    assert rn == -1000000.01
    assert an + bn == rn
    assert eng._split_rounded(0.0, 0.0) == (0.0, 0.0, 0.0)


def test_T91_delta_p_split_rounded_on_reference():
    # مقدارهای مرجع پیش از فاز E-6 (گردکردن بند ۸-۲ خاموش) — میراث
    res = _pipeline(_on(baravord_enabled=True, coef_rounding_2080=False,
                        work_period_start="۱۴۰۴/۰۱/۰۱",
                        work_period_end="۱۴۰۵/۰۲/۱۵",
                        provisional_coef_1405q1=PROV_COEF))
    t = res["adjustment"]["tadil"]
    # مقادیر دقیق موتور
    assert t["delta_p_definitive"] + t["delta_p_provisional"] \
        == pytest.approx(t["delta_p"], rel=1e-12)
    # تفکیک گردشده
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    r, a, b = eng._split_rounded(t["delta_p"], t["delta_p_definitive"], 2)
    assert a + b == r
    assert r == 9937407877.64


def test_T91_date_quarter():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    assert eng._date_quarter("۱۴۰۴/۰۱/۰۵") == "1404Q1"
    assert eng._date_quarter("۱۴۰۴/۱۲/۲۹") == "1404Q4"
    assert eng._date_quarter("۱۴۰۳/۱۰/۰۱") == "1403Q4"
    assert eng._date_quarter("بد") is None


def test_T91_jalali_leap():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    assert eng._jalali_leap(1404) is True
    assert eng._jalali_leap(1403) is False


# ── خروجی Excel ──

_XLS_EXTRA = dict(baravord_enabled=True,
                  proposal_date="۱۴۰۳/۱۲/۲۹",
                  work_period_start="۱۴۰۴/۰۱/۰۱",
                  work_period_end="۱۴۰۵/۰۲/۱۵",
                  provisional_coef_1405q1=PROV_COEF)


def test_T91_excel_sheets_with_both_engines():
    res = _pipeline(_on(**_XLS_EXTRA))
    data = ExcelExporter().export(META, res, _on(**_XLS_EXTRA), [])
    names = [n for n in zipfile.ZipFile(io.BytesIO(data)).namelist()
             if n.startswith("xl/worksheets")]
    assert len(names) == 19, names
    wb = zipfile.ZipFile(io.BytesIO(data)).read("xl/workbook.xml").decode("utf-8")
    for sheet in ("تعدیل پیمان", "برآورد به‌هنگام",
                  "بخش قطعی و علی‌الحساب", "مقادیر منتظر تأیید",
                  "قیمت‌های دستی", "سابقهٔ ویرایش"):
        assert sheet in wb


def test_T91_excel_tadil_sheet_has_quarter_table():
    res = _pipeline(_on(**_XLS_EXTRA))
    data = ExcelExporter().export(META, res, _on(**_XLS_EXTRA), [])
    shared = zipfile.ZipFile(io.BytesIO(data)).read(
        "xl/sharedStrings.xml").decode("utf-8")
    assert "شاخص It هر فصل در هر سه‌ماههٔ کارکرد" in shared
    # ردیف grand به‌هنگام‌شده در شیت برآورد
    assert "جمع کل به‌هنگام‌شده (قیمت پیمان)" in shared


def test_T91_excel_no_engine_sheets_by_default():
    res = _pipeline(default_settings())
    data = ExcelExporter().export(META, res, default_settings(), [])
    names = [n for n in zipfile.ZipFile(io.BytesIO(data)).namelist()
             if n.startswith("xl/worksheets")]
    assert len(names) == 16, names
    wb = zipfile.ZipFile(io.BytesIO(data)).read("xl/workbook.xml").decode("utf-8")
    assert "تعدیل پیمان" not in wb
    assert "بخش قطعی و علی‌الحساب" not in wb


def test_T91_excel_pending_registry_has_chapter_indices():
    res = _pipeline(_on())
    data = ExcelExporter().export(META, res, _on(), [])
    shared = zipfile.ZipFile(io.BytesIO(data)).read("xl/sharedStrings.xml").decode("utf-8")
    assert "شاخص فصول ابنیه" in shared
    assert "فصل ۶ — شاخص اسفند ۱۴۰۳ (مبنا)" in shared


# ── v4→فاز E: ضریب موقت ۱۴۰۵Q1 — محاسبهٔ خودکار از CPI + m ──
# (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱: coef = ۱ + m × (CPI[اردیبهشت ۱۴۰۵] ÷
# میانگین CPI[دی، بهمن، اسفند ۱۴۰۴] − ۱). CPI از مرکز آمار ایران در
# config/cpi_monthly.json و m به ازای رشته در config/provisional_m.json.
# ضریب دستی کاربر (provisional_coef_1405q1) اگر وارد شود معیار است.
# اگر شاخص ماهانهٔ CPI موجود نباشد، موتورها می‌ایستند.)

def test_T91_provisional_coef_computed_from_cpi():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    # ابنیه: m=۰٫۷ ⇒ ۱ + ۰٫۷ × (۶۱۹٫۶ ÷ ۵۰۸٫۴۳۳۳… − ۱)
    coef, st, tr = eng._provisional_coef_1405q1("ابنیه")
    assert st == "محاسبه‌شده"
    assert tr["m"] == pytest.approx(0.7, rel=1e-12)
    assert tr["numerator"] == pytest.approx(619.6, rel=1e-12)
    assert tr["denominator_mean"] == pytest.approx(508.43333333333334,
                                                   rel=1e-12)
    assert coef == pytest.approx(1.1530518586507572, rel=1e-12)
    # m=۱٫۱ — چهار رشتهٔ انتقال/توزیع برق
    c11, _s, _t = eng._provisional_coef_1405q1("توزیع نیروی برق")
    assert c11 == pytest.approx(1.2405100635940471, rel=1e-12)
    # m=۱٫۰ — جدول دوم پیوست
    c10, _s, _t = eng._provisional_coef_1405q1("فضای سبز")
    assert c10 == pytest.approx(1.2186455123582247, rel=1e-12)
    # رشتهٔ ناشناخته ⇒ None (قاعدهٔ طلایی: حدس زده نمی‌شود)
    cx, stx, _t = eng._provisional_coef_1405q1("رشتهٔ ناشناخته")
    assert cx is None
    assert stx == "ناموجود"


def test_T91_tadil_auto_provisional_when_work_reaches_1405q1():
    # بدون ورودی دستی، ضریب از CPI + m محاسبه و اعمال می‌شود.
    t, _w = _tadil(_on(work_period_start="۱۴۰۴/۰۱/۰۱",
                       work_period_end="۱۴۰۵/۰۲/۱۵"))
    assert not t.get("error")
    assert len(t["chapters"]) > 0
    assert t["delta_p"] > 0
    r = t["chapters"][0]
    assert r["quarters"][-1][0] == "1405Q1"
    assert r["quarters"][-1][2] == "موقت"
    assert r["quarters"][-1][1] == pytest.approx(CH06[1] * PROV_COEF,
                                                  rel=1e-12)


def test_T91_tadil_stops_when_cpi_missing(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "CPI_MONTHLY", {"months": {}})
    t, warns = _tadil(_on(work_period_start="۱۴۰۴/۰۱/۰۱",
                          work_period_end="۱۴۰۵/۰۲/۱۵"))
    assert t.get("error")
    assert t["chapters"] == []
    assert t["delta_p"] == 0.0
    assert any(w["level"] == "خطا"
               and w["item"] == "provisional_coef_1405q1" for w in warns)


def test_T91_tadil_runs_with_provisional_in_1405q1():
    t, _w = _tadil(_on(provisional_coef_1405q1=PROV_COEF,
                       work_period_start="۱۴۰۴/۰۱/۰۱",
                       work_period_end="۱۴۰۵/۰۲/۱۵"))
    assert not t.get("error")
    assert len(t["chapters"]) > 0
    assert t["delta_p"] > 0


def test_T91_tadil_delta_p_provisional_field():
    t, _w = _tadil(_on(provisional_coef_1405q1=PROV_COEF,
                       work_period_start="۱۴۰۴/۰۱/۰۱",
                       work_period_end="۱۴۰۵/۰۲/۱۵"))
    assert "delta_p_provisional" in t
    assert t["delta_p_provisional"] == pytest.approx(
        t["delta_p"] - t["delta_p_definitive"], rel=1e-9, abs=1e-6)
    assert t["delta_p_provisional"] > 0
    assert t["delta_p_definitive"] > 0


def test_T91_tadil_manual_indices_bypass_provisional_requirement():
    # اگر شاخص دستی It برای همهٔ فصل‌ها وارد شده باشد، ضریب موقت لازم
    # نیست و موتور متوقف نمی‌شود.
    s = _on(work_period_start="۱۴۰۴/۰۱/۰۱", work_period_end="۱۴۰۵/۰۲/۱۵")
    s["chapter_index_manual"] = {"06": {"io": 7273.8, "it": 11900.0,
                                        "src": "پیوست ۳"}}
    t, warns = _tadil(s, _ctx(chapters={"06": A_TEST}))
    assert not t.get("error")
    assert len(t["chapters"]) == 1
    assert not any(w["item"] == "provisional_coef_1405q1" for w in warns)


def test_T91_baravord_it_1405q1_with_provisional():
    b, _w = _baravord(_on(baravord_enabled=True,
                          baravord_it_period="1405Q1",
                          provisional_coef_1405q1=PROV_COEF),
                      _ctx(chapters={"06": 6e9}))
    assert b["it_q"] == "1405Q1"
    r = b["chapters"][0]
    assert r["status"] == "موقت"
    assert r["it"] == pytest.approx(CH06[1] * PROV_COEF)
    assert r["ratio"] == pytest.approx(CH06[1] * PROV_COEF / CH06[0])


def test_T91_baravord_it_1405q1_auto_provisional():
    # بدون ورودی دستی، It موقت ۱۴۰۵Q1 از CPI + m محاسبه می‌شود.
    b, _w = _baravord(_on(baravord_enabled=True,
                          baravord_it_period="1405Q1"),
                      _ctx(chapters={"06": 6e9}))
    assert b["it_q"] == "1405Q1"
    assert not b.get("error")
    r = b["chapters"][0]
    assert r["status"] == "موقت"
    assert r["it"] == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)
    assert r["ratio"] == pytest.approx(CH06[1] * PROV_COEF / CH06[0],
                                        rel=1e-12)


def test_T91_baravord_it_1405q1_stops_when_cpi_missing(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "CPI_MONTHLY", {"months": {}})
    b, warns = _baravord(_on(baravord_enabled=True,
                             baravord_it_period="1405Q1"))
    assert b.get("error")
    assert b["chapters"] == []
    assert any(w["level"] == "خطا"
               and w["item"] == "provisional_coef_1405q1" for w in warns)


def test_T91_baravord_it_q4_definitive_by_default():
    b, _w = _baravord(_on(baravord_enabled=True))
    assert b["it_q"] == "1404Q4"
    assert all(r["status"] == "قطعی" for r in b["chapters"])


# ── فاز E (بندهای ۲ و ۳): تعمیم ضریب موقت به همهٔ سه‌ماهه‌های ۱۴۰۵+ ──

def test_T91_quarter_is_provisional():
    e = TechnicalOfficeEngine
    assert e._quarter_is_provisional("1404Q4") is False
    assert e._quarter_is_provisional("1405Q1") is True
    assert e._quarter_is_provisional("1405Q2") is True
    assert e._quarter_is_provisional("1405Q4") is True
    assert e._quarter_is_provisional("1406Q2") is True
    assert e._quarter_is_provisional(None) is False
    assert e._quarter_is_provisional("x") is False


def test_T91_quarter_index_later_1405_quarters():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    for q in ("1405Q2", "1405Q3", "1405Q4", "1406Q1"):
        v, st = eng._quarter_index("06", q, PROV_COEF)
        assert v is not None and st == "موقت"
        assert v == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)
        vd, std = eng._quarter_discipline(q, PROV_COEF)
        assert vd is not None and std == "موقت"
        assert vd == pytest.approx(IT_Q4 * PROV_COEF, rel=1e-12)
    # بدون ضریب ⇒ ناموجود (قاعدهٔ طلایی: حدس زده نمی‌شود)
    v2, st2 = eng._quarter_index("06", "1405Q2", None)
    assert v2 is None and st2 == "ناموجود"


def test_T91_tadil_later_1405_quarters_provisional():
    # کارکرد تا مرداد ۱۴۰۵ ⇒ ۱۴۰۵Q1 و ۱۴۰۵Q2 هر دو موقت (بند ۳)
    t, _w = _tadil(_on(work_period_start="۱۴۰۴/۰۱/۰۱",
                       work_period_end="۱۴۰۵/۰۵/۱۵"))
    assert not t.get("error")
    _qs = [q for q, _f in t["split"]]
    assert "1405Q1" in _qs and "1405Q2" in _qs
    for r in t["chapters"]:
        for q, _iv, st in r["quarters"]:
            if q.startswith("1405"):
                assert st == "موقت"
        # مقدار همهٔ سه‌ماهه‌های موقت یکسان است (ضریب × قطعی ۱۴۰۴Q4)
        _prov = {q: iv for q, iv, st in r["quarters"]
                 if q.startswith("1405")}
        assert _prov["1405Q1"] == pytest.approx(_prov["1405Q2"], rel=1e-12)
    assert t["delta_p_provisional"] > 0


def test_T91_tadil_later_1405_quarters_stop_when_cpi_missing(monkeypatch):
    import app as _app
    monkeypatch.setattr(_app, "CPI_MONTHLY", {"months": {}})
    t, warns = _tadil(_on(work_period_start="۱۴۰۴/۰۱/۰۱",
                          work_period_end="۱۴۰۵/۰۵/۱۵"))
    assert t.get("error")
    assert t["chapters"] == []
    assert any(w["level"] == "خطا"
               and w["item"] == "provisional_coef_1405q1" for w in warns)


def test_T91_baravord_it_1405q2_provisional():
    b, _w = _baravord(_on(baravord_enabled=True,
                          baravord_it_period="1405Q2",
                          provisional_coef_1405q1=PROV_COEF),
                      _ctx(chapters={"06": 6e9}))
    assert b["it_q"] == "1405Q2"
    r = b["chapters"][0]
    assert r["status"] == "موقت"
    assert r["it"] == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)


def test_T91_baravord_it_1405q2_auto_provisional():
    b, _w = _baravord(_on(baravord_enabled=True,
                          baravord_it_period="1405Q2"),
                      _ctx(chapters={"06": 6e9}))
    assert b["it_q"] == "1405Q2"
    assert not b.get("error")
    r = b["chapters"][0]
    assert r["status"] == "موقت"
    assert r["it"] == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)


# ── فاز E (E3 — بخشنامهٔ ۱۴۴۳۷۴): Io ماهانهٔ خرداد ۱۴۰۵ ──
# اگر مهلت تسلیم پیشنهاد در تابستان ۱۴۰۵ باشد، Io شاخص ماهانهٔ
# خرداد ۱۴۰۵ (آحادبها) است، نه سه‌ماهه‌ای. تا این شاخص وارد نشده
# باشد، موتورها با خطا متوقف می‌شوند (قاعدهٔ طلایی: حدس زده نمی‌شود).
# ۱۴۴۳۷۴ همچنین ضریب تبدیل مبنا ندارد (حذف شد).

def test_T91_proposal_deadline_sets_io_quarter():
    # مهلت تسلیم مقدم بر تاریخ تسلیم است
    t, _w = _tadil(_on(proposal_date="۱۴۰۴/۰۵/۱۰",
                       proposal_deadline="۱۴۰۴/۰۸/۲۰"))
    assert t["io_q"] == "1404Q3"
    assert t["io_month"] is None


def test_T91_io_summer_1405_needs_monthly_index():
    t, warns = _tadil(_on(proposal_date="۱۴۰۵/۰۲/۱۵",
                          proposal_deadline="۱۴۰۵/۰۵/۱۰"))
    assert t.get("error")
    assert t["chapters"] == []
    assert t["io_month"] == "khordad_1405"
    assert any(w["level"] == "خطا" and w["item"] == "monthly_index_1405"
               for w in warns)


def test_T91_baravord_io_summer_1405_needs_monthly_index():
    b, warns = _baravord(_on(baravord_enabled=True,
                            proposal_date="۱۴۰۵/۰۲/۱۵",
                            proposal_deadline="۱۴۰۵/۰۶/۰۵"))
    assert b.get("error")
    assert b["chapters"] == []
    assert b["io_month"] == "khordad_1405"
    assert any(w["level"] == "خطا" and w["item"] == "monthly_index_1405"
               for w in warns)


def test_T91_io_summer_1405_uses_monthly_index(monkeypatch):
    # شاخص ماهانهٔ خرداد ۱۴۰۵ به‌صورت مصنوعی وارد می‌شود (دادهٔ واقعی
    # هنوز منتشر نشده — هرگز حدس زده نمی‌شود).
    import copy
    import app as _app
    _cfg = copy.deepcopy(_app.INDEX_BULLETINS)
    _cfg["monthly"]["chapters_abnieh"] = [
        {"chapter": 6, "khordad_1405": 12000.0, "page": 1}]
    _cfg["monthly"]["disciplines"] = [
        {"name": "ابنیه", "khordad_1405": 15000.0, "page": 1}]
    monkeypatch.setattr(_app, "INDEX_BULLETINS", _cfg)
    t, _w = _tadil(_on(proposal_date="۱۴۰۵/۰۲/۱۵",
                       proposal_deadline="۱۴۰۵/۰۵/۱۰",
                       work_period_start="۱۴۰۵/۰۴/۰۱",
                       work_period_end="۱۴۰۵/۰۶/۳۰",
                       provisional_coef_1405q1=PROV_COEF))
    assert not t.get("error")
    assert t["io_month"] == "khordad_1405"
    r = t["chapters"][0]
    # Io فصل ۶ = ۱۲۰۰۰ (ماهانه)، It = قطعی ۱۴۰۴Q4 × ضریب موقت
    assert r["io"] == pytest.approx(12000.0, rel=1e-12)
    _it = next((iv for q, iv, st in r["quarters"] if q == "1405Q2"), None)
    assert _it == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)


def test_T91_base_conversion_coef_ignored():
    # بخشنامهٔ ۱۴۴۳۷۴ ضریب تبدیل مبنا ندارد — حتی اگر در تنظیمات
    # قدیمی باشد، نادیده گرفته می‌شود.
    t, _w = _tadil(_on(base_conversion_coef=1.05))
    assert t["work_base"] == pytest.approx(A_TEST * PRICE_MULT)
    assert not any("ضریب تبدیل مبنا" in x[0] for x in t["chain"])


# ── فاز E (بندهای ۴ و ۵): هشدارهای شیت هشدارها ──

def _adj(settings, ctx=None):
    warns = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    out = eng._adjustment(ctx or _ctx(), warns)
    return out, warns


def test_T91_bund4_info_warning_when_provisional_used():
    out, warns = _adj(_on(proposal_date="۱۴۰۴/۰۱/۰۱",
                          work_period_start="۱۴۰۵/۰۱/۰۱",
                          work_period_end="۱۴۰۵/۰۲/۱۵",
                          provisional_coef_1405q1=PROV_COEF))
    assert out["tadil"]["chapters"]
    assert any(x["item"] == "definitive_1405" and x["level"] == "اطلاع"
               for x in warns)


def test_T91_bund4_no_warning_for_definitive_only():
    out, warns = _adj(_on(proposal_date="۱۴۰۴/۰۱/۰۱"))
    assert not any(x["item"] == "definitive_1405" for x in warns)


def test_T91_bund4_baravord_status_provisional():
    # موتور برآورد: It موقت (۱۴۰۵Q1) ⇒ هشدار بند ۴
    out, warns = _adj(_on(baravord_enabled=True,
                          baravord_it_period="1405Q1",
                          provisional_coef_1405q1=PROV_COEF))
    assert any(r["status"] == "موقت" for r in out["baravord"]["chapters"])
    assert any(x["item"] == "definitive_1405" and x["level"] == "اطلاع"
               for x in warns)


def test_T91_bund5_info_warning_when_engines_on():
    out, warns = _adj(_on())
    assert any(x["item"] == "instructions_744317" and x["level"] == "اطلاع"
               for x in warns)


def test_T91_excel_sheet_renamed_and_has_sections():
    res = _pipeline(_on(**_XLS_EXTRA))
    data = ExcelExporter().export(META, res, _on(**_XLS_EXTRA), [])
    wb = zipfile.ZipFile(io.BytesIO(data)).read("xl/workbook.xml").decode("utf-8")
    assert "بخش قطعی و علی‌الحساب" in wb
    assert "مابه‌التفاوت موقت و قطعی" not in wb
    shared = zipfile.ZipFile(io.BytesIO(data)).read(
        "xl/sharedStrings.xml").decode("utf-8")
    assert "جمع تعدیل (شامل علی‌الحساب، ریال)" in shared
