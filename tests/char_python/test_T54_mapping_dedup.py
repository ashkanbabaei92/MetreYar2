# -*- coding: utf-8 -*-
# T54 — رفع دوباره‌شماری آرماتور Mapping v1 که زیرمجموعهٔ Revit Schedule ها است.
#
# پیشینه: وقتی ۱۰ فایل واقعی Revit + هر دو خروجی داینامو با هم به engine داده
# می‌شدند، آرماتورهای Mapping v1 (۱,۹۱۰ kg) دوباره به سینی‌های فصل ۰۷ اضافه
# می‌شدند در حالی که همان میلگردها از قبل در Revit Schedule شمرده شده بودند
# (۱۷ مارک مشترک / ۱,۸۱۶ kg همپوشانی). نتیجه: +۷.۲٪ تورم baseTotal.
#
# Fix (app.py: _extract_rebar): مجموعهٔ revit_marks از مارک‌های آرماتور Revit
# ساخته می‌شود و ردیف‌های v1 که مارکشان در آن مجموعه است skip می‌شوند
# (Revit precedence). فقط میلگردهایی که در Revit نیستند اضافه می‌شوند.

import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (
    DynamoMappingParser,
    FehrestBahaParser,
    RevitScheduleParser,
    TechnicalOfficeEngine,
    default_settings,
    _default_fehrest_db,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


def _load_revit_tables():
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8") as fh:
            text = fh.read()
        tables.append(RevitScheduleParser.parse(fname, text))
    return tables


def _load_mapping():
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fname in sorted(fnames):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(root, fname), "rb") as fh:
                raw = fh.read()
            results.append(DynamoMappingParser.auto_detect_and_parse(raw, fname))
    return DynamoMappingParser.merge_formats(results)


def _compute(map_df):
    tables = _load_revit_tables()
    engine = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    return engine.compute(tables, map_df)


# ──────────────────────────── tests ────────────────────────────


def test_T54_mapping_rebar_dedup_base_total():
    """baseTotal نباید آرماتور تکراری v1 را شامل شود."""
    r = _compute(_load_mapping())
    # مقدار مورد انتظار با پایگاه واقعی ۱۴۰۴ پس از مرحلهٔ ۱۱ (حذف ضریب پرت،
    # بقایای تیرچه، زنجیرهٔ مالی جدید)
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


def test_T54_rebar_bucket_070101_not_inflated():
    """سینی ۰۷۰۱۰۱ نباید آرماتور تکراری v1 را دوباره بشمارد."""
    r = _compute(_load_mapping())
    line = next(l for l in r["lines"] if l["code"] == "070101")
    # ۱۲۵.۵۷ (Revit) + ۰.۱۶۴۶ (تنها میلگرد v1 که در Revit نیست) = ۱۲۵.۷۳
    assert line["qty"] == pytest.approx(125.7346, abs=1e-2)
    # قبل از fix: ۱۷۲.۶۵۶۰ (double-count)


def test_T54_all_rebar_buckets_match_revit_only():
    """سینی‌های ۰۷ باید برابر مجموع Revit + تنها افزودنی‌های اختصاصی v1 باشند."""
    r = _compute(_load_mapping())
    by_code = {l["code"]: l["qty"] for l in r["lines"]}
    assert by_code["070201"] == pytest.approx(575.978837, abs=1e-2)
    assert by_code["070202"] == pytest.approx(11550.555303, abs=1e-2)
    assert by_code["070203"] == pytest.approx(284.10, abs=1e-2)


def test_T54_v1_skipped_vs_kept():
    """۲۷۶ ردیف v1 به‌عنوان تکراری skip شده‌اند و ۱ ردیف نگه داشته شده."""
    r = _compute(_load_mapping())
    kept = [l for l in r["rebar"] if l.get("source") == "Mapping v1"]
    assert len(kept) == 1, f"expected 1 kept v1 rebar row, got {len(kept)}"
    # کل ردیف‌های آرماتور واقعی v1 در داده: ۲۷۷ → ۲۷۶ skip + ۱ kept
    assert kept[0]["weight"] == pytest.approx(0.1646, abs=1e-3)
    assert kept[0]["diameter"] == pytest.approx(8.0, abs=1e-6)


def test_T54_no_dedup_regression_without_mapping():
    """بدون mapping، خروجی نباید تغییر کند (dedup فقط روی v1 اثر می‌گذارد)."""
    r = _compute(None)
    # ۱۲.۵۳۶ تن × ۲۰ کیلومتر = ۲۵۰.۷۲ تن-کیلومتر (بدون افزودنی v1)
    assert r["base_total"] == pytest.approx(23218306845.90, abs=1.0)
    by_code = {l["code"]: l["qty"] for l in r["lines"]}
    assert by_code["070101"] == pytest.approx(125.57, abs=1e-2)
