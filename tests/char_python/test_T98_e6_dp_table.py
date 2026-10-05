# -*- coding: utf-8 -*-
# T98 — فاز E-6 (بخش ۰): جدول کامل ΔP در ۶ ترکیب
#   گردکردن ضریب (بند ۸-۲) × completed_within_term (تبصرهٔ ۲ بند ۱-۸)
#
# سناریوی مرجع §۱۴-۶: دورهٔ ۱۴۰۴/۰۱/۰۱ تا ۱۴۰۵/۰۲/۱۵،
# proposal_date = ۱۴۰۳/۱۲/۲۹، provisional_coef_1405q1 = 1.1530518586507572.
#
# جدول ΔP (مقادیر گردشدهٔ ۲ رقمی که در گزارش نمایش داده می‌شوند):
#   ┌──────────┬─────┬────────────────┬────────────────┬────────────────┬───────────────┐
#   │گردکردن   │ cwt │      ΔP        │    قطعی        │  علی‌الحساب     │   k_diff     │
#   ├──────────┼─────┼────────────────┼────────────────┼────────────────┼───────────────┤
#   │  خاموش   │ ─   │ ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴│ ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰│ ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴│      ۰        │
#   │  خاموش   │ بله │۱۰٬۴۶۰٬۴۲۹٬۳۴۴٫۸۸│ ۸٬۶۳۸٬۶۹۸٬۸۱۳٫۹۹│ ۱٬۸۲۱٬۷۳۰٬۵۳۰٫۸۹│ ۵۲۳٬۰۲۱٬۴۶۷٫۲۴│
#   │  خاموش   │ خیر │ ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴│ ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰│ ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴│      ۰        │
#   │  روشن    │ ─   │ ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲│ ۷٬۷۶۱٬۰۴۵٬۲۰۹٫۹۴│ ۲٬۲۲۳٬۲۳۲٬۱۹۸٫۲۸│      ۰        │
#   │  روشن    │ بله │۱۰٬۴۸۹٬۵۹۴٬۳۶۹٫۰۷│ ۸٬۶۳۹٬۱۷۸٬۲۷۸٫۹۱│ ۱٬۸۵۰٬۴۱۶٬۰۹۰٫۱۶│ ۵۰۵٬۳۱۶٬۹۶۰٫۸۶│
#   │  روشن    │ خیر │ ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲│ ۷٬۷۶۱٬۰۴۵٬۲۰۹٫۹۴│ ۲٬۲۲۳٬۲۳۲٬۱۹۸٫۲۸│      ۰        │
#   └──────────┴─────┴────────────────┴────────────────┴────────────────┴───────────────┘
#
# بندهای مسبب:
#   - گردکردن خاموش ≡ میراث پیش از E-6 (بند ۸-۲ اعمال نمی‌شود).
#   - cwt = بله ⇒ k = ۱ (تبصرهٔ ۲ بند ۱-۸)؛ k_diff = ΔP(k=1) − ΔP(k=0.95)
#     که طبق بند ۸-۴ به بخش قطعی افزوده می‌شود.
#   - cwt = ─ و cwt = خیر از نظر عددی یکسان هستند (k = ۰٫۹۵)؛
#     تفاوت فقط در برچسب قطعی/علی‌الحساب بودن k است (بند ۸-۳).
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")
PROV_COEF = 1.1530518586507572
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"
REF = dict(baravord_enabled=True,
           work_period_start="۱۴۰۴/۰۱/۰۱",
           work_period_end="۱۴۰۵/۰۲/۱۵",
           provisional_coef_1405q1=PROV_COEF)

# مقادیر دقیق موتور (raw) — از اجرای مرجع
RAW = {
    (False, None):  (9937407877.639488, 7709893479.404506, 2227514398.234982, 0.0),
    (False, True):  (10460429344.88367, 8638698813.985767, 1821730530.897903, 523021467.244183),
    (False, False): (9937407877.639488, 7709893479.404506, 2227514398.234982, 0.0),
    (True, None):   (9984277408.21705, 7761045209.936075, 2223232198.280975, 0.0),
    (True, True):   (10489594369.074144, 8639178278.91072, 1850416090.163424, 505316960.857094),
    (True, False):  (9984277408.21705, 7761045209.936075, 2223232198.280975, 0.0),
}
# مقادیر گردشدهٔ نمایشی (۲ رقم اعشار)
SPLIT = {
    (False, None):  (9937407877.64, 7709893479.40, 2227514398.24),
    (False, True):  (10460429344.88, 8638698813.99, 1821730530.89),
    (False, False): (9937407877.64, 7709893479.40, 2227514398.24),
    (True, None):   (9984277408.22, 7761045209.94, 2223232198.28),
    (True, True):   (10489594369.07, 8639178278.91, 1850416090.16),
    (True, False):  (9984277408.22, 7761045209.94, 2223232198.28),
}
# برآورد به‌هنگام (موتور ۲) — از k و گردکردن مستقل است
BARAVORD = 45437742820.32315

COMBOS = [(False, None), (False, True), (False, False),
          (True, None), (True, True), (True, False)]


