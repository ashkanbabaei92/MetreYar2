# -*- coding: utf-8 -*-
# T94 - لیستوفر آرماتور (ایراد ۱۱)
#
# ستون‌های رسمی: مارک | گروه سازه‌ای | طبقه | قطر | تعداد | طول هر شاخه |
# طول کل | وزن واحد | وزن کل | شکل خم. قواعد صریح ایراد ۱۱:
#   - مارک هرگز «—» نیست؛ در نبود پارامتر «Rebar Number/Mark» → «بدون مارک»
#     + هشدار.
#   - گروه هرگز «سایر» نیست؛ در نبود «Host Category» قابل‌تشخیص → «نامشخص»
#     + هشدار.
#   - جمع‌ها به تفکیک قطر و گروه سازه‌ای.
# جدول ترکیبی (canonical) — بدون وابستگی به golden یا دادهٔ واقعی.

import io
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (
    ExcelExporter,
    TechnicalOfficeEngine,
    default_settings,
    rebar_list_group,
    rebar_list_mark,
)

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _table():
    """جدول آرماتور ترکیبی: میزبان موجود / <varies> / فاقد مارک / نامشخص."""
    return {
        "id": "T94-rebar", "file_name": "T94.txt", "title": "T94 Rebar Schedule",
        "headers": [], "kind": "rebar_detailed", "kind_confidence": 1,
        "col_map": {}, "warnings": [], "grand_total": {},
        "rows": [
            {  # ۱ — میزبان «Structural Foundation» → گروه پی
                "cells": [],
                "values": {"weight": 60.5, "diameter": 14, "count": 5, "length": 50},
                "texts": {"mark": "FT-01", "barType": "AIII", "material": "AIII",
                          "hostCategory": "Structural Foundation", "level": "Story1",
                          "shape": "L"},
                "is_subtotal": False,
            },
            {  # ۲ — میزبان «<varies>» → گروه از مارک (تیر)
                "cells": [],
                "values": {"weight": 98.6, "diameter": 20, "count": 2, "length": 40},
                "texts": {"mark": "B01-ST01-MAIN-T", "barType": "AIII", "material": "AIII",
                          "hostCategory": "<varies>", "level": "Story2"},
                "is_subtotal": False,
            },
            {  # ۳ — هیچ مارکی وجود ندارد → «بدون مارک» + گروه نامشخص
                "cells": [],
                "values": {"weight": 1.18, "diameter": 8, "count": 1, "length": 3},
                "texts": {"barType": "AIII", "material": "AIII"},
                "is_subtotal": False,
            },
            {  # ۴ — مارک غیرقابل‌تشخیص و بدون میزبان → گروه نامشخص
                "cells": [],
                "values": {"weight": 4.44, "diameter": 10, "count": 4, "length": 16},
                "texts": {"mark": "ZZ-99", "barType": "AIII", "material": "AIII"},
                "is_subtotal": False,
            },
            {  # ۵ — میزبان «Floor» → دال (واژگان لیستوفر)
                "cells": [],
                "values": {"weight": 22.2, "diameter": 12, "count": 3, "length": 33},
                "texts": {"mark": "SL-N1", "barType": "AIII", "material": "AIII",
                          "hostCategory": "Floor"},
                "is_subtotal": False,
            },
        ],
    }


def _extract():
    eng = TechnicalOfficeEngine([], default_settings())
    lines, _bk, _bs, warns = eng._extract_rebar([_table()], None)
    return lines, warns


# ── helpers مستقیم (rebar_list_mark / rebar_list_group) ──

def test_T94_mark_never_dash():
    assert rebar_list_mark("FT-01") == "FT-01"
    assert rebar_list_mark("", "  ", None) == "بدون مارک"
    assert rebar_list_mark("  spaced  ") == "spaced"
    # اولویت: آرگومان اول
    assert rebar_list_mark("A", "B") == "A"
    assert rebar_list_mark("", "B") == "B"


