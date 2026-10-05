# -*- coding: utf-8 -*-
"""tools/make_reference_template.py — فاز E-8 §۶.۱.

قالبِ خالیِ «صورت‌وضعیتِ مرجع» را می‌سازد تا شرکت آن را با دادهٔ واقعی
پر کند و ما بتوانیم خروجیِ موتور را در برابرِ یک صورت‌وضعیتِ تأییدشده
اعتبارسنجی کنیم (§۶.۲ — docs/DATA_REQUEST.md).

سه شیت:
  ۱) «راهنما»        — راهنمای پر کردنِ هر ستون
  ۲) «صورت‌وضعیت»    — جدولِ فصول با یک ردیفِ نمونه (واضح علامت‌گذاری شده)
  ۳) «تعدیل و برآورد» — فیلدهای ΔP و برآورد به‌هنگام با برچسبِ It

اجرا:  python tools/make_reference_template.py
"""
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# خروجیِ استاندارد همیشه UTF-8 باشد — حتی وقتی کدپیجِ کنسول cp1252 است
# (در غیر این صورت printِ متنِ فارسی با UnicodeEncodeError می‌ایستد).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "templates", "reference_statement_template.xlsx")

FA = "۰۱۲۳۴۵۶۷۸۹"


def fa_num(v, digits=2):
    s = f"{v:,.{digits}f}"
    return "".join(FA[int(c)] if c.isdigit() else c for c in s)


HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(name="Tahoma", bold=True, color="FFFFFF", size=11)
BODY_FONT = Font(name="Tahoma", size=11)
NOTE_FONT = Font(name="Tahoma", size=10, color="555555")
TITLE_FONT = Font(name="Tahoma", bold=True, size=14)
EX_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BBBBBB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)


def set_rtl(ws):
    ws.sheet_view.rightToLeft = True


def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ── شیت ۱: راهنما ──
GUIDE = [
    ("ستون", "الزامی؟", "توضیح و فرمت"),
    ("ردیف", "بله", "شمارهٔ ردیف — فقط ترتیبی."),
    ("کد فصل", "بله", "کدِ دو رقمیِ فصلِ فهرست‌بها (مثل «۰۱»). باید با "
     "کدهای `data/fehrest baha 1404/` یکی باشد."),
    ("شرح", "خیر", "عنوانِ فصل — فقط برای خوانایی."),
    ("واحد", "بله", "واحدِ فصل (مترمربع، مترمکعب، کیلوگرم و ...)."),
    ("مقدار", "بله", "کمیتِ اجراشده — عددِ خالص، بدون ویرگول."),
    ("قیمت واحد (ریال)", "بله", "قیمتِ واحدِ قراردادی به **ریال** (نه تومان). "
     "اعدادِ اعشاری مجازند."),
    ("مبلغ (ریال)", "بله", "مقدار × قیمت واحد. موتور این را دوباره حساب "
     "می‌کند؛ اگر با عددِ نوشته‌شده اختلاف داشت، هشدار داده می‌شود."),
    ("ضریب بالاسری", "خیر", "اگر در صورت‌وضعیت ضریب اضافه شده؛ در غیر این "
     "صورت خالی بگذارید (پیش‌فرض: از تنظیمات)."),
    ("ضریب منطقه‌ای", "خیر", "مانند بالا."),
    ("مبلغ نهایی (ریال)", "بله", "مبلغ × ضرایب — جمع کل همین ستون با "
     "`grand_total` موتور مقایسه می‌شود."),
    ("", "", ""),
    ("قواعد", "", ""),
    ("۱", "", "همهٔ مبالغ **ریال** باشند. هیچ تبدیلِ تومان نکنید."),
    ("۲", "", "اعداد را با فرمتِ عددی بنویسید (نه متن)."),
    ("۳", "", "ردیفِ جمعِ کل را در آخر بنویسید و در ستونِ «ردیف» بنویسید "
     "«جمع کل»."),
    ("۴", "", "اگر ردیفی مطمئن نیستید، ستونِ «توضیح» را پر کنید تا دستی "
     "بررسی شود."),
]


# ── شیت ۲: صورت‌وضعیت ──
COLS = ["ردیف", "کد فصل", "شرح", "واحد", "مقدار", "قیمت واحد (ریال)",
        "مبلغ (ریال)", "ضریب بالاسری", "ضریب منطقه‌ای", "مبلغ نهایی (ریال)",
        "توضیح"]
EXAMPLE = ["۱", "۰۱", "کندن و خارج کردن بوته و ریشه‌ها", "مترمربع",
           fa_num(1250.0, 0), fa_num(2312.0, 0), fa_num(2890000.0, 0),
           fa_num(1.3, 1), fa_num(1.04, 2), fa_num(3906720.0, 0),
           "ردیفِ نمونه — قبل از تحویل پاک شود"]


