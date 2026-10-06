# -*- coding: utf-8 -*-
# T124 — فاز E-10 §۰ — دامنهٔ دستورالعمل ۱۴۰۳/۷۴۴۳۱۷ (۱۴۰۳/۱۲/۲۹).
#
# [SRC: بخشنامهٔ ۷۴۴۳۱۷/۱۴۰۳، صفحه ۱، بند ۲]:
#   «این بخشنامه صرفاً به رشته‌های مشخص شده در جدول زیر اعمال می‌شود.»
# موضوعِ دستورالعمل «رشته‌های بهره‌برداری، نگهداری و خدماتی» است و «ابنیه»
# و سایر رشته‌های ساختمانی در جدول نیستند. پس قاعدهٔ ماکزیمم
# [SRC: بخشنامهٔ ۶۶۶۳۱۲/۱۴۰۴، صفحه ۲، بند ۵] برای پروژهٔ ابنیه‌محور N/A است.
#
# این آزمون قفل می‌کند:
#   ۱) _project_discipline پیش‌فرض «ابنیه» است و تنظیمات regional_selection
#      را می‌خواند (رشتهٔ خالی/نامعتبر ⇒ پیش‌فرض)؛
#   ۲) موتور قاعدهٔ ماکزیمم را برای ابنیه اعمال نمی‌کند — حتی اگر
#      جدولِ ۷۴۴۳۱۷ با شاخصِ بسیار بزرگ پر شده باشد (N/A)؛
#   ۳) رشتهٔ مشمول ⇒ هشدارِ pending_d (نیازمندِ عددِ d)؛
#   ۴) دادهٔ جدولِ ۷۴۴۳۱۷ در config با PDF یکی است.
import copy
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import app as _app
from app import TechnicalOfficeEngine, _default_fehrest_db, default_settings

PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"                       # ⇒ Io = اسفند ۱۴۰۳
CH06 = (7273.8, 10632.1)                            # فصل ۶ — پیوست ۳ ۱۵۵۲۳۳
A_TEST = 10_000_000_000.0
OH, REG, PROP = 1.3, 1.04, 1.0
PRICE_MULT = OH * REG * PROP


def _ctx():
    return {"chapter_amounts": {"06": A_TEST}, "floors_amount": A_TEST,
            "base_total": A_TEST, "site_setup": 0.0, "advance_payment": 0.0,
            "overhead_coef": OH, "regional_coef": REG,
            "grand_total": A_TEST * PRICE_MULT,
            "floors_info": {"value": 1.0, "status": "کامل",
                            "eligible_total": A_TEST, "excluded_total": 0.0}}


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s["work_period_start"] = "۱۴۰۴/۱۰/۰۱"
    s["work_period_end"] = "۱۴۰۴/۱۲/۳۰"
    s.update(extra)
    return s


def _adj(settings, cfg=None, warns=None):
    warns = [] if warns is None else warns
    if cfg is not None:
        _app.INDEX_BULLETINS = cfg          # fixture.globally درج می‌شود
    eng = TechnicalOfficeEngine(_default_fehrest_db(), settings)
    return eng._adjustment(_ctx(), warns), warns


@pytest.fixture
def real_cfg():
    _saved = _app.INDEX_BULLETINS
    yield copy.deepcopy(_saved)
    _app.INDEX_BULLETINS = _saved


# ═════ §۰.۱ — رشتهٔ پروژه ═════

def test_T124_project_discipline_default():
    eng = TechnicalOfficeEngine(_default_fehrest_db(), default_settings())
    assert eng._project_discipline() == "ابنیه"


def test_T124_project_discipline_override_and_blank():
    s = default_settings()
    s["regional_selection"] = {"discipline": "راهداری"}
    assert TechnicalOfficeEngine(_default_fehrest_db(),
                                 s)._project_discipline() == "راهداری"
    s["regional_selection"] = {"discipline": "   "}
    assert TechnicalOfficeEngine(_default_fehrest_db(),
                                 s)._project_discipline() == "ابنیه"


# ═════ §۰.۲ — N/A برای ابنیه ═════

def test_T124_na_warning_for_abnieh(real_cfg):
    out, warns = _adj(_on(), cfg=real_cfg)
    _na = [x for x in warns if x["item"] == "instructions_744317_na"]
    assert _na, "هشدارِ N/A برای رشتهٔ ابنیه باید ظاهر شود"
    assert _na[0]["level"] == "اطلاع"
    assert "ابنیه" in _na[0]["message"]
    assert "N/A" in _na[0]["message"]
    # آیتمِ قدیمیِ بدونِ پسوند نباید ظاهر شود
    assert all(x["item"] != "instructions_744317" for x in warns)


