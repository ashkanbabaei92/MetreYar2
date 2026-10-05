# -*- coding: utf-8 -*-
"""
تست قراردادهای تأییدشده روی دادهٔ واقعی Revit (data/export revit):
  G1 — تقدم منابع حجم بتن پی (dedup per-ref، حذف بتن مگر، derived فقط fallback)
  G2 — سطر جمع بدون برچسب ⇒ Grand total و نه رکورد متره
  G3 — «STRUCTURAL ...» نباید به‌عنوان پله گروه‌بندی شود
به‌همراه دو شکاف classification: «قالب‌بندی اسکلت» و «بتن‌ریزی پی».
این تست‌ها golden ندارند و کاملاً assert محورند.
"""
import glob
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (  # noqa: E402
    FehrestBahaParser,
    RevitScheduleParser,
    TechnicalOfficeEngine,
    default_settings,
    structural_group,
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
FEHREST_DIR = os.path.join(ROOT, "data", "fehrest baha 1404")

FOUNDATION_CONCRETE = "جدول بتن‌ریزی پی - Foundation Concrete Schedule.txt"
SUPER_FORMWORK = "جدول ریزمتره قالب‌بندی اسکلت - Superstructure Formwork Schedule.txt"


def _raw_tables():
    paths = sorted(glob.glob(os.path.join(REVIT_DIR, "*.txt")))
    if not paths:
        pytest.skip("raw Revit exports are not available")
    return [RevitScheduleParser.parse(os.path.basename(p),
                                      open(p, encoding="utf-8").read()) for p in paths]


def _engine():
    files = sorted(f for f in os.listdir(FEHREST_DIR) if f.endswith(".txt"))
    if not files:
        pytest.skip("fehrest file is not available")
    rows, _skipped = FehrestBahaParser.parse_text(
        open(os.path.join(FEHREST_DIR, files[0]), encoding="utf-8").read())
    return TechnicalOfficeEngine(
        FehrestBahaParser.merge(FehrestBahaParser.embedded(), rows), default_settings())


def _rec(source, ref, kind, qty, group, unit="m3"):
    """رکورد کمیت ساختگی برای آزمون خالص قرارداد تقدم منابع."""
    return {"source": source, "table": source, "kind": kind, "ref": ref, "group": group,
            "material": "", "level": "", "from_mapping": False, "qty": qty, "unit": unit,
            "detail": ""}


def _formwork_table(rows):
    """جدول قالب‌بندی پی ساختگی: هر ردیف (mark, familyType, length_m)."""
    return {"file_name": "FW.txt", "title": "قالب‌بندی پی", "kind": "formwork_foundation",
            "col_map": {}, "grand_total": {}, "rows": [
                {"cells": [], "texts": {"mark": m, "familyType": f},
                 "values": {"length": l}, "is_subtotal": False} for m, f, l in rows]}


# ── G3 ──

def test_G3_structural_is_not_grouped_as_stair():
    assert structural_group(
        "C01-ST01 M_Concrete-Rectangular-Column: C45X60-20F20 Structural Columns",
        "structural_concrete") == "ستون"
    assert structural_group(
        "B01-ST01 M_Concrete-Rectangular Beam: B45X50 Structural Framing",
        "structural_concrete") == "تیر"
    assert structural_group(
        "JSL-TOP01-ST01 Floor: Slab_Topping_50mm Floors", "structural_concrete") == "سقف"
    # مارک‌ها/عناصر واقعی پله باید همچنان پله بمانند
    assert structural_group(
        "STR01-ST01 Cast-In-Place Stair: Monolithic Stair IRAN",
        "structural_concrete") == "پله"
    assert structural_group("STR-B1", "structural_concrete") == "پله"
    assert structural_group("Stairs: Runs Monolithic Run: 25 mm Nosing",
                            "structural_concrete") == "پله"
    # پی و بتن مگر بدون تغییر
    assert structural_group("FT-L(1-2) Wall Foundation: WF_A_1800x900",
                            "structural_concrete") == "پی"
    assert structural_group("LC-01  Structural Foundations", "structural_concrete") == "پی"


# ── G1 ──

def test_G1_dedup_per_ref_dedicated_source_wins_and_lean_excluded():
    eng = TechnicalOfficeEngine([], default_settings())
    recs = [
        _rec("Schedule: FC.txt", "FT-1", "structural_concrete", 10.0, "پی"),
        _rec("Schedule: FC.txt", "FT-2", "structural_concrete", 20.0, "پی"),
        _rec("Schedule: SC.txt", "FT-1", "structural_concrete", 10.0, "پی"),
        _rec("Schedule: SC.txt", "FT-2", "structural_concrete", 20.0, "پی"),
        _rec("Schedule: SC.txt", "LC-9", "structural_concrete", 5.0, "پی"),
        _rec("Schedule: SC.txt", "C1", "structural_concrete", 7.0, "پله"),
        _rec("Schedule: LC.txt", "LC-9", "lean_concrete", 5.0, "پی"),
    ]
    tables = [_formwork_table([("FT-1", "Wall Foundation: WF_A_1800x900", 10.0),
                               ("FT-2", "Wall Foundation: WF_A_2000x1000", 5.0),
                               ("FT-9", "Wall Foundation: WF_A_1000x1000", 3.0)])]
    direct, derived = eng._foundation_candidates(recs, tables)
    assert sorted(r["ref"] for r in direct) == ["FT-1", "FT-2"]     # هر المان فقط یک‌بار
    assert {r["source"] for r in direct} == {"Schedule: FC.txt"}   # منبع اختصاصی برنده است
    assert sum(r["qty"] for r in direct) == pytest.approx(30.0)
    assert "LC-9" not in {r["ref"] for r in direct}                # بتن مگر وارد 080301 نمی‌شود
    assert [r["ref"] for r in derived] == ["FT-9"]                 # fallback فقط per-ref
    assert derived[0]["qty"] == pytest.approx(3.0)


def test_G1_derived_is_used_only_when_no_direct_source():
    eng = TechnicalOfficeEngine([], default_settings())
    tables = [_formwork_table([("FT-1", "Wall Foundation: WF_A_1800x900", 10.0)])]
    direct, derived = eng._foundation_candidates([], tables)
    assert direct == []
    assert len(derived) == 1
    assert derived[0]["qty"] == pytest.approx(16.2)                # 10 × 1.8 × 0.9


# ── G2 ──

def test_G2_unlabeled_numeric_row_is_grand_total_not_record():
    text = ('"جدول نمونه"\n'
            '"Mark","Family and Type","Volume"\n'
            '"LC-01","Foundation Slab: 100mm","18.65 m³"\n'
            '"","","18.65 m³"\n')
    table = RevitScheduleParser.parse("g2.txt", text)
    assert len(table["rows"]) == 1
    assert table["grand_total"].get("volume") == pytest.approx(18.65)


# ── دادهٔ واقعی: شکاف‌های classification و مقادیر end-to-end ──

def test_real_exports_classification_has_no_unknown():
    tables = _raw_tables()
    assert len(tables) == 10
    kinds = {t["file_name"]: t["kind"] for t in tables}
    assert kinds[FOUNDATION_CONCRETE] == "structural_concrete"
    assert kinds[SUPER_FORMWORK] == "formwork_super"
    assert "unknown" not in set(kinds.values())


def test_real_exports_foundation_and_stair_quantities():
    tables = _raw_tables()
    foundation = next(t for t in tables
                      if t["kind"] == "structural_concrete" and len(t["rows"]) == 13)
    # سطر جمع بدون برچسب، دیگر رکورد نیست و به‌عنوان Grand total ثبت شده است
    assert foundation["grand_total"].get("volume") == pytest.approx(152.84, abs=0.02)

    res = _engine().compute(tables, None)
    by_id = {l["id"]: l for l in res["lines"]}
    assert res["quality"]["tables_unknown"] == 0

    # G1: حجم پی فقط یک‌بار و از یک منبع (نه direct، نه derived، نه LC-01)
    # مرحلهٔ ۱۳ (ایراد ۱): پی از نام متریال Revit ۳۵ مگاپاسکال → ۰۸۰۱۰۸؛
    # پله ۲۰ مگاپاسکال (تنظیم) → ۰۸۰۱۰۵. ردیف‌های جداگانه می‌مانند.
    found = next(l for l in res["lines"] if l["id"] == "conc-foundation")
    assert found["code"] == "080108"
    assert found["qty"] == pytest.approx(152.83, abs=0.02)
    assert len({s["source"] for s in found["sources"]}) == 1
    assert all("LC-01" not in str(s.get("ref")) for s in found["sources"])
    assert by_id["lean"]["code"] == "080102"
    assert by_id["lean"]["qty"] == pytest.approx(18.65, abs=0.02)

    # G3: بتن پله و قالب پله فقط سطرهای واقعی پله
    stair = next(l for l in res["lines"] if l["code"] == "080105" and l["id"] == "conc-stair")
    assert stair["qty"] == pytest.approx(7.18, abs=0.02)
    assert len(stair["sources"]) == 2
    assert by_id["form-stair"]["code"] == "060701"
    assert by_id["form-stair"]["qty"] == pytest.approx(69.0, abs=0.5)
    assert len(by_id["form-stair"]["sources"]) == 2