# ── شیت ۳: تعدیل و برآورد ──
ADJ_FIELDS = [
    ("فیلد", "مقدار", "توضیح"),
    ("مبلغ اولیهٔ قرارداد (ریال)", "", "برای کنترلِ سقفِ ۱۰٪ (نامه-۶ / D-18). "
     "بدون آن هیچ کنترلی اجرا نمی‌شود."),
    ("ضریب k", "", "۰٫۹۵ یا ۱ (بند ۱-۸ + تبصرهٔ ۲ / D-01)."),
    ("ΔP — بخش قطعی (ریال)", "", "مبلغِ تعدیلِ قطعی (بند ۸-۴)."),
    ("ΔP — علی‌الحساب (ریال)", "", "مبلغِ تعدیلِ علی‌الحساب."),
    ("ΔP — جمع (ریال)", "", "قطعی + علی‌الحساب؛ باید با خروجیِ موتور برابر "
     "باشد."),
    ("دورهٔ It", "", "مثلاً ۱۴۰۴Q4 یا ۱۴۰۵Q1 — **الزامی** (هر عددِ برآورد "
     "بدون It بی‌معناست)."),
    ("وضعیتِ It", "", "«قطعی» یا «موقت» — **الزامی**."),
    ("ضریبِ موقت", "", "اگر It موقت است (مثلاً ۱٫۱۵۳۱ برای ۱۴۰۵Q1)."),
    ("برآورد به‌هنگام (ریال)", "", "خروجیِ موتور برآورد؛ با It/وضعیت مطابقِ "
     "بالاست."),
    ("شاخصِ دورهٔ مبنا Io", "", "برای بازبینیِ دستی."),
    ("شاخصِ دورهٔ هدف It", "", "برای بازبینیِ دستی."),
]


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb = Workbook()

    # ── شیت ۱: راهنما ──
    ws = wb.active
    ws.title = "راهنما"
    set_rtl(ws)
    ws["A1"] = "راهنمای پر کردنِ قالبِ صورت‌وضعیتِ مرجع"
    ws["A1"].font = TITLE_FONT
    for r, row in enumerate(GUIDE, start=3):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = BORDER
    style_header(ws, 3, 3)
    widths(ws, [26, 10, 78])

    # ── شیت ۲: صورت‌وضعیت ──
    ws = wb.create_sheet("صورت‌وضعیت")
    set_rtl(ws)
    ws["A1"] = "صورت‌وضعیتِ مرجع — فصول"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("ستون‌های الزامی: ردیف، کد فصل، واحد، مقدار، قیمت واحد، "
                "مبلغ، مبلغ نهایی. ردیفِ نمونه را پاک کنید.")
    ws["A2"].font = NOTE_FONT
    hdr_row = 4
    for c, name in enumerate(COLS, start=1):
        ws.cell(row=hdr_row, column=c, value=name)
    style_header(ws, hdr_row, len(COLS))
    ex_row = hdr_row + 1
    for c, val in enumerate(EXAMPLE, start=1):
        cell = ws.cell(row=ex_row, column=c, value=val)
        cell.font = BODY_FONT
        cell.fill = EX_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center")
    # جایِ ردیف‌ها
    for r in range(ex_row + 1, ex_row + 26):
        for c in range(1, len(COLS) + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BORDER
            cell.font = BODY_FONT
    total_row = ex_row + 27
    ws.cell(row=total_row, column=1, value="جمع کل")
    ws.cell(row=total_row, column=11, value="جمعِ ستونِ «مبلغ نهایی»")
    for c in range(1, len(COLS) + 1):
        cell = ws.cell(row=total_row, column=c)
        cell.font = Font(name="Tahoma", bold=True, size=11)
        cell.border = BORDER
        cell.fill = PatternFill("solid", fgColor="D9E2F3")
    widths(ws, [7, 8, 38, 11, 12, 15, 16, 10, 11, 17, 30])
    ws.freeze_panes = ws.cell(row=hdr_row + 1, column=1)

    # ── شیت ۳: تعدیل و برآورد ──
    ws = wb.create_sheet("تعدیل و برآورد")
    set_rtl(ws)
    ws["A1"] = "تعدیلِ پیمان و برآورد به‌هنگام"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("هر عددِ برآورد **باید** دورهٔ It و وضعیتِ «قطعی/موقت» خود "
                "را داشته باشد (قاعدهٔ §۱۸-۱۰-۶).")
    ws["A2"].font = NOTE_FONT
    for r, row in enumerate(ADJ_FIELDS, start=4):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = BORDER
        if r > 4:
            ws.cell(row=r, column=2).fill = EX_FILL
    style_header(ws, 4, 3)
    widths(ws, [28, 26, 60])

    wb.save(OUT)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
