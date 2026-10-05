# -*- coding: utf-8 -*-
# T56 — اصلاح تشخیص واحدهای فهرست‌بهای ۱۴۰۴ + پاریتی کامل Python/TS.
#
# پیشینه: تشخیص واحد، واحدهای خط‌تیره‌دار را نمی‌شناخت. نتیجه:
#   • 280101 (حمل) واحد واقعی «تن-کیلومتر» داشت ولی به‌جای آن از روی
#     واژهٔ «آهن‌آلات» در شرح، «کیلوگرم» حدس زده می‌شد.
#   • ردیف‌های «دسیمترمکعب» (مثل 080501 گروت) و «رشته» (070705) نیز
#     از روی شرح حدس زده می‌شدند.
# اصلاح: افزودن تن-کیلومتر/دسیمترمکعب/رشته به _UNIT_WORDS، پذیرش
# پیشوند با خط تیره (w.startsWith(u + "-")) و قرار دادن واحدهای مرکب
# پیش از پایهٔ آن‌ها (تن-کیلومتر قبل از تن).
#
# مقادیر مورد انتظار این تست از خروجی واقعی Python گرفته شده‌اند و
# tests/char_ts/test_T56_fehrest_unit_fix.ts همین مقادیر را assert می‌کند
# → تطابق کامل دو زبان روی فایل رسمی ۱۴۰۴.

import os
import sys

import pytest

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
FEHREST_FILE = os.path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def parsed():
    return FehrestBahaParser.parse_text(_read(FEHREST_FILE))


# ──────────────────────────── واحد تن-کیلومتر ────────────────────────────


def test_T56_transport_unit_is_ton_kilometer(parsed):
    """۲۸۰۱۰۱ واحد رسمی «تن-کیلومتر» دارد، نه «کیلوگرم» (حدس از «آهن‌آلات»)."""
    rows, _skipped = parsed
    r = next((x for x in rows if x["code"] == "280101"), None)
    assert r is not None, "280101 missing from the real 1404 file"
    assert r["unit"] == "تن-کیلومتر"
    assert r["price"] == pytest.approx(28400)
    assert r["chapter"] == "28"


def test_T56_all_land_transport_rows_are_ton_kilometer(parsed):
    """هر ۸ ردیف حمل زمینی/آسفالتی فصل ۲۸ واحد «تن-کیلومتر» دارند."""
    rows, _skipped = parsed
    land = [x for x in rows if x["code"].startswith("28")
            and x["unit"] != "تن - مابل دریایی"]
    assert len(land) == 8
    for r in land:
        assert r["unit"] == "تن-کیلومتر", f"{r['code']}: {r['unit']}"


def test_T56_marine_transport_unit_preserved(parsed):
    """ردیف‌های حمل دریایی و واحد مرکب «تن - مابل دریایی» خود را نگه می‌دارند."""
    rows, _skipped = parsed
    marine = [x for x in rows if x["code"] in ("280501", "280502", "280503",
                                              "280504", "280505")]
    assert len(marine) == 5
    for r in marine:
        assert r["unit"] == "تن - مابل دریایی", f"{r['code']}: {r['unit']}"


# ─────────────────── دسیمترمکعب و رشته و واحدهای خط‌تیره‌دار ──────────────────


@pytest.mark.parametrize("code", ["080501", "080502", "060912", "060916"])
def test_T56_decimeter_cubic_detected(parsed, code):
    """ردیف‌های گروت/درز با واحد «دسیمترمکعب» دیگر از روی شرح حدس زده نمی‌شوند."""
    rows, _skipped = parsed
    r = next((x for x in rows if x["code"] == code), None)
    assert r is not None
    assert r["unit"] == "دسیمترمکعب", f"{code}: {r['unit']}"


def test_T56_band_unit_detected(parsed):
    """۰۷۰۷۰۵ (اضافه‌بها به ازای هر رشته کابل) واحد «رشته» دارد."""
    rows, _skipped = parsed
    r = next((x for x in rows if x["code"] == "070705"), None)
    assert r is not None
    assert r["unit"] == "رشته", f"070705: {r['unit']}"


def test_T56_compound_square_meter_month_detected(parsed):
    """واحد مرکب «مترمربع-ماه» همچنان شناسایی می‌شود."""
    rows, _skipped = parsed
    r = next((x for x in rows if x["unit"] == "مترمربع-ماه"), None)
    assert r is not None


# ───────────────────────── توزیع کامل واحدها (پاریتی) ────────────────────────
# این توزیع دقیقاً همان چیزی است که parseFehrestText در TypeScript تولید
# می‌کند (تست test_T56_fehrest_unit_fix.ts) → هیچ اختلاف واحدی بین دو زبان.

EXPECTED_UNITS = {
    "اصله": 8, "تن": 6, "تن - مابل دریایی": 5, "تن-کیلومتر": 8, "درصد": 8,
    "دستگاه": 3, "دسیمترمکعب": 8, "رشته": 1, "عدد": 38, "لنگه": 2,
    "مترطول": 133, "مترمربع": 859, "مترمربع-ماه": 1, "مترمکعب": 191,
    "مترمکعب -  کیلومتر\u200f": 3, "مقطوع": 50, "کیلوگرم": 241,
}


