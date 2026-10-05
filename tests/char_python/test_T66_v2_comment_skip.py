# -*- coding: utf-8 -*-
# T66 - رد سطرهای خلاصه/کامنت (شروع با #) در پارسر Mapping نسخهٔ ۲.
#
# فایل v2 (map3.txt) با سطر پایانی «# مجموع  تعداد کل المان‌ها: ۲۷۹» تمام
# می‌شود. پیش از این، این سطر به‌عنوان یک رکورد داده‌ای با کمیت‌های صفر
# جذب می‌شد (۲۸۰ رکورد در map3، ۸۳۶ رکورد پس از merge با map2). در عمل
# بی‌اثر بود چون همهٔ کمیت‌ها صفر است، ولی شمارش رکوردها را آلوده می‌کرد.
# اکنون سطرهای #دار صریحاً رد می‌شوند (۲۷۹ / ۸۳۵) و totals بی‌تغییر می‌مانند.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MAP3 = os.path.join(ROOT, "data", "dynamo", "mapping3", "map3.txt")
MAP2 = os.path.join(ROOT, "data", "dynamo", "mapping2", "map2.txt")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


def _parse(path):
    with open(path, "rb") as fh:
        return DynamoMappingParser.auto_detect_and_parse(fh.read(), os.path.basename(path))


def test_T66_v2_skips_hash_footer_rows():
    """map3 (v2) سطر خلاصهٔ #دار را رد می‌کند: ۲۷۹ رکورد، نه ۲۸۰."""
    fx = _parse(MAP3)
    assert fx["fmt"] == "v2"
    assert fx["records_count"] == 279, f"v2 record count: {fx['records_count']}"
    # هیچ رکوردی نباید باقیماندهٔ سطر #دار باشد
    df = fx["df"]
    assert not any(str(v).lstrip().startswith("#") for v in df.get("element_id", [])), \
        "یک سطر #دار به‌عنوان رکورد جذب شده است"


def test_T66_merged_record_count_is_835():
    """merge دو فایل Mapping: ۵۵۶ (v1) + ۲۷۹ (v2) = ۸۳۵ رکورد، نه ۸۳۶."""
    m2 = _parse(MAP2)
    m3 = _parse(MAP3)
    assert m2["fmt"] == "v1" and m2["records_count"] == 556
    assert m3["fmt"] == "v2" and m3["records_count"] == 279
    merged = DynamoMappingParser.merge_formats([m2, m3])
    assert len(merged) == 835, f"merged record count: {len(merged)}"


def test_T66_totals_unchanged_by_comment_skip():
    """حذف سطر خلاصه نباید هیچ کمیت/مبلغی را تغییر دهد."""
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
    r = TechnicalOfficeEngine(_default_fehrest_db(), default_settings()).compute(tables, map_df)

    assert len(r["lines"]) == 17
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)


if __name__ == "__main__":
    test_T66_v2_skips_hash_footer_rows()
    test_T66_merged_record_count_is_835()
    test_T66_totals_unchanged_by_comment_skip()
    print("T66 ok")