def test_T94_group_never_other():
    # میزبان برنده است
    assert rebar_list_group("Structural Foundation", "هرچیزی", "rebar_detailed")[0] == "پی"
    # «<varies>» نادیده گرفته می‌شود → سقوط به مارک
    g, unk = rebar_list_group("<varies>", "B01-ST01-MAIN", "rebar_detailed")
    assert (g, unk) == ("تیر", False)
    # واژگان: Floor میزبان → «سقف» → «دال»
    g, _ = rebar_list_group("Floor", "X", "rebar_detailed")
    assert g == "دال"
    # غیرقابل‌تشخیص → «نامشخص» + پرچم هشدار
    g, unk = rebar_list_group("", "ZZ-99", "rebar_detailed")
    assert (g, unk) == ("نامشخص", True)
    # «سقف تیرچه» حفظ می‌شود (به «دال» تبدیل نمی‌شود)
    g, _ = rebar_list_group("Structural Framing Joist", "JST-1", "rebar_joist")
    assert g in ("سقف تیرچه", "تیر")


# ── استخراج ──

def test_T94_columns_and_invariants():
    lines, _w = _extract()
    assert len(lines) == 5
    for r in lines:
        # قاعدهٔ صریح ایراد ۱۱: مارک هرگز «—»، گروه هرگز «سایر»
        assert r["mark"] != "—", "mark is dash"
        assert r["group"] != "سایر", "group is other"
        # ستون‌های جدید حاضر هستند
        assert "level" in r and "per_bar_length" in r and "unit_weight" in r
        # طول هر شاخه = طول کل / تعداد
        assert r["per_bar_length"] == pytest.approx(r["total_length"] / r["count"])
        # وزن واحد = وزن / طول کل (در صورت طول صفر، صفر)
        if r["total_length"]:
            assert r["unit_weight"] == pytest.approx(r["weight"] / r["total_length"])
        else:
            assert r["unit_weight"] == 0.0


def test_T94_group_and_level_values():
    lines, _w = _extract()
    by_mark = {r["mark"]: r for r in lines}
    assert by_mark["FT-01"]["group"] == "پی"            # از Host Category
    assert by_mark["FT-01"]["level"] == "Story1"
    assert by_mark["B01-ST01-MAIN-T"]["group"] == "تیر"  # <varies> → مارک
    assert by_mark["B01-ST01-MAIN-T"]["level"] == "Story2"
    assert by_mark["SL-N1"]["group"] == "دال"            # Floor → دال
    assert by_mark["ZZ-99"]["group"] == "نامشخص"
    assert by_mark["ZZ-99"]["level"] == ""
    # ردیف فاقد مارک
    nomark = [r for r in lines if r["mark"] == "بدون مارک"]
    assert len(nomark) == 1
    assert nomark[0]["group"] == "نامشخص"
    assert nomark[0]["per_bar_length"] == pytest.approx(3.0)


def test_T94_warnings_one_per_table():
    _lines, warns = _extract()
    # دو هشدار برای یک جدول (یک «بدون مارک» + دو «نامشخص»، هر کدام یکبار)
    assert len(warns) == 2
    assert any("«بدون مارک»" in w for w in warns)
    assert any("«نامشخص»" in w for w in warns)
    # شمارش درست در متن هشدار
    nm = [w for w in warns if "«بدون مارک»" in w][0]
    assert "۱ ردیف" in nm
    ug = [w for w in warns if "«نامشخص»" in w][0]
    assert "۲ ردیف" in ug


# ── خروجی Excel ──

def _sheet_rows(workbook_bytes, sheet_xml_name):
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as wb:
        sst = {}
        if "xl/sharedStrings.xml" in wb.namelist():
            for i, si in enumerate(ET.fromstring(wb.read("xl/sharedStrings.xml"))
                                   .findall(f"{NS}si")):
                sst[i] = "".join(t.text or "" for t in si.iter(f"{NS}t"))
        out = []
        for row in ET.fromstring(wb.read(sheet_xml_name)) \
                .findall(f"{NS}sheetData/{NS}row"):
            vals = []
            for c in row.findall(f"{NS}c"):
                t = c.get("t")
                v = c.find(f"{NS}v")
                if t == "s":
                    vals.append(sst.get(int(v.text), "") if v is not None else "")
                elif t == "inlineStr":
                    vals.append("".join(x.text or "" for x in c.iter(f"{NS}t")))
                else:
                    vals.append(v.text if v is not None else "")
            out.append(vals)
    return out


def _meta():
    return {"report_type": "موقت", "report_no": "1", "contract_no": "T94",
            "project_name": "T94", "employer": "", "contractor": "", "consultant": "",
            "period_start": "", "period_end": "", "location": "", "contract_date": ""}


