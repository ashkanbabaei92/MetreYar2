# -*- coding: utf-8 -*-
# T96 — فاز E-۵: پروفایل پروژه
#
# بخش a:
#   - هشدار مغایرت سال فهرست‌بها (سطح «هشدار»، آیتم fehrest_year_mismatch)
#   - نوع رویداد در سابقهٔ ویرایش (price/setting/meta) + مسیر برگشت Excel

import copy
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (
    TechnicalOfficeEngine,
    ExcelExporter,
    append_audit,
    default_settings,
    AUDIT_KIND_LABELS,
    parse_manual_entries_xlsx,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "char_shared",
    "fixtures", "revit", "T32_rebar_grand_total.json")

with open(FIXTURE_PATH, encoding="utf-8") as _f:
    FIXTURE = json.load(_f)


def _meta():
    return {"project_name": "تست T96", "employer": "", "contractor": "",
            "consultant": "", "contract_no": "", "contract_date": "۱۴۰۴/۰۱/۰۱",
            "location": "", "report_no": "۱", "report_type": "موقت",
            "period_start": "", "period_end": ""}


def _settings(**over):
    s = default_settings()
    s.update(over)
    return s


def _table():
    t = copy.deepcopy(FIXTURE["table"])
    t["grand_total"] = {"weight": 310}
    return t


def _compute(**over):
    s = _settings(**over)
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute([_table()], None)
    return res, s


def _mismatch(res):
    return [w for w in res["warnings"] if w["item"] == "fehrest_year_mismatch"]


# ── هشدار مغایرت سال فهرست‌بها ──

def test_T96_fehrest_year_match_no_warning():
    res, _ = _compute()
    assert _mismatch(res) == []


def test_T96_fehrest_year_mismatch_is_warning_level():
    res, _ = _compute(fehrest_year="۱۴۰۳")
    m = _mismatch(res)
    assert len(m) == 1
    assert m[0]["level"] == "هشدار"
    assert m[0]["category"] == "فهرست‌بها"
    assert res["warnings_by_level"].get("هشدار", 0) >= 1


def test_T96_fehrest_year_latin_and_persian_digits_equal():
    # «1404» و «۱۴۰۴» یکسان در نظر گرفته می‌شوند (نرمال‌سازی ارقام)
    res, _ = _compute(fehrest_year="1404")
    assert _mismatch(res) == []


def test_T96_fehrest_db_year_empty_no_warning():
    res, _ = _compute(fehrest_db_year="")
    assert _mismatch(res) == []


# ── نوع رویداد در سابقهٔ ویرایش ──

def test_T96_audit_kind_default_and_explicit():
    s = _settings()
    append_audit(s, "۰۶۰۳۰۱", "price", 100, 120, "استعلام")
    append_audit(s, "تنظیمات", "tadil_coef", 0.95, 1.0, "سایدبار", kind="setting")
    append_audit(s, "پیمان", "contract_no", "", "۹۹", "فرم", kind="meta")
    kinds = [a["kind"] for a in s["price_audit"]]
    assert kinds == ["price", "setting", "meta"]
    assert AUDIT_KIND_LABELS["meta"] == "مشخصات"


def test_T96_audit_kind_excel_roundtrip():
    s = _settings()
    append_audit(s, "۰۶۰۳۰۱", "price", 100, 120, "استعلام")
    append_audit(s, "تنظیمات", "tadil_coef", 0.95, 1.0, "سایدبار", kind="setting")
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute([_table()], None)
    wb = ExcelExporter().export(_meta(), res, s, [])
    payload = parse_manual_entries_xlsx(wb)
    assert payload is not None
    kinds = [a["kind"] for a in payload["price_audit"]]
    assert kinds == ["price", "setting"]


def test_T96_audit_kind_legacy_entry_defaults_to_price():
    # رکورد قدیمی بدون kind → پیش‌فرض «price» در مسیر برگشت Excel
    s = _settings()
    s["price_audit"] = [{"at": "۱۴۰۴/۰۱/۰۱", "user": "u", "item": "x",
                         "field": "price", "old": 1, "new": 2, "source": ""}]
    res = TechnicalOfficeEngine(FIXTURE["db"], s).compute([_table()], None)
    wb = ExcelExporter().export(_meta(), res, s, [])
    payload = parse_manual_entries_xlsx(wb)
    assert payload["price_audit"][0]["kind"] == "price"


# ── تفاضلِ تنظیمات و مشخصات (بخش b) ──

