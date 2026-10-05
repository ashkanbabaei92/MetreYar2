# -*- coding: utf-8 -*-
# T97 (بخش دوم) — فاز E-6: اعداد مرجع موتور تعدیل با گردکردن بند ۸-۲
# و ردیف مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) روی دادهٔ مرجع پروژه.
#
# اعداد مرجع (سناریوی §۱۴-۶، دورهٔ ۱۴۰۴/۰۱/۰۱ تا ۱۴۰۵/۰۲/۱۵):
#   گردکردن خاموش (میراث پیش از E-6):
#     ΔP       = ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴    قطعی = ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰
#     علی‌الحساب = ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴
#   گردکردن روشن (پیش‌فرض E-6، بند ۸-۲):
#     ΔP       = ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲    قطعی = ۷٬۷۶۱٬۰۴۵٬۲۰۹٫۹۴
#     علی‌الحساب = ۲٬۲۲۳٬۲۳۲٬۱۹۸٫۲۸
#   گردکردن روشن + completed_within_term = True (k = ۱، تبصرهٔ ۲):
#     ΔP       = ۱۰٬۴۸۹٬۵۹۴٬۳۶۹٫۰۷   k_diff = ۵۰۵٬۳۱۶٬۹۶۰٫۸۶ (بند ۸-۴)
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 ExcelExporter,
                 _default_fehrest_db, default_settings, round_coef_2080)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")
PROV_COEF = 1.1530518586507572
PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"

REF = dict(baravord_enabled=True,
           work_period_start="۱۴۰۴/۰۱/۰۱",
           work_period_end="۱۴۰۵/۰۲/۱۵",
           provisional_coef_1405q1=PROV_COEF)
REF_ALLDEF = dict(baravord_enabled=True,
                  work_period_start="۱۴۰۴/۰۱/۰۱",
                  work_period_end="۱۴۰۴/۱۲/۲۹",
                  provisional_coef_1405q1=PROV_COEF)

# اعداد خام موتور (دقیق) — از اجرای مرجع
DP_ROUND = 9984277408.217051
DP_ROUND_DEF = 7761045209.936075
DP_ROUND_PROV = 2223232198.280975
DP_ROUND_SPLIT = (9984277408.22, 7761045209.94, 2223232198.28)

DP_LEGACY = 9937407877.639488
DP_LEGACY_SPLIT = (9937407877.64, 7709893479.40, 2227514398.24)

DP_CWT = 10489594369.074144
K_DIFF = 505316960.857094


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


def _split(total, first):
    return TechnicalOfficeEngine(_default_fehrest_db(), default_settings())._split_rounded(
        total, first, 2)


def test_T97_rounding_on_is_default():
    assert default_settings()["coef_rounding_2080"] is True


def test_T97_coef_rows_carry_raw_and_used():
    res = _pipeline(_on(**REF))
    t = res["adjustment"]["tadil"]
    assert t["coef_rounding"] is True
    for r in t["chapters"]:
        assert r["coef_rows"], r["chapter"]
        for _q, raw, used in r["coef_rows"]:
            assert used == pytest.approx(round_coef_2080(raw), abs=1e-12)
    sr = t.get("setup_row")
    if sr:
        assert sr["delta_k095"] is not None


def test_T97_delta_p_rounding_on_reference():
    t = _pipeline(_on(**REF))["adjustment"]["tadil"]
    assert t["delta_p"] == pytest.approx(DP_ROUND, rel=1e-9)
    assert t["delta_p_definitive"] == pytest.approx(DP_ROUND_DEF, rel=1e-9)
    assert t["delta_p_provisional"] == pytest.approx(DP_ROUND_PROV, rel=1e-9)
    # نامساوی کلیدی: قطعی + علی‌الحساب ≡ ΔP (دقیق)
    assert t["delta_p_definitive"] + t["delta_p_provisional"] \
        == pytest.approx(t["delta_p"], rel=1e-12)
    r, a, b = _split(t["delta_p"], t["delta_p_definitive"])
    assert a + b == r
    assert (r, a, b) == pytest.approx(DP_ROUND_SPLIT, abs=1e-6)


def test_T97_delta_p_legacy_values_with_rounding_off():
    t = _pipeline(_on(coef_rounding_2080=False, **REF))["adjustment"]["tadil"]
    assert t["coef_rounding"] is False
    assert t["delta_p"] == pytest.approx(DP_LEGACY, rel=1e-9)
    r, a, b = _split(t["delta_p"], t["delta_p_definitive"])
    assert a + b == r
    assert (r, a, b) == pytest.approx(DP_LEGACY_SPLIT, abs=1e-6)


