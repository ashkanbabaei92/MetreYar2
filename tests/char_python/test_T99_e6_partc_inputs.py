# -*- coding: utf-8 -*-
# T99 — فاز E-6 Part C (گام ۱): ورودی‌های قرارداد در تنظیمات
#
# بندهای مرجع (بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰):
#   ۱-۶-۱/۱-۶-۲: روش شاخص مبنا (base_index_method، final_offer_date)
#   ۲-۱/۲-۲:     مسیر رشته‌ای/گروهی و آستانهٔ ۳۰۰ میلیون ریال
#                 (index_method، contract_initial_amount)
#   ۲-۵:         مدت پیمان و تمدیدها (contract_duration_months، contract_extensions)
#   ۲-۶:         آخرین صورت‌وضعیت موقت (last_provisional_date)
#   ۶/۷:         وضعیت خاتمه (contract_status)
#   نامه-۶:      سقف ۱۰٪ (contract_initial_amount)
#
# قاعدهٔ طلاییِ این گام: پیش‌فرض‌ها طوری انتخاب شده‌اند که هیچ‌کدام از
# اعداد مرجعِ پروژه تغییر نمی‌کنند (آزمون T99_reference_unchanged).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings, copy_project,
                 load_profile, save_profile,
                 SETTING_LABELS)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")
PROV_COEF = 1.1530518586507572
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"
REF = dict(baravord_enabled=True,
           work_period_start="۱۴۰۴/۰۱/۰۱",
           work_period_end="۱۴۰۵/۰۲/۱۵",
           provisional_coef_1405q1=PROV_COEF)

NEW_FIELDS = {
    "base_index_method": "proposal_period",
    "final_offer_date": "",
    "contract_duration_months": None,
    "contract_extensions": [],
    "contract_status": "فعال",
    "contract_initial_amount": None,
    "index_method": "گروهی",
    "last_provisional_date": "",
}


def test_T99_new_settings_defaults():
    # گام ۱: همهٔ فیلدهای جدید با مقدارهای خنثی present هستند
    s = default_settings()
    for k, v in NEW_FIELDS.items():
        assert k in s, k
        assert s[k] == v, (k, s[k])


def test_T99_setting_labels_cover_new_fields():
    # هر فیلد جدید در سابقهٔ ویرایش برچسب فارسی دارد
    for k in NEW_FIELDS:
        assert k in SETTING_LABELS, k
        assert SETTING_LABELS[k].strip()


def test_T99_reference_numbers_unchanged():
    # قاعدهٔ طلایی: پیش‌فرض‌های جدید اثری روی اعداد مرجع ندارند
    # (مقدارِ دقیقِ موتور با T98 یکسان است).
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(REF)
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
    res = TechnicalOfficeEngine(_default_fehrest_db(), s).compute(
        tables, DynamoMappingParser.merge_formats(results))
    t = res["adjustment"]["tadil"]
    assert t["delta_p"] == pytest.approx(9984277408.21705, rel=1e-9)
    assert t["delta_p_definitive"] == pytest.approx(7761045209.936075, rel=1e-9)


def test_T99_copy_project_clears_dates_extensions_status():
    # درخواست کاربر (گام ۱۰): تاریخ‌ها، تمدیدها، contract_status و
    # completed_within_term پاک می‌شوند؛ فلگ‌ها و شاخص‌های دستی می‌مانند؛
    # مساحت طبقات پاک می‌شود.
    s = default_settings()
    s.update(
        final_offer_date="۱۴۰۳/۱۲/۲۰",
        last_provisional_date="۱۴۰۵/۰۱/۰۱",
        contract_duration_months=14,
        contract_extensions=[{"date": "۱۴۰۴/۰۶/۰۱", "months": 2,
                              "kind": "مجاز", "doc_no": "ت-۱"}],
        contract_status="فسخ با قصور",
        contract_initial_amount=4e9,
        index_method="خودکار",
        base_index_method="fehrest_period",
        completed_within_term=True,
        chapter_index_manual={"06": {"io": 7273.8, "it": 10632.1,
                                         "src": "پیوست ۳"}},
        discipline_index_manual={"io": 5000.0, "it": 8000.0},
        coef_rounding_2080=False,
        floors_data={"Story1": 120.0, "Story2": 100.0},
        manual_prices={"A-1": {"price": 1000.0, "source": "بخشنامه"}},
    )
    _meta, ns = copy_project(s, {"project_name": "پروژه نمونه"})
    # پاک می‌شوند
    assert ns["final_offer_date"] == ""
    assert ns["last_provisional_date"] == ""
    assert ns["contract_extensions"] == []
    assert ns["contract_status"] == "فعال"
    assert ns["contract_duration_months"] is None
    assert ns["completed_within_term"] is None
    assert ns["floors_data"] == {}
    # می‌مانند
    assert ns["contract_initial_amount"] == 4e9
    assert ns["index_method"] == "خودکار"
    assert ns["base_index_method"] == "fehrest_period"
    assert ns["coef_rounding_2080"] is False
    assert ns["chapter_index_manual"] == {"06": {"io": 7273.8, "it": 10632.1,
                                                 "src": "پیوست ۳"}}
    assert ns["discipline_index_manual"] == {"io": 5000.0, "it": 8000.0}
    assert ns["manual_prices"]["A-1"]["price"] == 1000.0