def test_T96_settings_diff_logs_changes():
    from app import (_audit_diff_apply, _audit_snap, SETTING_LABELS)
    s = default_settings()
    snap = _audit_snap(s)
    s["tadil_coef"] = 0.9
    s["fehrest_year"] = "۱۴۰۳"
    _audit_diff_apply(s, snap, "setting", SETTING_LABELS,
                      "تنظیمات پروژه", s)
    entries = [a for a in s["price_audit"] if a["kind"] == "setting"]
    assert len(entries) == 2
    fields = {a["field"] for a in entries}
    assert "ضریب k تعدیل" in fields
    assert "سال فهرست‌بهای پروژه" in fields
    assert all(a["item"] == "تنظیمات پروژه" for a in entries)


def test_T96_settings_diff_no_change_no_log():
    from app import _audit_diff_apply, _audit_snap, SETTING_LABELS
    s = default_settings()
    snap = _audit_snap(s)
    _audit_diff_apply(s, snap, "setting", SETTING_LABELS,
                      "تنظیمات پروژه", s)
    assert s["price_audit"] == []


def test_T96_settings_diff_excludes_manual_entries():
    # تغییر manual_prices نباید رویدادِ setting ثبت کند
    # (رویداد اختصاصیِ خود را در محلِ عمل دارد)
    from app import _audit_diff_apply, _audit_snap, SETTING_LABELS
    s = default_settings()
    snap = _audit_snap(s)
    s["manual_prices"]["x"] = {"price": 100}
    s["excluded"].append({"id": "y", "reason": "", "user": "", "at": ""})
    _audit_diff_apply(s, snap, "setting", SETTING_LABELS,
                      "تنظیمات پروژه", s)
    assert not [a for a in s["price_audit"] if a["kind"] == "setting"]


def test_T96_meta_diff_logs_into_settings_registry():
    from app import _audit_diff_apply, _audit_snap, META_LABELS
    meta = {"project_name": "الف", "report_no": "۱", "contract_no": ""}
    s = default_settings()
    snap = _audit_snap(meta)
    meta["contract_no"] = "۹۹"
    _audit_diff_apply(meta, snap, "meta", META_LABELS,
                      "مشخصات پیمان", s)
    # سابقه در settings ثبت می‌شود، نه در meta
    assert "price_audit" not in meta
    entries = [a for a in s["price_audit"] if a["kind"] == "meta"]
    assert len(entries) == 1
    assert entries[0]["field"] == "شماره پیمان"
    assert entries[0]["new"] == '"۹۹"'


# ── بخش c: پروفایل پروژه (ذخیره/بارگذاری/مهاجرت) ──

def test_T96_profile_payload_shape():
    from app import profile_payload, PROFILE_KIND, PROFILE_VERSION
    s = default_settings()
    s["tadil_coef"] = 0.9
    meta = {"project_name": "پروژهٔ آزمایشی", "contract_no": "۹۹",
            "report_no": "۳", "contract_date": "۱۴۰۴/۰۱/۰۱"}
    p = profile_payload(s, meta)
    assert p["kind"] == PROFILE_KIND
    assert p["version"] == PROFILE_VERSION
    assert p["meta"]["contract_no"] == "۹۹"
    assert p["settings"]["tadil_coef"] == 0.9
    # کپیِ مستقل از settings اصلی
    s["tadil_coef"] = 1.0
    assert p["settings"]["tadil_coef"] == 0.9


def test_T96_profile_save_load_roundtrip(tmp_path):
    from app import (save_profile, load_profile, profile_sidecar_path,
                     _manual_record)
    s = default_settings()
    s["tadil_coef"] = 0.9
    s["fehrest_year"] = "۱۴۰۳"
    s["manual_prices"]["A-1"] = _manual_record(1000, doc_no="۱۲۳")
    meta = {"project_name": "پ", "contract_no": "۹۹", "report_no": "۳",
            "contract_date": "۱۴۰۴/۰۱/۰۱"}
    side = profile_sidecar_path(str(tmp_path / "P.rvt"))
    f1 = save_profile(side, s, meta)
    assert os.path.exists(f1)
    save_profile(side, s, meta)               # backup ساخته می‌شود
    assert os.path.exists(f1 + ".bak")
    m2, s2, w = load_profile(f1)
    assert w == [], w
    assert m2["contract_no"] == "۹۹"
    assert s2["tadil_coef"] == 0.9
    assert s2["fehrest_year"] == "۱۴۰۳"
    assert s2["manual_prices"]["A-1"]["doc_no"] == "۱۲۳"


def test_T96_profile_legacy_sidecar(tmp_path):
    from app import (save_manual_entries, load_profile, manual_sidecar_path,
                     _manual_record)
    s = default_settings()
    s["price_diff_warn_pct"] = 45.0
    s["manual_prices"]["A-1"] = _manual_record(1000, doc_no="۱۲۳")
    side = manual_sidecar_path(str(tmp_path / "L.rvt"))
    save_manual_entries(side, s)
    m, s2, w = load_profile(side)
    assert m is None                            # فایل قدیمی ⇒ بدون meta
    assert s2["price_diff_warn_pct"] == 45.0
    assert s2["manual_prices"]["A-1"]["doc_no"] == "۱۲۳"


