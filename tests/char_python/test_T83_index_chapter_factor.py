# -*- coding: utf-8 -*-
# T83 — شاخص تعدیل: ضریب فصل فقط روی همان فصل اثر می‌گذارد (بخش ۵).
#
# ضریب = I(هدف) ÷ I(مبنا) بر اساس دو رقم اول کد فهرست‌بها. اگر فقط فصل ۰۷
# شاخش ۳ برابر شود، فقط ردیف‌های 07xxxx ×۳ می‌شوند و بقیه دست‌نخورده
# می‌مانند. زنجیرهٔ مالی بعد از لایهٔ شاخص اعمال می‌شود.
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, IndexTable, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

TARGET = "1404Q1"


def _tables_and_map():
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    return tables, DynamoMappingParser.merge_formats(results)


def _table_with_ch07_tripled():
    """جدول شاخص: دورهٔ مبنا ۱۴۰۳Q4 (همه ۱٫۰) + دورهٔ هدف با فصل ۰۷ = ۳٫۰."""
    base = IndexTable.load()
    target_recs = []
    for r in base.records:
        nr = dict(r)
        nr["period"] = TARGET
        if r["chapter"] == "07":
            nr["value"] = 3.0
        target_recs.append(nr)
    return IndexTable({
        "base_period": base.base_period,
        "periods": base.periods + [TARGET],
        "indices": list(base.records) + target_recs,
    })


def test_T83_only_chapter_07_lines_are_tripled():
    it = _table_with_ch07_tripled()
    tables, map_df = _tables_and_map()
    r0 = TechnicalOfficeEngine(_default_fehrest_db(), default_settings(),
                               index_table=it).compute(tables, map_df)
    r1 = TechnicalOfficeEngine(_default_fehrest_db(),
                               dict(default_settings(), index_target_period=TARGET),
                               index_table=it).compute(tables, map_df)

    ch07 = [l for l in r0["lines"] if l["code"].startswith("07")]
    other = [l for l in r0["lines"] if not l["code"].startswith("07")]
    assert len(ch07) >= 1  # پروژهٔ نمونه ۴ ردیف 07xxxx دارد
    for l in r1["lines"]:
        if l["code"].startswith("07"):
            assert l["index_factor"] == pytest.approx(3.0)
        else:
            assert l["index_factor"] == pytest.approx(1.0)

    delta = sum(l["total"] for l in ch07)
    assert r1["base_total"] == pytest.approx(r0["base_total"] + 2 * delta, abs=1.0)
    # زنجیرهٔ مالی بعد از شاخص: grand = base جدید × ۱٫۳ × ۱٫۰۴ (ایراد ۴)
    assert r1["grand_total"] == pytest.approx(r1["base_total"] * 1.3 * 1.04, abs=1.0)
    # ردیف‌های غیر-۰۷ تغییر نکرده‌اند (کلید شناسهٔ ردیف: پی و پله هر دو ۰۸۰۱۰۵)
    by_id = {l["id"]: l["total"] for l in r1["lines"]}
    for l in other:
        assert by_id[l["id"]] == pytest.approx(l["total"], rel=1e-9)


def test_T83_report_lists_per_chapter_factors():
    it = _table_with_ch07_tripled()
    tables, map_df = _tables_and_map()
    r = TechnicalOfficeEngine(_default_fehrest_db(),
                              dict(default_settings(), index_target_period=TARGET),
                              index_table=it).compute(tables, map_df)
    rep = r["index"]
    assert rep is not None
    assert rep["base_period"] == "1403Q4"
    assert rep["target_period"] == TARGET
    assert rep["provisional"] is False
    factors = {row["chapter"]: row["factor"] for row in rep["chapters"]}
    assert factors["07"] == pytest.approx(3.0)
    for ch, f in factors.items():
        if ch != "07":
            assert f == pytest.approx(1.0)
    # هر سطر منبع و نوع شاخص را دارد
    for row in rep["chapters"]:
        assert row["kind"] == "قطعی"
        assert row["source"]
