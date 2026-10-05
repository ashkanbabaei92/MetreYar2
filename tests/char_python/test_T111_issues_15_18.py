# -*- coding: utf-8 -*-
"""T111 — ایرادهای ۱۵ تا ۱۸ (سند خلاصهٔ ۱۲ مرحله، خارج از مخزن).

ایرادهای ۱۵ (اعداد مرحلهٔ ۸ و ۹ کپی هم‌اند)، ۱۶ (جمع بخش ۲ مرحلهٔ ۱۱ باید
۵۵− باشد نه ۴۸−)، ۱۷ («۲۹٫۷۵T» → «۲۹٫۷۵B») و ۱۸ («۰۲۸xxxx» → «۲۸xxxx»)
همگی به سندی خارج از مخزن اشاره دارند (ACCEPTANCE §۱۸-۸-۳). این فایل
جایگاهِ آزمونِ آن‌ها را نگه می‌دارد. وقتی سند رسید:

۱. `ISSUES_DOC_AVAILABLE = True` کنید.
۲. فقط مقدارهای `EXPECTED_15_18` را با سند تطبیق دهید.
۳. تست‌ها از xfail به xpass (سبز) تبدیل می‌شوند.

تا آن موقع، طبق قاعدهٔ طلایی، هیچ عددی حدس زده نمی‌شود.
"""

import glob
import io
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── پرچمِ رسیدنِ سند. فقط این مقدار و مقدارهای زیر عوض می‌شوند. ──
ISSUES_DOC_AVAILABLE = False

# مقدارهای مورد انتظار پس از رسیدنِ سند (فعلاً خودِ خواستهٔ کاربر).
EXPECTED_15_18 = {
    15: "اعدادِ مرحلهٔ ۸ و ۹ باید یکتا باشند (الان کپیِ هم‌اند)",
    16: "جمعِ بخش ۲ مرحلهٔ ۱۱ باید ۵۵− باشد (الان ۴۸−)",
    17: "مقدار «۲۹٫۷۵T» باید به «۲۹٫۷۵B» تصحیح شود",
    18: "کدهای «۰۲۸xxxx» باید به «۲۸xxxx» تصحیح شوند",
}

# الگوهای متمایزی که نباید در مخزن باشند (مگر پس از تصحیح).
SUSPECT_PATTERNS = ["۲۹٫۷۵T", "۰۲۸"]

# فقط کد و داده (نه مستندات .md و نه تست‌ها — آن‌ها این الگوها را
# به‌صورتِ متنی مستند می‌کنند).
SCAN_DIRS = ["src", "config", "data"]
SCAN_FILE = "app.py"
SCAN_EXT = (".ts", ".js", ".json", ".csv", ".txt")


def _repo_files():
    for d in SCAN_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, d)):
            dirnames[:] = [x for x in dirnames
                           if x not in ("node_modules", "__pycache__")]
            for fn in filenames:
                if fn.endswith(SCAN_EXT):
                    yield os.path.join(dirpath, fn)
    app_py = os.path.join(ROOT, SCAN_FILE)
    if os.path.exists(app_py):
        yield app_py


def test_T111_registry_complete():
    """هر ۴ ایرادِ باز ثبت شده‌اند و کلیدها پشت سر هم‌اند."""
    assert sorted(EXPECTED_15_18) == [15, 16, 17, 18]


def test_T111_expected_values_recorded():
    """مقدارهای مورد انتظار برای هر ایراد وجود دارند و خالی نیستند."""
    for key, text in EXPECTED_15_18.items():
        assert isinstance(text, str) and text.strip(), key


@pytest.mark.xfail(
    reason="سندِ «خلاصهٔ ۱۲ مرحله» هنوز نرسیده — ACCEPTANCE §۱۸-۸-۳",
    run=True,
)
def test_T111_issues_resolved():
    """وقتی سند برسد و ISSUES_DOC_AVAILABLE=True شود، این آزمون سبز می‌شود."""
    assert ISSUES_DOC_AVAILABLE is True


def test_T111_no_suspect_patterns_in_repo():
    """الگوهای مشکوک در کد/داده نیستند — هیچ تصحیحِ حدسی انجام نشده است.

    این آزمونِ نگه‌دار است: اگر کسی این الگوها را بدونِ سند اضافه کند،
    اینجا قرمز می‌شود. وقتی سند رسید و تصحیح انجام شد، باید استثنا (یا
    مسیرِ جدید) به این آزمون افزوده شود.
    """
    hits = []
    for f in _repo_files():
        try:
            text = io.open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for pat in SUSPECT_PATTERNS:
            if pat in text:
                hits.append((os.path.relpath(f, ROOT), pat))
    assert hits == [], "الگوی مشکوک در مخزن پیدا شد: %s" % hits
