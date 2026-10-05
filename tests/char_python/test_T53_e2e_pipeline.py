# -*- coding: utf-8 -*-
# T53 - REAL END-TO-END PIPELINE (MetreYar2)
#
# Goal: run the fullest real production path available, from the project's real
# inputs to the final Excel output, without inventing any new contract.
#
# Chain:
#   real Revit files (data/export revit)
#     -> RevitScheduleParser.parse          (parse + kind detection)
#     -> parse_value_unit / to_si           (numeric normalization)
#     -> DynamoMappingParser.auto_detect_and_parse (real v1+v2 mapping)
#     -> TechnicalOfficeEngine.compute      (quantity aggregation + fehrest
#                                            matching + adjustment index
#                                            + financial chain)
#     -> ExcelExporter.export               (real xlsx output)
#
# Price source: the real 1404 fehrest file (data/fehrest baha 1404) via
# FehrestBahaParser.parse_text + merge - no production code changed.
#
# Modeled on T14/T32 (no golden dependency) and T35 (real Excel output check).

import io
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (
    DEMO_SCHEDULES,
    DynamoMappingParser,
    ExcelExporter,
    FehrestBahaParser,
    RevitScheduleParser,
    TechnicalOfficeEngine,
    default_settings,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")
FEHREST_FILE = os.path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt")

# codes the engine looks up for its rule-driven plans (پس از بازنگاشت مرحلهٔ ۲)
EXPECTED_CODES = {"080102", "080105", "080106", "080107", "060101", "060301",
                  "060501", "060701", "100305", "070101", "070201", "070202",
                  "070203", "280101"}


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _load_revit_tables():
    """Stage 1+2: parse the app's real sample project + numeric normalization.

    Mirrors load_demo() exactly: RevitScheduleParser.parse over DEMO_SCHEDULES,
    the app's shipped «بارگذاری دادهٔ نمونهٔ واقعی» entry point. No manual
    classification is applied - every table is classified automatically by the
    production classifier (titles containing the Persian zero-width non-joiner
    U+200C are normalized consistently now).
    """
    return [RevitScheduleParser.parse(name, text) for name, text in DEMO_SCHEDULES]


def _load_mapping():
    """Stage 3: parse the real Dynamo mapping files (v1 + v2)."""
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fname in sorted(fnames):
            if not fname.endswith(".txt"):
                continue
            path = os.path.join(root, fname)
            with open(path, "rb") as fh:
                raw = fh.read()
            results.append(DynamoMappingParser.auto_detect_and_parse(raw, fname))
    return DynamoMappingParser.merge_formats(results)


def _load_fehrest_db():
    """Stage 4: price database from the real 1404 file merged over the embedded base."""
    base = FehrestBahaParser.embedded()
    rows, skipped = FehrestBahaParser.parse_text(_read(FEHREST_FILE))
    assert skipped > 0, "the real 1404 fehrest file is expected to contain some unreadable rows"
    merged = FehrestBahaParser.merge(base, rows)
    return merged, len(rows)


def _meta():
    return {
        "project_name": "پروژهٔ مسکونی نمونه - اسکلت بتنی",
        "employer": "کارفرما", "contractor": "پیمانکار", "consultant": "مشاور",
        "contract_no": "T53", "contract_date": "1404/01/01", "location": "تهران",
        "report_no": "۱", "report_type": "موقت",
        "period_start": "1404/01/01", "period_end": "1404/01/31",
    }


# ──────────────────────────── pipeline stages ────────────────────────────


def test_T53_stage1_revit_parsing():
    """Stage 1: real parsing of the Revit exports + table-kind classification."""
    tables = _load_revit_tables()
    assert len(tables) == len(DEMO_SCHEDULES)

    kinds = {t["kind"] for t in tables}
    # every structural kind must be covered by the real data
    assert "structural_concrete" in kinds
    assert "formwork_super" in kinds
    assert "formwork_foundation" in kinds
    assert "rebar_detailed" in kinds
    assert "rebar_joist" in kinds
    assert "rebar_connection" in kinds
    assert "joist_floor" in kinds
    assert "joist_materials" in kinds
    assert "lean_concrete" in kinds
    assert "unknown" not in kinds, "a real table was left unclassified"

    for t in tables:
        # 0.75 is the production fallback for tables classified by column signature
        assert t["kind_conf"] >= 0.75, f"low classification confidence: {t['file_name']} = {t['kind_conf']}"
        assert len(t["rows"]) > 0, f"table with no data rows: {t['file_name']}"

    # the two ZWNJ titles must be classified automatically by the title rules
    # (0.97/0.95), not by the 0.70 column-signature fallback
    concrete = next(t for t in tables if t["kind"] == "structural_concrete")
    assert concrete["kind_conf"] == pytest.approx(0.97), \
        f"structural_concrete not classified by its title rule: {concrete['kind_conf']}"
    form = next(t for t in tables if t["kind"] == "formwork_super")
    assert form["kind_conf"] == pytest.approx(0.95), \
        f"formwork_super not classified by its title rule: {form['kind_conf']}"

    # numeric normalization: structural concrete volume must be summable
    total = sum(r["values"].get("volume", 0) for r in concrete["rows"] if not r["is_subtotal"])
    assert total == pytest.approx(264.28, abs=0.02), f"total concrete volume: {total}"
    assert concrete["grand_total"].get("volume") == pytest.approx(264.25, abs=0.02)

    # numeric normalization: superstructure formwork area
    area = sum(r["values"].get("area", 0) for r in form["rows"] if not r["is_subtotal"])
    assert area == pytest.approx(2183.0, abs=0.5), f"total formwork area: {area}"
    assert form["grand_total"].get("area") == pytest.approx(2184.0, abs=0.5)

    # internal Revit subtotal rows must be flagged
    joist = next(t for t in tables if t["kind"] == "joist_materials")
    assert any(r["is_subtotal"] for r in joist["rows"]), "subtotal rows were not detected"


def test_T53_stage2_mapping_parsing():
    """Stage 3: real Dynamo mapping parsing in both v1 and v2 formats."""
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fname in sorted(fnames):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(root, fname), "rb") as fh:
                raw = fh.read()
            results.append(DynamoMappingParser.auto_detect_and_parse(raw, fname))

    formats = {r["fmt"] for r in results}
    assert formats == {"v1", "v2"}, f"format detection failed: {formats}"
    for r in results:
        assert r["error"] is None, f"mapping parse error: {r['error']}"
        assert r["records_count"] > 0

    merged = DynamoMappingParser.merge_formats(results)
    assert not merged.empty
    assert "source_format" in merged.columns
    assert set(merged["source_format"]) == {"v1", "v2"}

    # the canonical fehrest-code column must exist (even when empty)
    assert "fehrest_code" in merged.columns


