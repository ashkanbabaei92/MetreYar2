# -*- coding: utf-8 -*-
# T95 — پنل قیمت دستی (فاز C، §۱۵-۴) — لایهٔ موتور (increment 4a)
#
# بررسی‌ها:
#   - مهاجرت ورودی‌های قدیمی (price_overrides float / manual_codes رشته /
#     excluded رشته) به رکوردهای ردیخی‌پذیر، **بدون تغییر ارقام** (درخواست
#     صریح کاربر).
#   - اعمال قیمت دستی روی ردیف‌ها: app_price / diff_pct / price_status.
#   - اولویت: دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی.
#   - ردیف‌های ستاره‌دار: ورود کامل دستی، کد با پسوند *، حضور در صورت‌وضعیت.
#   - هشدار اختلاف > آستانه (پیش‌فرض ۳۰٪).

import copy
import io
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (
    TechnicalOfficeEngine,
    default_settings,
    migrate_manual_entries,
    excluded_ids,
    manual_code_of,
    manual_price_of,
    price_status_of,
    MANUAL_ENTRIES_VERSION,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "char_shared",
    "fixtures", "revit", "T32_rebar_grand_total.json")

import json

with open(FIXTURE_PATH, encoding="utf-8") as _f:
    FIXTURE = json.load(_f)


def _settings(**over):
    s = default_settings()
    s.update({k: FIXTURE["settings"][k] for k in (
        "overhead_coef", "regional_coef", "floors_coef", "site_setup_amount",
        "insurance_pct", "tax_pct", "good_job_pct", "advance_payment")})
    s.pop("_manual_migrated", None)
    s.update(over)
    return s


def _table():
    return copy.deepcopy(FIXTURE["table"])


def _compute(**over):
    """محاسبه روی جدول ترکیبی T32 (سطل‌های آرماتور + حمل) با تنظیمات داده‌شده."""
    table = _table()
    table["grand_total"] = {"weight": 310}
    s = _settings(**over)
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute([table], None)
    return res, s


def _by_id(res):
    return {l["id"]: l for l in res["lines"]}


# ── کمک‌توابع سطح ماژول ──

def test_T95_migrate_manual_entries():
    s = {"price_overrides": {"rebar-070201": 999.0},
         "manual_codes": {"rebar-070203": "070201"},
         "excluded": ["transport-rebar"]}
    migrate_manual_entries(s)
    rec = s["manual_prices"]["rebar-070201"]
    assert rec["price"] == 999.0
    assert rec["source"] == "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)"
    assert rec["status"] == "نیازمند تأیید"
    assert s["manual_codes"]["rebar-070203"] == {
        "code": "070201", "reason": "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)",
        "user": "", "at": ""}
    assert s["excluded"] == [{"id": "transport-rebar", "reason": "",
                              "user": "", "at": ""}]
    # Idempotent
    migrate_manual_entries(s)
    assert s["manual_prices"]["rebar-070201"]["price"] == 999.0


def test_T95_helpers():
    s = {"manual_prices": {"a": {"price": 12.5}},
         "manual_codes": {"b": {"code": "070201"}, "c": "070203"}}
    assert manual_price_of(s, "a") == 12.5
    assert manual_price_of(s, "z") is None
    assert manual_code_of(s, "b") == "070201"
    assert manual_code_of(s, "c") == "070203"
    assert manual_code_of(s, "z") == ""
    assert excluded_ids(s) == set()
    assert excluded_ids({"excluded": ["x", {"id": "y"}]}) == {"x", "y"}


def test_T95_price_status_priority():
    assert price_status_of({"manual": {"price": 1}}) == "دستی"
    assert price_status_of({"needs_review": True}) == "نیازمند ورود"
    assert price_status_of({"estimated": True}) == "موقت"
    assert price_status_of({"method": "fuzzy", "confidence": 0.4}) == "پیش‌فرض اپ"
    assert price_status_of({"method": "rule-exact", "confidence": 0.99}) == "قطعی"
    # دستی برنده است حتی اگر needs_review باشد
    assert price_status_of({"manual": {"price": 1}, "needs_review": True}) == "دستی"


# ─ـ مهاجرت: ارقام تغییر نمی‌کنند (درخواست صریح کاربر) ──

