#!/usr/bin/env python3
"""MetreYar2 Characterization Runner - Python
Reads real data from data/ and generates Golden Masters.
Usage: GENERATE=1 python tests/char_python/run_characterization.py (generate/update)
       python tests/char_python/run_characterization.py (compare; exit code 1 on any diff/missing)
"""

import os
import sys
import json
import csv
import io
import re
import difflib
import hashlib
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
GENERATE = os.environ.get("GENERATE") == "1"

from app import (
    RevitScheduleParser, parse_value_unit, to_si, convert_persian_digits,
    normalize_text, fuzzy_match, conf_label, rebar_unit_weight, chapter_title,
    money_to_words, number_to_persian_words, TechnicalOfficeEngine,
    FehrestBahaParser, default_settings, to_si as to_si_fn,
)

RESULTS = {}


def sanitize_id(test_id):
    return re.sub(r'[^\w\-.]', '_', test_id)


def stable_slug(name):
    """برگهٔ پایدار و بدون برخورد از یک نام فایل:
    نام کاملِ sanitize‌شده + هش کوتاهِ نام کامل.
    • برای فایل‌های متفاوت همیشه متفاوت است (هش نام کامل).
    • برای اجرای مجددِ یک فایل همیشه یکسان است.
    • مستقل از ترتیب اجرای تست‌ها (فقط به نام فایل وابسته است)."""
    base = sanitize_id(str(name).strip())
    digest = hashlib.sha1(str(name).strip().encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}"


