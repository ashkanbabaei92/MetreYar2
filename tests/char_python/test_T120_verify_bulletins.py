# -*- coding: utf-8 -*-
# T120 — فاز E-9 §۳.۱/§۳.۲: ابزارِ راستی‌آزماییِ شاخص‌ها در برابرِ PDF رسمی.
#
# ابزارِ tools/verify_bulletins.py همهٔ مقادیرِ config/index_bulletins.json را
# با بخشنامهٔ ۱۵۵۲۳۳ (۳۱ بررسی) و — در حالتِ پیش‌فرض — CPIها، PROV_COEF و
# جدولِ m را با بخشنامهٔ ۱۴۴۳۷۳ تطبیق می‌دهد. PDFها در docs/sources/bulletins
# هستند و git-track نمی‌شوند؛ اگر نبودند، آزمون skip می‌شود (نه fail).
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TOOL = os.path.join(ROOT, "tools", "verify_bulletins.py")
PDF_MAIN = os.path.join(ROOT, "docs", "sources", "bulletins", "Tadil1404-34.pdf")

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _skip_if_pdfs_missing():
    if not os.path.exists(PDF_MAIN):
        pytest.skip("PDF بخشنامه موجود نیست (docs/sources/bulletins git-track نمی‌شود)")


def _run(*args):
    proc = subprocess.run([sys.executable, TOOL, *args],
                          capture_output=True, text=True,
                          cwd=ROOT, encoding="utf-8")
    return proc


def test_T120_indexes_match_official_bulletin():
    proc = _run("--indexes")
    out = proc.stdout or ""
    assert proc.returncode == 0, "شاخص‌ها با PDF مطابق نیستند:\n" + out
    assert "نتیجه: PASS" in out
    # ۳۱ بررسی: ردیفِ ابنیه + ۳۰ فصل
    assert "۳۱" in out or "تعداد بررسی" in out


def test_T120_cpi_and_prov_coef_and_m_table():
    proc = _run("--cpi")
    out = proc.stdout or ""
    assert proc.returncode == 0, "CPI/PROV_COEF/m نامطبابق:\n" + out + (proc.stderr or "")
    # PROV_COEF با Decimal دقیقاً بازتولید می‌شود
    assert "1.1530518586507572" in out
    # جدولِ m: ۱۶ رشته با m=۰٫۷ در صفحهٔ ۴ و mهای {۱٫۰، ۱٫۱} در صفحهٔ ۵
    assert "m=۰٫۷" in out or "0.7" in out
    # هشدارهای نامِ رشته‌ها فقط هشدارند، نه خطا
    assert "✗" not in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