def _on(**extra):
    s = default_settings()
    s["tadil_enabled"] = True
    s["proposal_date"] = PROPOSAL_DATE
    s.update(extra)
    return s


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


def _tadil_of(rnd, cwt):
    return _pipeline(_on(coef_rounding_2080=rnd, completed_within_term=cwt, **REF))[
        "adjustment"]["tadil"]


def _split(total, first):
    return TechnicalOfficeEngine(_default_fehrest_db(), default_settings())._split_rounded(
        total, first, 2)


@pytest.mark.parametrize("rnd,cwt", COMBOS)
def test_T98_raw_engine_values(rnd, cwt):
    # بخش ۰: هر ۶ ترکیب با مقادیر دقیق موتور مطابق جدول بالا
    t = _tadil_of(rnd, cwt)
    dp, defi, prov, kdiff = RAW[(rnd, cwt)]
    assert t["delta_p"] == pytest.approx(dp, rel=1e-9)
    assert t["delta_p_definitive"] == pytest.approx(defi, rel=1e-9)
    assert t["delta_p_provisional"] == pytest.approx(prov, rel=1e-9)
    assert t["k_diff"] == pytest.approx(kdiff, rel=1e-9)
    assert t["coef"] == pytest.approx(1.0 if cwt is True else 0.95)


@pytest.mark.parametrize("rnd,cwt", COMBOS)
def test_T98_display_split_exact(rnd, cwt):
    # بخش ۰: تفکیک گردشدهٔ نمایشی؛ جمع قطعی + علی‌الحساب ≡ ΔP
    t = _tadil_of(rnd, cwt)
    r, a, b = _split(t["delta_p"], t["delta_p_definitive"])
    assert a + b == r
    assert (r, a, b) == pytest.approx(SPLIT[(rnd, cwt)], abs=1e-6)


@pytest.mark.parametrize("rnd,cwt", COMBOS)
def test_T98_invariant_def_plus_prov(rnd, cwt):
    # نامساوی کلیدی در هر ۶ ترکیب: قطعی + علی‌الحساب ≡ ΔP (دقیق)
    t = _tadil_of(rnd, cwt)
    assert t["delta_p_definitive"] + t["delta_p_provisional"] \
        == pytest.approx(t["delta_p"], rel=1e-12)


def test_T98_rounding_off_cwt_null_is_legacy():
    # بخش ۰ گام ۳: با گردکردن خاموش و cwt = ─ همهٔ اعداد
    # دقیقاً برابر پیش از فاز E-6 هستند.
    t = _tadil_of(False, None)
    assert t["delta_p"] == pytest.approx(9937407877.639488, rel=1e-12)
    r, a, b = _split(t["delta_p"], t["delta_p_definitive"])
    assert (r, a, b) == pytest.approx((9937407877.64, 7709893479.40, 2227514398.24),
                                      abs=1e-9)


@pytest.mark.parametrize("rnd", [False, True])
def test_T98_cwt_null_equals_cwt_false(rnd):
    # cwt = ─ و cwt = خیر از نظر عددی یکسانند (k = ۰٫۹۵)؛
    # فقط برچسب قطعی/علی‌الحساب بودن k فرق می‌کند (بند ۸-۳).
    t_none = _tadil_of(rnd, None)
    t_false = _tadil_of(rnd, False)
    for f in ("delta_p", "delta_p_definitive", "delta_p_provisional", "k_diff"):
        assert t_none[f] == pytest.approx(t_false[f], rel=1e-12)


@pytest.mark.parametrize("rnd", [False, True])
def test_T98_k_diff_is_cwt_delta(rnd):
    # تبصرهٔ ۲ بند ۱-۸: k_diff = ΔP(k=1) − ΔP(k=0.95)
    t_true = _tadil_of(rnd, True)
    t_false = _tadil_of(rnd, False)
    assert t_true["k_diff"] == pytest.approx(t_true["delta_p"] - t_false["delta_p"],
                                             abs=0.01)
    assert t_true["k_diff"] > 0
    assert t_false["k_diff"] == 0.0


@pytest.mark.parametrize("rnd,cwt", COMBOS)
def test_T98_baravord_independent_of_k_and_rounding(rnd, cwt):
    # موتور ۲ (برآورد به‌هنگام) نه k دارد و نه گردکردن بند ۸-۲؛
    # در هر ۶ ترکیب یکسان است.
    res = _pipeline(_on(coef_rounding_2080=rnd, completed_within_term=cwt, **REF))
    b = res["adjustment"]["baravord"]
    assert b["result_amount"] == pytest.approx(BARAVORD, rel=1e-12)
    assert b["grand_updated"] == pytest.approx(BARAVORD, rel=1e-12)


def test_T98_rounding_effect_is_small():
    # بند ۸-۲: اثر گردکردن روی ΔP کوچک است (کمتر از ۰٫۵٪)
    for cwt in (None, True, False):
        off, on = _tadil_of(False, cwt), _tadil_of(True, cwt)
        assert abs(on["delta_p"] - off["delta_p"]) / off["delta_p"] < 0.005
