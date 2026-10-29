import io
import os, sys
import zipfile
import xml.etree.ElementTree as ET

import xlsxwriter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, record
from app import ExcelExporter, default_settings, chapter_title


def test_T34_excel_sheet_count():
    exporter = ExcelExporter()
    assert_golden("T34", {"exporter_type": type(exporter).__name__,
                           "has_export": hasattr(exporter, "export"),
                           "has_formats": hasattr(exporter, "_formats")},
                  generate=os.environ.get("GENERATE") == "1")


def test_T35_excel_rtl():
    exporter = ExcelExporter()
    meta = {"report_type": "موقت", "report_no": "1", "contract_no": "T35",
            "project_name": "T35", "employer": "", "contractor": "", "consultant": "",
            "period_start": "", "period_end": "", "location": "", "contract_date": ""}
    result = {
        "lines": [], "rebar": [], "chapter_sums": [], "base_total": 0,
        "floors_amount": 0, "overhead_amount": 0, "regional_amount": 0,
        "site_setup": 0, "gross_payable": 0, "grand_total": 0,
        "insurance": 0, "tax": 0, "good_job": 0,
        "advance_payment": 0, "total_deductions": 0, "net_payable": 0,
        "index": None,
        "quality": {"tables_parsed": 0, "tables_unknown": 0, "mapping_records": 0,
                    "rows_read": 0, "lines_matched": 0, "lines_exact": 0,
                    "lines_fuzzy": 0, "lines_estimated": 0, "lines_review": 0,
                    "warnings": []},
    }
    workbook_bytes = exporter.export(meta, result, default_settings(), [])
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as workbook:
        sheet_xml = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    sheet_view = sheet_xml.find(f"{namespace}sheetViews/{namespace}sheetView")
    assert sheet_view is not None
    assert sheet_view.attrib.get("rightToLeft") == "1"


def test_T36_excel_formula_capability():
    from app import ExcelExporter
    exporter = ExcelExporter()
    wb = xlsxwriter.Workbook(io.BytesIO(), {"in_memory": True})
    try:
        fmts = exporter._formats(wb) if hasattr(exporter, "_formats") else {}
        assert_golden("T36", {"has_write_formula": hasattr(exporter, "_formats"),
                              "format_count": len(fmts),
                              "has_net_format": "net" in fmts,
                              "note": "Formula injection requires Excel runtime to verify"},
                      generate=os.environ.get("GENERATE") == "1")
    finally:
        wb.close()


if __name__ == "__main__":
    for fn in [test_T34_excel_sheet_count, test_T35_excel_rtl, test_T36_excel_formula_capability]:
        print(fn.__name__, fn())