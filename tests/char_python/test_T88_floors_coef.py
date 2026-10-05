# -*- coding: utf-8 -*-
# T88 — ضریب طبقات (ایراد ۳ — مرحلهٔ ۱۳).
#
# پیوست ۴ فهرست‌بهای ابنیه ۱۴۰۴: P = (Σ(i×Fi) + Σ(j×Bj)) / S.
# طبقه‌بندی ترازهای Revit: زیرهمکف (B0) | همکف (F0) | بالاتر (F1..Fn).
# مساحت طبقات از مدل خوانده می‌شود و قابل ویرایش است؛ اگر مساحت طبقات
# بالاتر از همکف موجود نباشد → ضریب ۱ با برچسب «ناقص» + هشدار خطا.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

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


def _sched_recs():
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    recs = []
    for t in tables:
        recs.extend(eng._records_from_table(t))
    return recs


@pytest.mark.parametrize("name,expected", [
    ("Story1", ("ground", 0)),
    ("Story2", ("above", 1)),
    ("Story6", ("above", 5)),
    # تراز بالای فونداسیون طبقه نیست (درخواست کاربر — بند ۱)؛ با
    # floors_data["Foundation Top"]["is_floor"]=True به below_base برمی‌گردد.
    ("Foundation Top", ("none", 0)),
    ("Roof", None),
])
def test_T88_level_kind(name, expected):
    assert TechnicalOfficeEngine._level_kind(name) == expected


def test_T88_real_project_floors_table():
    """هفت تراز؛ Foundation Top غیرطبقه‌ای، Story6 بام، مساحت مدل فقط Story1."""
    rows = TechnicalOfficeEngine(_default_fehrest_db(),
                                 default_settings())._floors_table(_sched_recs())
    by_name = {r["name"]: r for r in rows}
    assert len(rows) == 7
    assert by_name["Foundation Top"]["kind"] == "none"   # پی، نه زیرهمکف
    assert by_name["Foundation Top"]["index"] == 0       # مستثنی از Σ
    assert by_name["Story1"]["kind"] == "ground"
    assert by_name["Story1"]["area_model"] == pytest.approx(63.0, abs=1e-6)
    assert by_name["Story1"]["area"] == pytest.approx(63.0, abs=1e-6)
    assert by_name["Story2"]["index"] == 1               # F1 (بام Story6 مستثنی)
    assert by_name["Story5"]["index"] == 4               # F4
    assert by_name["Story6"]["kind"] == "roof"           # بام: ۳ ستون بدون سقف
    assert by_name["Story6"]["index"] == 0
    assert by_name["Story6"]["area_model"] is None       # نیازمند ورود دستی
    assert by_name["Story6"]["area"] is None


def test_T88_default_is_incomplete():
    """بدون مساحت طبقات بالا → ضریب ۱ با برچسب ناقص + هشدار خطا."""
    r = _pipeline(default_settings())
    fc = r["coefs"]["floors"]
    assert fc["value"] == 1.0
    assert fc["status"] == "ناقص"
    assert r["status"]["floors_status"] == "ناقص"
    errs = [w for w in r["warnings"]
            if w["category"] == "ضریب طبقات" and w["level"] == "خطا"]
    assert len(errs) == 1
    assert r["status"]["complete"] is False


def test_T88_formula_when_areas_provided():
    """با ورود مساحت ۵ طبقه (Foundation Top غیرطبقه‌ای، بام Story6 مستثنی).

    صورت = (۱+۲+۳+۴) × ۶۳ (طبقات بالاتر) = ۶۳۰.
    همکف (B0) در صورت سهمی ندارد. Foundation Top هم طبقه نیست.
    مخرج ۱۰۰ × S = ۱۰۰ × ۵ × ۶۳ = ۳۱۵۰۰.
    P = ۱ + ۶۳۰ ÷ ۳۱۵۰۰ = ۱/۰۲.
    """
    areas = {"Foundation Top": 63.0, "Story1": 63.0, "Story2": 63.0,
             "Story3": 63.0, "Story4": 63.0, "Story5": 63.0}
    r = _pipeline(dict(default_settings(), floors_data=areas))
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(1.02, rel=1e-9)
    assert fc["value"] > 1.0
    assert fc["status"] == "محاسبه‌شده"
    # اعمال فقط روی ردیف‌های مشمول (فصل ۲۸ مستثنی)
    assert fc["eligible_total"] == pytest.approx(r["base_total"] - fc["excluded_total"])
    assert "28" in fc["excluded_chapters"]
    assert r["floors_amount"] == pytest.approx(
        fc["eligible_total"] * 1.02 + fc["excluded_total"], rel=1e-9)
    assert r["grand_total"] == pytest.approx(
        r["floors_amount"] * 1.3 * 1.04, rel=1e-6)
    assert not any(w["category"] == "ضریب طبقات" and w["level"] == "خطا"
                  for w in r["warnings"])
    # مخرج جایگزین «S» (مغایر متن رسمی) در خروجی ثبت می‌شود
    assert fc["calc"]["divisor"] == "100×S"
    assert fc["calc"]["p_alt"] == pytest.approx(3.0, rel=1e-9)
    # بام و فونداسیون از صورت و مخرج فرمول مستثنی شده‌اند
    _by = {x["name"]: x for x in fc["rows"]}
    assert _by["Story6"]["kind"] == "roof"
    assert _by["Foundation Top"]["kind"] == "none"


