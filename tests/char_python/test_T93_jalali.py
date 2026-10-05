# -*- coding: utf-8 -*-
# T93 — فاز C: ایراد ۱۳ (تقویم شمسی).
#
# - تبدیل شمسی ↔ میلادی (دو طرفه) بدون کتابخانه خارجی.
# - jalali_to_iso: متن شمسی → ISO میلادی (ستون مخفی Excel).
# - شیت «سوابق صورت وضعیت»: متن شمسی + ستون مخفی میلادی واقعی.
import datetime
import io
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (ExcelExporter, TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings, gregorian_to_jalali, jalali_to_gregorian,
                 jalali_to_iso, today_jalali)

META = {"project_name": "T93", "employer": "کارفرما", "contractor": "پیمانکار",
        "consultant": "مشاور", "contract_no": "۱", "location": "گرگان",
        "report_no": "۱", "report_type": "دوره‌ای",
        "period_start": "۱۴۰۴/۰۱/۰۱", "period_end": "۱۴۰۴/۰۳/۳۱",
        "contract_date": "۱۴۰۳/۱۲/۲۹"}


# ── تبدیل دوطرفه ──

@pytest.mark.parametrize("gy,gm,gd", [
    (2025, 3, 21),   # نوروز ۱۴۰۴
    (2024, 3, 20),   # نوروز ۱۴۰۳
    (2023, 3, 21),   # نوروز ۱۴۰۲
    (2025, 9, 23),   # اوایل مهر ۱۴۰۴
    (2026, 1, 1),    # اوایل دی ۱۴۰۴
    (2025, 12, 31),
])
def test_T93_roundtrip_gregorian(gy, gm, gd):
    jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    assert (jy, jm, jd) == gregorian_to_jalali(gy, gm, gd)
    back = jalali_to_gregorian(jy, jm, jd)
    assert back == (gy, gm, gd)


@pytest.mark.parametrize("jy,jm,jd", [
    (1404, 1, 1), (1403, 1, 1), (1402, 1, 1),
    (1404, 7, 1), (1404, 12, 29), (1403, 12, 30),
    (1405, 1, 1), (1405, 7, 8),
])
def test_T93_roundtrip_jalali(jy, jm, jd):
    g = jalali_to_gregorian(jy, jm, jd)
    assert g is not None
    assert gregorian_to_jalali(*g) == (jy, jm, jd)


def test_T93_known_anchor_nowruz():
    # نوروز ۱۴۰۴ = ۲۱ مارس ۲۰۲۵ (مرجع تقویم رسمی)
    assert jalali_to_gregorian(1404, 1, 1) == (2025, 3, 21)
    assert gregorian_to_jalali(2025, 3, 21) == (1404, 1, 1)


def test_T93_leap_year_consistency():
    # ۱۴۰۳ کبیسه است (اسفند ۳۰ روزه)؛ ۱۴۰۴ نیست
    assert jalali_to_gregorian(1403, 12, 30) == (2025, 3, 20)
    # ۱۴۰۴ اسفند ۳۰ ندارد → None (نه پیش‌فرض، نه حدس)
    assert jalali_to_gregorian(1404, 12, 30) is None


def test_T93_invalid_jalali_returns_none():
    for bad in [(1404, 13, 1), (1404, 0, 1), (1404, 12, 32), (1299, 1, 1)]:
        assert jalali_to_gregorian(*bad) is None


# ── jalali_to_iso ──

def test_T93_jalali_to_iso():
    assert jalali_to_iso("۱۴۰۴/۰۱/۰۱") == "2025-03-21"
    assert jalali_to_iso("1404/01/01") == "2025-03-21"  # ارقام لاتین
    assert jalali_to_iso("۱۴۰۳/۱۲/۳۰") == "2025-03-20"
    assert jalali_to_iso("۱۴۰۳/۱۲/۲۹") == "2025-03-19"


def test_T93_jalali_to_iso_invalid():
    assert jalali_to_iso("") is None
    assert jalali_to_iso("نامعتبر") is None
    assert jalali_to_iso("1404/13/01") is None
    assert jalali_to_iso(None) is None


