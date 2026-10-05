# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# T110 — فاز E-6 Part C گام ۱۲ (حرف g): پنلِ «وضعیت ورودی‌ها»
#
# تک‌منبعِ حقیقتِ تفسیرهای «منتظر تأیید کاربر»: PENDING_INTERPRETATIONS
# در app.py — استفاده در پنلِ Streamlit و شیتِ Excel «مقادیر منتظر تأیید».
# این تست بررسی می‌کند:
#   ۱) ساختار: هر ورودی یک ۵-تایی (شناسه، موضوع، تفسیر، گزینه، اثر) است.
#   ۲) شناسه‌ها D-01..D-N پشتِ سرِ هم و یکتا هستند (فاز E-8 §۱).
#   ۳) هیچ فیلدی خالی نیست (قاعدهٔ طلایی: هر ورودی مستند است).
#   ۴) شیتِ Excel «مقادیر منتظر تأیید» شاملِ جدول می‌شود.
#   ۵) همهٔ subjectها با نسخهٔ TS (PENDING_INTERPRETATIONS در adjustment.ts)
#      یکی هستند (پاریتی — از طریقِ فایلِ مشترکِ تست).
# آینهٔ tests/char_ts/test_T110_inputs_status_panel.ts
# ─────────────────────────────────────────────────────────────
import io
import os

import openpyxl
import pytest

pytestmark = pytest.mark.slow

from app import (DynamoMappingParser, ExcelExporter, PENDING_INTERPRETATIONS,
                 RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

META = {"project_name": "T110", "report_no": "1", "report_type": "برآورد",
        "contract_no": "", "employer": "", "contractor": "", "consultant": "",
        "period_start": "", "period_end": "", "location": "",
        "contract_date": ""}

# subjectهای MUST — باید در هر دو زبان یکسان باشند (پاریتی)
MUST_SUBJECTS = [
    "ضریب k ورودی کاربر نیست (بند ۱-۸)",
    "مبنای کسرِ ۵٪ (بند ۷)",
    "گردنشدنِ ضریبِ تبدیلِ ۳-۵ قبل از ضرب در مبلغ",
    "مبنای «مبلغ برآورد» در سقفِ ۱۰٪ نامه-۶ (گام ۷)",
]


# ── ۱) ساختار و یکتاییِ شناسه‌ها ──

def test_T110_structure_is_five_tuples():
    assert len(PENDING_INTERPRETATIONS) >= 18
    for entry in PENDING_INTERPRETATIONS:
        assert isinstance(entry, tuple) and len(entry) == 5
        _no, subj, impl, alt, eff = entry
        assert isinstance(_no, str) and _no.startswith("D-"), \
            "شناسه باید D-xx باشد: %r" % (_no,)
        for txt in (subj, impl, alt, eff):
            assert isinstance(txt, str) and txt.strip(), \
                "هیچ فیلدی نباید خالی باشد (قاعدهٔ طلایی: مستندسازی)"


def test_T110_numbers_are_contiguous_and_unique():
    nos = [e[0] for e in PENDING_INTERPRETATIONS]
    assert nos == ["D-%02d" % i for i in range(1, len(PENDING_INTERPRETATIONS) + 1)]
    assert len(set(nos)) == len(nos)


# ── ۲) موضوع‌های کلیدی موجودند (پاریتیِ Must با TS) ──

def test_T110_key_subjects_present():
    subjects = [e[1] for e in PENDING_INTERPRETATIONS]
    for s in MUST_SUBJECTS:
        assert s in subjects, "موضوعِ کلیدی گم شده: %s" % s


# ── ۳) تفسیرِ سقفِ ۱۰٪ (تفسیر ۱۸) اثرِ عددیِ مستند دارد ──

def test_T110_ceiling_entry_has_numeric_effect():
    ceil = [e for e in PENDING_INTERPRETATIONS if e[0] == "D-18"]
    assert len(ceil) == 1
    _no, _s, impl, alt, eff = ceil[0]
    assert "base_total" in impl and "grand_total" in alt
    assert "۸٬۹۹۰٬۱۵۷٬۲۵۳٫۶۹" in eff


# ── ۴) شیتِ Excel «مقادیر منتظر تأیید» جدول را در بر دارد ──

@pytest.fixture(scope="module")
def pending_sheet():
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = "۱۴۰۳/۱۲/۲۹"
    s["work_period_start"] = "۱۴۰۴/۰۱/۰۱"
    s["work_period_end"] = "۱۴۰۴/۱۲/۲۹"
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
    res = TechnicalOfficeEngine(
        _default_fehrest_db(), s).compute(
            tables, DynamoMappingParser.merge_formats(results))
    buf = ExcelExporter().export(META, res, s, [])
    wb = openpyxl.load_workbook(io.BytesIO(buf), data_only=True)
    assert "مقادیر منتظر تأیید" in wb.sheetnames
    return wb["مقادیر منتظر تأیید"]


def test_T110_excel_sheet_contains_interpretations(pending_sheet):
    cells = []
    for r in pending_sheet.iter_rows():
        cells.extend(str(c.value) for c in r if c.value is not None)
    joined = "\n".join(cells)
    # عنوانِ جدول
    assert "تصمیماتِ باز — منتظر تأیید کاربر" in joined
    # هر موضوع
    for e in PENDING_INTERPRETATIONS:
        assert e[1] in joined, "موضوع در شیت Excel نیست: %s" % e[1]
    # شناسهٔ اول و آخر در شیت است (D-01 .. D-20)
    assert "D-01" in joined
    assert "D-%02d" % len(PENDING_INTERPRETATIONS) in joined