def test_T95_migration_totals_identical():
    """ویرایش قدیمیِ price_overrides و رکورد جدیدِ manual_prices باید
    دقیقاً همان base/grand را بدهند — تا ریال."""
    res_legacy, _s = _compute(price_overrides={"rebar-070201": 999.0})
    res_new, _s2 = _compute(manual_prices={
        "rebar-070201": {"price": 999.0, "source": "استعلام",
                         "doc_no": "Q-1", "doc_date": "۱۴۰۴/۰۵/۰۱", "note": "",
                         "status": "دستی", "chapter": "", "user": "", "at": ""}})
    assert res_legacy["base_total"] == pytest.approx(res_new["base_total"])
    assert res_legacy["grand_total"] == pytest.approx(res_new["grand_total"])
    # و مهاجرت واقعاً رکورد قدیمی را برچسب می‌زند
    assert _s["manual_prices"]["rebar-070201"]["source"] == \
        "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)"


# ─ـ اعمال قیمت دستی ──

def test_T95_manual_price_fields():
    res, s = _compute()
    base_line = _by_id(res)["rebar-070201"]
    orig_price = base_line["price"]

    res2, _s2 = _compute(manual_prices={
        "rebar-070201": {"price": orig_price * 2, "source": "بخشنامه",
                         "doc_no": "۱۴۰۵/۱۵۵۲۳۳", "doc_date": "۱۴۰۵/۰۴/۱۲",
                         "note": "استعلام قیمت فولاد", "status": "دستی",
                         "chapter": "07", "user": "دفتر فنی", "at": "۱۴۰۵/۰۷/۰۸"}})
    line = _by_id(res2)["rebar-070201"]
    assert line["price"] == pytest.approx(orig_price * 2)
    assert line["total"] == pytest.approx(line["qty"] * orig_price * 2)
    assert line["app_price"] == pytest.approx(orig_price)
    assert line["diff_pct"] == pytest.approx(100.0)
    assert line["price_status"] == "دستی"
    assert line["manual"]["doc_no"] == "۱۴۰۵/۱۵۵۲۳۳"
    # رفتار قدیمی: قیمت دستی، ردیف را تأییدشده می‌کند
    assert line["estimated"] is False
    assert line["needs_review"] is False
    # ردیف‌های دیگر دست‌نخورده
    assert _by_id(res2)["rebar-070203"]["price"] == \
        _by_id(res)["rebar-070203"]["price"]
    # زنجیرهٔ مالی با قیمت جدید محاسبه می‌شود
    assert res2["base_total"] > res["base_total"]


def test_T95_diff_warning_above_threshold():
    orig = _by_id(_compute()[0])["rebar-070201"]["price"]
    res, _s = _compute(price_diff_warn_pct=30.0, manual_prices={
        "rebar-070201": {"price": orig * 2, "source": "استعلام", "doc_no": "",
                         "doc_date": "", "note": "", "status": "دستی",
                         "chapter": "", "user": "", "at": ""}})
    pw = [w for w in res["warnings"] if w.get("category") == "قیمت دستی"]
    assert len(pw) == 1
    assert "070201" in pw[0]["message"]
    assert "بازبینی" in pw[0]["action"] or "بررسی" in pw[0]["action"]
    # زیر آستانه: هشدار نیست
    res2, _s2 = _compute(price_diff_warn_pct=300.0, manual_prices={
        "rebar-070201": {"price": orig * 2, "source": "استعلام", "doc_no": "",
                         "doc_date": "", "note": "", "status": "دستی",
                         "chapter": "", "user": "", "at": ""}})
    assert not [w for w in res2["warnings"] if w.get("category") == "قیمت دستی"]


def test_T95_status_summary_and_needs_entry():
    res, _s = _compute()
    assert res["needs_price_entry"] > 0  # transport-rebar: needs_review=True
    assert "قطعی" in res["price_status_summary"]
    assert res["price_status_summary"]["نیازمند ورود"] >= 1
    # ستاره‌داری نیست
    assert res["starred_total"] == 0


# ─ـ ردیف‌های ستاره‌دار ──