def test_T96_profile_corrupt_file(tmp_path):
    from app import load_profile
    f = tmp_path / "bad.json"
    f.write_text("not json at all", encoding="utf-8")
    m, s, w = load_profile(str(f))
    assert m is None and s is None
    assert len(w) == 1


def test_T96_profile_version_mismatch(tmp_path):
    from app import profile_payload, load_profile
    p = profile_payload(default_settings(), {"project_name": "پ"})
    p["version"] = 99
    f = str(tmp_path / "v.json")
    io.open(f, "w", encoding="utf-8").write(json.dumps(p, ensure_ascii=False))
    m, s, w = load_profile(f)
    assert s is not None
    assert any("نسخه" in x for x in w)


def test_T96_profile_unknown_keys_dropped(tmp_path):
    from app import profile_payload, load_profile
    p = profile_payload(default_settings(), {"project_name": "پ"})
    p["settings"]["bogus_key"] = 1
    p["meta"]["bogus_meta"] = 2
    f = str(tmp_path / "u.json")
    io.open(f, "w", encoding="utf-8").write(json.dumps(p, ensure_ascii=False))
    m, s, w = load_profile(f)
    assert s is not None
    assert "bogus_key" not in s
    assert "bogus_meta" not in m
    assert any("ناشناخته" in x for x in w)


def test_T96_profile_camelcase_keys_adopted(tmp_path):
    # پروفایلِ ساخته‌شده در نسخهٔ TypeScript (کلیدهای camelCase)
    from app import load_profile
    ts = {
        "kind": "metreyar_project_profile",
        "version": 1,
        "exportedAt": "2026-10-02T00:00:00",
        "meta": {"projectName": "از TS", "contractNo": "۵", "reportNo": "۲"},
        "settings": {"tadilCoef": 0.8, "fehrestYear": "۱۴۰۳",
                     "priceUser": "دفتر فنی"},
    }
    f = str(tmp_path / "ts.json")
    io.open(f, "w", encoding="utf-8").write(json.dumps(ts, ensure_ascii=False))
    m, s, w = load_profile(f)
    assert s["tadil_coef"] == 0.8
    assert s["fehrest_year"] == "۱۴۰۳"
    assert s["price_user"] == "دفتر فنی"
    assert m["project_name"] == "از TS"
    assert m["contract_no"] == "۵"
    assert m["report_no"] == "۲"


# ── بخش d: پروژهٔ جدید از روی این پروژه ──

def test_T96_copy_project():
    from app import copy_project, _manual_record
    s = default_settings()
    s["proposal_date"] = "۱۴۰۵/۰۴/۰۱"
    s["proposal_deadline"] = "۱۴۰۵/۰۵/۰۱"
    s["proposal_coef"] = 1.15
    s["work_period_start"] = "۱۴۰۴/۰۱"
    s["work_period_end"] = "۱۴۰۴/۰۶"
    s["tadil_coef"] = 0.9
    s["manual_prices"]["A-1"] = _manual_record(1000, doc_no="۱۲۳")
    meta = {"project_name": "پروژهٔ آزمایشی", "contract_no": "۹۹",
            "contract_date": "۱۴۰۴/۰۱/۰۱", "report_no": "۳",
            "period_start": "۱۴۰۴/۰۱", "period_end": "۱۴۰۴/۰۶"}
    nm, ns = copy_project(s, meta)
    # هویتی/زمانی پاک می‌شوند
    assert nm["project_name"] == "کپی از پروژهٔ آزمایشی"
    assert nm["report_no"] == "۱"
    assert nm["contract_no"] == "" and nm["contract_date"] == ""
    assert nm["period_start"] == "" and nm["period_end"] == ""
    assert ns["proposal_date"] == "" and ns["proposal_deadline"] == ""
    assert ns["proposal_coef"] == 1.0
    assert ns["work_period_start"] == "" and ns["work_period_end"] == ""
    # فنی و دستی نگه داشته می‌شوند
    assert ns["tadil_coef"] == 0.9
    assert ns["manual_prices"]["A-1"]["doc_no"] == "۱۲۳"
    # سابقهٔ ویرایش از صفر با یک رکورد
    assert len(ns["price_audit"]) == 1
    a = ns["price_audit"][0]
    assert a["kind"] == "meta"
    assert a["field"] == "copy"
    assert a["old"] == "پروژهٔ آزمایشی"
    assert a["new"] == "کپی از پروژهٔ آزمایشی"
    # پروژهٔ اصلی دست‌نخورده می‌ماند
    assert s["proposal_date"] == "۱۴۰۵/۰۴/۰۱"
    assert s["price_audit"] == []
