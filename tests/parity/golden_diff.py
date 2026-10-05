#!/usr/bin/env python3
"""Golden master diff: compare old golden master vs new for regression detection."""

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
        report.append({"path": path, "type_changed": True,
                        "old_type": type(a).__name__, "new_type": type(b).__name__})
        return report
    if isinstance(a, dict):
        all_keys = set(list(a.keys()) + list(b.keys()))
        for k in sorted(all_keys):
            p = f"{path}.{k}" if path else k
            if k in EXCLUDE_FIELDS:
                continue
            if k not in a:
                report.append({"path": p, "added_in_new": True})
            elif k not in b:
                report.append({"path": p, "removed_in_new": True})
            else:
                diff(a[k], b[k], p, report)
    elif isinstance(a, list):
        if len(a) != len(b):
            report.append({"path": path, "list_length_changed": True,
                             "old_len": len(a), "new_len": len(b)})
        for i, (ai, bi) in enumerate(zip(a, b)):
            diff(ai, bi, f"{path}[{i}]", report)
    elif isinstance(a, float):
        delta = abs(a - b)
        if delta > TOLERANCE:
            report.append({"path": path, "value_changed": True,
                             "old": a, "new": b, "delta": delta})
    elif a != b:
        report.append({"path": path, "value_changed": True,
                         "old": a, "new": b})
    return report


def main():
    old_dir = sys.argv[1] if len(sys.argv) > 1 else "golden"
    new_dir = sys.argv[2] if len(sys.argv) > 2 else "golden_new"
    base = os.path.dirname(__file__)
    if not os.path.isabs(old_dir):
        old_dir = os.path.join(base, old_dir)
    if not os.path.isabs(new_dir):
        new_dir = os.path.join(base, new_dir)
    if not os.path.exists(old_dir):
        print(f"Old golden dir not found: {old_dir}")
        sys.exit(1)
    if not os.path.exists(new_dir):
        print(f"New golden dir not found: {new_dir}")
        sys.exit(1)
    results = []
    for f in sorted(os.listdir(old_dir)):
        if f.endswith(".json"):
            test_id = f.replace(".json", "")
            old_file = os.path.join(old_dir, f)
            new_file = os.path.join(new_dir, f)
            if not os.path.exists(new_file):
                results.append({"test_id": test_id, "status": "removed"})
                continue
            old_data = load_json(old_file)
            new_data = load_json(new_file)
            report = diff(old_data, new_data)
            results.append({"test_id": test_id, "regressions": len(report),
                              "changed": report})
    regressions = [r for r in results if r.get("regressions", 0) > 0]
    print(f"Total: {len(results)}, Regressions: {len(regressions)}")
    for r in regressions:
        print(f"  {r['test_id']}: {r['regressions']} changes")
        for c in r.get("changed", [])[:5]:
            print(f"    {c}")


if __name__ == "__main__":
    main()