def test_T53_stage3_fehrest_real_file():
    """Stage 4: parse and merge the real 1404 fehrest."""
    merged, n_rows = _load_fehrest_db()
    assert n_rows > 100, f"fehrest file has too few rows: {n_rows}"

    by_code = {r["code"]: r for r in merged}
    # codes the engine needs must be present after the merge
    for code in ("080102", "080105", "080106", "080107", "060101", "060301",
                 "060501", "060701", "100305", "070101", "070201", "070202",
                 "070203", "280101"):
        assert code in by_code, f"code {code} not found in the real fehrest"

    # real prices must override the embedded estimated defaults
    assert by_code["070202"]["price"] == pytest.approx(375500)
    assert by_code["070203"]["price"] == pytest.approx(358500)
    assert by_code["060101"]["price"] == pytest.approx(2538000)


def test_T53_stage4_compute_and_financial():
    """Stages 5-9: full quantity, price, waste, factor and financial computation."""
    tables = _load_revit_tables()
    map_df = _load_mapping()
    db, _n = _load_fehrest_db()

    settings = default_settings()
    engine = TechnicalOfficeEngine(db, settings)
    result = engine.compute(tables, map_df)

    assert result is not None
    assert len(result["lines"]) > 0, "no BOQ lines were produced"
    assert result["quality"]["tables_parsed"] == len(DEMO_SCHEDULES)
    assert result["quality"]["tables_unknown"] == 0
    assert result["quality"]["rows_read"] > 0

    codes = {line["code"] for line in result["lines"]}
    # the main plan rows must have been produced (کدهای جدید پس از بازنگاشت)
    assert "080105" in codes or "080106" in codes or "080107" in codes, \
        "no structural concrete row produced"
    assert "060101" in codes or "060301" in codes or "060501" in codes, "no formwork row produced"

    # financial chain (مرحلهٔ ۱۳ — دستورالعمل کاربرد ۲-۷/۲-۸):
    #   جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای
    #   + تجهیز و برچیدن (مبلغ) = مبلغ ناخالص نهایی
    # کسورات قانونی بر ناخالص اثر نمی‌گذارند؛ فقط در بلوک جداگانهٔ
    # «خالص پرداختی» محاسبه می‌شوند. ضرایب طبقات/منطقه‌ای اکنون موتور
    # محاسبه می‌کند (ایراد ۳/۴) و در result["coefs"] با وضعیت گزارش می‌شوند.
    s = settings
    floors_coef = result["coefs"]["floors"]["value"] or 1.0
    regional_coef = result["coefs"]["regional"]["value"] or 1.0
    assert result["base_total"] > 0
    assert result["floors_amount"] == pytest.approx(result["base_total"] * floors_coef)
    assert result["overhead_amount"] == pytest.approx(
        result["floors_amount"] * s["overhead_coef"])
    assert result["regional_amount"] == pytest.approx(
        result["overhead_amount"] * regional_coef)
    assert result["site_setup"] == pytest.approx(s["site_setup_amount"])
    assert result["gross_payable"] == pytest.approx(
        result["regional_amount"] + s["site_setup_amount"])
    assert result["grand_total"] == result["gross_payable"]
    assert result["total_deductions"] == pytest.approx(
        result["gross_payable"] * (s["insurance_pct"] + s["tax_pct"] + s["good_job_pct"]) / 100
        + s["advance_payment"])
    assert result["net_payable"] == pytest.approx(
        result["gross_payable"] - result["total_deductions"])
    assert result["grand_total"] > 0

    # every line must carry a price, a unit and a fehrest description
    for line in result["lines"]:
        assert line["price"] > 0, f"line without a price: {line['code']}"
        # ۲۸۰۱۰۱ در فهرست‌بهای ۱۴۰۴ واحد «تن-کیلومتر» دارد (حمل به ازای هر
        # تن-کیلومتر)؛ تشخیص واحد این اکنون درست انجام می‌شود و این یکای
        # رسمی است، نه مقدار نامعتبر.
        assert line["unit"] in ("مترمربع", "مترمکعب", "کیلوگرم", "تن",
                                "مترطول", "تن-کیلومتر"), \
            f"invalid unit: {line['unit']}"
        assert len(line["desc"]) > 5
        # مرحلهٔ ۱۱ بخش ۱: هیچ ضریب پرتی وجود ندارد — qty تنها مقدار است
        assert line["total"] == pytest.approx(line["qty"] * line["price"])
        assert line.get("index_factor", 1.0) == pytest.approx(
            line.get("total_indexed", line["total"]) / line["total"]
            if line["total"] else 1.0)


