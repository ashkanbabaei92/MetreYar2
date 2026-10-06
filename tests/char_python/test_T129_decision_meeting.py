# -*- coding: utf-8 -*-
# T129 — بستهٔ جلسهٔ تصمیم (فاز E-10 §۵).
#
# tools/make_decision_meeting.py دو سند می‌سازد: docs/DECISION_MEETING.md
# و docs/DECISION_MEETING.docx. این آزمون قفل می‌کند:
#   ۱) ساختار: ۵ بخش (مقدمه، ۵ تصمیمِ اول، همهٔ تصمیم‌ها، حساسیت،
#      tornado، گروه‌ها) و page breakهای docx؛
#   ۲) ترتیب: تصمیم‌ها مرتب بر اساس max |اثر| روی ΔP/برآورد/سقف؛
#   ۳) اعداد: S1 = baseline، S3 = S1، شرطی = ΔPِ D-01 (همان اندازه‌گیری)،
#      و S2 = عددِ پین‌شدهٔ اجرای ترکیبی؛
#   ۴) بازه: hi − lo = spread و درصدها درست‌اند.
# آینهٔ test_T129_decision_meeting.ts (فایلِ .md مشترک است).
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MD = os.path.join(ROOT, "docs", "DECISION_MEETING.md")
DOCX = os.path.join(ROOT, "docs", "DECISION_MEETING.docx")
SCEN = os.path.join(ROOT, "tools", "decision_impact_scenarios.json")

with open(SCEN, "r", encoding="utf-8") as _fh:
    PAYLOAD = json.load(_fh)
RESULTS = PAYLOAD["results"]
BASE_DP = PAYLOAD["baseline_metrics"]["delta_p"]

# عددِ پین‌شدهٔ اجرای ترکیبیِ S2 (هفت گزینهٔ بِ قابلِ پیاده‌شده با هم).
# این عدد با اجرای واقعیِ موتور در فاز E-10 §۵ به‌دست آمده و قابلِ
# بازتولید با tools/make_decision_meeting.py است.
S2_DELTA_P = 10224815159.58

FA = "۰۱۲۳۴۵۶۷۸۹"


def _fmt(v, digits=2):
    """همان قالبِ fa_numِ ابزار: جداکنندهٔ هزارگان ␣ ٬ و اعشار ␣ ە."""
    s = "{:,.{d}f}".format(v, d=digits)
    s = "".join(FA[int(c)] if c.isdigit() else c for c in s)
    return s.replace(",", "٬").replace(".", "٫")


def _read_md():
    with open(MD, "r", encoding="utf-8") as fh:
        return fh.read()


# ── ۱) ساختار ──

def test_T129_files_exist():
    assert os.path.exists(MD)
    assert os.path.getsize(DOCX) > 10000


def test_T129_sections():
    t = _read_md()
    for h in ("# بستهٔ جلسهٔ تصمیم",
              "## ۵ تصمیمِ اول — بیشترین |اثر|",
              "## همهٔ تصمیم‌ها — مرتب بر اساس max |اثر|",
              "## تحلیل حساسیت — سه سناریو",
              "## نمودار tornado",
              "## تصمیم‌های ردشده، ادغام‌شده و منتظر داده"):
        assert h in t, h


def test_T129_docx_structure():
    from docx import Document
    d = Document(DOCX)
    assert len(d.tables) == 3, "سه جدول: تصمیم‌ها، حساسیت، tornado"
    # جدولِ تصمیم‌ها: هدر + ۱۳ تصمیمِ باز/داده
    dec_t, sens_t, tor_t = d.tables
    assert len(dec_t.rows) == 14
    assert len(sens_t.rows) == 5   # هدر + S1 + S2 + S3 + شرطی
    assert len(tor_t.columns) >= 40, "tornado باید حداقل ۴۰ ستون داشته باشد"
    assert d.element.xml.count('w:type="page"') >= 5, "هر بخش یک صفحهٔ جدا"


# ── ۲) ترتیب بر اساس max |اثر| ──

def _max_effect(res):
    vals = [abs(v) for v in (res.get("d_delta_p"), res.get("d_baravord"),
                             res.get("d_ceiling")) if v is not None]
    return max(vals) if vals else None


def test_T129_top_five_order():
    """۵ تصمیمِ اول باید مرتب بر اساس max |اثر| باشند."""
    t = _read_md()
    top_part = t.split("## ۵ تصمیمِ اول")[1].split("## همهٔ تصمیم‌ها")[0]
    ids = re.findall(r"### (D-\d\d) —", top_part)
    assert len(ids) == 5, ids
    scored = []
    for i in ids:
        scored.append((i, _max_effect(RESULTS[i])))
    for (i1, v1), (i2, v2) in zip(scored, scored[1:]):
        assert v1 >= v2, "%s (%s) باید قبل از %s (%s) باشد" % (i1, v1, i2, v2)


