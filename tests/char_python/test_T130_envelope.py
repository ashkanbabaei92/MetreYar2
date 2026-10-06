# -*- coding: utf-8 -*-
# T130 — بازهٔ حساسیتِ واقعی (فاز E-10.1 §۱).
#
# tools/make_decision_meeting.py چهار سناریوی envelope را با **اجرای همزمان**
# می‌سازد و در tools/meeting_scenarios.json می‌نویسد. این آزمون قفل می‌کند:
#   ۱) انتخابِ هر سناریو با اندازه‌گیریِ فردیِ تصمیم‌ها هم‌خوان است
#      (کمینه/بیشینه درست انتخاب شده‌اند)؛
#   ۲) کمینه ≤ پایه ≤ بیشینه برای هر دو سنجه (ΔP و برآورد)؛
#   ۳) اعداد و پهنای بازه در .md با JSON هم‌خوان‌اند؛
#   ۴) هر توصیه یک برچسبِ منبع دارد و ادعای اشتباهِ E-9 صریح رد می‌شود.
# آینهٔ test_T130_envelope.ts
import json
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MEET = os.path.join(ROOT, "tools", "meeting_scenarios.json")
IMPACT = os.path.join(ROOT, "tools", "decision_impact_scenarios.json")
MD = os.path.join(ROOT, "docs", "DECISION_MEETING.md")

with open(MEET, "r", encoding="utf-8") as _fh:
    M = json.load(_fh)
with open(IMPACT, "r", encoding="utf-8") as _fh:
    IMP = json.load(_fh)
R = IMP["results"]

FIX_IDS = ("D-14", "D-15", "D-16")
SETTING_IDS = [sc["id"] for sc in IMP["scenarios"]
               if sc["kind"] == "setting" and sc["id"] not in FIX_IDS]
FIX_VARIANTS = ("D-14", "D-15")

FA = "۰۱۲۳۴۵۶۷۸۹"


def _fmt(v, digits=2):
    """همان قالبِ fa_numِ ابزار: جداکنندهٔ هزارگان ٬ و اعشار ە."""
    s = "{:,.{d}f}".format(v, d=digits)
    return ("".join(FA[int(c)] if c.isdigit() else c for c in s)
            .replace(",", "٬").replace(".", "٫"))


def _read_md():
    with open(MD, "r", encoding="utf-8") as fh:
        return fh.read()


def _expected(metric, want_max):
    """انتخابِ مورد انتظار از روی اندازه‌گیریِ فردی (آینهٔ envelope_overrides)."""
    out = []
    for i in SETTING_IDS:
        d = R[i].get(metric)
        if d is not None and ((want_max and d > 0) or (not want_max and d < 0)):
            out.append(i)
    cands = [(f, R[f][metric]) for f in FIX_VARIANTS
             if R.get(f, {}).get(metric) is not None]
    if cands:
        bf = (max(cands, key=lambda t: t[1]) if want_max
              else min(cands, key=lambda t: t[1]))
        if (want_max and bf[1] > 0.0) or (not want_max and bf[1] < 0.0):
            out.append(bf[0] + " [FIX]")
    return out


@pytest.mark.parametrize("eid, metric, want_max", [
    ("E-min-dp", "d_delta_p", False),
    ("E-max-dp", "d_delta_p", True),
    ("E-min-bar", "d_baravord", False),
    ("E-max-bar", "d_baravord", True),
])
def test_T130_envelope_choices(eid, metric, want_max):
    """انتخابِ تصمیم‌ها در هر سناریو با extremumِ اندازه‌گیریِ فردی باشد."""
    got = M["envelope"][eid]["flips"]
    assert sorted(got) == sorted(_expected(metric, want_max))


def test_T130_envelope_bounds():
    """کمینه ≤ پایه ≤ بیشینه — برای ΔP و برای برآورد."""
    for lo, hi, key in (("E-min-dp", "E-max-dp", "delta_p"),
                        ("E-min-bar", "E-max-bar", "baravord")):
        lo_v = M["envelope"][lo][key]
        hi_v = M["envelope"][hi][key]
        base_v = M["baseline"][key]
        assert lo_v <= base_v <= hi_v, (lo, key, lo_v, base_v, hi_v)


def test_T130_doc_matches_json():
    """اعدادِ بازه و پهنای آن در .md دقیقاً با JSON هم‌خوان باشند."""
    seg = _read_md().split("## بازهٔ حساسیتِ واقعی")[1].split("## نمودار tornado")[0]
    for eid in ("E-min-dp", "E-max-dp", "E-min-bar", "E-max-bar"):
        v = M["envelope"][eid]
        assert _fmt(v["delta_p"]) in seg, (eid, "delta_p")
        assert _fmt(v["baravord"]) in seg, (eid, "baravord")
    w_dp = (M["envelope"]["E-max-dp"]["delta_p"]
            - M["envelope"]["E-min-dp"]["delta_p"])
    w_br = (M["envelope"]["E-max-bar"]["baravord"]
            - M["envelope"]["E-min-bar"]["baravord"])
    assert _fmt(w_dp) in seg, "پهنای ΔP"
    assert _fmt(w_br) in seg, "پهنای برآورد"


def test_T130_e9_claim_corrected():
    """اعدادِ ادعا‌شدهٔ E-9 صریح رد و مقادیرِ درستِ قابلِ بازتولید ذکر شوند."""
    seg = _read_md().split("## بازهٔ حساسیتِ واقعی")[1].split("## نمودار tornado")[0]
    # اعدادِ ادعا‌شده (که در هیچ فایل و هیچ کامیتی از مخزن نیستند)
    assert "۲٬۴۷۰٬۸۶۱٬۰۸۳٫۱۳" in seg
    assert "۲٬۳۳۳٬۴۶۳٬۵۸۰٫۸۴" in seg
    # مقادیرِ درست — از decision_impact_scenarios.json
    assert _fmt(R["D-14"]["d_baravord"]) in seg
    assert _fmt(R["D-15"]["d_baravord"]) in seg


def test_T130_recommendation_sources():
    """هر ردیف یک برچسبِ منبعِ صریح داشته باشد."""
    t = _read_md()
    table = t.split("## همهٔ تصمیم‌ها")[1].split("## تحلیل حساسیت")[0]
    rows = re.findall(r"^\| \d+ \| (D-\d\d)", table, re.M)
    assert len(rows) == 13, rows
    for lbl in ("[متن بخشنامه]", "[انتخاب مهندسی]",
                "[رویهٔ رایج، نیازمند تأیید مشاور]", "[وضعیت فعلی]",
                "[دادهٔ ورودی — واقعیتِ پروژه]"):
        assert lbl in table, lbl
    # ۵ تصمیمِ اول هم منبعِ توصیه دارند
    top = t.split("## ۵ تصمیمِ اول")[1].split("## همهٔ تصمیم‌ها")[0]
    assert top.count("- **منبع توصیه:**") == 5
