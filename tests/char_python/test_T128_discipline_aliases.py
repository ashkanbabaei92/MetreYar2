# -*- coding: utf-8 -*-
# T128 — نگاشتِ املای ۱۱ نام رشته (فاز E-10 §۴).
#
# نامِ ۱۱ رشته در PDF رسمیِ بخشنامهٔ ۱۴۴۳۷۳ با املایِ متفاوتی از
# کلیدهای m_by_discipline در config ظاهر می‌شود (تفاوت در همزه،
# نیم‌فاصله، یا ترتیبِ شکستنِ سطرها در استخراج). جدولِ m_aliases در
# config/provisional_m.json نامِ رسمیِ PDF (canonical) را به کلیدِ config
# (alias) نگاشت می‌کند و موتور هر دو را می‌پذیرد.
#
# این آزمون قفل می‌کند:
#   ۱) هر دو املا برای هر ۱۱ نام، coef یکسانی برمی‌گردانند (دقیقاً مساوی)؛
#   ۲) trace نشان می‌دهد کدام املا استفاده شده (discipline_key)؛
#   ۳) هیچ کلیدِ موجودی از m_by_discipline حذف نشده است؛
#   ۴) نامِ ناشناخته همچنان None می‌دهد (قاعدهٔ طلایی: حدس زده نمی‌شود).
# آینهٔ test_T128_discipline_aliases.ts.
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import TechnicalOfficeEngine, _default_fehrest_db, default_settings

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CFG = json.load(open(os.path.join(ROOT, "config", "provisional_m.json"),
                     encoding="utf-8"))
CPI = json.load(open(os.path.join(ROOT, "config", "cpi_monthly.json"),
                     encoding="utf-8"))["months"]

# جفت‌ها از خودِ config خوانده می‌شوند (منبعِ واحد) — کلیدِ «_note»
# توضیح است و جزو aliasها نیست.
ALIASES = {k: v for k, v in CFG["m_aliases"].items() if not k.startswith("_")}


def _expected_coef(m):
    """coef مورد انتظار از فرمولِ ۱۴۴۳۷۳ و CPIهای واقعیِ config."""
    num = CFG["meta"]["numerator_month"]
    den = CFG["meta"]["denominator_months"]
    n_v = float(CPI[str(num["year"])][str(num["month"])])
    d_vs = [float(CPI[str(d["year"])][str(d["month"])]) for d in den]
    return 1.0 + float(m) * (n_v / (sum(d_vs) / len(d_vs)) - 1.0)


@pytest.fixture(scope="module")
def eng():
    return TechnicalOfficeEngine(_default_fehrest_db(), default_settings())


def test_T128_alias_table_shape():
    assert len(ALIASES) == 11, "باید ۱۱ نام باشد"
    table = CFG["m_by_discipline"]
    # هر alias به یک کلیدِ موجود اشاره می‌دهد (کلیدی حذف نمی‌شود)
    for cano, key in ALIASES.items():
        assert key in table, "%s باید در m_by_discipline باشد" % key
        assert cano != key or cano in table  # مواردِ یکسان هم موجودند
    # canonicalها یکتا هستند
    assert len(set(ALIASES)) == 11


def test_T128_no_key_removed():
    """کلیدهای فعلیِ m_by_discipline باید همه همچنان موجود باشند."""
    assert "ابنیه" in CFG["m_by_discipline"]
    assert CFG["m_by_discipline"]["ابنیه"] == 0.7
    assert CFG["m_by_discipline"]["توزیع نیروی برق"] == 1.1


@pytest.mark.parametrize("cano,key", sorted(ALIASES.items()))
def test_T128_both_spellings_same_value(eng, cano, key):
    # هر دو املا
    c_can, st_can, tr_can = eng._provisional_coef_1405q1(cano)
    c_key, st_key, tr_key = eng._provisional_coef_1405q1(key)
    assert st_can == "محاسبه‌شده", "%s → %s" % (cano, st_can)
    assert st_key == "محاسبه‌شده"
    # دقیقاً مساوی (bit-identical در همان زبان)
    assert c_can == c_key
    assert c_can == pytest.approx(_expected_coef(CFG["m_by_discipline"][key]),
                                  rel=1e-12)
    # trace: نامِ درخواست‌شده و کلیدِ حل‌شده
    assert tr_can["discipline"] == cano
    assert tr_can["discipline_key"] == key
    assert tr_key["discipline_key"] == key
    assert tr_can["m"] == pytest.approx(CFG["m_by_discipline"][key], rel=1e-12)


def test_T128_unknown_still_none(eng):
    cx, stx, _t = eng._provisional_coef_1405q1("رشتهٔ ناشناخته")
    assert cx is None
    assert stx == "ناموجود"


def test_T128_exception_path_untouched(eng):
    """استثنای «به جز فصل ۱۵» همچنان با کلیدِ config کار می‌کند."""
    c, st, _t = eng._provisional_coef_1405q1("راهداری", chapter="15")
    assert c is None
    assert st == "استثنا"