def test_T129_full_table_sorted():
    t = _read_md()
    table = t.split("## همهٔ تصمیم‌ها")[1].split("## تحلیل حساسیت")[0]
    ids = re.findall(r"\| \d+ \| (D-\d\d)", table)
    # هر تصمیمِ باز/داده دقیقاً یک‌بار
    expected = [i for i in ("D-%02d" % n for n in range(1, 21))
                if RESULTS.get(i, {}).get("kind") not in ("rejected", "merged")]
    assert sorted(ids) == sorted(expected), set(expected) ^ set(ids)
    # مرتب‌سازی غیرصعودی بر اساس max |اثر| (Noneها آخرند — مثلِ ابزار)
    def _key(v):
        return (v is not None, v if v is not None else 0.0)
    keys = [_key(_max_effect(RESULTS[i])) for i in ids]
    for k1, k2 in zip(keys, keys[1:]):
        assert k1 >= k2, (k1, k2)


# ── ۳) اعدادِ سناریوها ──

def test_T129_scenario_numbers():
    t = _read_md()
    # S1 = baseline
    assert _fmt(BASE_DP) in t
    # S3 = S1 (توصیه همان وضعیتِ فعلی)
    s3_line = [ln for ln in t.splitlines() if ln.startswith("| **S3**")][0]
    assert _fmt(BASE_DP) in s3_line
    # شرطی = همان ΔPِ اندازه‌گیری‌شدهٔ D-01
    cond = [ln for ln in t.splitlines() if ln.startswith("| **شرطی**")][0]
    assert _fmt(RESULTS["D-01"]["delta_p"]) in cond
    # S2 = عددِ پین‌شده
    s2_line = [ln for ln in t.splitlines() if ln.startswith("| **S2**")][0]
    assert _fmt(S2_DELTA_P) in s2_line


def test_T129_range_consistency():
    t = _read_md()
    lo = BASE_DP
    hi = S2_DELTA_P
    spread = hi - lo
    line = [ln for ln in t.splitlines() if "بازهٔ کمینه تا بیشینهٔ ΔP" in ln][0]
    assert _fmt(lo) in line
    assert _fmt(hi) in line
    assert _fmt(spread) in line
    # درصدها
    assert _fmt(100.0 * spread / BASE_DP) in line
    base_total = PAYLOAD["baseline_metrics"]["base_total"]
    assert _fmt(100.0 * spread / base_total) in line


def test_T129_interaction_note():
    """مجموعِ فردی در برابرِ ترکیب باید ذکر شود (جمع‌زدن ممنوع)."""
    t = _read_md()
    flips = ("D-01", "D-03", "D-04", "D-08", "D-09", "D-10", "D-13")
    naive = sum(RESULTS[i]["d_delta_p"] for i in flips)
    assert _fmt(naive) in t
    assert "هم‌کنش" in t


# ── ۴) tornado ──

def test_T129_tornado_excludes_ceiling():
    """D-18 اختلافِ سقف دارد و در جدولِ tornado نیست (مقیاسِ متفاوت)."""
    t = _read_md()
    tor = t.split("## نمودار tornado")[1].split("## تصمیم‌های ردشده")[0]
    # فقط ردیف‌های جدول (متنِ توضیحی D-18 را دارد پس «not in tor» غلط است)
    ids = re.findall(r"^\| (D-\d\d) \|", tor, re.M)
    assert "D-18" not in ids
    # شاملِ همهٔ تصمیم‌های قابلِ اندازه‌گیری به‌جز D-18
    want = [i for i in ("D-%02d" % n for n in range(1, 21))
            if RESULTS.get(i, {}).get("d_delta_p") is not None and i != "D-18"]
    assert sorted(ids) == sorted(want), set(want) ^ set(ids)


def _tornado_value(res):
    """مقدار و جهتِ نوار: بزرگترین |اثر| روی کانال‌های ΔP/برآورد."""
    best = None
    for key in ("d_delta_p", "d_baravord"):
        v = res.get(key)
        if v is not None and (best is None or abs(v) > abs(best)):
            best = v
    return best


def test_T129_tornado_directions():
    t = _read_md()
    tor = t.split("## نمودار tornado")[1].split("## تصمیم‌های ردشده")[0]
    for ln in tor.splitlines():
        m = re.match(r"^\| (D-\d\d) \| ([^|]+)\| ([−+])([^|]+)\| (.*?)\|", ln)
        if not m:
            continue
        did, _subj, sign, _val, bar = m.groups()
        v = _tornado_value(RESULTS[did])
        if v is None or v == 0:
            assert "│" in bar or "█" not in bar, did
            continue
        neg = v < 0
        assert (sign == "−") == neg, did
        assert ("◄" in bar) == neg, (did, bar)
        assert ("►" in bar) == (not neg), (did, bar)
