# -*- coding: utf-8 -*-
# T117 — پاریتیِ اثرِ واقعیِ تصمیمات (فاز E-9 §۱).
#
# این آزمون‌ها اثرِ هر تصمیمِ باز را با اجرای واقعیِ موتور روی پروژهٔ مرجع
# اندازه می‌گیرند و عدد را قفل می‌کنند. آینهٔ test_T117_decision_impact.ts.
# منبعِ اعداد: tools/decision_impact.py → docs/decision_impact.csv.
#
# نکتهٔ مهم: D-03 و D-13 اثرشان صفر **نیست** (برخلافِ مستنداتِ E-6) —
# اینجا با عدد اثبات می‌شود.
import os
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, RevitScheduleParser,
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

PROV_COEF = 1.1530518586507572
BASE = dict(tadil_enabled=True, tadil_approved=True,
            proposal_date="۱۴۰۳/۱۲/۲۹",
            baravord_enabled=True, baravord_approved=True,
            work_period_start="۱۴۰۴/۰۱/۰۱", work_period_end="۱۴۰۵/۰۲/۱۵",
            provisional_coef_1405q1=PROV_COEF)

NEW1E9 = dict(new_item_amount=1e9, new_item_base_period="1404Q1")

# id | فلپ | فلپِ پایه (اگر متفاوت) | ΔP | برآورد
SCENARIOS = [
    ("D-01", dict(completed_within_term=True), None,
     10489594369.074144, 45437742820.323151),
    ("D-03", dict(coef_rounding_2080=False), None,
     9937407877.639488, 45437742820.323151),
    ("D-04", dict(negative_coef_rounding="toward_zero"), None,
     9984277408.217051, 45437742820.323151),
    ("D-08", dict(fault_deduction_on_negative=True), None,
     9984277408.217051, 45437742820.323151),
    ("D-09", dict(provisional_diff_method="own_period"), None,
     9984277408.217051, 45437742820.323151),
    ("D-10", dict(contract_extensions=[
        dict(date="۱۴۰۵/۰۲/۱۵", months=3, kind="مجاز",
             doc_no="سناریوی ابزار")]), None,
     9984277408.217051, 45437742820.323151),
    ("D-11", dict(index_method="رشته‌ای"), None,
     9725954520.896103, 46172170291.967438),
    ("D-13", dict(index_method="رشته‌ای"), None,
     9725954520.896103, 46172170291.967438),
    ("D-14", dict(NEW1E9, new_item_method="فهرست پیمان"), None,
     10294107505.304430, 46908603903.783905),
    ("D-15", dict(NEW1E9, new_item_method="قیمت روز"),
     dict(new_item_amount=1e9, new_item_base_period="",
          new_item_method="قیمت روز"),
     10265165355.642443, 46771206401.056770),
    ("D-16", dict(NEW1E9, new_item_method="قیمت روز"),
     dict(NEW1E9, new_item_method="فهرست پیمان"),
     10265165355.642443, 46771206401.056770),
]

# اثرِ مورد انتظار (فلپ − پایه) به ریال
EFFECTS = {
    "D-01": (505316960.86, 0.0),
    "D-03": (-46869530.58, 0.0),
    "D-04": (0.0, 0.0),
    "D-08": (0.0, 0.0),
    "D-09": (0.0, 0.0),
    "D-10": (0.0, 0.0),
    "D-11": (-258322887.32, 734427471.64),
    "D-13": (-258322887.32, 734427471.64),
    "D-14": (309830097.09, 1470861083.46),
    "D-15": (280887947.43, 1333463580.73),
    "D-16": (-28942149.66, -137397502.73),
}

BASE_DELTA_P = 9984277408.217051
BASE_BARAVORD = 45437742820.323151


def _pipeline(settings):
    tables = []
    for fname in sorted(os.listdir(REVIT_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fname), "r",
                      encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fname, fh.read()))
    results = []
    for root, _dirs, fnames in os.walk(DYNAMO_DIR):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    map_df = DynamoMappingParser.merge_formats(results)
    return TechnicalOfficeEngine(_default_fehrest_db(), settings).compute(
        tables, map_df)


def _on(**extra):
    s = default_settings()
    s.update(BASE)
    s.update(extra)
    return s


def _metrics(r):
    t = (r.get("adjustment") or {}).get("tadil") or {}
    b = (r.get("adjustment") or {}).get("baravord") or {}
    return t.get("delta_p"), b.get("result_amount")


def test_T117_baseline_reference():
    dp, bar = _metrics(_pipeline(_on()))
    assert dp == pytest.approx(BASE_DELTA_P, rel=1e-9)
    assert bar == pytest.approx(BASE_BARAVORD, rel=1e-9)


@pytest.mark.parametrize("sid,flip,base_flip,exp_dp,exp_bar", SCENARIOS,
                         ids=[s[0] for s in SCENARIOS])
def test_T117_decision_impact(sid, flip, base_flip, exp_dp, exp_bar):
    dp, bar = _metrics(_pipeline(_on(**flip)))
    assert dp == pytest.approx(exp_dp, rel=1e-9)
    assert bar == pytest.approx(exp_bar, rel=1e-9)
    # اثر = فلپ − پایه (مستقل از عددِ ثابت)
    if base_flip is None:
        ref_dp, ref_bar = BASE_DELTA_P, BASE_BARAVORD
    else:
        ref_dp, ref_bar = _metrics(_pipeline(_on(**base_flip)))
    exp_ddp, exp_dbar = EFFECTS[sid]
    assert (dp - ref_dp) == pytest.approx(exp_ddp, abs=0.02)
    assert (bar - ref_bar) == pytest.approx(exp_dbar, abs=0.02)


def test_T117_d03_and_d13_are_not_zero():
    # مستنداتِ E-6 می‌گفتند صفر — این اجرا آن را رد می‌کند.
    assert EFFECTS["D-03"][0] != 0
    assert EFFECTS["D-13"][0] != 0
    assert EFFECTS["D-13"][1] != 0


def test_T117_ceiling_difference():
    # D-18: اختلافِ دو سقف
    bt = _pipeline(_on())["base_total"]
    gt = _pipeline(_on())["grand_total"]
    assert gt * 1.1 - bt * 1.1 == pytest.approx(8990157253.69, abs=0.02)
