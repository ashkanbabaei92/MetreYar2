# -*- coding: utf-8 -*-
# T133 — شکافِ ۲۰۸۰ → ۱۷۳۰۷۳ (فاز E-11-A).
#
# این آزمون‌ها شکاف‌های مستندشده در docs/COMPLIANCE_2080_vs_173073.md را
# به‌صورتِ ماشینی قفل می‌کنند. در فاز E-11-A هنوز پیاده نشده‌اند، پس دو
# آزمون xfail (انتظارِ شکست) و یکی skip است. وقتی در فاز E-11-B پیاده
# شوند، xfailها به xpass (سبز) تبدیل می‌شوند — دقیقاً مثلِ T111.
#
#   ۱) گردکردن ۴→۳ رقم (۱۷۳۰۷۳ ۵-۳ در برابر ۲۰۸۰ ۸-۲)  → xfail
#   ۲) طبقهٔ سومِ k = ۰٫۹۷۵ (۱۷۳۰۷۳ ۸-۲)                  → xfail
#   ۳) بخشِ bulletin_173073 در config                     → skip (داده)
#   ۴) خودِ فایلِ تحلیل موجود و کامل است                   → سبز (همین)
#
# آینهٔ test_T133_gap_173073.ts (پاریتیِ py↔ts).
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import _tadil_k, default_settings, round_coef_2080

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CONFIG = os.path.join(ROOT, "config", "index_bulletins.json")
COMPLIANCE = os.path.join(ROOT, "docs", "COMPLIANCE_2080_vs_173073.md")


# ── ۱) ۱۷۳۰۷۳ بند ۵-۳: ضریب ابتدا با ۴ رقم اعشار محاسبه، سپس به ۳ رقم
# گرد می‌شود. ۲۰۸۰ بند ۸-۲: ۳ رقم → ۲ رقم. اعداد از probes واقعی موتور
# آمده‌اند: round_coef_2080(0.1235) = 0.12 و round_coef_2080(0.1234) = 0.12.
@pytest.mark.xfail(
    reason="۱۷۳۰۷۳ بند ۵-۳: گردکردن ۴→۳ رقم هنوز پیاده نشده — "
           "COMPLIANCE §۲-۷ / D-03 (نیازمند تغییرِ کد)",
    run=True,
)
@pytest.mark.parametrize("raw,expected", [
    (0.1235, 0.124),   # رقم چهارم (=۵) ⇒ حذف و یک واحد به رقم سوم
    (0.1234, 0.123),   # رقم چهارم (<۵) ⇒ حذف
])
def test_T133_rounding_3_digits_173073(raw, expected):
    """تحت ۱۷۳۰۷۳ بند ۵-۳ ضریب به ۳ رقم گرد می‌شود، نه ۲."""
    assert round_coef_2080(raw) == pytest.approx(expected, abs=1e-12)


# ── ۲) ۱۷۳۰۷۳ بندهای ۸-۱/۸-۲: سه طبقه. ۲۰۸۰ فقط دو طبقه دارد.
# «extended» = حالتِ سومِ پیشنهادی (اتمام در مدتِ اولیه + تأخیرهای مجاز).
@pytest.mark.xfail(
    reason="۱۷۳۰۷۳ بندهای ۸-۱/۸-۲: طبقهٔ k=۰٫۹۷۵ هنوز وجود ندارد — "
           "COMPLIANCE §۲-۱ / D-01 (نیازمند تغییرِ کد)",
    run=True,
)
def test_T133_k_third_tier_0975():
    s = default_settings()
    s["completed_within_term"] = "extended"
    k, _label, _src = _tadil_k(s)
    assert k == pytest.approx(0.975, abs=1e-12)


# ── ۳) بخشِ bulletin_173073 هنوز در config نیست.
@pytest.mark.skip(
    reason="تا فاز E-11-B ۳-۲: بخشِ bulletin_173073 هنوز اضافه نشده — "
           "نیازمندِ ثبتِ هش و مسیرِ neu/101-173073.pdf",
)
def test_T133_config_bulletin_173073():
    with io.open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    assert "bulletin_173073" in cfg, "بخشِ ۱۷۳۰۷۳ به config اضافه شود"


# ── ۴) خودِ تحلیلِ شکاف موجود است (این یکی سبز است).
def test_T133_compliance_doc_exists():
    """فایلِ تحلیلِ شکاف وجود دارد و بخش‌های §۲ (ریسک‌ها) و §۶ (برنامه)
    را دارد."""
    with io.open(COMPLIANCE, encoding="utf-8") as fh:
        text = fh.read()
    assert "## ۲. ۱۱ موردِ پرخطر" in text
    assert "## ۶. برنامهٔ فاز E-11-B" in text
    for token in ("۰٫۹۷۵", "۵-۳", "۱-۸-۱", "۲-۱-۵-۲"):
        assert token in text, token