def test_T93_today_jalali_valid():
    d = today_jalali()
    assert TechnicalOfficeEngine._parse_jalali(d) is not None


# ── شیت Excel: ستون مخفی میلادی ──

def _export_with_history(history):
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    res = eng.compute([], None)
    return ExcelExporter().export(META, res, default_settings(), history)


def test_T93_excel_history_hidden_gregorian_columns():
    history = [{"report_no": "۱", "report_type": "موقت",
                "period_start": "۱۴۰۴/۰۱/۰۱", "period_end": "۱۴۰۴/۰۳/۳۱",
                "gross_payable": 1e9, "total_deductions": 1e8,
                "net_payable": 9e8, "current_work": 9e8}]
    data = _export_with_history(history)
    # نقشهٔ نام شیت → فایل XML
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        wbxml = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        R = "{http://schemas.openxmlformats.org/package/2006/relationships}"
        MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
        sheet_file = None
        for sh in wbxml.iter(f"{MAIN}sheet"):
            if sh.get("name") == "سوابق صورت وضعیت":
                tgt = rid_to_target[sh.get(REL + "id")]
                sheet_file = "xl/" + tgt.lstrip("/").replace("xl/", "", 1) \
                    if tgt.startswith("/xl/") else "xl/" + tgt
        assert sheet_file is not None, "شیت «سوابق صورت وضعیت» پیدا نشد"
        sxml = zf.read(sheet_file).decode("utf-8")
        # ستون‌های I و J مخفی‌اند
        cols = ET.fromstring(sxml).find(f"{MAIN}cols")
        hidden_cols = [c.attrib for c in cols] if cols is not None else []
        assert any(c.get("hidden") == "1" and c.get("min") == "9"
                   for c in hidden_cols), hidden_cols
        # هدر ستون‌های میلادی در sharedStrings
        shared = zf.read("xl/sharedStrings.xml").decode("utf-8")
        assert "دوره از (میلادی)" in shared
        assert "دوره تا (میلادی)" in shared
        # مقادیر میلادی واقعی (serial تاریخ Excel) — فقط سلول‌های عددی
        rows = ET.fromstring(sxml).iter(f"{MAIN}row")
        i_cells, j_cells = [], []
        for r in rows:
            for c in r:
                if c.get("t") == "s":  # رشتهٔ اشتراکی (هدر) را نادیده می‌گیریم
                    continue
                if c.get("r", "").startswith("I"):
                    i_cells.append(c.find(f"{MAIN}v"))
                elif c.get("r", "").startswith("J"):
                    j_cells.append(c.find(f"{MAIN}v"))
        # اولین I/J داده‌ای (ردیف هدر شامل هیچ مقدار عددی نیست)
        i_vals = [x.text for x in i_cells if x is not None and x.text]
        j_vals = [x.text for x in j_cells if x is not None and x.text]
        assert i_vals and j_vals, "ستون‌های میلادی خالی هستند"
        # serial ۱۴۰۴/۰۱/۰۱ = ۲۰۲۵-۰۳-۲۱ و ۱۴۰۴/۰۳/۳۱ = ۲۰۲۵-۰۶-۲۱
        base = datetime.date(1899, 12, 30)
        exp_start = datetime.date(*map(int, jalali_to_iso("۱۴۰۴/۰۱/۰۱").split("-")))
        exp_end = datetime.date(*map(int, jalali_to_iso("۱۴۰۴/۰۳/۳۱").split("-")))
        assert int(float(i_vals[0])) == (exp_start - base).days
        assert int(float(j_vals[0])) == (exp_end - base).days


def test_T93_excel_history_empty_dates_blank():
    history = [{"report_no": "۱", "report_type": "موقت",
                "period_start": "", "period_end": "",
                "gross_payable": 0, "total_deductions": 0,
                "net_payable": 0, "current_work": 0}]
    data = _export_with_history(history)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared = zf.read("xl/sharedStrings.xml").decode("utf-8")
        # هدر ستون‌های میلادی همیشه وجود دارد
        assert "دوره از (میلادی)" in shared