def test_T97_no_k_diff_when_cwt_unset():
    t = _pipeline(_on(**REF))["adjustment"]["tadil"]
    assert t["completed_within_term"] is False
    assert t["k_diff"] == 0.0
    t2 = _pipeline(_on(completed_within_term=None, **REF))["adjustment"]["tadil"]
    assert t2["k_diff"] == 0.0


def test_T97_tabsare2_k_diff_added_to_definitive():
    t_true = _pipeline(_on(completed_within_term=True, **REF))["adjustment"]["tadil"]
    t_false = _pipeline(_on(completed_within_term=False, **REF))["adjustment"]["tadil"]
    assert t_true["coef"] == 1.0
    assert t_true["completed_within_term"] is True
    # مابه‌التفاوت k = ۱ نسبت به k = ۰٫۹۵ (تبصرهٔ ۲)
    assert t_true["k_diff"] == pytest.approx(K_DIFF, abs=0.01)
    assert t_true["k_diff"] == pytest.approx(
        t_true["delta_p"] - t_false["delta_p"], abs=0.01)
    assert t_true["delta_p"] == pytest.approx(DP_CWT, rel=1e-9)
    # invariant کلی حفظ می‌شود
    assert t_true["delta_p_definitive"] + t_true["delta_p_provisional"] \
        == pytest.approx(t_true["delta_p"], rel=1e-12)
    r, a, b = _split(t_true["delta_p"], t_true["delta_p_definitive"])
    assert a + b == r


def test_T97_tabsare2_all_definitive_moves_k_diff_to_definitive():
    # وقتی همهٔ شاخص‌ها cuttei هستند، کل ΔP قطعی است و k_diff
    # طبق بند ۸-۴ به بخش قطعی افزوده می‌شود (تبصرهٔ ۲).
    t = _pipeline(_on(completed_within_term=True, **REF_ALLDEF))
    t = t["adjustment"]["tadil"]
    assert t["delta_p_definitive"] == pytest.approx(
        t["delta_p"] + t["k_diff"], rel=1e-9)
    assert t["delta_p_provisional"] == pytest.approx(-t["k_diff"], rel=1e-9)
    assert t["k_diff"] > 0

META_XLS = {"report_type": "دوره‌ای", "report_no": "۱",
            "contract_no": "۱", "project_name": "پروژه نمونه",
            "employer": "کارفرما", "contractor": "پیمانکار",
            "consultant": "مشاور", "period_start": "۱۴۰۴/۰۱/۰۱",
            "period_end": "۱۴۰۴/۰۳/۳۱", "location": "گرگان",
            "contract_date": "۱۴۰۴/۰۱/۰۱"}


def _export_xlsx(settings):
    import zipfile
    res = _pipeline(settings)
    data = ExcelExporter().export(META_XLS, res, settings, [])
    shared = zipfile.ZipFile(io.BytesIO(data)).read(
        "xl/sharedStrings.xml").decode("utf-8")
    return res, shared


def test_T97_excel_tadil_sheet_has_coefficient_table():
    # فاز E-6 (بند ۸-۲): جدول ضریب خام/گردشده در شیت تعدیل پیمان
    _, shared = _export_xlsx(_on(**REF))
    assert "ضریب تعدیل هر فصل در هر سه‌ماههٔ کارکرد" in shared
    assert "ضریب خام" in shared
    assert "ضریب گردشده" in shared


def test_T97_excel_ghati_sheet_kdiff_row_only_when_completed():
    # فاز E-6 (بند ۸-۴): ردیف مابه‌التفاوت فقط وقتی کار تمام شده باشد
    _, shared_off = _export_xlsx(_on(**REF))
    # برچسب ردیف تبصرهٔ ۲ فقط وقتی کار تمام شده باشد ظاهر می‌شود
    # (متنِ توضیحی رجیستری pending این رشته را ندارد)
    assert "مابه‌التفاوت k = ۰٫۹۵ → ۱" not in shared_off
    _, shared_on = _export_xlsx(_on(completed_within_term=True, **REF))
    assert "مابه‌التفاوت k = ۰٫۹۵ → ۱" in shared_on
    assert "همزمان با صورت‌وضعیت قطعی پرداخت" in shared_on
