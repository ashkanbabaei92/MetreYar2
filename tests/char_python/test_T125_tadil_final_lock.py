# -*- coding: utf-8 -*-
# T125 — قفلِ خروجیِ نهاییِ تعدیل (فاز E-10 §۲).
#
# قاعده: در «تعدیل صورت‌وضعیت» اگر دورهٔ کارکرد خالی باشد، Excel نهایی
# نباید ساخته شود — فقط «پیش‌نویس» با واترمارکِ «پیش‌نویس – دورهٔ کارکرد
# وارد نشده» روی همهٔ شیت‌ها. اگر completed_within_term نامشخص باشد، خروجی
# مجاز است ولی با برچسب «علی‌الحساب – k = ۰٫۹۵» (بند ۱-۸ بخشنامهٔ ۲۰۸۰).
#
# این آزمون:
#   ۱) موتور: work_period_missing وقتی دوره خالی است True و وقتی پر است False؛
#   ۲) موتور: k_provisional وقتی completed_within_term نامشخص است True و
#      k = ۰٫۹۵ است، و وقتی کار در مدت تمام شده False و k = ۱ است؛
#   ۳) export با report_type نهایی + دورهٔ خالی ⇒ ValueError با نامِ فیلدها؛
#   ۴) export با report_type پیش‌نویس + دورهٔ خالی ⇒ ساخته می‌شود و واترمارک
#      روی همهٔ شیت‌ها می‌نشیند؛
#   ۵) export با دورهٔ پر ⇒ ساخته می‌شود و واترمارک نیست؛
#   ۶) برچسبِ «علی‌الحساب — k = ۰٫۹۵» در شیتِ تعدیل هست وقتی تکلیف نامشخص است.
#
# آینهٔ test_T125_tadil_final_lock.ts.
import io
import os
import re
import sys
import zipfile

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, ExcelExporter, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

BANNER = "پیش‌نویس – دورهٔ کارکرد وارد نشده"
K_PROV_LABEL = "علی‌الحساب — k = ۰٫۹۵"

META = {"report_type": "موقت", "report_no": "۱", "contract_no": "۱",
        "project_name": "پروژه نمونه", "employer": "کارفرما",
        "contractor": "پیمانکار", "consultant": "مشاور",
        "period_start": "", "period_end": "",
        "location": "گرگان", "contract_date": "۱۴۰۴/۰۱/۰۱"}

_BASE = dict(tadil_enabled=True, baravord_enabled=False,
             proposal_date="۱۴۰۳/۱۲/۲۹",
             provisional_coef_1405q1=1.1530518586507572)

_MEMO = {}


def _pipeline(extra):
    key = tuple(sorted((str(k), str(v)) for k, v in extra.items()))
    if key in _MEMO:
        return _MEMO[key]
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r",
                      encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    s = default_settings()
    s.update(_BASE)
    s.update(extra)
    res = TechnicalOfficeEngine(_default_fehrest_db(), s).compute(
        tables, DynamoMappingParser.merge_formats(results))
    _MEMO[key] = (res, s)
    return _MEMO[key]


def _shared_strings(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    if "xl/sharedStrings.xml" not in z.namelist():
        return ""
    return z.read("xl/sharedStrings.xml").decode("utf-8")


def _banner_hits(data):
    """(تعدادِ شیت‌ها، تعدادِ شیت‌هایی که واترمارک را دارند)."""
    z = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in z.namelist()
             if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)]
    if "xl/sharedStrings.xml" not in z.namelist():
        return len(names), 0
    shared = z.read("xl/sharedStrings.xml").decode("utf-8")
    sis = re.split(r"<si[^>]*>", shared)
    idx = None
    for i in range(1, len(sis)):
        if BANNER in sis[i]:
            idx = i - 1
            break
    if idx is None:
        return len(names), 0
    hits = 0
    for n in names:
        xml = z.read(n).decode("utf-8")
        if re.search(r'<c [^>]*t="s"[^>]*><v>%d</v>' % idx, xml):
            hits += 1
    return len(names), hits


