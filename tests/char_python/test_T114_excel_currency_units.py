# -*- coding: utf-8 -*-
# T114 — یکدستیِ واحدِ پول در خروجیِ Excel (فاز E-۷ بخش ۲).
#
# قاعده: هر ستونِ پولی (و هر برچسبِ ردیفِ پولی) در همهٔ شیت‌های Excel باید
# واحدِ «ریال» را در برچسب خود داشته باشد. واحدِ استانداردِ پروژه ریال است؛
# تومان فقط در نمایشِ انتخابیِ کاربر (fmt_money) دیده می‌شود و هرگز در
# خروجیِ Excel نمی‌آید.
#
# این آزمون:
#   ۱) برچسب‌های پولیِ مورد انتظار را بررسی می‌کند (همگی «ریال» دارند)؛
#   ۲) متغیرهایِ بدونِ «ریال» را ممنوع می‌کند (در صورتِ افزودنِ ستونِ
#      پولیِ بدونِ برچسب، آزمون شکست می‌خورد).
#
# آینهٔ test_T114_excel_currency_units.ts.
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import (DynamoMappingParser, ExcelExporter, RevitScheduleParser,
                  TechnicalOfficeEngine, _default_fehrest_db, default_settings)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

META = {"report_type": "دوره‌ای", "report_no": "۱", "contract_no": "۱",
        "project_name": "پروژه نمونه", "employer": "کارفرما", "contractor": "پیمانکار",
        "consultant": "مشاور", "period_start": "۱۴۰۴/۰۱/۰۱", "period_end": "۱۴۰۴/۰۳/۳۱",
        "location": "گرگان", "contract_date": "۱۴۰۴/۰۱/۰۱"}
PROV_COEF = 1.1530518586507572

# برچسب‌های پولی که باید «ریال» داشته باشند (ستون‌ها و ردیف‌های جمع)
MONEY_LABELS = [
    # شیتِ خلاصهٔ مالی و برآورد
    "مبلغ (ریال)", "مبلغ کل (ریال)",
    # شیتِ صورت وضعیت
    "بهای واحد (ریال)", "بهای کل (پایه، ریال)", "بهای کل (به‌هنگام، ریال)",
    "بهای فهرست (ریال)", "بهای دستی (ریال)",
    # شیتِ سوابق صورت وضعیت
    "ناخالص تجمعی (ریال)", "کسورات تجمعی (ریال)", "خالص تجمعی (ریال)",
    "کارکرد این دوره (ریال)",
    # شیتِ تعدیل پیمان / برآورد به‌هنگام / بخش قطعی
    "مبلغ پایه (A_c، ریال)", "مبلغ تعدیل (ΔP_c، ریال)",
    "مبلغ به‌هنگام‌شده (ریال)",
    "بخش قطعی (ریال)", "بخش علی‌الحساب (ریال)",
    "جمع تعدیل (شامل علی‌الحساب، ریال)",
    "بخش قطعی (شاخص‌های قطعی ۱۴۰۴، ریال)",
    "بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1، ریال)",
    "مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ — همراه قطعی، بند ۸-۴، ریال)",
    "کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷، ریال)",
    "مبلغ نهایی (A + جمع تعدیل، ریال)",
    "برآورد به‌هنگام‌شده (ریال)",
    "زنجیرهٔ مبلغ پایه (A) — مبالغ به ریال",
    # شیتِ ضرایب
    "تجهیز و برچیدن کارگاه (ریال)",
]

# متغیرهایِ ممنوع: برچسب‌های پولیِ بدونِ «ریال» (نگه‌دارندهٔ رگرسیون)
FORBIDDEN = [
    "بهای واحد", "بهای کل (پایه)", "بهای کل (به‌هنگام)",
    "بهای فهرست", "بهای دستی",
    "ناخالص تجمعی", "کسورات تجمعی", "خالص تجمعی", "کارکرد این دوره",
    "مبلغ پایه (A_c)", "مبلغ تعدیل (ΔP_c)", "مبلغ به‌هنگام‌شده",
    "جمع تعدیل (شامل علی‌الحساب)", "مبلغ نهایی (A + جمع تعدیل)",
    "برآورد به‌هنگام‌شده",
]
# استثناهای مجاز (زیررشته‌ای از برچسب‌های مجاز بالا که شاملِ «ریال» نیستند
# ولی در متنِ توضیحات ظاهر می‌شوند)
_OK_SUBSTR = ["بهای واحد (ریال)", "بهای کل (پایه، ریال)", "بهای کل (به‌هنگام، ریال)"]