def test_T88_full_formula_when_roof_cleared():
    """بدون استثنای بام (floors_roof_levels خالی) ولی Foundation Top همچنان
    غیرطبقه‌ای: صورت ۹۴۵، مخرج ۱۰۰×۳۷۸.

    P = ۱ + ۹۴۵ ÷ ۳۷۸۰۰ = ۱/۰۲۵ — فونداسیون حتی بدون استثنای بام طبقه نیست.
    """
    areas = {"Foundation Top": 63.0, "Story1": 63.0, "Story2": 63.0,
             "Story3": 63.0, "Story4": 63.0, "Story5": 63.0, "Story6": 63.0}
    s = dict(default_settings(), floors_data=areas, floors_roof_levels=[])
    r = _pipeline(s)
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(1.025, rel=1e-9)
    assert fc["calc"]["p_alt"] == pytest.approx(3.5, rel=1e-9)


def test_T88_foundation_top_is_floor_override():
    """Foundation Top با is_floor=True به B1 (زیرهمکف) برمی‌گردد: P = ۶۱۱/۶۰۰.

    صورت = (۱+۲+۳+۴) × ۶۳ + ۱ × ۶۳ (B1) = ۶۹۳؛ مخرج ۱۰۰ × ۶ × ۶۳ = ۳۷۸۰۰.
    """
    areas = {"Foundation Top": {"area": 63.0, "is_floor": True},
             "Story1": 63.0, "Story2": 63.0, "Story3": 63.0,
             "Story4": 63.0, "Story5": 63.0}
    r = _pipeline(dict(default_settings(), floors_data=areas))
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(611.0 / 600.0, rel=1e-9)
    _by = {x["name"]: x for x in fc["rows"]}
    assert _by["Foundation Top"]["kind"] == "below_base"
    assert _by["Foundation Top"]["index"] == 1


def test_T88_is_floor_false_excludes_story():
    """is_floor=False یک طبقهٔ بالاتر را از Σ خارج می‌کند (با شماره‌گذاری مجدد).

    Story2 حذف → F1..F3 = Story3..Story5: صورت = ۶×۶۳ = ۳۷۸؛
    مخرج ۱۰۰ × ۴ × ۶۳ = ۲۵۲۰۰ → P = ۱ + ۳۷۸ ÷ ۲۵۲۰۰ = ۱/۰۱۵.
    """
    areas = {"Story1": 63.0, "Story2": {"area": 63.0, "is_floor": False},
             "Story3": 63.0, "Story4": 63.0, "Story5": 63.0}
    r = _pipeline(dict(default_settings(), floors_data=areas))
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(1.015, rel=1e-9)
    _by = {x["name"]: x for x in fc["rows"]}
    assert _by["Story2"]["kind"] == "none"


def test_T88_divisor_S_deviation_warns():
    """انتخاب مخرج «S» هشدار سطح «هشدار» با ذکر مغایرت ثبت می‌کند."""
    areas = {"Foundation Top": 63.0, "Story1": 63.0, "Story2": 63.0,
             "Story3": 63.0, "Story4": 63.0, "Story5": 63.0}
    r = _pipeline(dict(default_settings(), floors_data=areas,
                       floors_divisor="S"))
    fc = r["coefs"]["floors"]
    # صورت ۶۳۰ ÷ مخرج ۳۱۵ = ۲ → P = ۳
    assert fc["value"] == pytest.approx(3.0, rel=1e-9)
    dev = [w for w in r["warnings"] if w["category"] == "ضریب طبقات"
           and w["level"] == "هشدار"]
    assert dev and "مغایر" in dev[0]["message"]


