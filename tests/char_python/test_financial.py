import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, record
from app import TechnicalOfficeEngine, default_settings, FehrestBahaParser, chapter_title, rebar_unit_weight, money_to_words


def test_T31_grand_total_rebalancing():
    db = FehrestBahaParser.embedded()
    settings = default_settings()
    engine = TechnicalOfficeEngine(db, settings)
    tables = []
    try:
        result = engine.compute(tables, None)
    except Exception as e:
        result = {"error": str(e)}
    assert_golden("T31", {"has_rebalancing": "grand_total" in result if isinstance(result, dict) else False,
                           "keys": list(result.keys()) if isinstance(result, dict) else [],
                           "result": result},
                  generate=os.environ.get("GENERATE") == "1")


def test_T42_rebar_weight_table():
    weights = {d: rebar_unit_weight(d) for d in [8, 14, 25, 36]}
    assert_golden("T42", {"weights": weights}, generate=os.environ.get("GENERATE") == "1")


def test_T43_chapter_titles():
    chapters = ["01", "06", "07", "08", "10", "28", "99"]
    titles = {c: chapter_title(c) for c in chapters}
    assert_golden("T43", {"chapters": titles}, generate=os.environ.get("GENERATE") == "1")


def test_T44_money_to_words():
    amounts = [0, 1000, 12345678, -5000, 1000000000]
    results = {}
    for a in amounts:
        results[str(a)] = money_to_words(a)
    assert_golden("T44", {"amounts": results}, generate=os.environ.get("GENERATE") == "1")


def test_T45_technical_office_engine():
    db = FehrestBahaParser.embedded()
    settings = default_settings()
    engine = TechnicalOfficeEngine(db, settings)
    assert_golden("T45", {"engine_type": type(engine).__name__,
                           "has_compute": hasattr(engine, "compute"),
                           "has_db": engine.db is not None,
                           "db_count": len(engine.db) if engine.db else 0},
                  generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    for fn in [test_T31_grand_total_rebalancing, test_T42_rebar_weight_table,
               test_T43_chapter_titles, test_T44_money_to_words, test_T45_technical_office_engine]:
        print(fn.__name__, fn())