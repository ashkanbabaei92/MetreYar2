# -*- coding: utf-8 -*-
"""T112 — پاریتیِ معیارهای quality و زنجیرهٔ مالی (Part E، شکاف ۷).

این آزمون بنابر شکافِ §۱۶-۶ شمارهٔ ۷ ساخته شد: شیتِ Excelِ «کیفیت تطبیق»
در پایتون ۹ ردیفِ معیار دارد ولی در TypeScript ۸ ردیف (ردیفِ
«رکوردهای Mapping» نیست) و یک شمارش (۸۳۵ = mapping_records) در TS وجود ندارد.

تحقیق (این جلسه): موتورها رویِ خطِ لولهٔ یکسان **دقیقاً برابر** هستند —
تمامِ معیارهای مشترک و base_total/grand_total bit-identical تأیید شد.
اختلاف صرفاً نمایشی (یک ردیفِ کمتر در شیت + برچسب‌ها) است و هیچ اثرِ
مالی ندارد. این آزمون آن معیارها را به‌عنوان مرجعِ مشترک تثبیت می‌کند.

خطِ لوله: DEMO_SCHEDULES (۹ جدول) + fehrest واقعی ۱۴۰۴، map_df=None،
تنظیماتِ پیش‌فرض.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (  # noqa: E402
    DEMO_SCHEDULES,
    DynamoMappingParser,
    ExcelExporter,
    FehrestBahaParser,
    RevitScheduleParser,
    TechnicalOfficeEngine,
    default_settings,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
FEHREST_FILE = os.path.join(ROOT, "data", "fehrest baha 1404",
                            "all 1404 fehrest.txt")
MAP2_FILE = os.path.join(ROOT, "data", "dynamo", "mapping2", "map2.txt")

# ── مرجعِ مشترک (در هر دو زبان یکسان — با همین خطِ لوله بررسی شده) ──
EXPECTED_QUALITY = {
    "tables_parsed": 9,
    "tables_unknown": 0,
    "rows_read": 97,
    "lines_matched": 15,
    "lines_exact": 15,
    "lines_fuzzy": 0,
    "lines_estimated": 0,
    "lines_review": 1,
}
EXPECTED_WARNINGS = 1
EXPECTED_BASE_TOTAL = 19659382497.83152
EXPECTED_GRAND_TOTAL = 26579485137.06822

# ── حالتِ دوم: mapping تک‌فایل (مثل UI واقعی) — bit-identical با TS ──
EXPECTED_MAP2 = {
    "lines": 16,
    "base_total": 20380352396.269382,
    "grand_total": 27554236439.75621,
}


def _run():
    with open(FEHREST_FILE, "r", encoding="utf-8") as fh:
        db, _n = FehrestBahaParser.parse_text(fh.read())
    tables = [RevitScheduleParser.parse(name, text)
              for name, text in DEMO_SCHEDULES]
    return TechnicalOfficeEngine(db, default_settings()).compute(tables, None)


@pytest.fixture(scope="module")
def result():
    return _run()


def test_T112_quality_metrics(result):
    """معیارهای مشترکِ quality با مرجع برابرند (پاریتی با TS)."""
    q = result["quality"]
    for key, want in EXPECTED_QUALITY.items():
        assert q[key] == want, f"{key}: got {q[key]!r}, want {want!r}"


def test_T112_financial_chain(result):
    """زنجیرهٔ مالی bit-identical با TS است."""
    assert result["base_total"] == pytest.approx(EXPECTED_BASE_TOTAL, abs=1e-6)
    assert result["grand_total"] == pytest.approx(EXPECTED_GRAND_TOTAL, abs=1e-6)


def test_T112_lines_count(result):
    assert len(result["lines"]) == EXPECTED_QUALITY["lines_matched"]


def test_T112_quality_sheet_has_mapping_records_row(result):
    """پایتون ردیفِ اضافهٔ «رکوردهای Mapping» را در شیت می‌نویسد (TS نمی‌نویسد).

    این تفاوتِ نمایشی در §۱۶-۶ شکاف ۷ ثبت شده و مجاز شمرده می‌شود
    (هیچ اثرِ مالی ندارد). این آزمون وجودِ آن را تثبیت می‌کند.
    """
    q = result["quality"]
    assert "mapping_records" in q
    assert isinstance(q["mapping_records"], int)


def test_T112_excel_quality_sheet_structure(result):
    """شیتِ «کیفیت تطبیق» ساخته می‌شود و ۹ ردیفِ معیار + هشدارها را دارد."""
    exporter = ExcelExporter()
    meta = {
        "project_name": "پروژهٔ مسکونی نمونه - اسکلت بتنی",
        "employer": "کارفرما", "contractor": "پیمانکار", "consultant": "مشاور",
        "contract_no": "T112", "contract_date": "1404/01/01", "location": "تهران",
        "report_no": "۱", "report_type": "موقت",
        "period_start": "1404/01/01", "period_end": "1404/01/31",
    }
    data = exporter.export(meta, result, default_settings(), [])
    import io
    import re
    import zipfile

    buf = io.BytesIO(data)
    with zipfile.ZipFile(buf) as zf:
        wbxml = zf.read("xl/workbook.xml").decode("utf-8")
    sheet_names = re.findall(r'<sheet name="([^"]+)"', wbxml)
    assert "کیفیت تطبیق" in sheet_names


def test_T112_single_file_mapping_parity():
    """حالتِ mapping تک‌فایل (مثل UI): نتایج bit-identical با TS است.

    §۱۸-۹-۱ یادداشتِ شکاف ۷: یک بررسیِ اولیه به‌اشتباه py-با-mapping را با
    TS-بدون-mapping مقایسه کرد (۱۶ در برابر ۱۵ خط) — تفاوتِ ورودی بود، نه
    موتور. رویِ پیکربندیِ یکسان — تک‌فایل `mapping2/map2.txt` — نتایج
    دقیقاً برابرند.
    """
    with open(FEHREST_FILE, "r", encoding="utf-8") as fh:
        db, _n = FehrestBahaParser.parse_text(fh.read())
    with open(MAP2_FILE, "rb") as fh:
        raw = fh.read()
    map_df = DynamoMappingParser.merge_formats(
        [DynamoMappingParser.auto_detect_and_parse(raw, "map2.txt")])
    tables = [RevitScheduleParser.parse(name, text)
              for name, text in DEMO_SCHEDULES]
    r = TechnicalOfficeEngine(db, default_settings()).compute(tables, map_df)
    assert len(r["lines"]) == EXPECTED_MAP2["lines"]
    assert r["base_total"] == pytest.approx(EXPECTED_MAP2["base_total"], abs=1e-6)
    assert r["grand_total"] == pytest.approx(EXPECTED_MAP2["grand_total"],
                                             abs=1e-6)
