import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, load_json, load_json_fixture, record
from app import TechnicalOfficeEngine, default_settings, chapter_title, fuzzy_match
from app import FehrestBahaParser


def test_T14_mapping_direct_coded():
    """T14 — قرارداد مشترک Python/TypeScript از fixture مشترک tests/char_shared (بدون وابستگی به golden)."""
    import pandas as pd

    fx_path = os.path.join(os.path.dirname(__file__), "..", "char_shared",
                           "fixtures", "mapping", "T14_direct_coded.json")
    fx = load_json(fx_path)

    rows = fx["mapping"]["rows"]
    db = [dict(r) for r in fx["fehrest_db"]]  # پایگاه هرمتیک fixture؛ نه پایگاه تعبیه‌شده
    settings = {**default_settings(), **fx["settings"]}
    engine = TechnicalOfficeEngine(db, settings)
    lines = engine._direct_coded_lines(pd.DataFrame(rows))

    # سازگاری خودِ fixture با قراردادش
    assert fx["mapping"]["recordCount"] == len(rows)
    assert len(fx["expected"]) == fx["meta"]["expected_line_count"]
    assert fx["tolerance"]["rtol"] > 0 and fx["tolerance"]["atol"] > 0

    exclude = set(fx.get("exclude_fields", []))
    aliases = fx.get("field_aliases", {})
    rtol = fx["tolerance"]["rtol"]
    atol = fx["tolerance"]["atol"]

    def value_of(line, field):
        if field == "source_format":  # ویژگی گروه است نه فیلد خط
            return str(line["id"]).rsplit("-", 1)[-1]
        alias = aliases.get(field)  # نام بومی زبان در صورت وجود (پایتون = نام کانونیکال)
        return line[alias] if alias in line else line.get(field)

    actual_by_id = {}
    for line in lines:
        actual_by_id[line["id"]] = {k: v for k, v in line.items() if k not in exclude}

    problems = []
    expected_ids = sorted(e["id"] for e in fx["expected"])
    if sorted(actual_by_id) != expected_ids:
        problems.append(
            f"ID_SET: خط ناخواسته {sorted(set(actual_by_id) - set(expected_ids))} — "
            f"خط تولیدنشده {sorted(set(expected_ids) - set(actual_by_id))}")

    mismatches = []
    for want in fx["expected"]:
        actual = actual_by_id.get(want["id"])
        if actual is None:
            mismatches.append(f"{want['id']}: خط تولید نشد")
            continue
        for field in fx["compare_fields"]:
            if field == "id":
                continue
            w, g = want[field], value_of(actual, field)
            if isinstance(w, bool):
                ok = g is w
            elif isinstance(w, (int, float)):
                ok = (isinstance(g, (int, float)) and not isinstance(g, bool)
                      and abs(g - w) <= atol + rtol * abs(w))
            else:
                ok = g == w
            if not ok:
                mismatches.append(f"{want['id']}.{field}: انتظار {w!r} — دریافت {g!r}")
    problems.extend(mismatches)

    produced_codes = {line["code"] for line in lines}
    forbidden = [f"{n['element_id']} ({n['fehrest_code']!r}) — {n['reason']}"
                 for n in fx["not_expected"] if n["fehrest_code"] in produced_codes]
    problems.extend("NOT_EXPECTED: " + f for f in forbidden)

    by_element = {r["element_id"]: r for r in rows}
    case_failures = []
    for case in fx["cases"]:
        derived = set()
        for element_id in case["rows"]:
            row = by_element.get(element_id)
            if row is None:
                case_failures.append(f"{case['case']}: ردیف {element_id} در fixture نیست")
                continue
            code = str(row.get("fehrest_code", "")).strip()
            derived.add(f"direct-{code}-{row.get('source_format', 'v2')}")
        fix = f" (نیازمند {case['fix']})" if case.get("fix") else ""
        for line_id in case["expect_lines"]:
            if line_id not in actual_by_id:
                case_failures.append(f"[{case['case']}] انتظار خط {line_id} — تولید نشد{fix}")
        for line_id in derived:
            if line_id not in case["expect_lines"] and line_id in actual_by_id:
                case_failures.append(f"[{case['case']}] خط ناخواسته {line_id}{fix}")
    problems.extend(case_failures)

    # تنها اِسِرت نهایی: تمام divergenceها در یک اجرا گزارش می‌شوند
    assert problems == [], "ناهمخوانی با قرارداد T14:\n" + "\n".join(problems)