def _shared_strings(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    return z.read("xl/sharedStrings.xml").decode("utf-8")


def _wb(data):
    return zipfile.ZipFile(io.BytesIO(data)).read(
        "xl/workbook.xml").decode("utf-8")


_XLS_EXTRA = dict(tadil_enabled=True, baravord_enabled=True,
                  proposal_date="۱۴۰۳/۱۲/۲۹",
                  work_period_start="۱۴۰۴/۰۱/۰۱",
                  work_period_end="۱۴۰۵/۰۲/۱۵",
                  provisional_coef_1405q1=PROV_COEF,
                  completed_within_term=True,
                  contract_status="فسخ با قصور")


@pytest.fixture(scope="module")
def excel_bytes():
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
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    map_df = DynamoMappingParser.merge_formats(results)
    s = default_settings()
    s.update(_XLS_EXTRA)
    res = TechnicalOfficeEngine(_default_fehrest_db(), s).compute(tables, map_df)
    return ExcelExporter().export(META, res, s, [])


def test_T114_money_labels_have_rial_unit(excel_bytes):
    shared = _shared_strings(excel_bytes)
    missing = [m for m in MONEY_LABELS if m not in shared]
    assert not missing, "برچسب‌های پولیِ بدونِ «ریال» یا ناموجود: %s" % missing
    # همهٔ برچسب‌ها واقعاً «ریال» دارند
    assert all("ریال" in m for m in MONEY_LABELS)


def test_T114_no_money_label_without_rial(excel_bytes):
    shared = _shared_strings(excel_bytes)
    bad = []
    for f in FORBIDDEN:
        # برچسبِ بدونِ «ریال» فقط اگر به‌طورِ مستقل ظاهر شود خطاست
        if ">" + f + "<" in shared.replace(" ", " "):
            # بررسی اینکه داخلِ یک برچسبِ بزرگ‌ترِ «ریال‌دار» نیست
            _ok = any(ok in shared and f in ok for ok in _OK_SUBSTR)
            if not _ok:
                bad.append(f)
    assert not bad, "برچسبِ پولیِ بدونِ واحدِ «ریال» یافت شد: %s" % bad


def test_T114_no_toman_in_excel(excel_bytes):
    # خروجیِ Excel همیشه ریال است؛ «تومان» فقط در نمایشِ UIِ انتخابی است.
    shared = _shared_strings(excel_bytes)
    # «میلیارد تومان» در شیتِ خلاصهٔ مالی مجاز نیست
    assert "میلیارد تومان" not in shared
    assert "تومان" not in shared


def test_T114_workbook_has_money_sheets(excel_bytes):
    wb = _wb(excel_bytes)
    for name in ("خلاصهٔ مالی و برآورد", "صورت وضعیت", "سوابق صورت وضعیت",
                 "تعدیل پیمان", "برآورد به‌هنگام", "بخش قطعی و علی‌الحساب"):
        assert name in wb


# ── تابعِ نمایشِ پول (UI): واحد همیشه present، تبدیلِ تومان = ÷۱۰ ──

def test_T114_fmt_money_units():
    from app import fmt_money
    # واحدِ پیش‌فرض ریال است
    assert fmt_money(1234567890, "rial", rounding=False) == "۱,۲۳۴,۵۶۷,۸۹۰ ریال"
    assert "ریال" in fmt_money(1000)
    # تومان = ریال ÷ ۱۰ (تبدیلِ عمدیِ نمایشی، مستند در این آزمون)
    assert fmt_money(1234567890, "toman", rounding=False) == "۱۲۳,۴۵۶,۷۸۹.۰ تومان"
    assert fmt_money(1000, "toman") == "۱۰۰.۰ تومان"
    # بدونِ واحد
    assert fmt_money(1234567890, "rial", rounding=False, with_unit=False) \
        == "۱,۲۳۴,۵۶۷,۸۹۰"


def test_T114_fmt_money_rounding():
    from app import fmt_money
    # رند به ۱۰۰۰ ریال (پیش‌فرض)
    assert fmt_money(1499, "rial") == "۱,۰۰۰ ریال"
    assert fmt_money(1500, "rial") == "۲,۰۰۰ ریال"
    # بدون رند
    assert fmt_money(1499, "rial", rounding=False) == "۱,۴۹۹ ریال"


def test_T114_fmt_money_no_unit_loss():
    # هرگز خروجیِ پولی بدون واحدِ صریح داده نمی‌شود (مگر درخواستِ صریح)
    from app import fmt_money
    for cur in ("rial", "toman"):
        s = fmt_money(999999999999, cur)
        assert "ریال" in s or "تومان" in s
