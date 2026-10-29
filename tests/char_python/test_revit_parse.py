import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, load_fixture, save_json, record
from app import RevitScheduleParser


def test_T01_R1_simple():
    text = load_fixture("revit", "R1_simple.txt")
    result = RevitScheduleParser.parse("test_R1.txt", text)
    assert_golden("T01", result, generate=os.environ.get("GENERATE") == "1")


def test_T02_R2_title_subtitle():
    text = load_fixture("revit", "R2_title_subtitle.txt")
    result = RevitScheduleParser.parse("test_R2.txt", text)
    assert_golden("T02", result, generate=os.environ.get("GENERATE") == "1")


def test_T03_R3_subtotal():
    text = load_fixture("revit", "R3_subtotal.txt")
    result = RevitScheduleParser.parse("test_R3.txt", text)
    assert_golden("T03", result, generate=os.environ.get("GENERATE") == "1")


def test_T04_R4_unknown():
    text = load_fixture("revit", "R4_unknown.txt")
    result = RevitScheduleParser.parse("test_R4.txt", text)
    assert_golden("T04", result, generate=os.environ.get("GENERATE") == "1")


def test_T05_R5_incomplete():
    text = load_fixture("revit", "R5_incomplete.txt")
    result = RevitScheduleParser.parse("test_R5.txt", text)
    assert_golden("T05", result, generate=os.environ.get("GENERATE") == "1")


def test_T55_doubled_quote_dialect():
    """Revit's doubled-quote CSV parses like standard CSV."""
    doubled = ('"جدول نمونه - Revit Schedule"","""\n'
               '"Mark"",""Family and Type"",""Volume"\n'
               '""","""","""\n'
               '"LC-01"",""Foundation Slab: 100mm"",""18.65 m³"\n')
    result = RevitScheduleParser.parse("dbl.txt", doubled)
    assert result["headers"] == ["Mark", "Family and Type", "Volume"]
    assert result["col_map"].get("volume") == 2
    assert len(result["rows"]) == 1
    assert result["rows"][0]["texts"]["mark"] == "LC-01"
    assert result["rows"][0]["values"]["volume"] == pytest.approx(18.65)

    standard = RevitScheduleParser.parse(
        "std.txt", '"Standard Schedule" ,""\n"Mark","Volume"\n"LC-01","18.65 m³"\n')
    assert standard["headers"] == ["Mark", "Volume"]
    assert len(standard["rows"]) == 1
    assert standard["rows"][0]["values"]["volume"] == pytest.approx(18.65)

    quoted = RevitScheduleParser.parse(
        "quoted.txt", '"Quoted Schedule" ,""\n'
        '"Mark","Description","Volume"\n'
        '"LC-01","1,000 mm bar with ""quote""","1.0 m³"\n')
    assert quoted["headers"] == ["Mark", "Description", "Volume"]
    assert quoted["rows"][0]["cells"][1] == '1,000 mm bar with "quote"'
    assert quoted["rows"][0]["values"]["volume"] == pytest.approx(1.0)


def test_T56_bom_does_not_leak_into_title():
    """A UTF-8 BOM must not leak into the title or classification."""
    body = ('"جدول ریزمتره حجم بتن سازه‌ای - Structural Concrete Schedule","","",""\n'
            '"Category","Family and Type","Material: Volume"\n'
            '"Floors","Floor: Slab20","13.95 m³"\n')
    result = RevitScheduleParser.parse("bom.txt", "\ufeff" + body)
    assert result["title"].startswith("جدول")
    assert result["kind"] == "structural_concrete"
    assert result["kind_conf"] == pytest.approx(0.97)
    assert result["rows"][0]["values"]["volume"] == pytest.approx(13.95)


if __name__ == "__main__":
    for fn in [test_T01_R1_simple, test_T02_R2_title_subtitle, test_T03_R3_subtotal,
               test_T04_R4_unknown, test_T05_R5_incomplete,
               test_T55_doubled_quote_dialect, test_T56_bom_does_not_leak_into_title]:
        print(fn.__name__, fn())