def test_T88_footprint_hint():
    """رَدپای ساختمان از بتن مگر (۱۸.۶۵ m³ ÷ ۰.۱ m = ۱۸۶.۵ m²)."""
    r = _pipeline(default_settings())
    fp = r["coefs"]["floors"]["footprint"]
    assert fp is not None
    assert fp["volume"] == pytest.approx(18.65, abs=1e-6)
    assert fp["area"] == pytest.approx(186.5, abs=1e-6)
    assert fp["status"] == "تخمینی (دستی)"


def test_T88_manual_override():
    """floors_auto=False → عدد دستی کاربر جایگزین فرمول می‌شود."""
    s = dict(default_settings(), floors_auto=False, floors_coef=1.12)
    r = _pipeline(s)
    assert r["coefs"]["floors"]["value"] == pytest.approx(1.12, rel=1e-9)
    assert r["coefs"]["floors"]["status"] == "دستی"


def test_T88_formula_source_recorded():
    """فرمول و بند پیوست ۲ در خروجی ثبت می‌شود (قابلیت ردیابی)."""
    r = _pipeline(default_settings())
    assert "S" in r["coefs"]["floors"]["formula"]
    assert r["coefs"]["floors"]["clause"]           # «تمام اقلام کار ساختمان...»


def test_T88_price_refs_recorded():
    """ارجاع بهای ردیف‌های کلیدی در شیت «صورت وضعیت» (ایراد ۲ و ۴)."""
    from app import PRICE_REFS
    r = _pipeline(default_settings())
    codes = {l["code"] for l in r["lines"]}
    assert "060401" in codes and "060401" in PRICE_REFS
    assert "ردیف ۲۵۴" in PRICE_REFS["060401"]
    assert "صفحهٔ ۸۲" in (r["coefs"]["regional"]["source"] or "")


# ─ـ فاز E-6 Part C گام ۱۰ (حرف d): کمتر از ۵ طبقه و S = ۰ ──

def test_T88_fewer_than_five_floors():
    """فقط همکف + یک طبقهٔ بالاتر (سه طبقهٔ دیگر is_floor=False).

    صورت = ۱ × ۶۳ = ۶۳ (فقط Story2 = F1)؛ مخرج ۱۰۰ × ۲ × ۶۳ = ۱۲۶۰۰.
    P = ۱ + ۶۳ ÷ ۱۲۶۰۰ = ۱/۰۰۵.
    """
    areas = {"Foundation Top": 63.0, "Story1": 63.0, "Story2": 63.0,
             "Story3": {"area": 63.0, "is_floor": False},
             "Story4": {"area": 63.0, "is_floor": False},
             "Story5": {"area": 63.0, "is_floor": False}}
    r = _pipeline(dict(default_settings(), floors_data=areas))
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(1.005, rel=1e-9)
    assert fc["status"] == "محاسبه‌شده"
    _by = {x["name"]: x for x in fc["rows"]}
    assert _by["Story2"]["index"] == 1
    assert _by["Story3"]["kind"] == "none"
    assert not any(w["category"] == "ضریب طبقات" and w["level"] == "خطا"
                  for w in r["warnings"])


def test_T88_zero_S_returns_incomplete():
    """همهٔ مساحت‌ها صفر ⇒ S = ۰ ⇒ ضریب ۱ + برچسب «ناقص» + هشدار."""
    areas = {k: 0.0 for k in ("Foundation Top", "Story1", "Story2", "Story3",
                              "Story4", "Story5")}
    r = _pipeline(dict(default_settings(), floors_data=areas))
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(1.0)
    assert fc["status"] == "ناقص"
    zero = [w for w in r["warnings"] if w["category"] == "ضریب طبقات"
            and w["level"] == "هشدار"
            and "هیچ مساحت" in w["message"]]
    assert len(zero) == 1


def test_T88_all_non_floor_zero_S():
    """همهٔ ترازها is_floor=False ⇒ صورت و مخرج صفر ⇒ ضریب ۱ + «ناقص»."""
    areas = {k: {"area": 63.0, "is_floor": False}
             for k in ("Foundation Top", "Story1", "Story2", "Story3",
                       "Story4", "Story5")}
    r = _pipeline(dict(default_settings(), floors_data=areas))
    fc = r["coefs"]["floors"]
    assert fc["value"] == pytest.approx(1.0)
    assert fc["status"] == "ناقص"
    assert any(w["category"] == "ضریب طبقات" and "هیچ مساحت" in w["message"]
               for w in r["warnings"])
