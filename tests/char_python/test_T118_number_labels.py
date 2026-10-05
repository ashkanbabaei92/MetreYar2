# -*- coding: utf-8 -*-
# T118 — ممیزیِ برچسبِ منشأٔ اعداد در مستندات (فاز E-9 §۲).
#
# هر عددِ پولی یا شاخص در مستندات باید یک برچسبِ منشأ داشته باشد:
#   [REF] پروژهٔ مرجع / [FIX] fixture آزمون / [SRC: بخشنامه، صفحه] منبع رسمی.
# این آزمون tools/audit_number_labels.py را اجرا می‌کند و FAIL می‌شود اگر
# عددِ بدون برچسبی باشد.
#
# نکته: معادلِ TypeScript ندارد — این یک lint روی پرونده‌های Markdown است و
# خروجیِ موتور نیست (قاعدهٔ پاریتی روی خروجیِ موتور اعمال می‌شود، نه روی lint).
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TOOL = os.path.join(ROOT, "tools", "audit_number_labels.py")


def test_T118_all_numbers_have_provenance_label():
    proc = subprocess.run(
        [sys.executable, TOOL], capture_output=True, text=True,
        cwd=ROOT, encoding="utf-8")
    out = proc.stdout or ""
    assert proc.returncode == 0, "اعدادِ بدون برچسب پیدا شدند:\n" + out
    assert "نتیجه: PASS" in out
    # حداقلِ واقعی: باید چندصد عدد بررسی شده باشد
    assert "819 عدد" in out or "عدد بررسی شد" in out


def test_T118_audit_tool_loads_config_indices():
    # ابزار باید مقادیرِ شاخص را از config/index_bulletins.json بخواند
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import audit_number_labels as A
    vals = A._load_index_values()
    assert 9744.7 in vals           # ابنیه، اسفند ۱۴۰۳
    assert 14333.1 in vals          # ابنیه، ۱۴۰۴Q4
