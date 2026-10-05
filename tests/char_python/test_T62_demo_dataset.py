# -*- coding: utf-8 -*-
# T62 - مسیر دادهٔ نمونهٔ داخلی (DEMO_SCHEDULES) با golden اختصاصی
#
# پروژهٔ نمونهٔ تعبیه‌شده («بارگذاری دادهٔ نمونهٔ واقعی» در UI) یک زیرمجموعهٔ
# قدیمی‌تر از فایل‌های data/export revit است: ۹ جدول در برابر ۱۰، جدول
# بتن‌ریزی پی را ندارد، جدول آرماتور فقط یک «بخش نمونه» است، و فرمت
# نقل‌قول‌گذاری CSV استاندارد است (نه doubled-quote خروجی واقعی Revit).
# به همین دلیل مجموع آن با مسیر فایل‌های واقعی متفاوت است و golden
# مستقلی دارد. این تست تضمین می‌کند که مسیر دمو در دو زبان یکسان می‌ماند
# و هر تغییر ناخواسته در دادهٔ نمونه شناسایی می‌شود.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DEMO_SCHEDULES, DynamoMappingParser, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

from helper import load_json, golden_path, record  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


def _demo_pipeline():
    """اجرای کامل موتور روی دادهٔ نمونهٔ داخلی + mapping واقعی."""
    tables = [RevitScheduleParser.parse(name, text) for name, text in DEMO_SCHEDULES]
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fname in sorted(fnames):
            if fname.endswith(".txt"):
                with open(os.path.join(root, fname), "rb") as fh:
                    results.append(DynamoMappingParser.auto_detect_and_parse(fh.read(), fname))
    map_df = DynamoMappingParser.merge_formats(results)
    r = TechnicalOfficeEngine(_default_fehrest_db(), default_settings()).compute(tables, map_df)
    return tables, r


def test_T62_demo_dataset_is_not_real_files():
    """تأیید اینکه دادهٔ نمونه با فایل‌های واقعی فرق دارد (نه یک کپی)."""
    revit_dir = os.path.join(ROOT, "data", "export revit")
    disk_names = {f for f in sorted(os.listdir(revit_dir)) if f.endswith(".txt")}
    demo_names = {name for name, _text in DEMO_SCHEDULES}
    assert demo_names != disk_names, "دادهٔ نمونه اکنون با فایل‌های واقعی یکسان است؛ golden باید حذف شود"
    assert len(demo_names) == 9
    assert len(disk_names) == 10


def test_T62_demo_pipeline_golden():
    tables, r = _demo_pipeline()
    snap = {
        "tables": len(tables),
        "lines": len(r["lines"]),
        "base_total": round(r["base_total"], 2),
        "grand_total": round(r["grand_total"], 2),
    }
    record("T62_demo_pipeline", snap, generate=os.environ.get("GENERATE") == "1")
    golden = load_json(golden_path("T62_demo_pipeline"))
    assert snap == golden, f"مسیر دمو تغییر کرد: {snap} != {golden}"
    # مقادیر مرجع (نباید با مسیر فایل‌های واقعی یکسان باشند)
    # مرحلهٔ ۱۳: ضریب منطقه‌ای پیش‌فرض (گرگان ۱٫۰۴) در زنجیره اعمال می‌شود.
    assert snap["base_total"] == pytest.approx(20380352396.27, abs=1.0)
    assert snap["grand_total"] == pytest.approx(20380352396.27 * 1.3 * 1.04, abs=1.0)


if __name__ == "__main__":
    test_T62_demo_dataset_is_not_real_files()
    test_T62_demo_pipeline_golden()
    print("T62 ok")