def test_T56_unit_distribution_matches_typescript(parsed):
    """توزیع واحدها باید با TypeScript یکسان باشد (۱۷ نوع واحد)."""
    rows, _skipped = parsed
    units = {}
    for r in rows:
        units[r["unit"]] = units.get(r["unit"], 0) + 1
    assert units == EXPECTED_UNITS, (
        f"unit distribution changed — TS parity would break\n"
        f"got:      {sorted(units.items())}\n"
        f"expected: {sorted(EXPECTED_UNITS.items())}")


# ───────────────────── تطابق کد/شرح/فصل/قیمت/واحد (پاریتی) ─────────────────────
# مقادیر: خروجی واقعی Python؛ TypeScript همین جدول را assert می‌کند.
# کدهای هدف موتور پس از بازنگاشت مرحلهٔ ۲ روی فهرست‌بهای واقعی ۱۴۰۴.

EXPECTED_ENGINE_CODES = {
    "080102": ("مترمکعب", 17152000),   # lean — بتن با ۱۵۰ کیلوگرم سیمان
    "080105": ("مترمکعب", 19535000),   # پی و پله — ۲۰ MPa
    "080106": ("مترمکعب", 20162000),   # سقف — ۲۵ MPa
    "080107": ("مترمکعب", 20924000),   # ستون/تیر — ۳۰ MPa
    "060101": ("مترمربع", 2538000),
    "060301": ("مترمربع", 3378000),
    "060501": ("مترمربع", 4288000),
    "060701": ("مترمربع", 4100000),
    "070101": ("کیلوگرم", 452000),
    "070201": ("کیلوگرم", 441500),
    "070202": ("کیلوگرم", 375500),
    "070203": ("کیلوگرم", 358500),
    "100305": ("مترمربع", 8391000),    # تیرچه‌بلوک یونولیت ۲۵cm
    "280101": ("تن-کیلومتر", 28400),   # حمل ۳۰–۷۵km
}


@pytest.mark.parametrize("code", sorted(EXPECTED_ENGINE_CODES))
def test_T56_engine_codes_match_typescript(parsed, code):
    """هر کد خروجی موتور: واحد و قیمت یکسان در Python و TS."""
    rows, _skipped = parsed
    r = next((x for x in rows if x["code"] == code), None)
    assert r is not None, f"{code} missing"
    unit, price = EXPECTED_ENGINE_CODES[code]
    assert r["unit"] == unit, f"{code} unit: {r['unit']!r} != {unit!r}"
    assert r["price"] == pytest.approx(price), f"{code} price: {r['price']}"


def test_T56_080303_absent_from_real_file(parsed):
    """۰۸۰۳۰۳ در فهرست‌بهای ۱۴۰۴ وجود ندارد — تنها از طریق embedded نگه داشته می‌شود."""
    rows, _skipped = parsed
    assert next((x for x in rows if x["code"] == "080303"), None) is None


def test_T56_parse_counts_stable(parsed):
    """تعداد ردیف/skip با قبل از اصلاح واحد تغییر نکرده."""
    rows, skipped = parsed
    assert len(rows) == 1565
    assert skipped == 34


# ─────────────────────────────── merge ──────────────────────────────────


def test_T56_merge_preserves_embedded_only_codes():
    """merge: کدهای غایب در فایل واقعی (080303) از embedded زنده می‌مانند و
    قیمت‌های واقعی روی embedded override می‌شوند."""
    base = FehrestBahaParser.embedded()
    rows, _skipped = FehrestBahaParser.parse_text(_read(FEHREST_FILE))
    merged = {r["code"]: r for r in FehrestBahaParser.merge(base, rows)}

    assert "080303" in merged, "080303 must survive via the embedded base"
    assert merged["080303"]["price"] == pytest.approx(7200000)
    # قیمت واقعی جایگزین قیمت تخمینی embedded
    assert merged["070202"]["price"] == pytest.approx(375500)
    assert merged["070202"]["estimated"] is False
    assert merged["060101"]["price"] == pytest.approx(2538000)


# ───────────── حفظ خروجی فعلی: ۱۰ جدول Revit + ۲ mapping ─────────────


def test_T56_default_pipeline_output_unchanged():
    """اصلاح تشخیص واحد نباید مسیر پیش‌فرض (embedded) را تغییر دهد:
    ۱۰ فایل Revit + ۲ mapping، همان baseTotal قبلی."""
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            tables.append(RevitScheduleParser.parse(fname, _read(os.path.join(REVIT_DIR, fname))))

    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fname in sorted(fnames):
            if fname.endswith(".txt"):
                with open(os.path.join(root, fname), "rb") as fh:
                    results.append(DynamoMappingParser.auto_detect_and_parse(fh.read(), fname))
    map_df = DynamoMappingParser.merge_formats(results)

    engine = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    r = engine.compute(tables, map_df)

    # پس از فعال‌سازی فهرست‌بهای واقعی ۱۴۰۴ و بازنگاشت کدها (مرحلهٔ ۱۱:
    # حذف ضریب پرت، بقایای تیرچه، زنجیرهٔ مالی جدید)
    assert r["base_total"] == pytest.approx(23218381337.01, abs=1.0)
    assert r["grand_total"] == pytest.approx(31391251567.64, abs=1.0)
    assert len(r["lines"]) == 17