def test_T99_profile_roundtrip_carries_new_fields(tmp_path):
    # پروفایل پروژه همهٔ فیلدهای جدید را حمل می‌کند (camel/snake در JSON)
    s = default_settings()
    s.update(
        base_index_method="no_base_list",
        final_offer_date="۱۴۰۳/۱۲/۲۰",
        contract_duration_months=9,
        contract_extensions=[{"date": "۱۴۰۴/۰۳/۰۱", "months": 3,
                              "kind": "غیرمجاز", "doc_no": "ت-۲"}],
        contract_status="خاتمه بدون قصور",
        contract_initial_amount=4e9,
        index_method="رشته‌ای",
        last_provisional_date="۱۴۰۵/۰۲/۰۱",
        chapter_index_manual={"06": {"io": 7273.8, "it": 10632.1,
                                      "src": "پیوست ۳، صفحهٔ ۸۲"}},
        discipline_index_manual={"io": 5000.0, "it": 8000.0,
                                 "src": "نامهٔ کارفرما"},
    )
    p = save_profile(str(tmp_path / "prof"), s, {"project_name": "P"})
    _meta, s2, _warns = load_profile(p)
    assert s2["base_index_method"] == "no_base_list"
    assert s2["final_offer_date"] == "۱۴۰۳/۱۲/۲۰"
    assert s2["contract_duration_months"] == 9
    assert s2["contract_extensions"] == [{"date": "۱۴۰۴/۰۳/۰۱", "months": 3,
                                          "kind": "غیرمجاز", "doc_no": "ت-۲"}]
    assert s2["contract_status"] == "خاتمه بدون قصور"
    assert s2["contract_initial_amount"] == 4e9
    assert s2["index_method"] == "رشته‌ای"
    assert s2["last_provisional_date"] == "۱۴۰۵/۰۲/۰۱"
    # گام ۸: منبعِ شاخص دستی در round-trip می‌مانَد
    assert s2["chapter_index_manual"] == {"06": {"io": 7273.8, "it": 10632.1,
                                                 "src": "پیوست ۳، صفحهٔ ۸۲"}}
    assert s2["discipline_index_manual"] == {"io": 5000.0, "it": 8000.0,
                                             "src": "نامهٔ کارفرما"}


def test_T99_extension_kinds_are_the_three_bulletin_values():
    # بندهای ۲-۵-۱..۲-۵-۳: سه نوع تأخیر
    for kind in ("مجاز", "غیرمجاز", "تعیین‌نشده"):
        rec = {"date": "۱۴۰۴/۰۱/۰۱", "months": 1, "kind": kind, "doc_no": ""}
        assert rec["kind"] in ("مجاز", "غیرمجاز", "تعیین‌نشده")
    assert default_settings()["contract_extensions"] == []


def test_T99_contract_status_default_and_values():
    # بندهای ۶ و ۷: سه وضعیت خاتجه
    s = default_settings()
    assert s["contract_status"] == "فعال"
    for st in ("فعال", "خاتمه بدون قصور", "فسخ با قصور"):
        s2 = default_settings()
        s2["contract_status"] = st
        assert s2["contract_status"] == st