def test_T95_starred_row():
    res_base, _s = _compute()
    res, _s2 = _compute(starred_rows=[{
        "code": "990101", "desc": "قفل‌سازی و یراق‌آلات درب‌ها", "unit": "عدد",
        "qty": 12, "price": 2500000, "source": "فاکتور", "doc_no": "F-77",
        "doc_date": "۱۴۰۴/۰۶/۰۱", "note": "خرید محلی", "chapter": "31",
        "user": "دفتر فنی", "at": "۱۴۰۵/۰۷/۰۸"}])
    star = [l for l in res["lines"] if l.get("starred")]
    assert len(star) == 1
    assert star[0]["code"] == "990101*"
    assert star[0]["chapter"] == "31"
    assert star[0]["qty"] == 12
    assert star[0]["total"] == pytest.approx(12 * 2500000)
    assert star[0]["price_status"] == "دستی"
    # در زنجیرهٔ مالی و شاخص تعدیل حاضر است
    assert res["base_total"] - res_base["base_total"] == pytest.approx(12 * 2500000)
    assert res["starred_total"] > 0
    assert res["starred_pct"] > 0
    # کد بدون ستاره خودکار ستاره می‌گیرد
    assert all(l["code"].endswith("*") for l in res["lines"] if l.get("starred"))


def test_T95_starred_row_invalid_skipped():
    res, _s = _compute(starred_rows=[
        {"code": "X1", "qty": 0, "price": 100},       # qty صفر → skip
        {"code": "X2", "qty": 5, "price": 0},         # قیمت صفر → skip
        {"code": "X3", "qty": 5, "price": 100, "chapter": "31",
         "desc": "تست", "unit": "عدد"},               # معتبر
    ])
    assert len([l for l in res["lines"] if l.get("starred")]) == 1


# ─ـ مستثنی‌ها ──

def test_T95_excluded_as_records():
    res, _s = _compute(excluded=[{"id": "transport-rebar", "reason": "حمل اختصاصی",
                                  "user": "دفتر فنی", "at": "۱۴۰۵/۰۷/۰۸"}])
    assert "transport-rebar" not in _by_id(res)
    assert res["base_total"] < _compute()[0]["base_total"]
    # ساختار قدیمی رشته‌ای هم هنوز کار می‌کند
    res2, _s2 = _compute(excluded=["transport-rebar"])
    assert "transport-rebar" not in _by_id(res2)


# ─ـ فایل کناری + ورود/خروج Excel ──

import tempfile

from app import (
    ExcelExporter,
    save_manual_entries,
    load_manual_entries,
    parse_manual_entries_xlsx,
    apply_manual_entries,
    manual_entries_payload,
)


def _meta():
    return {"report_type": "موقت", "report_no": "1", "contract_no": "T95",
            "project_name": "T95", "employer": "", "contractor": "", "consultant": "",
            "period_start": "", "period_end": "", "location": "", "contract_date": ""}


def _full_settings():
    """تنظیمات با یک قیمت دستی + یک ردیف ستاره‌دار + یک سابقهٔ ویرایش."""
    res0, s = _compute()
    orig = _by_id(res0)["rebar-070201"]["price"]
    s["manual_prices"] = {
        "rebar-070201": {"price": orig * 1.5, "source": "استعلام", "doc_no": "Q-1",
                         "doc_date": "۱۴۰۴/۰۵/۰۱", "note": "استعلام فولاد",
                         "status": "دستی", "chapter": "", "user": "دفتر فنی",
                         "at": "۱۴۰۵/۰۷/۰۸ ۱۰:۰۰"}}
    s["starred_rows"] = [{"code": "990101", "desc": "قفل‌سازی درب‌ها", "unit": "عدد",
                          "qty": 4, "price": 2500000, "chapter": "31",
                          "source": "فاکتور", "doc_no": "F-77", "doc_date": "۱۴۰۴/۰۶/۰۱",
                          "note": "خرید محلی", "user": "دفتر فنی",
                          "at": "۱۴۰۵/۰۷/۰۸ ۱۱:۰۰"}]
    s["price_audit"] = [{"at": "۱۴۰۵/۰۷/۰۸ ۱۰:۰۰", "user": "دفتر فنی",
                         "item": "rebar-070201", "field": "price",
                         "old": orig, "new": orig * 1.5, "source": "استعلام"}]
    s["price_user"] = "دفتر فنی"
    return s