def test_T53_stage5_excel_export():
    """Stage 10: feed the real computed result into the real Excel exporter."""
    tables = _load_revit_tables()
    map_df = _load_mapping()
    db, _n = _load_fehrest_db()
    settings = default_settings()
    result = TechnicalOfficeEngine(db, settings).compute(tables, map_df)

    assert len(result["lines"]) > 0, "empty compute result; Excel would be meaningless"

    exporter = ExcelExporter()
    workbook_bytes = exporter.export(_meta(), result, settings, [])

    assert isinstance(workbook_bytes, (bytes, bytearray))
    assert len(workbook_bytes) > 1000

    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as wb:
        names = wb.namelist()
        assert "xl/workbook.xml" in names
        # the eleven official report sheets (مرحلهٔ ۱۳: + ضریب طبقات، + هشدارها،
        # + مقادیر منتظر تأیید؛ فاز C: + قیمت‌های دستی، + سابقهٔ ویرایش)
        wb_xml = ET.fromstring(wb.read("xl/workbook.xml"))
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        sheets = [s.get("name") for s in wb_xml.iter(f"{ns}sheet")]
        assert len(sheets) == 16, f"sheet count: {len(sheets)}"
        assert "خلاصهٔ مالی و برآورد" in sheets
        assert "خلاصه و وضعیت" in sheets
        assert "مشخصات پیمان" in sheets
        assert "ضرایب" in sheets
        assert "شاخص‌ها" in sheets
        assert "منابع و بخشنامه‌ها" in sheets
        assert "صورت وضعیت" in sheets
        assert "متره ریز" in sheets
        assert "لیستوفر آرماتور" in sheets
        assert "سوابق صورت وضعیت" in sheets
        assert "کیفیت تطبیق" in sheets
        assert "ضریب طبقات" in sheets
        assert "هشدارها" in sheets
        assert "مقادیر منتظر تأیید" in sheets
        # فاز C — پنل قیمت دستی
        assert "قیمت‌های دستی" in sheets
        assert "سابقهٔ ویرایش" in sheets

        # every sheet must be right-to-left
        for sheet_xml_name in [n for n in names if n.startswith("xl/worksheets/sheet")]:
            sx = ET.fromstring(wb.read(sheet_xml_name))
            sv = sx.find(f"{ns}sheetViews/{ns}sheetView")
            assert sv is not None, f"sheet without a sheetView: {sheet_xml_name}"
            assert sv.attrib.get("rightToLeft") == "1", \
                f"sheet is left-to-right: {sheet_xml_name}"

        # the BOQ sheet must carry the real meter rows
        _boq_idx = sheets.index("صورت وضعیت") + 1  # فاز D: صورت وضعیت = برگهٔ ۸
        boq = ET.fromstring(wb.read(f"xl/worksheets/sheet{_boq_idx}.xml"))
        rows = boq.findall(f"{ns}sheetData/{ns}row")
        assert len(rows) > 20, f"BOQ sheet has too few rows: {len(rows)}"