def test_T94_excel_sheet():
    lines, _w = _extract()
    result = {
        "lines": [], "rebar": lines, "chapter_sums": [], "base_total": 0,
        "floors_amount": 0, "overhead_amount": 0, "regional_amount": 0,
        "site_setup": 0, "gross_payable": 0, "grand_total": 0, "insurance": 0,
        "tax": 0, "good_job": 0, "advance_payment": 0, "total_deductions": 0,
        "net_payable": 0, "index": None,
        "quality": {"tables_parsed": 0, "tables_unknown": 0, "mapping_records": 0,
                    "rows_read": 0, "lines_matched": 0, "lines_exact": 0,
                    "lines_fuzzy": 0, "lines_estimated": 0, "lines_review": 0,
                    "warnings": []},
    }
    wb_bytes = ExcelExporter().export(_meta(), result, default_settings(), [])
    rows = _sheet_rows(wb_bytes, "xl/worksheets/sheet7.xml")  # فاز D: لیستوفر = برگهٔ ۷
    # یافتن ردیف سرستون (هدر پروژه بالاتر از آن است)
    hdr_i = next(i for i, r in enumerate(rows)
                 if r and r[0] == "مارک" and "گروه سازه‌ای" in r[1:3])
    hdr = rows[hdr_i]
    assert hdr[:10] == ["مارک", "گروه سازه‌ای", "طبقه", "قطر (mm)", "تعداد",
                        "طول هر شاخه (m)", "طول کل (m)", "وزن واحد (kg/m)",
                        "وزن کل (kg)", "شکل خم"]
    data = [r for r in rows[hdr_i + 1:] if r and r[0] and not r[0].startswith("جمع")]
    assert len(data) == 5
    # قواعد در سلول‌های اکسل هم برقرار است
    for r in data:
        assert r[0] != "—"
        assert r[1] != "سایر"
    # جمع به تفکیک قطر + گروه + کل
    labels = [r[0] for r in rows if r and r[0]]
    assert "جمع به تفکیک قطر" in labels
    assert "جمع به تفکیک گروه" in labels
    assert "جمع کل" in labels

    total_w = sum(r["weight"] for r in lines)
    tot_row = next(r for r in rows if r and r[0] == "جمع کل")
    assert float(tot_row[8]) == pytest.approx(total_w)

    def _section_sum(start_label, end_label):
        i0 = next((i for i, r in enumerate(rows) if r and r[0] == start_label), None)
        if i0 is None:
            return 0.0
        s = 0.0
        for r in rows[i0 + 1:]:
            if r and r[0] == end_label:
                break
            # ردیف‌های جمع: برچسب در ستون دوم و مقدار در ستون وزن کل
            if len(r) > 8 and r[8] not in ("", None):
                s += float(r[8])
        return s

    assert _section_sum("جمع به تفکیک قطر", "جمع به تفکیک گروه") == pytest.approx(total_w)
    assert _section_sum("جمع به تفکیک گروه", "جمع کل") == pytest.approx(total_w)


# ── دادهٔ واقعی پروژه (الزام پذیرش ایراد ۱۱) ──

def _load_real():
    from app import (DynamoMappingParser, RevitScheduleParser)
    revit_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                             "export revit")
    tables = []
    for fn in sorted(os.listdir(revit_dir)):
        if fn.lower().endswith((".txt", ".csv")):
            tables.append(RevitScheduleParser.parse(
                fn, open(os.path.join(revit_dir, fn), encoding="utf-8-sig").read()))
    return tables


def test_T94_real_data_invariants():
    """روی دادهٔ واقعی پروژه: مارک «—» و گروه «سایر» وجود ندارد و وزن کل
    (۱۲٬۵۳۶ کیلوگرم) تغییر نکرده است — بخش‌های کارکنده دست‌نخورده می‌مانند."""
    tables = _load_real()
    eng = TechnicalOfficeEngine([], default_settings())
    lines, _bk, _bs, _w = eng._extract_rebar(tables, None)
    assert len(lines) > 100, "real rebar list-off too small"
    for r in lines:
        assert r["mark"] != "—", f"dash mark: {r}"
        assert r["group"] != "سایر", f"other group: {r}"
        assert r["per_bar_length"] == pytest.approx(r["total_length"] / r["count"])
    # کل وزن آرماتور پروژه (تأییدشده در T53 stage6) تغییر نکرده
    assert sum(r["weight"] for r in lines) == pytest.approx(12536.2041, abs=1e-2)