def test_T95_sidecar_roundtrip():
    s = _full_settings()
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute(
        [{**_table(), "grand_total": {"weight": 310}}], None)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "proj.json")
        saved = save_manual_entries(path, s)
        assert os.path.exists(saved)
        assert os.path.exists(saved + ".bak") is False  # فایل جدیدی هست
        # بازنویسی → backup ساخته می‌شود
        save_manual_entries(saved, s)
        assert os.path.exists(saved + ".bak")
        s2 = _settings()
        loaded, warns = load_manual_entries(saved, s2)
        assert not warns
        assert s2["manual_prices"]["rebar-070201"]["price"] == \
            s["manual_prices"]["rebar-070201"]["price"]
        assert s2["starred_rows"] == s["starred_rows"]
        assert s2["price_audit"] == s["price_audit"]
        res2 = TechnicalOfficeEngine(FIXTURE["db"], s2).compute(
            [{**_table(), "grand_total": {"weight": 310}}], None)
        assert res2["base_total"] == pytest.approx(res["base_total"])
        assert res2["grand_total"] == pytest.approx(res["grand_total"])


def test_T95_excel_price_columns():
    s = _full_settings()
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute(
        [{**_table(), "grand_total": {"weight": 310}}], None)
    wb_bytes = ExcelExporter().export(_meta(), res, s, [])
    import zipfile
    import xml.etree.ElementTree as ET
    NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(wb_bytes)) as wb:
        sx = ET.fromstring(wb.read("xl/workbook.xml"))
        sheets = [x.get("name") for x in sx.iter(f"{NS}sheet")]
        # شیت صورت‌وضعیت اکنون ۱۷ ستون دارد (فایل‌ها به ترتیب شیت‌ها)
        boq = ET.fromstring(wb.read("xl/worksheets/sheet8.xml"))  # فاز D: صورت وضعیت = برگهٔ ۸
    assert "قیمت‌های دستی" in sheets
    assert "سابقهٔ ویرایش" in sheets
    assert boq.find(f"{NS}cols/{NS}col[@min='17']") is not None


def test_T95_excel_roundtrip():
    """خروجی Excel → ورود مجدد → محاسبه: ارقام باید عیناً یکسان باشند
    (جابه‌جایی قیمت‌ها بین پروژه‌ها — درخواست کاربر)."""
    s = _full_settings()
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute(
        [{**_table(), "grand_total": {"weight": 310}}], None)
    wb_bytes = ExcelExporter().export(_meta(), res, s, [])

    payload = parse_manual_entries_xlsx(wb_bytes)
    assert payload is not None
    assert "rebar-070201" in payload["manual_prices"]
    assert payload["manual_prices"]["rebar-070201"]["price"] == \
        s["manual_prices"]["rebar-070201"]["price"]
    assert payload["manual_prices"]["rebar-070201"]["doc_no"] == "Q-1"
    assert len(payload["starred_rows"]) == 1
    assert payload["starred_rows"][0]["qty"] == 4
    assert len(payload["price_audit"]) == 1
    assert payload["price_audit"][0]["item"] == "rebar-070201"

    s2 = _settings()
    warns = apply_manual_entries(s2, payload)
    assert not warns
    res2 = TechnicalOfficeEngine(FIXTURE["db"], s2).compute(
        [{**_table(), "grand_total": {"weight": 310}}], None)
    assert res2["base_total"] == pytest.approx(res["base_total"])
    assert res2["grand_total"] == pytest.approx(res["grand_total"])
    assert _by_id(res2)["rebar-070201"]["price_status"] == "دستی"


def test_T95_payload_and_empty_export():
    """خروجی با هیچ ورودی دستی هم باید شیت‌ها را بسازد (round-trip خالی)."""
    res, s = _compute()
    wb_bytes = ExcelExporter().export(_meta(), res, s, [])
    payload = parse_manual_entries_xlsx(wb_bytes)
    assert payload is not None
    assert payload["manual_prices"] == {}
    assert payload["starred_rows"] == []
    payload2 = manual_entries_payload(s)
    assert payload2["version"] == MANUAL_ENTRIES_VERSION
