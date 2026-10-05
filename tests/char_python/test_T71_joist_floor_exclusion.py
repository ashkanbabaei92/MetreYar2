# -*- coding: utf-8 -*-
# T71/T72/T73 - مرحلهٔ ۹: رفع دوبارشماری سقف تیرچه‌بلوک + اضافه‌بهای مقاومت.
#
# مبنا: فهرست‌بهای ابنیه ۱۴۰۴، فصل دهم، الزامات عمومی:
#   بند ۳: ردیف‌های سقف تیرچه‌بلوک شامل شمع‌بندی، داربست، قالب‌بندی،
#          بتن‌ریزی و نگهداری است → المان تیرچه نباید بتن (۰۸۰۱۰۵..۰۸۰۱۰۷)
#          یا قالب (فصل ۰۶، از جمله ۰۶۰۵۰۱) جداگانه تولید کند.
#   بند ۸: بتن سقف ۲۰ MPa فرض؛ بیش از ۲۰ تا ۲۵ → ۱۰۰۷۰۱ (۵۹٬۵۰۰ ریال/m²)،
#          بیش از ۲۵ تا ۳۰ → ۱۰۰۷۰۲ (۷۶٬۵۰۰ ریال/m²) روی کل مساحت سقف.
#   بند ۹: ضخامت سقف = زیر تیرچه تا ۵ cm بتن روی بلوک داخل نرخ ۱۰۰۳۰۵ است؛
#          فقط بتن مازاد بر ۵ cm (طبق مشخصات فنی) جداگانه حساب می‌شود.
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (JOIST_BLOCK_STRENGTH_SURCHARGE, DynamoMappingParser,
                 RevitScheduleParser, TechnicalOfficeEngine, _default_fehrest_db,
                 default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

# مرجع مرحلهٔ ۸ (قبل از رفع دوبارشماری) — برای تطبیق اختلاف کمیت.
STAGE8_CONC_COL_BEAM = 250.36   # m³ شامل ۸٫۴۲ m³ تیرچه
STAGE8_FORM_BEAM = 1621.0       # m² شامل ۱۶۲ m² تیرچه


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


def _line(result, plan_id):
    return next(l for l in result["lines"] if l["id"] == plan_id)


def _codes(result):
    return {l["code"] for l in result["lines"]}


# ── T71: المان‌های سقف تیرچه‌بلوک ردیف بتن/قالب تولید نمی‌کنند ──

def test_T71_joist_elements_excluded_from_concrete_and_formwork():
    """JSL01: حذف ۸٫۴۲ m³ از ۰۸۰۱۰۷ و ۱۶۲ m² از ۰۶۰۵۰۱؛ ۱۰۰۳۰۵ بدون تغییر."""
    r = _pipeline(default_settings())
    # بتن ستون/تیر: ۲۵۰٫۳۶ − ۸٫۴۲ (JSL01) = ۲۴۱٫۹۴
    cb = _line(r, "conc-col-beam")
    assert cb["code"] == "080107"
    assert cb["qty"] == pytest.approx(241.94, abs=1e-4)
    # قالب تیر: ۱۶۲۱ − ۱۶۲ (JSL01) = ۱۴۵۹
    fb = _line(r, "form-beam")
    assert fb["code"] == "060501"
    assert fb["qty"] == pytest.approx(1459.0, abs=1e-4)
    # سقف تیرچه‌بلوک دست‌نخورده
    jb = _line(r, "joist-block")
    assert jb["code"] == "100305"
    assert jb["qty"] == pytest.approx(40.966508, abs=1e-6)


def test_T71_no_joist_line_in_concrete_or_formwork_codes():
    """هیچ ردیفی در ۰۸۰۱۰۵/۰۸۰۱۰۶/۰۸۰۱۰۷ یا ۰۶۰۵۰۱ نباید از تیرچه باشد.

    این بررسی مستقل از دادهٔ نمونه: با تأمین فقط دو جدول (Structural
    Concrete + Joist Floor) موتور باید ۸٫۴۲ m³ تیرچه را در بتن نیاورد.
    """
    def _read(fname):
        with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
            return RevitScheduleParser.parse(fname, fh.read())

    conc_name = next(f for f in sorted(os.listdir(REVIT_DIR))
                     if "حجم بتن سازه‌ای" in f and "Structural Concrete" in f)
    joist_name = next(f for f in sorted(os.listdir(REVIT_DIR))
                      if "سقف تیرچه بلوک" in f and "Joist Floor" in f)
    tables = [_read(conc_name), _read(joist_name)]
    r = TechnicalOfficeEngine(_default_fehrest_db(), default_settings()).compute(tables, None)
    # ۸٫۴۲ m³ تیرچه در structural_concrete هست ولی نباید به ردیفی برود.
    codes = _codes(r)
    assert "080107" in codes  # ستون/تیرهای واقعی (۲۴۱٫۹۴)
    assert "100305" in codes
    assert _line(r, "conc-col-beam")["qty"] == pytest.approx(241.94, abs=1e-4)


def test_T71_reconciliation_with_stage8_reference():
    """اثر حذف دوبارشماری تیرچه: دقیقاً ۸٫۴۲ m³ بتن + ۱۶۲ m² قالب.

    مقادیر مرحلهٔ ۸ (قبل از حذف دوبارشماری): بتن ستون/تیر ۲۵۰٫۳۶ m³ و قالب
    تیر ۱۶۲۱ m². بعد از حذف المان JSL01 این مقادیر ۲۴۱٫۹۴ و ۱۴۵۹ می‌شوند.
    با مقاومت ۲۰ MPa (بدون اضافه‌بها) هیچ ردیف ۱۰۰۷۰۱/۱۰۰۷۰۲ تولید نمی‌شود؛
    پیش‌فرض ۲۵ MPa اضافه‌بهای ۱۰۰۷۰۱ را روی مساحت سقف می‌نهد. (مرحلهٔ ۱۱:
    totals مطلق مرجع به‌خاطر حذف ضریب پرت و زنجیرهٔ مالی جدید تغییر کرده‌اند،
    پس این تطبیق روی مقادیر کمیتی انجام می‌شود.)
    """
    s20 = default_settings()
    s20["joist_block_concrete_mpa"] = 20
    r20 = _pipeline(s20)
    cb, fb = _line(r20, "conc-col-beam"), _line(r20, "form-beam")
    assert cb["qty"] + 8.42 == pytest.approx(STAGE8_CONC_COL_BEAM, abs=1e-4)
    assert fb["qty"] + 162.0 == pytest.approx(STAGE8_FORM_BEAM, abs=1e-4)
    assert not any(l["code"] in ("100701", "100702") for l in r20["lines"])

    r25 = _pipeline(default_settings())
    surcharge = _line(r25, "joist-strength-surcharge")
    assert r25["base_total"] == pytest.approx(r20["base_total"] + surcharge["total"], abs=1.0)


# ── T72: ماتریس مقاومت بتن سقف تیرچه‌بلوک (بند ۸ فصل دهم) ──

def test_T72_strength_matrix_surcharge_rows():
    """۲۰ → هیچ / ۲۵ → ۱۰۰۷۰۱ / ۳۰ → ۱۰۰۷۰۲ با مقدار = مساحت خالص سقف."""
    # ۲۰ MPa: هیچ ردیف اضافه‌بها
    s = default_settings()
    s["joist_block_concrete_mpa"] = 20
    r = _pipeline(s)
    assert not any(l["code"] in ("100701", "100702") for l in r["lines"])
    assert len(r["lines"]) == 16

    # ۲۵ و ۳۰ MPa: ردیف اضافه‌بها روی کل مساحت ۱۰۰۳۰۵
    for mpa, code, price in ((25, "100701", 59500.0), (30, "100702", 76500.0)):
        s = default_settings()
        s["joist_block_concrete_mpa"] = mpa
        r = _pipeline(s)
        assert len(r["lines"]) == 17
        sc = _line(r, "joist-strength-surcharge")
        jb = _line(r, "joist-block")
        assert sc["code"] == code
        assert sc["unit"] == "مترمربع"
        assert sc["qty"] == pytest.approx(jb["qty"], abs=1e-9)
        assert sc["price"] == pytest.approx(price, abs=0.5)
        assert sc["total"] == pytest.approx(jb["qty"] * price, abs=1.0)
        # بتن سقف تیرچه‌بلوک به ۰۸۰۱۰۶ نگاشت نمی‌شود
        assert _line(r, "conc-slab")["qty"] == pytest.approx(2.631675, abs=1e-6)


def test_T72_surcharge_mapping_table():
    """جدول نگاشت اضافه‌بهای مقاومت فقط سه کلید ۲۰/۲۵/۳۰ دارد."""
    assert set(JOIST_BLOCK_STRENGTH_SURCHARGE) == {20, 25, 30}
    assert JOIST_BLOCK_STRENGTH_SURCHARGE[20] is None
    assert JOIST_BLOCK_STRENGTH_SURCHARGE[25] == ("100701", 59500.0)
    assert JOIST_BLOCK_STRENGTH_SURCHARGE[30] == ("100702", 76500.0)


# ── T73: ضخامت بتن روی بلوک (بند ۹ فصل دهم) ──

def test_T73_excess_concrete_matrix():
    """ضخامت روی بلوک ۵ و ۷ cm → بتن مازاد ۰ و ۰٫۰۲×مساحت سقف."""
    # ۵ cm (پیش‌فرض): صفر مازاد
    r5 = _pipeline(default_settings())
    assert _line(r5, "conc-slab")["qty"] == pytest.approx(2.631675, abs=1e-6)

    # ۷ cm: (۷−۵)/۱۰۰ × ۴۰٫۹۶۶۵۰۸ = ۰٫۸۱۹۳۳ m³ به ۰۸۰۱۰۶ (مقاومت ۲۵)
    s7 = default_settings()
    s7["joist_block_top_thickness_cm"] = 7
    r7 = _pipeline(s7)
    slab7 = _line(r7, "conc-slab")
    jb = _line(r7, "joist-block")
    assert slab7["qty"] == pytest.approx(2.631675 + 0.02 * jb["qty"], abs=1e-6)
    assert slab7["qty"] == pytest.approx(3.451005, abs=1e-6)
    # ۱۰۰۳۰۵ و بقیهٔ ردیف‌ها بدون تغییر
    assert _line(r7, "joist-block")["qty"] == pytest.approx(40.966508, abs=1e-6)
    assert _line(r7, "conc-col-beam")["qty"] == pytest.approx(241.94, abs=1e-4)
    # ردیف اضافه‌بها روی مساحت خالص سقف (نه روی حجم مازاد)
    sc = _line(r7, "joist-strength-surcharge")
    assert sc["qty"] == pytest.approx(jb["qty"], abs=1e-9)


def test_T73_excess_uses_selected_strength():
    """بتن مازاد به ردیف متناظر با مقاومت انتخابی می‌رود، نه لزوماً ۰۸۰۱۰۶.

    با مقاومت ۳۰ MPa، مازاد باید به ۰۸۰۱۰۷ (conc-col-beam) برود.
    """
    s = default_settings()
    s["joist_block_top_thickness_cm"] = 7
    s["joist_block_concrete_mpa"] = 30
    r = _pipeline(s)
    excess = 0.02 * 40.966508
    assert _line(r, "conc-col-beam")["qty"] == pytest.approx(241.94 + excess, abs=1e-6)
    assert _line(r, "conc-slab")["qty"] == pytest.approx(2.631675, abs=1e-6)


if __name__ == "__main__":
    test_T71_joist_elements_excluded_from_concrete_and_formwork()
    test_T71_no_joist_line_in_concrete_or_formwork_codes()
    test_T71_reconciliation_with_stage8_reference()
    test_T72_strength_matrix_surcharge_rows()
    test_T72_surcharge_mapping_table()
    test_T73_excess_concrete_matrix()
    test_T73_excess_uses_selected_strength()
    print("T71/T72/T73 OK")