def record(test_id, data, category="general"):
    """ثبت نتیجهٔ یک تست در Golden Master.
    • حالت GENERATE (صریح): golden را می‌سازد یا به‌روزرسانی می‌کند.
    • حالت compare: golden موجود + اختلاف → شکست؛ golden گمشده → شکست.
      در حالت compare هیچ‌گاه golden جدیدی ساخته نمی‌شود."""
    test_id = sanitize_id(test_id)
    key = f"{category}/{test_id}"
    gp = os.path.join(GOLDEN_DIR, f"{test_id}.json")

    if GENERATE:
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(gp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        result = {"status": "golden_created", "test_id": test_id, "category": category}
        RESULTS[key] = result
        return result

    if not os.path.exists(gp):
        result = {"status": "missing_golden", "test_id": test_id, "category": category}
        RESULTS[key] = result
        return result

    try:
        with open(gp, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except Exception as e:
        result = {"status": "error", "test_id": test_id, "category": category, "error": str(e)}
        RESULTS[key] = result
        return result

    # مقایسهٔ بر اساس معنای JSON: golden پس از round-trip ذخیره شده است
    # (tupleها در golden به list تبدیل می‌شوند)، پس actual را هم با همان
    # round-trip نرمال می‌کنیم تا false-positive نگیریم.
    normalized = json.loads(json.dumps(data, ensure_ascii=False, default=str))
    if existing != normalized:
        result = {
            "status": "diff",
            "test_id": test_id,
            "category": category,
            "golden": existing,
            "actual": data,
        }
        RESULTS[key] = result
        return result

    result = {"status": "pass", "test_id": test_id, "category": category}
    RESULTS[key] = result
    return result


def load_revit_files():
    revit_dir = os.path.join(DATA_DIR, "export revit")
    files = []
    for f in sorted(os.listdir(revit_dir)):
        if f.endswith(".txt"):
            path = os.path.join(revit_dir, f)
            with open(path, "r", encoding="utf-8") as fh:
                files.append((f, fh.read()))
    return files


def load_dynamo_files():
    dyn_dir = os.path.join(DATA_DIR, "dynamo")
    files = []
    for root, dirs, fnames in os.walk(dyn_dir):
        for f in sorted(fnames):
            if f.endswith(".txt"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    files.append((os.path.relpath(path, DATA_DIR), fh.read()))
    return files


def load_fehrest_file():
    fehrest_dir = os.path.join(DATA_DIR, "fehrest baha 1404")
    for f in sorted(os.listdir(fehrest_dir)):
        if f.endswith(".txt"):
            path = os.path.join(fehrest_dir, f)
            with open(path, "r", encoding="utf-8") as fh:
                return (f, fh.read())
    return None


# ── C1: Revit Parse (T01-T10) ──

def run_revit_parse():
    files = load_revit_files()
    for i, (name, text) in enumerate(files):
        # شناسهٔ پایدار و بدون برخورد: نام کامل + هش (به‌جای برش ۲۰ کاراکتری)
        test_id = f"T01_R{stable_slug(name)}"
        try:
            result = RevitScheduleParser.parse(name, text)
            record(test_id, {
                "file": name,
                "title": result.get("title"),
                "kind": result.get("kind"),
                "kind_conf": result.get("kind_conf"),
                "headers": result.get("headers", []),
                "rows_count": len(result.get("rows", [])),
                "subtotal_count": sum(1 for r in result.get("rows", []) if r.get("is_subtotal")),
                "grand_total_keys": list(result.get("grand_total", {}).keys()),
                "warnings": result.get("warnings", []),
                "col_map": result.get("col_map", {}),
            }, "revit_parse")
        except Exception as e:
            record(test_id, {"error": str(e), "file": name}, "revit_parse")


# ── C2: Number Parse (T11-T18) ──

def run_number_parse():
    revit_files = load_revit_files()
    test_num = 0
    for fname, text in revit_files:
        for line in text.split("\n"):
            cells = re.findall(r'"([^"]*)"', line)
            for cell in cells:
                parsed = parse_value_unit(cell)
                if parsed and parsed[0] is not None:
                    test_num += 1
                    if test_num > 20:
                        return
                    test_id = f"T11_num{test_num}"
                    si = to_si(parsed[0], parsed[1]) if parsed else None
                    record(test_id, {
                        "input": cell, "file": fname,
                        "parse": {"value": parsed[0], "unit": parsed[1]},
                        "si": si,
                    }, "number_parse")


# ── C3: Mapping (T19-T24) ──

def run_mapping():
    dyn_files = load_dynamo_files()
    for fname, text in dyn_files[:2]:
        test_id = f"T19_map_{fname[:20]}"
        try:
            import pandas as pd
            df = pd.read_csv(io.StringIO(text), sep="\t", dtype=str, on_bad_lines="skip")
            settings = default_settings()
            db = FehrestBahaParser.embedded()
            engine = TechnicalOfficeEngine(db, settings)
            direct_lines = engine._direct_coded_lines(df)
            record(test_id, {
                "file": fname,
                "df_rows": len(df),
                "df_columns": list(df.columns)[:20],
                "direct_coded_lines": len(direct_lines),
                "has_fehrest_code": "fehrest_code" in df.columns if "fehrest_code" in df.columns else False,
            }, "mapping")
        except Exception as e:
            record(test_id, {"error": str(e), "file": fname}, "mapping")


# ── C4: Rebar Weight (T25-T28) ──

def run_rebar():
    diameters = [6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36]
    for d in diameters:
        test_id = f"T25_phi{d}"
        record(test_id, {
            "diameter": d, "weight": rebar_unit_weight(d),
            "source": "REBAR_UNIT_WEIGHT table",
        }, "rebar")


# ── C5: Normalize (T29-T35) ──

def run_normalize():
    samples = []
    for fname, text in load_revit_files():
        for line in text.split("\n"):
            for token in re.findall(r'[\u0600-\u06FF\u0660-\u0669]+', line):
                samples.append(token)
                if len(samples) >= 15:
                    break
            if len(samples) >= 15:
                break
        if len(samples) >= 15:
            break

    for i, s in enumerate(samples):
        test_id = f"T29_norm_{i+1}"
        record(test_id, {
            "input": s,
            "to_en_digits": convert_persian_digits(s),
            "normalized": normalize_text(s),
        }, "normalize")


# ── C6: Fuzzy (T36-T39) ──

def run_fuzzy():
    db = FehrestBahaParser.embedded()
    queries = []
    for row in db[:10]:
        queries.append(row["desc"])
    for i, q in enumerate(queries[:6]):
        test_id = f"T36_fz_{i+1}"
        result = fuzzy_match(q[:50], [r["desc"] for r in db[:20]], threshold=0.3)
        record(test_id, {
            "query": q[:80],
            "best_match": result[0][:80] if result[0] else None,
            "score": round(result[1], 4) if result[1] else 0,
            "all_candidates": len(result[2]),
        }, "fuzzy")


# ── C7: Excel Export (T40-T42) ──

def run_excel():
    test_id = "T40_excel"
    try:
        from app import ExcelExporter
        exporter = ExcelExporter()
        record(test_id, {
            "exporter_type": type(exporter).__name__,
            "has_export": hasattr(exporter, "export"),
            "has_formats": hasattr(exporter, "_formats"),
        }, "excel")
    except Exception as e:
        record(test_id, {"error": str(e)}, "excel")


# ── C8: Financial Engine (T43-T48) ──

def run_financial():
    test_id = "T43_financial"
    try:
        settings = default_settings()
        engine = TechnicalOfficeEngine(FehrestBahaParser.embedded(), settings)
        revit_files = load_revit_files()
        tables = []
        for fname, text in revit_files[:3]:
            parsed = RevitScheduleParser.parse(fname, text)
            tables.append(parsed)
        result = engine.compute(tables, None)
        record(test_id, {
            "tables_parsed": len(tables),
            "has_result": result is not None,
            "keys": list(result.keys()) if isinstance(result, dict) else [],
            "lines_count": len(result.get("lines", [])) if isinstance(result, dict) else 0,
            "base_total": result.get("base_total", 0) if isinstance(result, dict) else 0,
            "grand_total": result.get("grand_total", 0) if isinstance(result, dict) else 0,
        }, "financial")
    except Exception as e:
        record(test_id, {"error": str(e), "type": type(e).__name__}, "financial")


# ── C9: Utility (T49-T52) ──

def run_utility():
    test_id = "T49_chapter_titles"
    chapters = ["01", "06", "07", "08", "10", "28", "99", "41"]
    record(test_id, {ch: chapter_title(ch) for ch in chapters}, "utility")

    test_id = "T50_money_words"
    amounts = [0, 1000, 500000, 12345678]
    record(test_id, {str(a): money_to_words(a) for a in amounts}, "utility")

    test_id = "T51_idempotency"
    revit_files = load_revit_files()
    if revit_files:
        fname, text = revit_files[0]
        r1 = RevitScheduleParser.parse(fname, text)
        r2 = RevitScheduleParser.parse(fname, text)
        record(test_id, {
            "identical_kind": r1.get("kind") == r2.get("kind"),
            "identical_headers": r1.get("headers") == r2.get("headers"),
            "rows_match": len(r1.get("rows", [])) == len(r2.get("rows", [])),
        }, "utility")

    test_id = "T52_fehrest_db"
    db = FehrestBahaParser.embedded()
    record(test_id, {
        "total_rows": len(db),
        "estimated_count": sum(1 for r in db if r.get("estimated")),
        "verified_count": sum(1 for r in db if not r.get("estimated")),
        "codes": [r["code"] for r in db[:10]],
    }, "utility")


def main():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    run_revit_parse()
    run_number_parse()
    run_mapping()
    run_rebar()
    run_normalize()
    run_fuzzy()
    run_excel()
    run_financial()
    run_utility()

    # Summary
    total = len(RESULTS)
    by_cat = {}
    for k in RESULTS:
        cat = k.split("/")[0]
        by_cat[cat] = by_cat.get(cat, 0) + 1

    print(f"\n=== Characterization Complete ===")
    print(f"Total tests: {total}")
    for cat, count in sorted(by_cat.items()):
        print(f"  {cat}: {count}")
    print(f"Golden Master dir: {GOLDEN_DIR}")
    print(f"Generate mode: {GENERATE}")

    if GENERATE:
        return

    # حالت compare: شکست‌ها را گزارش می‌کنیم و با کد خروجی غیرصفر پایان می‌دهیم.
    # (پس از این، drift در خروجی parser/engine دیگر سایلنت نادیده گرفته نمی‌شود.)
    fail_statuses = ("diff", "missing_golden", "error")
    failures = [v for v in RESULTS.values() if v.get("status") in fail_statuses]
    for v in failures:
        print(f"  FAIL [{v['status']}] {v['category']}/{v['test_id']}")
    print(f"Passed: {total - len(failures)}/{total}")
    for s in fail_statuses:
        n = sum(1 for v in failures if v["status"] == s)
        if n:
            print(f"  {s}: {n}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
