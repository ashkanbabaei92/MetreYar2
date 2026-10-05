# -*- coding: utf-8 -*-
# T119 — فاز E-9 §۳.۳ (بند ۵: فصلِ حملِ ردیف‌های مترمکعب‌کیلومتر) و
#        فاز E-9 §۳.۶ (جانشانیِ خودکارِ موقت→قطعی).
#
# §۳.۳ — بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵ (صفحهٔ ۲): ردیف‌های پایه‌ای با
#        واحدِ «مترمکعب کیلومتر» که حملِ آن‌ها در فصل‌های غیر از فصل حمل
#        منظور شده، با شاخص‌های فصل حمل همان رشته تعدیل می‌شوند.
# §۳.۶ — بند ۳ بخشنامهٔ ۱۴۴۳۷۳: هنگامی که شاخصِ قطعیِ یک سه‌ماههٔ ۱۴۰۵
#        اعلام و وارد شد، موتورها خودبه‌خود از آن استفاده می‌کنند.
#
# همتایِ TypeScript این آزمون: tests/char_ts/test_T119_clause5_definitive.ts
import copy
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import app  # noqa: E402  (برای monkeypatchِ INDEX_BULLETINS)

from app import (TechnicalOfficeEngine, _default_fehrest_db,  # noqa: E402
                 default_settings)

# شاخص‌های قطعی استخراج‌شده از پیوست ۳ (بخشنامهٔ ۱۵۵۲۳۳)
CH06 = (7273.8, 10632.1)                           # فصل ۶ قالب‌بندی — صفحهٔ ۶
CH28 = (13243.1, 18897.9)                          # فصل ۲۸ حمل‌ونقل — صفحهٔ ۷
A_TEST = 10_000_000_000.0
PROV_COEF = 1.1530518586507572
OH, REG, PROP = 1.3, 1.04, 1.0
PRICE_MULT = OH * REG * PROP
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"


def _ctx(chapters=None, base=A_TEST, haul_moved=0.0):
    return {"chapter_amounts": chapters or {"06": base},
            "haul_moved_amount": haul_moved,
            "floors_amount": base, "base_total": base, "site_setup": 0.0,
            "advance_payment": 0.0,
            "overhead_coef": OH, "regional_coef": REG,
            "grand_total": base * PRICE_MULT,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": base, "excluded_total": 0.0}}


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["tadil_approved"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    return s


def _eng(**extra):
    """موتور با تنظیماتِ روشنِ موتور تعدیل (تاریخ تسلیم پیشنهاد الزامی است)."""
    return TechnicalOfficeEngine(_default_fehrest_db(), _on(**extra))


def _patch_definitive(monkeypatch, quarters, disciplines=None, chapters=None):
    """جایگزینیِ بخشِ definitive_1405 با دادهٔ آزمون (کپیِ عمیقِ config)."""
    cfg = copy.deepcopy(app.INDEX_BULLETINS)
    cfg["definitive_1405"] = {
        "quarters": quarters,
        "disciplines": disciplines if disciplines is not None else [],
        "chapters_abnieh": chapters if chapters is not None else [],
    }
    monkeypatch.setattr(app, "INDEX_BULLETINS", cfg)


# ═════════ §۳.۳ — بند ۵: واحدِ حمل ═════════

def test_T119_haul_unit_matching():
    e = TechnicalOfficeEngine
    # واحدهایِ حمل (با فاصله/خط‌تیره/نیم‌فاصله)
    assert e._is_haul_unit("مترمکعب کیلومتر") is True
    assert e._is_haul_unit("مترمکعب - کیلومتر") is True
    assert e._is_haul_unit("مترمکعب‌کیلومتر") is True       # نیم‌فاصله
    assert e._is_haul_unit("مکعب کیلومتر") is True
    # واحدهایِ غیرحمل
    assert e._is_haul_unit("مترمکعب") is False
    assert e._is_haul_unit("کیلوگرم") is False
    assert e._is_haul_unit("متر مربع") is False
    assert e._is_haul_unit("") is False
    assert e._is_haul_unit(None) is False
    # فصلِ حملِ پیش‌فرض = ۲۸
    assert e._haul_target_chapter() == "28"


def test_T119_haul_disabled_when_config_off(monkeypatch):
    cfg = copy.deepcopy(app.INDEX_BULLETINS)
    cfg.setdefault("clause5_haul", {})["enabled"] = False
    monkeypatch.setattr(app, "INDEX_BULLETINS", cfg)
    assert TechnicalOfficeEngine._is_haul_unit("مترمکعب کیلومتر") is False


def test_T119_haul_note_emitted_when_amount_moved():
    eng = _eng()
    warns = []
    t = eng._tadil_engine(_ctx(chapters={"06": A_TEST, "28": 2_000_000_000.0},
                               haul_moved=2_000_000_000.0), warns)
    assert not t.get("error")
    notes = [w for w in warns if w.get("item") == "clause5_haul"]
    assert len(notes) == 1
    assert notes[0]["level"] == "اطلاع"
    assert "فصل ۲۸" in notes[0]["message"]
    assert notes[0]["ref"] == "بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵"


def test_T119_haul_note_absent_when_nothing_moved():
    eng = _eng()
    warns = []
    eng._tadil_engine(_ctx(chapters={"06": A_TEST}, haul_moved=0.0), warns)
    assert all(w.get("item") != "clause5_haul" for w in warns)


def test_T119_haul_note_not_in_baravord():
    """بند ۵ فقط یک یادداشتِ اطلاعاتی است؛ برآورد به‌هنگام هم آن را می‌دهد
    (هر دو موتور از همان chapter_amounts استفاده می‌کنند) ولی زنجیرهٔ مالی
    و خروجیِ عددی هر موتور مستقل می‌مانند (قاعدهٔ طلایی ۵)."""
    eng = _eng()
    warns = []
    b = eng._baravord_engine(_ctx(chapters={"06": A_TEST, "28": 1_000_000_000.0},
                                  haul_moved=1_000_000_000.0), warns)
    assert not b.get("error")
    assert any(w.get("item") == "clause5_haul" for w in warns)


# ═════════ §۳.۶ — جانشانیِ خودکارِ موقت→قطعی ═════════

def test_T119_definitive_field_naming():
    e = TechnicalOfficeEngine
    assert e._definitive_field("1405Q1") == "q1_1405"
    assert e._definitive_field("1405Q2") == "q2_1405"
    assert e._definitive_field("1405Q4") == "q4_1405"
    assert e._definitive_field("garbage") is None
    assert e._definitive_field(None) is None


def test_T119_no_definitive_by_default():
    eng = _eng()
    assert eng._quarter_has_definitive("1405Q1") is False
    assert eng._quarter_has_definitive("1405Q2") is False
    assert eng._quarter_has_definitive("1404Q4") is False
    # مسیرِ موقت همچنان برقرار است
    v, st = eng._quarter_index("06", "1405Q1", PROV_COEF)
    assert v == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)
    assert st == "موقت"


def test_T119_announced_without_rows_stays_provisional(monkeypatch):
    """فقط announced=true کافی نیست؛ باید ردیفِ مقدار هم وارد شده باشد
    (قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود)."""
    _patch_definitive(monkeypatch,
                      quarters={"1405Q1": {"announced": True}})
    eng = _eng()
    assert eng._quarter_has_definitive("1405Q1") is False
    v, st = eng._quarter_index("06", "1405Q1", PROV_COEF)
    assert v == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)
    assert st == "موقت"