def test_T124_max_rule_not_applied_for_abnieh(real_cfg):
    # حتی اگر جدولِ ۷۴۴۳۱۷ با شاخصِ بسیار بزرگ پر شود، موتور نباید
    # قاعدهٔ ماکزیمم را برای ابنیه اعمال کند (N/A — بند ۲).
    _cfg = copy.deepcopy(real_cfg)
    _cfg["instructions_744317"]["chapters_abnieh"] = [
        {"chapter": 6, "q4": 99999.0, "page": 1}]
    warns = []
    eng = TechnicalOfficeEngine(_default_fehrest_db(), _on())
    t = eng._tadil_engine(_ctx(), warns)
    r = t["chapters"][0]
    assert r["it"] == pytest.approx(CH06[1], rel=1e-12)


# ═════ §۰.۳ — رشتهٔ مشمول ⇒ pending_d ═════

def test_T124_pending_d_for_covered_discipline(real_cfg):
    _cfg = copy.deepcopy(real_cfg)
    _cfg["instructions_744317"]["disciplines"] = [
        {"name": "ابنیه", "rows": [{"chapters": [6], "m": 0.99}]}]
    _cfg["instructions_744317"]["chapters_abnieh"] = [
        {"chapter": 6, "q4": 99999.0, "page": 1}]
    out, warns = _adj(_on(), cfg=_cfg)
    _pd = [x for x in warns if x["item"] == "instructions_744317_pending_d"]
    assert _pd, "هشدارِ pending_d برای رشتهٔ مشمول باید ظاهر شود"
    assert _pd[0]["level"] == "اطلاع"
    assert "ابنیه" in _pd[0]["message"]
    assert "d" in _pd[0]["message"]
    assert all(x["item"] != "instructions_744317_na" for x in warns)
    # و باز هم قاعدهٔ ماکزیمم اعمال نمی‌شود (عدد d وارد نشده)
    eng = TechnicalOfficeEngine(_default_fehrest_db(), _on())
    t = eng._tadil_engine(_ctx(), [])
    assert t["chapters"][0]["it"] == pytest.approx(CH06[1], rel=1e-12)


# ═════ §۰.۴ — یکسان بودنِ جدولِ config با PDF ═════

def test_T124_config_scope_matches_pdf():
    b = _app.INDEX_BULLETINS["instructions_744317"]
    # [SRC: صفحه ۱، بند ۲]
    assert "صرفاً به رشته‌های مشخص شده" in b["scope_clause"]
    # [SRC: ۶۶۶۳۱۲، صفحه ۲، بند ۵]
    assert "بزرگ‌تر است، ملاک عمل" in b["max_rule"]
    assert "۶۶۶۳۱۲" in b["max_rule"]
    cov = set(b["covered_disciplines"])
    assert cov == {d["name"] for d in b["disciplines"]}
    assert len(cov) == 8
    assert "ابنیه" not in cov
    expected = {
        "بهره‌برداری و نگهداری تأسیسات آب شرب":
            [([1, 2, 3, 9], 0.35), ([4], 0.65), ([8], 0.70)],
        "بهره‌برداری و نگهداشت تجهیزات برقی، کنترلی و ابزار دقیق "
        "تأسیسات آب و فاضلاب": [([1], 0.70), ([2, 3], 0.45)],
        "بهره‌برداری و نگهداری از شبکه جمع‌آوری و خطوط انتقال فاضلاب":
            [([1, 2, 3, 4], 0.35)],
        "نگهداری و تعمیرات شبکه انتقال و فوق توزیع نیروی برق":
            [("همه فصل‌ها", 0.50)],
        "راهداری": [([24], 0.45)],
        "نگهداری، تعمیر روسازی و ابنیه خطوط راه‌آهن":
            [([1], 0.55), ([4], 0.70)],
        "پسماند": [([1, 9], 0.65), ([6, 11], 0.35), ([10], 0.40)],
        "فضای سبز": [([2, 5, 7, 9, 10, 12, 17], 0.55), ([1, 13], 0.40)],
    }
    by_name = {d["name"]: d for d in b["disciplines"]}
    assert set(by_name) == set(expected)
    for name, rows in expected.items():
        got = [(r["chapters"], r["m"]) for r in by_name[name]["rows"]]
        assert got == rows, name