_WP_EMPTY = dict(work_period_start="", work_period_end="")
_WP_FULL = dict(work_period_start="۱۴۰۴/۰۱/۰۱", work_period_end="۱۴۰۵/۰۲/۱۵")


# ── ۱) موتور: پرچمِ work_period_missing ──

def test_T125_engine_work_period_missing_when_empty():
    res, _s = _pipeline(_WP_EMPTY)
    t = res["adjustment"]["tadil"]
    assert t is not None
    assert t["work_period_missing"] is True
    # هشدارِ هدایت‌کنندهٔ به فیلد هم صادر می‌شود (قاعدهٔ طلایی)
    assert any(w.get("item") == "work_period_missing_for_it"
               for w in res["warnings"])


def test_T125_engine_work_period_present_when_set():
    res, _s = _pipeline(_WP_FULL)
    t = res["adjustment"]["tadil"]
    assert t is not None
    assert t["work_period_missing"] is False
    assert not any(w.get("item") == "work_period_missing_for_it"
                   for w in res["warnings"])


# ── ۲) موتور: k علی‌الحساب در برابر قطعی ──

def test_T125_engine_k_provisional_when_cwt_unknown():
    res, _s = _pipeline(_WP_EMPTY)
    t = res["adjustment"]["tadil"]
    assert t["k_provisional"] is True
    assert t["coef"] == pytest.approx(0.95)
    assert "علی‌الحساب" in t["k_status"]


def test_T125_engine_k_definitive_when_cwt_true():
    res, _s = _pipeline(dict(_WP_EMPTY, completed_within_term=True))
    t = res["adjustment"]["tadil"]
    assert t["k_provisional"] is False
    assert t["coef"] == pytest.approx(1.0)


# ── ۳) export: خروجیِ نهایی وقتی دوره خالی است ممنوع است ──

def test_T125_export_final_refused_when_work_period_missing():
    res, s = _pipeline(_WP_EMPTY)
    with pytest.raises(ValueError) as ei:
        ExcelExporter().export(META, res, s, [])
    msg = str(ei.value)
    assert "تاریخ شروع دورهٔ صورت‌وضعیت" in msg
    assert "تاریخ پایان دورهٔ صورت‌وضعیت" in msg


# ── ۴) export: پیش‌نویس مجاز است با واترمارک روی همهٔ شیت‌ها ──

def test_T125_export_draft_allowed_with_watermark_on_all_sheets():
    res, s = _pipeline(_WP_EMPTY)
    meta = {**META, "report_type": "پیش‌نویس — موقت"}
    data = ExcelExporter().export(meta, res, s, [])
    n_sheets, hits = _banner_hits(data)
    assert n_sheets > 1
    assert hits == n_sheets, \
        "واترمارک باید روی همهٔ شیت‌ها بنشیند (%d از %d)" % (hits, n_sheets)


# ─ـ ۵) export: وقتی دوره پر است واترمارکی نیست ──

def test_T125_export_no_banner_when_work_period_present():
    res, s = _pipeline(_WP_FULL)
    data = ExcelExporter().export(META, res, s, [])
    n_sheets, hits = _banner_hits(data)
    assert hits == 0
    assert BANNER not in _shared_strings(data)


# ─ـ ۶) export: برچسبِ علی‌الحسابِ k در شیتِ تعدیل ──

def test_T125_export_k_provisional_label_in_tadil_sheet():
    res, s = _pipeline(_WP_FULL)
    data = ExcelExporter().export(META, res, s, [])
    shared = _shared_strings(data)
    assert K_PROV_LABEL in shared


def test_T125_export_k_definitive_label_absent_when_cwt_true():
    res, s = _pipeline(dict(_WP_FULL, completed_within_term=True))
    data = ExcelExporter().export(META, res, s, [])
    shared = _shared_strings(data)
    assert K_PROV_LABEL not in shared