def test_T119_announced_false_stays_provisional(monkeypatch):
    _patch_definitive(monkeypatch,
                      quarters={"1405Q1": {"announced": False}},
                      disciplines=[{"name": "ابنیه", "q1_1405": 16000.0}],
                      chapters=[{"chapter": "06", "q1_1405": 12000.0}])
    eng = _eng()
    assert eng._quarter_has_definitive("1405Q1") is False
    v, st = eng._quarter_index("06", "1405Q1", PROV_COEF)
    assert st == "موقت"


def test_T119_definitive_replaces_provisional(monkeypatch):
    _patch_definitive(monkeypatch,
                      quarters={"1405Q1": {"announced": True}},
                      disciplines=[{"name": "ابنیه", "q1_1405": 16000.0,
                                    "page": 9}],
                      chapters=[{"chapter": "06", "q1_1405": 12000.0,
                                 "page": 9}])
    eng = _eng()
    assert eng._quarter_has_definitive("1405Q1") is True
    # فصل: مقدارِ قطعیِ مستقیم
    v, st = eng._quarter_index("06", "1405Q1", PROV_COEF)
    assert (v, st) == (12000.0, "قطعی")
    # رشته: مقدارِ قطعیِ مستقیم
    vd, std = eng._quarter_discipline("1405Q1", PROV_COEF)
    assert (vd, std) == (16000.0, "قطعی")
    # سه‌ماههٔ بعدتر هنوز اعلام نشده ⇒ همان مسیرِ موقت
    v2, st2 = eng._quarter_index("06", "1405Q2", PROV_COEF)
    assert v2 == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)
    assert st2 == "موقت"
    # ۱۴۰۴Q4 (قطعیِ پیوست ۳) دست‌نخورده می‌ماند
    v3, st3 = eng._quarter_index("06", "1404Q4", PROV_COEF)
    assert (v3, st3) == (CH06[1], "قطعی")


def test_T119_definitive_partial_chapter_falls_back_to_provisional(monkeypatch):
    """اگر شاخصِ قطعیِ یک فصلِ خاص وارد نشده باشد ولی فصلِ دیگری هست،
    همان فصل موقت می‌ماند (افتادن به مسیرِ موقت، نه حدس)."""
    _patch_definitive(monkeypatch,
                      quarters={"1405Q1": {"announced": True}},
                      chapters=[{"chapter": "08", "q1_1405": 15000.0}])
    eng = _eng()
    v, st = eng._quarter_index("06", "1405Q1", PROV_COEF)
    assert v == pytest.approx(CH06[1] * PROV_COEF, rel=1e-12)
    assert st == "موقت"


def test_T119_definitive_used_in_full_tadil(monkeypatch):
    _patch_definitive(monkeypatch,
                      quarters={"1405Q1": {"announced": True}},
                      chapters=[{"chapter": "06", "q1_1405": 12000.0}])
    eng = _eng(work_period_start="۱۴۰۴/۰۱/۰۱", work_period_end="۱۴۰۵/۰۲/۱۵")
    warns = []
    t = eng._tadil_engine(_ctx(chapters={"06": A_TEST}), warns)
    assert not t.get("error")
    # شاخصِ قطعیِ واردشده در جدولِ فصل × سه‌ماهه ظاهر می‌شود
    rows = {r["chapter"]: r for r in (t.get("chapters") or [])}
    assert "06" in rows
    q1 = [(_q, _iv, _st) for _q, _iv, _st in (rows["06"].get("quarters") or [])
          if _q == "1405Q1"]
    assert q1, "خروجی موتور باید ردیفِ ۱۴۰۵Q1 را داشته باشد"
    assert q1[0][1] == 12000.0
    assert q1[0][2] == "قطعی"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