def test_T53_stage6_rebar_and_quality():
    """Supplementary stage: the rebar list-off and the match-quality report."""
    tables = _load_revit_tables()
    map_df = _load_mapping()
    db, _n = _load_fehrest_db()
    result = TechnicalOfficeEngine(db, default_settings()).compute(tables, map_df)

    # the rebar list-off is extracted from the three real rebar tables
    assert len(result["rebar"]) > 0, "rebar list-off is empty"
    total_kg = sum(r["weight"] for r in result["rebar"])
    assert total_kg > 1000, f"total rebar weight is too low: {total_kg}"

    for r in result["rebar"]:
        assert r["weight"] > 0
        assert r["price_code"] in ("070101", "070201", "070202", "070203")

    # weight bucketing must preserve the total (Grand-total balancing is allowed)
    bucket_sum = sum(line["qty"] for line in result["lines"] if line["chapter"] == "07")
    assert bucket_sum >= total_kg - 1e-6, "bucketed weight is below the list-off"

    q = result["quality"]
    assert q["lines_matched"] == len(result["lines"])
    assert q["lines_exact"] + q["lines_fuzzy"] == q["lines_matched"]
    assert q["lines_estimated"] >= 0
    assert q["lines_review"] >= 0


if __name__ == "__main__":
    for fn in [
        test_T53_stage1_revit_parsing,
        test_T53_stage2_mapping_parsing,
        test_T53_stage3_fehrest_real_file,
        test_T53_stage4_compute_and_financial,
        test_T53_stage5_excel_export,
        test_T53_stage6_rebar_and_quality,
    ]:
        print(fn.__name__, "→", fn())
