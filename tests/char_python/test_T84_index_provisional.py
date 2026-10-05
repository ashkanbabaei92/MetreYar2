# -*- coding: utf-8 -*-
# T84 — شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل (مرحلهٔ ۱۱ بخش ۵).
#
# رکورد موقت مقدارش یک «ضریب» نسبت به آخرین شاخص قطعیِ قبل از آن دوره
# است: I(موقت) = value × I(قطعی دورهٔ قبل). ضریب تعدیل = I(هدف) ÷ I(مبنا).
# گزارش، شاخص موقت را با پرچم provisional و برچسب «موقت» نشان می‌دهد.
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


def _table_with_provisional_07(factor):
    """دورهٔ هدف: فصل ۰۷ موقت با ضریب داده‌شده، بقیه قطعی ۱٫۰."""
    base = IndexTable.load()
    target_recs = []
    for r in base.records:
        nr = dict(r)
        nr["period"] = TARGET
        if r["chapter"] == "07":
            nr["kind"] = "موقت"
            nr["value"] = factor
            nr["source"] = "بخشنامهٔ موقت آزمایشی — شماره ۹۹/۹۹۹۹۹"
        target_recs.append(nr)
    return IndexTable({
        "base_period": base.base_period,
        "periods": base.periods + [TARGET],
        "indices": list(base.records) + target_recs,
    })


def test_T84_provisional_multiplies_previous_definitive():
    """موقت ۱٫۵ روی قطعی ۳٫۰ → مستوى ۴٫۵ → ضریب ۴٫۵ برای فصل ۰۷."""
    # جدول با فصل ۰۷ قطعی ۳٫۰ در دورهٔ میانی و موقت ۱٫۵ در دورهٔ هدف
    base = IndexTable.load()
    mid, target = "1404Q1", "1404Q2"
    recs = list(base.records)  # 1403Q4 همه ۱٫۰
    for r in base.records:  # دورهٔ میانی: فصل ۰۷ قطعی ۳٫۰
        nr = dict(r, period=mid)
        if r["chapter"] == "07":
            nr["value"] = 3.0
        recs.append(nr)
    for r in base.records:  # دورهٔ هدف: فصل ۰۷ موقت ۱٫۵
        nr = dict(r, period=target, kind="موقت", source="بخشنامهٔ موقت آزمایشی")
        if r["chapter"] == "07":
            nr["value"] = 1.5
        recs.append(nr)
    it = IndexTable({"base_period": base.base_period,
                     "periods": base.periods + [mid, target], "indices": recs})
    assert it._level(target, "07") == pytest.approx(4.5)
    assert it.factor("070202", target) == pytest.approx(4.5)
    # سایر فصل‌ها: موقت ۱٫۰ × قطعی ۱٫۰ = ۱٫۰
    assert it.factor("080106", target) == pytest.approx(1.0)
    assert it.factor("100305", target) == pytest.approx(1.0)


def test_T84_engine_marks_provisional_report():
    it = _table_with_provisional_07(1.5)
    tables, map_df = _tables_and_map()
    r = TechnicalOfficeEngine(_default_fehrest_db(),
                              dict(default_settings(), index_target_period=TARGET),
                              index_table=it).compute(tables, map_df)
    rep = r["index"]
    assert rep is not None
    assert rep["provisional"] is True
    kinds = {row["chapter"]: row["kind"] for row in rep["chapters"]}
    assert kinds["07"] == "موقت"
    # فصل ۰۷ موقت ۱٫۵ × قطعی ۱٫۰ = ۱٫۵
    factors = {row["chapter"]: row["factor"] for row in rep["chapters"]}
    assert factors["07"] == pytest.approx(1.5)
    for ch, f in factors.items():
        if ch != "07":
            assert f == pytest.approx(1.0)
    for l in r["lines"]:
        if l["code"].startswith("07"):
            assert l["index_factor"] == pytest.approx(1.5)
        else:
            assert l["index_factor"] == pytest.approx(1.0)
    # منبع بخشنامه در گزارش هست
    row07 = next(row for row in rep["chapters"] if row["chapter"] == "07")
    assert row07["source"]


def test_T84_provisional_needs_a_previous_definitive():
    """شاخص موقت بدون شاخص قطعیِ دورهٔ قبل → خطای صریح."""
    it = IndexTable({
        "base_period": "1403Q4",
        "periods": ["1403Q4", "1404Q1"],
        "indices": [{"period": "1403Q4", "chapter": "08", "value": 1.0,
                     "kind": "موقت", "source": "s"},  # مبنا هم موقت!
                    {"period": "1404Q1", "chapter": "08", "value": 1.5,
                     "kind": "موقت", "source": "s"}],
    })
    with pytest.raises(ValueError):
        it.factor("080106", "1404Q1")
