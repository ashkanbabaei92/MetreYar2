# -*- coding: utf-8 -*-
# T82 — لایهٔ شاخص تعدیل: دورهٔ هدف = دورهٔ مبنا (مرحلهٔ ۱۱ بخش ۵).
#
# کلیات فهرست‌بهای ۱۴۰۴ بند ۲۲: ضریب تعدیل هر فصل = I(دورهٔ هدف) ÷
# I(دورهٔ مبنا) روی مبلغ ردیف، قبل از ضرایب زنجیرهٔ مالی. اگر دورهٔ هدف
# برابر دورهٔ مبنا باشد ضریب همهٔ فصل‌ها ۱ است و خروجی bit-identical با
# حالت بدون شاخص می‌ماند — همین رفتار آزمون می‌شود.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, IndexTable, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


def _pipeline(settings):
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
    map_df = DynamoMappingParser.merge_formats(results)
    return TechnicalOfficeEngine(_default_fehrest_db(), settings).compute(tables, map_df)


def test_T82_canonical_table_is_base_period_all_ones():
    """فایل indices/abnieh.json: دورهٔ مبنا ۱۴۰۳Q4، همهٔ فصل‌ها قطعی و ۱٫۰."""
    it = IndexTable.load()
    assert it.base_period == "1403Q4"
    assert it.periods == ["1403Q4"]
    chapters = {r["chapter"] for r in it.records}
    assert len(chapters) >= 28
    for r in it.records:
        assert r["kind"] == "قطعی"
        assert r["value"] == pytest.approx(1.0)
        assert r["source"]  # هر رکورد منبع بخشنامه دارد
    # ضریب هر کد در دورهٔ مبنا = ۱
    for code in ("080106", "070202", "100305", "060501", "280101", "080102"):
        assert it.factor(code, "1403Q4") == 1.0


def test_T82_default_target_is_base_period():
    """پیش‌فرض index_target_period=None → دورهٔ مبنا → همهٔ ضرایب ۱."""
    r = _pipeline(default_settings())
    assert default_settings()["index_target_period"] is None
    for l in r["lines"]:
        assert l["index_factor"] == pytest.approx(1.0)
        assert l["total_indexed"] == pytest.approx(l["total"], rel=1e-12)
    assert r["index"] is None  # گزارش شاخص فقط هنگام تعدیل واقعی تولید می‌شود
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


def test_T82_explicit_base_period_is_bit_identical():
    """تعیین صریح دورهٔ مبنا به‌عنوان هدف → همان خروجی دقیق."""
    r_implicit = _pipeline(default_settings())
    r_explicit = _pipeline(dict(default_settings(), index_target_period="1403Q4"))
    assert len(r_explicit["lines"]) == len(r_implicit["lines"])
    for a, b in zip(r_implicit["lines"], r_explicit["lines"]):
        assert a["code"] == b["code"]
        assert b["index_factor"] == pytest.approx(1.0)
        assert b["total_indexed"] == pytest.approx(a["total_indexed"], rel=1e-12)
    assert r_explicit["base_total"] == pytest.approx(r_implicit["base_total"], abs=1e-6)
    assert r_explicit["grand_total"] == pytest.approx(r_implicit["grand_total"], abs=1e-6)


def test_T82_empty_table_is_a_noop():
    """جدول خالی (بدون دورهٔ مبنا) → هیچ تعدیلی؛ ضریب ۱ برای هر کد."""
    it = IndexTable.empty()
    assert it.base_period is None
    assert it.factor("080106", "anything") == 1.0
    r = TechnicalOfficeEngine(_default_fehrest_db(), default_settings(),
                              index_table=IndexTable.empty()).compute([], None)
    assert r["index"] is None
