#!/usr/bin/env python3
"""Cross-platform parity diff: compare Python vs TypeScript JSON outputs."""

import json
import os
import sys

TOLERANCE = 0.001
EXCLUDE_FIELDS = {"id"}


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def diff(a, b, path="", report=None):
    if report is None:
        report = []
    if type(a) != type(b):
        report.append({"path": path, "type_mismatch": True,
                        "python_type": type(a).__name__, "ts_type": type(b).__name__})
        return report
    if isinstance(a, dict):
        all_keys = set(list(a.keys()) + list(b.keys()))
        for k in sorted(all_keys):
            p = f"{path}.{k}" if path else k
            if k in EXCLUDE_FIELDS:
                continue
            if k not in a:
                report.append({"path": p, "status": "missing_in_python"})
            elif k not in b:
                report.append({"path": p, "status": "missing_in_typescript"})
            else:
                diff(a[k], b[k], p, report)
    elif isinstance(a, list):
        if len(a) != len(b):
            report.append({"path": path, "list_length_mismatch": True,
                             "python_len": len(a), "ts_len": len(b)})
        for i, (ai, bi) in enumerate(zip(a, b)):
            diff(ai, bi, f"{path}[{i}]", report)
    elif isinstance(a, float):
        delta = abs(a - b)
        if delta > TOLERANCE:
            report.append({"path": path, "float_diff": True,
                             "python": a, "typescript": b, "delta": delta})
    elif a != b:
        report.append({"path": path, "value_diff": True,
                         "python": a, "typescript": b})
    return report


def compare(test_id, py_dir, ts_dir):
    py_file = os.path.join(py_dir, f"{test_id}.json")
    ts_file = os.path.join(ts_dir, f"{test_id}.json")
    if not os.path.exists(py_file):
        return [{"test_id": test_id, "error": f"missing: {py_file}"}]
    if not os.path.exists(ts_file):
        return [{"test_id": test_id, "error": f"missing: {ts_file}"}]
    py_data = load_json(py_file)
    ts_data = load_json(ts_file)
    report = diff(py_data, ts_data)
    return [{"test_id": test_id, "differences": report,
              "pass": len(report) == 0}]


def main():
    py_dir = os.path.join(os.path.dirname(__file__), "char_python", "output")
    ts_dir = os.path.join(os.path.dirname(__file__), "char_ts", "output")
    if not os.path.exists(py_dir):
        print(f"Python output dir not found: {py_dir}")
        sys.exit(1)
    if not os.path.exists(ts_dir):
        print(f"TypeScript output dir not found: {ts_dir}")
        sys.exit(1)
    results = []
    for f in sorted(os.listdir(py_dir)):
        if f.endswith(".json"):
            test_id = f.replace(".json", "")
            results.extend(compare(test_id, py_dir, ts_dir))
    diffs = [r for r in results if r.get("differences")]
    print(f"Total: {len(results)}, Differences: {len(diffs)}")
    for r in diffs:
        print(f"  {r['test_id']}: {len(r.get('differences', []))} diffs")
        for d in r.get("differences", [])[:3]:
            print(f"    {d}")


if __name__ == "__main__":
    main()