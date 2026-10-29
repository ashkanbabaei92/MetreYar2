import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, load_fixture, record
from app import RevitScheduleParser


def test_T39_idempotency():
    text = load_fixture("revit", "R1_simple.txt")
    r1 = RevitScheduleParser.parse("test.txt", text)
    r2 = RevitScheduleParser.parse("test.txt", text)
    assert_golden("T39", {"r1_headers": r1.get("headers"), "r2_headers": r2.get("headers"),
                           "r1_kind": r1.get("kind"), "r2_kind": r2.get("kind"),
                           "r1_rows": len(r1.get("rows", [])), "r2_rows": len(r2.get("rows", [])),
                           "identical": r1.get("headers") == r2.get("headers") and
                                        r1.get("kind") == r2.get("kind") and
                                        len(r1.get("rows", [])) == len(r2.get("rows", []))},
                  generate=os.environ.get("GENERATE") == "1")


def test_T40_dedup_repeated():
    text = load_fixture("revit", "R3_subtotal.txt")
    result = RevitScheduleParser.parse("test_R3.txt", text)
    rows = result.get("rows", [])
    subtotal_rows = [r for r in rows if r.get("is_subtotal")]
    data_rows = [r for r in rows if not r.get("is_subtotal")]
    assert_golden("T40", {
        "total_rows": len(rows), "subtotal_rows": len(subtotal_rows), "data_rows": len(data_rows),
        "subtotal_content": [r.get("texts") for r in subtotal_rows],
    }, generate=os.environ.get("GENERATE") == "1")


def test_T41_dedup_same_values():
    text = load_fixture("revit", "R2_title_subtitle.txt")
    result = RevitScheduleParser.parse("test_R2.txt", text)
    rows = result.get("rows", [])
    assert_golden("T41", {
        "total_rows": len(rows),
        "rows_detail": [{"values": r.get("values"), "texts": r.get("texts"),
                          "is_subtotal": r.get("is_subtotal")} for r in rows],
    }, generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    for fn in [test_T39_idempotency, test_T40_dedup_repeated, test_T41_dedup_same_values]:
        print(fn.__name__, fn())