# -*- coding: utf-8 -*-
# T127 — پاک‌سازیِ فهرستِ تصمیم‌ها (فاز E-10 §۳).
#
# بعد از این فاز هیچ گزینه‌ای در DECISION_SHEET.md نماند که در کد قابلِ
# اجرا نباشد. این آزمون قفل می‌کند:
#   ۱) شش تصمیمِ «ردشده در طراحی» از DECISION_SHEET حذف شده‌اند؛
#   ۲) D-11 به‌جای حذف، «ادغام‌شده در D-13» است؛
#   ۳) فلگِ D-04 در هر دو زبان وجود دارد و رفتارِ گردکردنِ منفی درست است.
# آینهٔ test_T127_decision_cleanup.ts.
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import default_settings, round_coef_2080

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SHEET = os.path.join(ROOT, "docs", "DECISION_SHEET.md")
PENDING = os.path.join(ROOT, "docs", "PENDING_DECISIONS.md")

# تصمیم‌هایی که در فاز E-10 §۳ «ردشده در طراحی» شدند و از DECISION_SHEET
# حذف شده‌اند (ولی شناسه‌ها در PENDING_DECISIONS باقی می‌مانند).
REJECTED = ["D-02", "D-05", "D-06", "D-07", "D-12", "D-17"]

# تصمیم‌هایی که هنوز در DECISION_SHEET هستند (۱۲ تصمیمِ باز + D-01 + D-11).
REMAINING = ["D-01", "D-03", "D-04", "D-08", "D-09", "D-10", "D-11",
             "D-13", "D-14", "D-15", "D-16", "D-18", "D-19", "D-20"]


import re

_ID = re.compile(r"^## (D-\d\d)\b")


def _headings(path):
    """شناسه‌های «## D-xx» یک فایلِ markdown را برمی‌گرداند."""
    with open(path, "r", encoding="utf-8") as fh:
        return [m.group(1)
                for m in (_ID.match(ln.strip()) for ln in fh) if m]


def _registry_ids(path):
    """شناسه‌های ردیف‌های جدولِ «| D-xx | ...» یک فایلِ markdown."""
    with open(path, "r", encoding="utf-8") as fh:
        out = []
        for ln in fh:
            m = re.match(r"^\|\s*(D-\d\d)\s*\|", ln)
            if m:
                out.append(m.group(1))
    return out


def _section(path, did):
    """متنِ بخشِ «## <did>» تا هدینگِ بعدی."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out, on = [], False
    for ln in lines:
        if _ID.match(ln.strip()):
            on = ln.strip().startswith("## %s " % did)
            continue
        if on:
            out.append(ln)
    return "\n".join(out)


# ── ۱) ساختارِ DECISION_SHEET ──

def test_T127_rejected_removed_from_sheet():
    hs = _headings(SHEET)
    for did in REJECTED:
        assert did not in hs, "%s باید از DECISION_SHEET حذف می‌شد" % did


def test_T127_no_renumbering():
    """شناسه‌ها حذف یا باز‌شماری نشده‌اند — هر ۲۰ شناسه در رجیستریِ
    PENDING_DECISIONS همچنان موجودند."""
    ids = _registry_ids(PENDING)
    assert sorted(set(ids)) == sorted("D-%02d" % i for i in range(1, 21)), ids


def test_T127_d11_merged_into_d13():
    sec = _section(SHEET, "D-11")
    assert sec, "بخشِ D-11 باید وجود داشته باشد (شناسه حذف نمی‌شود)"
    assert "D-13" in sec, "D-11 باید به D-13 ارجاع دهد"
    assert "ادغام" in sec.replace("ادغام‌شده", "ادغام"), sec
    # متنِ کاملِ سؤال/گزینه‌ها فقط یک‌بار (در D-13) آمده است
    assert _section(SHEET, "D-13").count("گزینهٔ الف") == 1


def test_T127_sheet_only_executable_options():
    """هر تصمیمِ باقی‌مانده یا دادهٔ ورودی است، یا گزینه‌هایش قابلِ اجرا."""
    hs = _headings(SHEET)
    assert sorted(hs) == sorted(REMAINING), hs


# ── ۲) فلگِ D-04 (گردکردنِ ضرایبِ منفی) ──

def test_T127_d04_flag_default():
    s = default_settings()
    assert s["negative_coef_rounding"] == "away_from_zero"
    assert s["coef_rounding_2080"] is True


@pytest.mark.parametrize("x,away,toward", [
    # متنِ بخشنامه دربارهٔ جهتِ گردکردنِ منفی ساکت است؛ گزینهٔ الف روی قدر
    # مطلق (دور از صفر)، گزینهٔ ب مستقیمِ منفی (به‌سمتِ صفر).
    (0.1250, 0.13, 0.13),      # مثبت تحت تأثیر نیست
    (-0.1250, -0.13, -0.12),   # مرزِ نیم‌به‌بالا
    (-0.1240, -0.12, -0.12),   # رقمِ سوم < ۵
    (-0.1260, -0.13, -0.12),   # رقمِ سوم ≥ ۵
    (0.0, 0.0, 0.0),
])
def test_T127_d04_rounding_direction(x, away, toward):
    assert round_coef_2080(x) == pytest.approx(away), "پیش‌فرض = الف"
    assert round_coef_2080(x, False) == pytest.approx(away)
    assert round_coef_2080(x, True) == pytest.approx(toward), "گزینهٔ ب"