def test_T20_exact_estimated_zero_override_parity_contract():
    """T20 — بازنویسی قیمتِ یک طرحِ تخمینی با صفرِ صریح: لایهٔ قیمت دستی
    (مرحلهٔ ۵.۵ compute) باید قیمت را صفر کند و ردیف را تأییدشده کند.
    هم‌تراز با قرارداد TS — هر دو زبان روی «lines» assert می‌کنند."""
    db = [{"code": "080102", "chapter": "08", "desc": "بتن با ۱۵۰ کیلوگرم سیمان",
           "unit": "مترمکعب", "price": 17152000, "estimated": True}]
    settings = {**default_settings(), "price_overrides": {"lean": 0}}
    table = {"file_name": "lean.txt", "title": "Lean", "headers": [],
             "kind": "lean_concrete", "kind_conf": 0.97, "col_map": {},
             "warnings": [], "grand_total": {},
             "rows": [{"cells": [], "values": {"volume": 10}, "texts": {},
                       "is_subtotal": False}]}
    res = TechnicalOfficeEngine(db, settings).compute([table], None)
    line = next((l for l in res["lines"] if l["id"] == "lean"), None)

    assert line is not None
    assert line["method"] == "rule-exact"
    assert line["price"] == 0
    assert line["estimated"] is False
    assert line["needs_review"] is False
    assert line["price_status"] == "دستی"


def test_T15_mapping_exact_match():
    data = load_json_fixture("mapping", "parity.json")
    settings = {**default_settings(), **data.get("settings", {})}
    engine = TechnicalOfficeEngine(FehrestBahaParser.embedded(), settings)
    db = FehrestBahaParser.embedded()
    for row in data["mapping"]["rows"][:3]:
        code = row.get("fehrest_code", "")
        if code:
            result = FehrestBahaParser.by_code(db, code)
            if result:
                m = engine._match({"target": result["code"], "query": result["desc"],
                                   "unit": result["unit"], "price": result["price"],
                                   "fallback_price": result["price"], "id": "test"})
                m["input_code"] = code
                m["row_desc"] = result["desc"]
                assert_golden("T15", m, generate=os.environ.get("GENERATE") == "1")
                return
    assert_golden("T15", {"status": "no_valid_rows"}, generate=os.environ.get("GENERATE") == "1")


def test_T16_mapping_fuzzy():
    data = load_json_fixture("mapping", "parity.json")
    db = FehrestBahaParser.embedded()
    results = []
    for row in data["mapping"]["rows"][:3]:
        code = row.get("fehrest_code", "")
        if code:
            candidates = FehrestBahaParser.search(db, f"ردیف {code}", top=3, min_score=0.3)
            results.append({"code": code, "candidates": [(candidate["code"], score)
                                                             for candidate, score in candidates]})
    assert_golden("T16", {"results": results}, generate=os.environ.get("GENERATE") == "1")


def test_T17_mapping_estimated():
    data = load_json_fixture("mapping", "parity.json")
    db = FehrestBahaParser.embedded()
    results = []
    for row in data["fehrest_db"]:
        results.append({
            "code": row["code"],
            "estimated": row.get("estimated", False),
            "price": row["price"],
        })
    assert_golden("T17", {"estimated_flags": results}, generate=os.environ.get("GENERATE") == "1")


def test_T18_mapping_no_match():
    db = FehrestBahaParser.embedded()
    result = fuzzy_match("zzz_no_match_12345", [r["desc"] for r in db], threshold=0.6)
    assert_golden("T18", {"query": "zzz_no_match_12345", "result": result},
                  generate=os.environ.get("GENERATE") == "1")


def test_T19_mapping_manual_override():
    db = FehrestBahaParser.embedded()
    settings = default_settings()
    settings["manual_codes"] = {"test-plan": "080201"}
    engine = TechnicalOfficeEngine(db, settings)
    m = engine._match({"target": "080201", "query": "test", "unit": "m3",
                        "price": 5000000, "fallback_price": 5000000, "id": "test"})
    assert_golden("T19", m, generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    for fn in [test_T14_mapping_direct_coded, test_T15_mapping_exact_match,
               test_T16_mapping_fuzzy, test_T17_mapping_estimated,
               test_T18_mapping_no_match, test_T19_mapping_manual_override]:
        print(fn.__name__, fn())