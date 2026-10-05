# -*- coding: utf-8 -*-
# T85 — شاخص تعدیل: فصل مفقود → خطای صریح (مرحلهٔ ۱۱ بخش ۵).
#
# اگر برای دورهٔ هدف شاخص یکی از فصل‌ها در indices/abnieh.json موجود
# نباشد، موتور باید با یک پیام خطای روشن متوقف شود — نه آنکه ساکت
# ضریب ۱ فرض کند (تعدیل پنهان می‌شود) و نه آنکه عددی از حافظه بسازد.
import os
import sys

import pytest

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


def _table_missing_chapter(missing):
    """دورهٔ هدف که شاخص همهٔ فصل‌ها را دارد به‌جز «missing»."""
    base = IndexTable.load()
    target_recs = [dict(r, period=TARGET) for r in base.records
                   if r["chapter"] != missing]
    return IndexTable({
        "base_period": base.base_period,
        "periods": base.periods + [TARGET],
        "indices": list(base.records) + target_recs,
    })


def test_T85_missing_chapter_raises_on_factor():
    it = _table_missing_chapter("08")
    with pytest.raises(ValueError, match="فصل 08"):
        it.factor("080106", TARGET)
    with pytest.raises(ValueError):
        it.factor("080105", TARGET)


def test_T85_engine_stops_on_missing_chapter():
    """خطای شاخص مفقود قبل از هر خروجی ناقص پرتاب می‌شود."""
    tables, map_df = _tables_and_map()
    it = _table_missing_chapter("08")
    with pytest.raises(ValueError, match="شاخص"):
        TechnicalOfficeEngine(_default_fehrest_db(),
                              dict(default_settings(), index_target_period=TARGET),
                              index_table=it).compute(tables, map_df)


def test_T85_report_marks_missing_chapter_as_null():
    """گزارش، فصل مفقود را با ضریب None نشان می‌دهد (نه ۱)."""
    it = _table_missing_chapter("10")
    rep = it.report(TARGET)
    row10 = next(row for row in rep["chapters"] if row["chapter"] == "10")
    assert row10["factor"] is None
    row08 = next(row for row in rep["chapters"] if row["chapter"] == "08")
    assert row08["factor"] == pytest.approx(1.0)


def test_T85_zero_base_level_raises():
    """شاخص دورهٔ مبنا صفر → خطای صریح (تقسیم بر صفر ممنوع)."""
    it = IndexTable({
        "base_period": "1403Q4",
        "periods": ["1403Q4", "1404Q1"],
        "indices": [{"period": "1403Q4", "chapter": "08", "value": 0.0,
                     "kind": "قطعی", "source": "s"},
                    {"period": "1404Q1", "chapter": "08", "value": 1.5,
                     "kind": "قطعی", "source": "s"}],
    })
    with pytest.raises(ValueError):
        it.factor("080106", "1404Q1")
