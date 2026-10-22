# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║  متره‌یار — سامانهٔ جامع دفتر فنی هوشمند (نسخهٔ ۴.۰)                  ║
║  برپایهٔ فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه ۱۴۰۴ (سازمان برنامه)      ║
║  ورودی: Schedule های Revit + هر دو فرمت خروجی اسکریپت‌های Dynamo      ║
║  اجرا: streamlit run app.py                                          ║
║  کتابخانه‌های مجاز: streamlit, pandas, openpyxl, xlsxwriter          ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import io
import logging
import os
import re
import csv
import copy
import difflib
import json
from datetime import datetime, date, timedelta, timezone

import pandas as pd
import streamlit as st
import xlsxwriter
import openpyxl

# ────────────────────────────────────────────────────────────────
# پیکربندی لاگ‌گیری
# ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_logger = logging.getLogger("MetreYar")

APP_NAME = "متره‌یار — دفتر فنی هوشمند"
APP_VERSION = "4.0.0"

# فاز E-10.1 §۳ — حالتِ ارائه. وقتی demo_mode روشن است، این واترمارک روی
# همهٔ خروجیِ Excel و همهٔ صفحاتِ UI می‌نشیند تا هر کسی که خروجی را می‌بیند
# بداند با صورت‌وضعیتِ تأییدشدهٔ واقعی اعتبارسنجی نشده است.
DEMO_BANNER = "نسخهٔ نمایشی – اعتبارسنجی‌نشده با صورت‌وضعیت تأییدشده"

# ════════════════════════════════════════════════════════════════
# توابع دست‌نویس سطح مدول (بدون هیچ کتابخانهٔ خارجی)
# ════════════════════════════════════════════════════════════════

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"

# نگاشت حروف عربی به فرم استاندارد فارسی (برای نرمال‌سازی متن)
_CHAR_TRANS = str.maketrans({
    "ك": "ک", "ى": "ی", "ة": "ه", "ئ": "ی",
    "إ": "ا", "أ": "ا", "ٱ": "ا", "ء": "", "ٔ": "",
    # «ی عربی» (U+064A): تنها شکلِ ی در انکودینگ Windows-1256 است؛
    # بدون این نگاشت فایل‌های cp1256 بعد از رمزگشایی با متن فارسی می‌انمایند.
    "ي": "ی",
})


def convert_persian_digits(text, to_english: bool = True) -> str:
    """
    تبدیل ارقام فارسی/عربی به انگلیسی (to_english=True) یا بالعکس (False).
    ورودی هر نوع داده‌ای می‌تواند باشد؛ خروجی همیشه رشته است.
    """
    s = str(text)
    if to_english:
        out = []
        for ch in s:
            i = FA_DIGITS.find(ch)
            if i >= 0:
                out.append(EN_DIGITS[i])
                continue
            j = AR_DIGITS.find(ch)
            out.append(EN_DIGITS[j] if j >= 0 else ch)
        return "".join(out)
    return "".join(FA_DIGITS[int(c)] if c.isdigit() else c for c in s)


def fa(value) -> str:
    """تبدیل ارقام یک مقدار به ارقام فارسی برای نمایش."""
    return convert_persian_digits(value, to_english=False)


def fa_float(value, ndigits: int = 1) -> str:
    """قالب‌بندی عدد اعشاری با جداکنندهٔ هزارگان و ارقام فارسی."""
    return fa(f"{float(value):,.{ndigits}f}")


def decode_text(raw: bytes) -> str:
    """
    تبدیل بایت‌های یک فایل متنی به رشته با تشخیص خودکار انکودینگ.

    زنجیرهٔ امن و قطعی (بدون وابستگی به کتابخانهٔ تشخیص انکودینگ):
      ۱) UTF-8 با BOM  (خروجی واقعی Revit)
      ۲) UTF-8 بدون BOM (فهرست‌بها، فایل‌های Mapping)
      ۳) Windows-1256   (خروجی Revit در ویندوز فارسی‌محور قدیمی)

    فایل‌های UTF-8 موجود هیچ تغییری در رفتار نمی‌بینند (بدون پس‌رفت).
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("windows-1256", errors="replace")


def normalize_text(text) -> str:
    """
    نرمال‌سازی کامل متن فارسی/انگلیسی برای مقایسه‌های فازی:
    یکسان‌سازی حروف، حذف اِعراب، نیم‌فاصله→فاصله، تبدیل ارقام، حذف علائم نگارشی.
    """
    if text is None:
        return ""
    t = convert_persian_digits(str(text)).lower()
    t = re.sub(r"[ً-ْٰ]", "", t)                     # حذف اِعراب عربی
    t = re.sub(r"[‎‏​‍‌]", " ", t)              # حذف علائم جهت‌دهی یونی‌کد (شامل نیم‌فاصله U+200C)
    t = t.translate(_CHAR_TRANS)
    t = re.sub(r"[-_/\\.,;:!?(){}[\]\"'«»<>|*+×÷=~#$%^&\n\r\t]+", " ", t)
    t = re.sub(r"(ها|های)(?=\s|$)", " ", t)         # پسوند «های/ها» چسبیده
    return re.sub(r"\s+", " ", t).strip()


def parse_value_unit(raw):
    """
    تجزیهٔ رشته‌های عددی واحد‌دار Revit مانند «18.65 m³»، «74,484.56 mm»، «12001.91 kg».
    خروجی: (مقدار float، واحد str) یا None در صورت شکست.
    """
    if raw is None:
        return None
    t = convert_persian_digits(str(raw)).strip()
    if not t:
        return None
    m = re.match(r"^([+-]?[0-9\s,٬'’ .\u202f]+)\s*([^\d\s].*)?$", t)
    if not m:
        return None
    num = (m.group(1) or "").replace(" ", "").replace(" ", "").replace("\u202f", "")
    # تشخیص ممیز اعشار: اگر ویرگول بعد از نقطه آمده باشد، ویرگول ممیز است
    if num.rfind(",") > num.rfind("."):
        num = num.replace(".", "").replace(",", ".")
    else:
        num = num.replace(",", "")
    try:
        value = float(num)
    except ValueError:
        return None
    return value, (m.group(2) or "").strip().lower()


def to_si(value: float, unit: str):
    """تبدیل مقدار+واحد به واحد استاندارد SI. خروجی: (مقدار تبدیل‌شده، نوع کمیت)"""
    u = unit.replace(" ", "").lower()
    if u in ("mm", "میلیمتر"):
        return value / 1000.0, "m"
    if u in ("cm", "سانتیمتر"):
        return value / 100.0, "m"
    if u in ("m", "متر", "مترطول"):
        return value, "m"
    if u in ("mm2", "mm²"):
        return value / 1e6, "m2"
    if u in ("cm2", "cm²"):
        return value / 1e4, "m2"
    if u in ("m2", "m²", "مترمربع"):
        return value, "m2"
    if u in ("m3", "m³", "مترمکعب"):
        return value, "m3"
    if u in ("g", "gr", "گرم"):
        return value / 1000.0, "kg"
    if u in ("kg", "کیلوگرم"):
        return value, "kg"
    if u in ("ton", "t", "تن"):
        return value * 1000.0, "kg"
    if u in ("", "-", "#", "count", "عدد"):
        return value, "count"
    return value, None


def fmt_num(n: float, dec: int = 2) -> str:
    """قالب‌بندی عدد با ارقام فارسی و جداکنندهٔ هزارگان."""
    try:
        if abs(float(n) - round(float(n))) < 1e-9 and dec == 2:
            return fa(f"{float(n):,.0f}")
        return fa(f"{float(n):,.{dec}f}")
    except (TypeError, ValueError):
        return fa(str(n))


def fmt_money(rial: float, currency: str = "rial", rounding: bool = True, with_unit: bool = True) -> str:
    """قالب‌بندی پول با واحد انتخابی (ریال/تومان) و گزینهٔ رند ۱۰۰۰ ریال."""
    v = round(float(rial) / 1000) * 1000 if rounding else round(float(rial))
    if currency == "toman":
        s, unit = f"{v / 10:,.1f}", "تومان"
    else:
        s, unit = f"{v:,.0f}", "ریال"
    return fa(s) + (f" {unit}" if with_unit else "")


# ════════════════════════════════════════════════════════════════
# اجباری: تاریخ شمسی دست‌نویس
# ════════════════════════════════════════════════════════════════

def gregorian_to_jalali(gy: int, gm: int, gd: int):
    """
    تبدیل تاریخ میلادی به شمسی (الگوریتم استاندارد JDN — بدون کتابخانه خارجی).
    خروجی: تاپل (سال، ماه، روز جلالی).
    """
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm = 1 + days // 31 if days < 186 else 7 + (days - 186) // 30
    jd = 1 + (days % 31 if days < 186 else (days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int):
    """
    تبدیل تاریخ شمسی به میلادی (معکوسِ gregorian_to_jalali — ایراد ۱۳).

    پیاده‌سازی: جستجوی دودویی روی همان تابع میلادی→شمسیِ موجود. این
    روش به هیچ فرضی دربارهٔ قواعد کبیسه یا مبدأِ شمارش روزها نیاز
    ندارد و همواره با gregorian_to_jalali دقیقاً سازگار است.
    ورودی نامعتبر (مثل اسفند ۳۰ در سال غیرکبیسه) → None.
    """
    if not (1300 <= jy <= 1500 and 1 <= jm <= 12 and jd >= 1):
        return None
    target = (jy, jm, jd)
    # سال جلالی ≈ میلادی − ۶۲۱/۶۲۲؛ بازهٔ جستجو سه سال میلادی است.
    lo = date(jy + 620, 1, 1).toordinal()
    hi = date(jy + 623, 12, 31).toordinal()
    while lo <= hi:
        mid = (lo + hi) // 2
        d = date.fromordinal(mid)
        got = gregorian_to_jalali(d.year, d.month, d.day)
        if got == target:
            return d.year, d.month, d.day
        if got < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def jalali_to_iso(text):
    """
    تاریخ شمسی (متن) → ISO میلادی «YYYY-MM-DD» یا None (ایراد ۱۳).

    ستون مخفی میلادی در Excel از این تابع ساخته می‌شود. ورودی نامعتبر → None.
    """
    p = TechnicalOfficeEngine._parse_jalali(text)
    if not p:
        return None
    g = jalali_to_gregorian(*p)
    if g is None:
        return None
    return "%04d-%02d-%02d" % g


def jalali_now_str():
    """تاریخ و ساعت لحظهٔ به وقت تهران، به‌صورت متن شمسی (برای سابقهٔ
    ویرایش و فایل کناری — قاعدهٔ طلایی ۲: تمام تاریخ‌ها شمسی)."""
    tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tz)
    j = gregorian_to_jalali(now.year, now.month, now.day)
    return f"{j[0]}/{j[1]:02d}/{j[2]:02d} {now.hour:02d}:{now.minute:02d}"


def today_jalali() -> str:
    """تاریخ شمسی امروز به فرمت «۱۴۰۴/۰۷/۲۵» با ارقام فارسی."""
    now = datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return fa(f"{jy}/{jm:02d}/{jd:02d}")


def is_valid_jalali_date(text: str) -> bool:
    """اعتبارسنجی رشتهٔ تاریخ شمسی ورودی کاربر (سال/ماه/روز با جداکنندهٔ / یا -)."""
    if not text or not str(text).strip():
        return False
    m = re.match(r"^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$", convert_persian_digits(str(text)).strip())
    if not m:
        return False
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1300 <= y <= 1500 and 1 <= mo <= 12 and d >= 1):
        return False
    dim = 31 if mo <= 6 else (30 if mo <= 11 else 29)
    return d <= dim


# ════════════════════════════════════════════════════════════════
# اجباری: تبدیل عدد به حروف فارسی (مبالغ صورت‌وضعیت)
# ════════════════════════════════════════════════════════════════

_ONES = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
_TEENS = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
_TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
_HUNDREDS = ["", "یکصد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]
_SCALES = ["", " هزار", " میلیون", " میلیارد", " بیلیون", " بیلیارد", " تریلیون"]


def _three_digits_word(num: int) -> str:
    """تبدیل یک عدد سه‌رقمی به حروف فارسی."""
    parts = []
    h, r = divmod(num, 100)
    if h:
        parts.append(_HUNDREDS[h])
    if 10 <= r < 20:
        parts.append(_TEENS[r - 10])
    else:
        t, o = divmod(r, 10)
        if t:
            parts.append(_TENS[t])
        if o:
            parts.append(_ONES[o])
    return " و ".join(parts)


def number_to_persian_words(number) -> str:
    """تبدیل عدد صحیح به حروف فارسی (از یک تا تریلیون)."""
    try:
        n = int(abs(float(number)))
    except (TypeError, ValueError):
        return ""
    if n == 0:
        return "صفر"
    groups, scale = [], 0
    while n > 0 and scale < len(_SCALES):
        g = n % 1000
        if g:
            groups.insert(0, _three_digits_word(g) + _SCALES[scale])
        n //= 1000
        scale += 1
    return re.sub(r"\s+", " ", " و ".join(groups)).strip()


def money_to_words(rial: float) -> str:
    """مبلغ ریال به حروف فارسی (با مدیریت مقادیر منفی)."""
    r = int(round(float(rial)))
    if r == 0:
        return "صفر ریال"
    return ("منفی " if r < 0 else "") + f"{number_to_persian_words(r)} ریال"


# ════════════════════════════════════════════════════════════════
# اجباری: موتور تطبیق فازی دست‌نویس با difflib (بدون rapidfuzz)
# ════════════════════════════════════════════════════════════════

_STOP_WORDS = {"و", "به", "از", "در", "با", "برای", "هر", "نوع", "تا", "مورد"}


def _tokens(text: str):
    """مجموعهٔ توکن‌های نرمال‌شدهٔ یک متن بدون کلمات ایست."""
    return sorted({t for t in normalize_text(text).split() if t and t not in _STOP_WORDS})


def _quick_ratio(a: str, b: str) -> float:
    """نسبت شباهت ترتیبی دو رشته با difflib (۰ تا ۱)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _token_set_ratio(a: str, b: str) -> float:
    """
    Token-Set Ratio به سبک RapidFuzz — پیاده‌سازی داخلی با difflib:
    اشتراک توکن‌ها به‌علاوهٔ باقی‌ماندهٔ هر طرف به‌صورت جداگانه مقایسه می‌شود.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    set_a, set_b = set(ta), set(tb)
    inter = sorted(set_a & set_b)
    s0 = " ".join(inter)
    s1 = " ".join(inter + sorted(set_a - set_b))
    s2 = " ".join(inter + sorted(set_b - set_a))
    return max(_quick_ratio(s0, s1), _quick_ratio(s0, s2), _quick_ratio(s1, s2))


def _numeric_bonus(a: str, b: str) -> float:
    """امتیاز افزودهٔ اشتراک اعداد (عیار بتن، قطر میلگرد، ضخامت و...)."""
    na = re.findall(r"\d+(?:\.\d+)?", normalize_text(a))
    if not na:
        return 0.0
    nb = set(re.findall(r"\d+(?:\.\d+)?", normalize_text(b)))
    shared = sum(1 for t in na if t in nb)
    return min(0.06, shared / len(na) * 0.08)


def fuzzy_match(query: str, choices, threshold: float = 0.6):
    """
    تطبیق فازی متن با difflib استاندارد پایتون.
    ورودی: عبارت جست‌وجو + فهرست گزینه‌ها + آستانه.
    خروجی: (بهترین گزینه، امتیاز، فهرست کامل (گزینه، امتیاز) مرتب‌شده) یا (None، ۰، []).
    """
    scored = []
    for ch in choices:
        base = _token_set_ratio(query, str(ch))
        score = base * 0.94 + _numeric_bonus(query, str(ch))
        if base >= 0.995:
            score += 0.06
        scored.append((ch, min(1.0, score)))
    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored or scored[0][1] < threshold:
        return None, 0.0, scored
    return scored[0][0], scored[0][1], scored


def conf_label(c: float) -> str:
    """برچسب فارسی درجهٔ اطمینان تطبیق."""
    if c >= 0.92:
        return "قطعی"
    if c >= 0.78:
        return "بالا"
    if c >= 0.62:
        return "متوسط"
    return "پایین"


# وزن واحد میلگرد (کیلوگرم بر متر) — جدول اشتال
REBAR_UNIT_WEIGHT = {
    6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888, 14: 1.208, 16: 1.578,
    18: 1.998, 20: 2.466, 22: 2.984, 25: 3.853, 28: 4.834, 30: 5.549,
    32: 6.313, 36: 7.99, 40: 9.864,
}


def rebar_unit_weight(d_mm: float) -> float:
    """وزن یکای میلگرد از روی قطر (kg/m)؛ در غیاب قطر جدول، از فرمول تقریبی."""
    d = int(round(float(d_mm)))
    return REBAR_UNIT_WEIGHT.get(d, (d * d) / 162.0)


# ════════════════════════════════════════════════════════════════
# کلاس FehrestBahaParser — پایگاه فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴
# ردیف‌های فصل‌های ۰۱ و ۰۳ با ارقام رسمی فایل مرجع تعبیه شده‌اند؛
# ردیف‌های کلیدی فصل‌های ۰۵ تا ۲۸ با پرچم «تخمینی» و قابل‌جایگزینی
# توسط فایل رسمی کاربر یا ویرایش دستی هستند.
# ════════════════════════════════════════════════════════════════

CHAPTERS = {
    "01": "عملیات تخریب",
    "02": "عملیات خاکی با دست",
    "03": "عملیات خاکی با ماشین",
    "04": "عملیات بنایی با سنگ",
    "05": "قالب‌بندی غیرفولادی",
    "06": "قالب‌بندی فولادی",
    "07": "کارهای فولادی با میلگرد",
    "08": "بتن درجا",
    "09": "کارهای فولادی سنگین",
    "10": "سقف تیرچه و بلوک",
    "11": "آجرکاری و شفته‌ریزی",
    "12": "بتن پیش‌ساخته و بلوک‌چینی",
    "13": "عایق‌کاری رطوبتی",
    "14": "عایق‌کاری حرارتی و پوشش‌های مقاوم در برابر آتش",
    "15": "کارهای آزبست سیمان",
    "16": "کارهای فولادی سبک",
    "17": "کارهای آلومینیومی",
    "18": "اندودکاری و بندکشی",
    "19": "کارهای چوبی",
    "20": "کاشی‌کاری با کاشی‌های سرامیکی",
    "21": "فرش موزاییک و کف‌پوش بتنی",
    "22": "کارهای سنگی با سنگ پلاک",
    "23": "کارهای پلاستیکی و پلیمری",
    "24": "شیشه و نصب آن",
    "25": "رنگ‌آمیزی",
    "26": "زیراساس و اساس",
    "27": "آسفالت",
    "28": "حمل و نقل",
    "29": "کارهای دستمزدی",
    "41": "مصالح پایکار (پیوست ۱)",
    "99": "تجهیز و برچیدن کارگاه",
}


def chapter_title(no: str) -> str:
    """عنوان فارسی فصل فهرست‌بها بر اساس شمارهٔ دورقمی."""
    return CHAPTERS.get(no, f"فصل {no}")


def rebar_density(rebar_kg: float, concrete_m3: float) -> float:
    """تراکم میلگرد (kg/m³) = وزن آرماتور ÷ حجم بتن سازه‌ای.

    مبنای شرط ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴ (آستانهٔ ۱۸۰ kg/m³).
    """
    return rebar_kg / concrete_m3 if concrete_m3 > 0 else 0.0


# آستانهٔ تراکم میلگرد در شرط ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴:
# «...در صورتی که میلگرد به کار رفته بیش از ۱۸۰ کیلوگرم در مترمکعب بتن باشد».
REBAR_DENSITY_THRESHOLD = 180.0


# آستانهٔ ضخامت در شرط ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴:
# «هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد» (بر حسب متر).
THIN_CONCRETE_THRESHOLD_M = 0.15


def thin_concrete_net(tables) -> float:
    """حجم کف‌سازی بتنی روی زمین با ضخامت ≤ ۱۵ سانتی‌متر (m³) — از داده‌ها.

    مبنای شرط ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴ (بند ۳-۳ فصل ۸): این اضافه‌بها
    فقط به «کف‌سازی بتنی» (دال روی زمین) تعلق می‌گیرد، نه به دال معلق.
    نشانهٔ دال روی زمین این است که المان در جدول خودش هم ستون «حجم» و هم
    ستون «مساحت» دارد (مساحت رویه با ضخامت ثابت) و نیازی به قالب‌بندی زیره
    ندارد. دال‌های معلق (گروه سازه‌ای «سقف») که مساحتشان فقط از جدول
    قالب‌بندی زیره به‌دست می‌آید، ارزیابی نمی‌شوند.

    تیر/ستون/پله هم ارزیابی نمی‌شوند: مساحت قالب‌بندی آن‌ها شامل کناره‌ها
    و پاهاست و حجم÷مساحت ضخامت نیست.
    """
    thin = 0.0
    for t in tables:
        if t["kind"] not in ("lean_concrete", "structural_concrete"):
            continue
        for r in t["rows"]:
            if r["is_subtotal"]:
                continue
            v = r["values"].get("volume", 0) or 0
            if v <= 0:
                continue
            # فقط مساحت رویهٔ همان جدول (دال روی زمین، بدون قالب‌بندی زیره)؛
            # دال معلق که مساحتش فقط از قالب‌بندی زیره می‌آید ارزیابی نمی‌شود.
            a = r["values"].get("area", 0) or 0
            if a > 0 and v / a <= THIN_CONCRETE_THRESHOLD_M:
                thin += v
    return thin


# ردیف‌های رسمی تأییدشده (کد، فصل، شرح، واحد، بها) — استخراج‌شده از فایل fehrest_1404
_FEHREST_VERIFIED = [
    ("010301", "01", "تخریب کلی ساختمان‌های با مصالح خشتی و چینه‌ای", "مترمربع", 3065000),
    ("010302", "01", "تخریب کلی ساختمان‌های با مصالح بنایی غیر از خشتی و چینه‌ای", "مترمربع", 3623000),
    ("010405", "01", "تخریب بتن غیرمسلح", "مترمکعب", 15775000),
    ("010406", "01", "تخریب بتن مسلح، به انضمام بریدن میلگردها", "مترمکعب", 22928000),
    ("010407", "01", "تخریب شفته با هر عیار", "مترمکعب", 3432000),
    ("010409", "01", "تخریب سقف تیرچه و بلوک به انضمام بریدن تیرچه و میلگردها", "مترمکعب", 11468000),
    ("010509", "01", "تراشیدن اندودهای ماسه سیمان، باتارد، یا ماسه آهک از روی کلیه سطوح", "مترمربع", 1196000),
    ("010705", "01", "برچیدن هر نوع اسکلت فولادی ساختمان با هرگونه اتصال", "کیلوگرم", 30900),
    ("030103", "03", "کندن زمین در زمین‌های خاکی با بولدوزر و حمل مواد حاصل تا فاصله ۲۰ متر از مرکز ثقل برداشت و توده کردن آن", "مترمکعب", 147000),
    ("030105", "03", "کندن زمین در زمین‌های سنگی با بولدوزر و حمل مواد حاصل تا فاصله ۲۰ متر", "مترمکعب", 933500),
    ("030301", "03", "رگلاژ و پروفیله کردن سطح شیروانی ترانشه‌ها و شیروانی خاک‌ریزها", "مترمربع", 44000),
    ("030501", "03", "کندن زمین با بیل هیدرولیکی در زمین‌های خاکی و ریختن خاک کنده شده در کنار محل", "مترمکعب", 314000),
    ("030504", "03", "کندن زمین با چکش هیدرولیکی در زمین‌های سنگی و حمل و تخلیه مواد تا فاصله ۲۰ متر", "مترمکعب", 3039000),
    ("030601", "03", "اضافه‌بها به ردیف‌های کندن زمین، هرگاه عمق کندن زمین تا ۲ متر باشد", "مترمکعب", 51300),
    ("030701", "03", "بارگیری مواد حاصل از عملیات خاکی و حمل با کامیون تا فاصله ۱۰۰ متری مرکز ثقل برداشت و تخلیه آن", "مترمکعب", 210500),
    ("030801", "03", "تسطیح بستر خاک‌ریزها یا سطوح کنده شده با گریدر یا سایر وسایل مکانیکی", "مترمربع", 5650),
    ("030803", "03", "آب‌پاشی و کوبیدن زمین طبیعی یا بستر خاک‌ریزها تا عمق ۱۵ سانتی‌متر با تراکم ۹۰ درصد پروکتور اصلاحی", "مترمربع", 23100),
    ("030903", "03", "پخش، آب‌پاشی، تسطیح و کوبیدن قشرهای خاک یا توونان ریخته شده با ۹۵ درصد کوبیدگی پروکتور اصلاحی", "مترمکعب", 306500),
    ("031001", "03", "ریختن خاک‌های کنار پی‌ها، گودها و ترانشه‌ها به صورت لایه‌لایه به درون آن‌ها با وسیله مکانیکی", "مترمکعب", 54500),
]

# ردیف‌های کلیدی سازه‌ای با بهای تخمینی پیش‌فرض (قابل‌ویرایش / قابل‌جایگزینی با فایل رسمی)
_FEHREST_ESTIMATED = [
    ("050101", "تهیه وسایل و قالب‌بندی چوبی برای پی‌ها و شناژهای پی", "مترمربع", 1050000),
    ("050102", "تهیه وسایل و قالب‌بندی چوبی برای ستون‌ها و شناژهای قائم", "مترمربع", 1400000),
    ("050103", "تهیه وسایل و قالب‌بندی چوبی برای تیرها و شناژهای افقی", "مترمربع", 1350000),
    ("050104", "تهیه وسایل و قالب‌بندی چوبی برای تاوه‌ها (دال‌ها) و سقف‌ها", "مترمربع", 1250000),
    ("050105", "تهیه وسایل و قالب‌بندی چوبی برای پله‌ها", "مترمربع", 1180000),
    ("060101", "تهیه وسایل و قالب‌بندی با استفاده از قالب فلزی در پی‌ها و شناژهای پی", "مترمربع", 1150000),
    ("060201", "تهیه وسایل و قالب‌بندی با استفاده از قالب فلزی در دیوارها به ارتفاع تا ۳٫۵ متر", "مترمربع", 1480000),
    ("060301", "تهیه وسایل و قالب‌بندی با استفاده از قالب فلزی در ستون‌ها و شناژهای قائم با مقطع چهارضلعی، به ارتفاع تا ۳٫۵ متر", "مترمربع", 1750000),
    ("060401", "تهیه وسایل و قالب‌بندی با استفاده از قالب فلزی در تاوه‌ها (دال‌ها) به ارتفاع تا ۳٫۵ متر", "مترمربع", 1620000),
    ("060501", "تهیه وسایل و قالب‌بندی با استفاده از قالب فلزی در تیرها و شناژهای افقی با ارتفاع جان تا ۶۰ سانتی‌متر", "مترمربع", 1580000),
    ("060701", "تهیه وسایل و قالب‌بندی با استفاده از قالب فلزی در پله‌ها و رمپ‌ها", "مترمربع", 1500000),
    ("070101", "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد ساده از نوع AI برای بتن مسلح، با سیم‌پیچی لازم", "کیلوگرم", 505000),
    ("070201", "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار از نوع AIII به قطر تا ۱۰ میلی‌متر، برای بتن مسلح با سیم‌پیچی لازم", "کیلوگرم", 522000),
    ("070202", "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار از نوع AIII به قطر ۱۲ تا ۱۸ میلی‌متر، برای بتن مسلح با سیم‌پیچی لازم", "کیلوگرم", 510000),
    ("070203", "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار از نوع AIII به قطر ۲۰ و بیش از ۲۰ میلی‌متر، برای بتن مسلح با سیم‌پیچی لازم", "کیلوگرم", 498000),
    ("080201", "تهیه و اجرای بتن مگر (با عیار ۱۵۰ کیلوگرم سیمان در مترمکعب)", "مترمکعب", 5200000),
    ("080301", "تهیه و اجرای بتن با عیار حداقل ۳۵۰ کیلوگرم سیمان در مترمکعب برای انواع پی‌ها", "مترمکعب", 6900000),
    ("080302", "تهیه و اجرای بتن با عیار حداقل ۳۵۰ کیلوگرم سیمان در مترمکعب برای ستون‌ها و تیرها", "مترمکعب", 7400000),
    ("080303", "تهیه و اجرای بتن با عیار حداقل ۳۵۰ کیلوگرم سیمان در مترمکعب برای دال‌ها و سقف‌ها", "مترمکعب", 7200000),
    ("080304", "تهیه و اجرای بتن با عیار حداقل ۳۵۰ کیلوگرم سیمان در مترمکعب برای پله‌ها", "مترمکعب", 7450000),
    ("100101", "تهیه و اجرای سقف تیرچه و بلوک با بلوک‌های سیمانی یا سفالی، به انضمام پاشنه و میلگرد پاشنه", "مترمربع", 2350000),
    ("100102", "تهیه و اجرای سقف تیرچه و بلوک با بلوک‌های پلی‌استایرن منبسط‌شده (یونولیت)، به انضمام پاشنه و میلگرد پاشنه", "مترمربع", 2780000),
    ("110101", "آجرکاری با آجر فشاری و ملات ماسه سیمان در سقف‌ها و ضرورت‌های ساختمان", "مترمکعب", 3950000),
    ("110201", "شفته‌ریزی با ماسه‌باطره و سیمان برای کف‌ها و بام‌ها", "مترمربع", 1300000),
    ("120101", "دیوارچینی با بلوک سبک سیمانی (پوکه‌ای) به ضخامت تا ۷ سانتی‌متر با ملات ماسه سیمان", "مترمربع", 850000),
    ("120103", "دیوارچینی با بلوک سبک سیمانی (پوکه‌ای) به ضخامت ۱۵ سانتی‌متر با ملات ماسه سیمان", "مترمربع", 1050000),
    ("120104", "دیوارچینی با بلوک سبک سیمانی (پوکه‌ای) به ضخامت ۲۰ سانتی‌متر با ملات ماسه سیمان", "مترمربع", 1250000),
    ("180101", "اندود گچ و خاک روی سطوح آجری، بلوکی و مانند آن", "مترمربع", 640000),
    ("180102", "اندود گچ رویه روی کلیهٔ سطوح", "مترمربع", 620000),
    ("210101", "فرش موزاییک ساده (۳۰×۳۰ سانتی‌متر) با ملات دوغاب", "مترمربع", 1900000),
    ("280101", "حمل مصالح فلزی (میلگرد و پروفیل) تا فاصله ۱۰ کیلومتر", "تن", 420000),
]

# واحدهای مرکب (تن-کیلومتر، مترمربع-ماه) باید پیش از پایهٔ خود بیایند تا
# تطبیق پیشوندی، واحد کامل را پیش از شکل کوتاه‌تر آن برگزیند.
_UNIT_WORDS = ["مترمربع-ماه", "مترمربع", "مترمکعب", "دسیمترمکعب", "مترطول",
               "کیلوگرم", "تن-کیلومتر", "تن", "اصله", "رشته", "عدد",
               "دستگاه", "لنگه", "مقطوع", "درصد", "باب", "رقم"]


class FehrestBahaParser:
    """پارسر و مدیر پایگاه دادهٔ ردیف‌های فهرست‌بهای ۱۴۰۴."""

    @staticmethod
    def embedded():
        """ساخت پایگاه پیش‌فرض (ردیف‌های رسمی + ردیف‌های کلیدی تخمینی)."""
        rows = [
            {"code": c, "chapter": ch, "desc": d, "unit": u, "price": float(p), "estimated": False}
            for c, ch, d, u, p in _FEHREST_VERIFIED
        ]
        rows += [
            {"code": c, "chapter": c[:2], "desc": d, "unit": u, "price": float(p), "estimated": True}
            for c, d, u, p in _FEHREST_ESTIMATED
        ]
        return rows

    @staticmethod
    def _cell_number(cell: str):
        """تجزیهٔ سلول عددی فهرست‌بها (با جداکنندهٔ هزارگان) → float یا None."""
        t = convert_persian_digits(cell).replace(",", "").replace("٬", "").replace(" ", "")
        if not re.match(r"^-?\d+(\.\d+)?$", t):
            return None
        try:
            return float(t)
        except ValueError:
            return None

    @staticmethod
    def parse_text(text: str):
        """
        تجزیهٔ فایل متنی/CSV فهرست‌بها با ساختار «شمارهٔ ۶رقمی | فصل | شرح | واحد | بهای واحد»
        (جداکننده تب یا کاما). خروجی: (فهرست ردیف‌ها، تعداد سطرهای ناخوانا).
        """
        rows, skipped, seen = [], 0, set()
        for raw in io.StringIO(text):
            line = raw.strip()
            if not line:
                continue
            if "\t" in line:
                cells = [c.strip().strip('"') for c in line.split("\t")]
            else:
                try:
                    cells = [c.strip() for c in next(csv.reader(io.StringIO(line)))]
                except csv.Error:
                    cells = line.split(",")
            if len(cells) < 2:
                continue
            code_idx = next((i for i, c in enumerate(cells)
                             if re.match(r"^\d{6}$", convert_persian_digits(c))), -1)
            if code_idx < 0:
                skipped += 1
                continue
            code = convert_persian_digits(cells[code_idx])
            after = [c for c in cells[code_idx + 1:] if c]
            chapter = code[:2]
            for i, c in enumerate(after):
                if re.match(r"^\d{1,2}$", convert_persian_digits(c)):
                    chapter = convert_persian_digits(c).zfill(2)
                    after.pop(i)
                    break
            price = 0.0
            for c in reversed(after):
                v = FehrestBahaParser._cell_number(c)
                if v is not None and v != 0:
                    price = v
                    break
            unit = ""
            for c in after:
                w = c.replace("«", " ").replace("»", " ").strip()
                if any(w == u or w.startswith(u + " ") or w.startswith(u + "-")
                       for u in _UNIT_WORDS):
                    unit = w
                    break
            texts = [c for c in after
                     if FehrestBahaParser._cell_number(c) is None and c != unit and len(c) > 2]
            desc = max(texts, key=len, default="")
            desc = re.sub(r"\s+", " ", re.sub(r"[\"«»]", " ", desc)).strip()
            if len(desc) < 5:
                skipped += 1
                continue
            if not unit:
                unit = ("مترمکعب" if re.search(r"مترمکعب|حجم|بتن|خاک", desc)
                        else "کیلوگرم" if re.search(r"میلگرد|آهن|وزن", desc)
                        else "مترطول" if "مترطول" in desc else "مترمربع")
            if code in seen:
                continue
            seen.add(code)
            rows.append({"code": code, "chapter": chapter, "desc": desc,
                         "unit": unit, "price": float(price), "estimated": False})
        return rows, skipped

    @staticmethod
    def merge(base_rows, uploaded_rows):
        """ادغام فهرست آپلودی کاربر با پایگاه؛ ردیف‌های رسمی جایگزین تخمینی می‌شوند."""
        merged = {r["code"]: dict(r) for r in base_rows}
        for r in uploaded_rows:
            merged[r["code"]] = {**r, "estimated": False}
        return sorted(merged.values(), key=lambda r: r["code"])

    @staticmethod
    def by_code(rows, code: str):
        """یافتن یک ردیف بر اساس کد شش‌رقمی."""
        for r in rows:
            if r["code"] == code:
                return r
        return None

    @staticmethod
    def search(rows, query: str, top: int = 5, min_score: float = 0.3):
        """جست‌وجوی فازی در پایگاه؛ خروجی: فهرست (ردیف، امتیاز) مرتب‌شده."""
        out = []
        for row in rows:
            _, score, _ = fuzzy_match(query, [row["desc"]], threshold=-1)
            if score >= min_score:
                out.append((row, score))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top]


# ════════════════════════════════════════════════════════════════
# کلاس RevitScheduleParser — تجزیه‌گر خروجی‌های Schedule رویت
# (CSV نقل‌قول‌دار / TSV) با تشخیص خودکار نوع جدول
# ════════════════════════════════════════════════════════════════

_HEADER_MAP = [
    (r"^mark$|شماره مارک|مارک", "mark"),
    (r"family and type|family.*type|فامیل", "familyType"),
    (r"^category$|دسته|کتگوری", "category"),
    (r"host category", "hostCategory"),
    # «Host Mark» مارک المان میزبان آرماتور — مبنای محاسبهٔ per-element
    # تراکم میلگرد در ردیف اختیاری ۰۸۰۳۱۰ (بند ۳-۶ فصل ۸).
    (r"host mark", "hostMark"),
    (r"material: name|material name|^material$|مصالح", "material"),
    (r"reference level|level|تراز", "level"),
    (r"^count$|تعداد", "count"),
    (r"formwork area|مساحت قالب", "area"),
    (r"material: area|area$|مساحت", "area"),
    (r"material: volume|volume$|حجم", "volume"),
    (r"bar length|^length$|طول کل|طول", "length"),
    (r"^width$|عرض", "width"),
    (r"bar diameter|diameter|قطر", "diameter"),
    (r"bar type|نوع میلگرد|دن", "barType"),
    (r"rebar shape|^shape$|شکل", "shape"),
    (r"spacing|فاصله", "spacing"),
    (r"total weight|وزن|weight|kg", "weight"),
]

_NUM_COLS = {"count", "length", "width", "diameter", "spacing", "volume", "area", "weight"}
_TEXT_COLS = {"mark", "familyType", "category", "hostCategory", "hostMark", "material", "level", "barType", "shape"}

KIND_LABEL = {
    "lean_concrete": "ریزمترهٔ بتن مگر",
    "structural_concrete": "ریزمترهٔ بتن سازه‌ای",
    "formwork_foundation": "قالب‌بندی پی",
    "formwork_super": "قالب‌بندی سازه",
    "joist_floor": "سقف تیرچه‌بلوک",
    "joist_materials": "بتن پاشنه و یونولیت",
    "rebar_detailed": "لیستوفر تفصیلی آرماتور",
    "rebar_joist": "آرماتور تیرچه",
    "rebar_connection": "آرماتور اتصال تیرچه",
    "unknown": "جدول نامشخص",
}

KINDS = list(KIND_LABEL.keys())


class RevitScheduleParser:
    """تجزیه‌گر هوشمند فایل‌های Schedule خروجی Revit."""

    @staticmethod
    def _semantic_of(header: str):
        """تشخیص ستون معنایی از روی عنوان سرستون."""
        h = normalize_text(header)
        for pattern, col in _HEADER_MAP:
            if re.search(pattern, h):
                return col
        return None

    @staticmethod
    def _classify(title: str, headers):
        """تشخیص نوع جدول بر اساس عنوان و امضای ستونی."""
        t = normalize_text(title)
        hs = [normalize_text(h) for h in headers]
        rules = [
            (r"بتن مگر|lean concrete|بتن نظافت|blinding", "lean_concrete", 0.97),
            (r"قالب بندی پی|foundation formwork", "formwork_foundation", 0.97),
            (r"قالب بندی (سازه|اسکلت)|superstructure formwork|formwork schedule", "formwork_super", 0.95),
            (r"حجم بتن سازه ای|بتن ریزی پی|structural concrete", "structural_concrete", 0.97),
            (r"سقف تیرچه بلوک|joist floor", "joist_floor", 0.97),
            (r"بتن پاشنه|یونولیت|eps block|joist concrete", "joist_materials", 0.97),
            (r"اتصال تیرچه|connection rebar", "rebar_connection", 0.96),
            (r"آرماتور(های)? تیرچه|joist rebar", "rebar_joist", 0.96),
            (r"آرماتور|rebar|لیستوفر|میلگرد", "rebar_detailed", 0.93),
        ]
        for pattern, kind, conf in rules:
            if re.search(pattern, t):
                return kind, conf

        def has(p):
            return any(re.search(p, h) for h in hs)

        if has(r"diameter|bar type") and has(r"weight|kg"):
            return "rebar_detailed", 0.75
        if has(r"formwork area"):
            return "formwork_foundation", 0.75
        if has(r"material: area") and has(r"category"):
            return "formwork_super", 0.70
        if has(r"material: volume") and has(r"category"):
            return "structural_concrete", 0.70
        return "unknown", 0.0

    @staticmethod
    def parse(file_name: str, text: str) -> dict:
        """
        تجزیهٔ کامل یک فایل خروجی Revit.
        خروجی: دیکشنری جدول شامل عنوان، سرستون‌ها، رکوردها، Grand total و نوع تشخیصی.
        """
        table = {"file_name": file_name, "title": file_name, "headers": [], "rows": [],
                 "grand_total": {}, "kind": "unknown", "kind_conf": 0.0, "col_map": {}, "warnings": []}
        if text.startswith("\ufeff"):
            text = text[1:]
        try:
            sample = "\n".join(text.splitlines()[:12])
            doubled_quote = any(
                re.search(r'^\s*"[^"\r\n]*""\s*,\s*""[^"\r\n]*"', line)
                for line in text.splitlines()[:12]
            )
            if doubled_quote:
                text = text.replace('""', '"')
            delim = "\t" if sample.count("\t") > sample.count('","') else ","
            grid = [
                [c.strip() for c in row]
                for row in csv.reader(io.StringIO(text), delimiter=delim)
                if any(str(c).strip() for c in row)
            ]
        except csv.Error as e:
            table["warnings"].append(f"خطای تجزیهٔ CSV: {e}")
            return table

        if len(grid) < 2:
            table["warnings"].append("ساختار جدول یافت نشد.")
            return table

        # عنوان: اولین سلول پر سطر نخست (قسمت فارسیِ «فارسی - English»)
        title = next((c for c in grid[0] if c), file_name)
        title = re.split(r"\s+-\s+", title, maxsplit=1)[0].strip() or title
        table["title"] = title

        # سطر سرستون: نخستین سطر دارای دست‌کم ۲ سلول پر پس از عنوان
        header_idx = 1
        for i in range(1, min(len(grid), 6)):
            if sum(1 for c in grid[i] if c) >= 2:
                header_idx = i
                break
        headers = [h.strip().strip('"') for h in grid[header_idx]]
        table["headers"] = headers

        col_map = {}
        for i, h in enumerate(headers):
            sem = RevitScheduleParser._semantic_of(h)
            if sem and sem not in col_map:
                col_map[sem] = i
        table["col_map"] = col_map

        for cells in grid[header_idx + 1:]:
            first = str(cells[0]).lower() if cells else ""
            # ردیف Grand total رسمی Revit
            if re.match(r"^\s*grand total", first):
                gt = {}
                for j, c in enumerate(cells):
                    pv = parse_value_unit(c)
                    if pv:
                        sem = next((s for s, idx in col_map.items() if idx == j), None)
                        v, si = to_si(pv[0], pv[1])
                        key = sem if (sem in _NUM_COLS) else f"col{j}"
                        gt[key] = v if si else pv[0]
                table["grand_total"] = gt
                continue
            values, texts = {}, {}
            for sem, idx in col_map.items():
                c = cells[idx] if idx < len(cells) else ""
                if sem in _NUM_COLS:
                    pv = parse_value_unit(c)
                    if pv:
                        v, si = to_si(pv[0], pv[1])
                        values[sem] = v if si else pv[0]
                elif sem in _TEXT_COLS:
                    texts[sem] = c
            # سطر جمع بدون برچسب Revit: هیچ ستون متنی پر ندارد و فقط مقدار عددی
            # دارد ⇒ Grand total همان Schedule تلقی میشود و رکورد متره نمیسازد.
            if values and not any(str(v).strip() for v in texts.values()):
                if not table["grand_total"]:
                    table["grand_total"] = dict(values)
                continue
            # ردیف جمع‌جزئی داخلی (مثل «Rebar - Φ8: 13») → از محاسبات حذف می‌شود
            first_filled = next((c for c in cells if str(c).strip()), "")
            is_subtotal = bool(re.search(r":\s*\d+\s*$", first_filled)) and "grand total" not in first
            table["rows"].append({"cells": cells, "values": values,
                                  "texts": texts, "is_subtotal": is_subtotal})

        kind, conf = RevitScheduleParser._classify(title, headers)
        table["kind"], table["kind_conf"] = kind, conf
        if kind == "unknown":
            table["warnings"].append("نوع جدول به‌صورت خودکار تشخیص داده نشد؛ لطفاً دستی تعیین کنید.")
        return table


# ════════════════════════════════════════════════════════════════
# کلاس DynamoMappingParser — تشخیص هوشمند هر دو فرمت خروجی Dynamo
# فرمت v1: TSV انگلیسی ۵۵ستونی (Rebar-محور)        فرمت v2: اکسل/TSV
# فارسی ۱۶ستونی (Element-محور + ستون «کد فهرست بها»)
# ════════════════════════════════════════════════════════════════

# نام‌های کانونیکال ستون‌های خروجی نهایی Mapping
MAP_CANON_COLS = [
    "element_id", "category", "family", "type", "mark", "level", "phase",
    "material", "fehrest_code", "note", "volume_m3", "area_m2", "length_m",
    "formwork_m2", "rebar_detail", "rebar_weight_kg",
    "diameter_mm", "steel_type", "prefix", "host_mark", "host_family", "position",
]

# نگاشت هدرهای فارسی/انگلیسی v2 به نام کانونیکال
_V2_HEADER_CANON = {
    "ElementId": "element_id", "دسته": "category", "Family": "family", "Type": "type",
    "Mark": "mark", "طبقه": "level", "فاز": "phase", "متریال": "material",
    "کد فهرست بها": "fehrest_code", "توضیحات": "note",
    "حجم (m³)": "volume_m3", "سطح (m²)": "area_m2", "طول (m)": "length_m",
    "قالب‌بندی (m²)": "formwork_m2", "جزئیات میلگرد": "rebar_detail",
    "وزن کل میلگرد (kg)": "rebar_weight_kg",
}

# نگاشت هدرهای انگلیسی v1 به نام کانونیکال + میلی‌متر به متر در واحدهای طول
_V1_HEADER_CANON = {
    "ElementId": "element_id", "Category": "category", "Family": "family", "Type": "type",
    "Mark": "mark", "MappingMark": "mark", "Prefix": "prefix",
    "HostCategory": "category", "HostFamily": "host_family", "HostType": "type",
    "HostMark": "host_mark", "HostLevel": "level",
    "Diameter_mm": "diameter_mm", "SteelType": "steel_type",
    "Length_mm": "length_m", "Quantity": "quantity",
    "Material": "material", "RebarShape": "rebar_detail",
    "Volume_m3": "volume_m3", "Area_m2": "area_m2",
    "HostVolume_m3": "host_volume_m3", "HostArea_m2": "host_area_m2",
    "Position": "position", "StructuralContext": "position",
}


class DynamoMappingParser:
    """پارسر هوشمند خروجی داینامو (پشتیبانی از هر دو فرمت txt و xlsx)."""

    @staticmethod
    def _canon_v2_header(header: str) -> str:
        """
        کانونیک‌سازی مقاوم هدر ستون‌های v2: تحمل تفاوت ی/ي، ک/ك و نیم‌فاصله،
        سپس تطبیق فازی روی کلیدهای استاندارد برای تحمل تغییرات جزئی عنوان.
        """
        if header in _V2_HEADER_CANON:
            return _V2_HEADER_CANON[header]
        hn = (header.replace("ي", "ی").replace("ك", "ک")
              .replace("‌", " ").replace("\t", " ").strip())
        if hn in _V2_HEADER_CANON:
            return _V2_HEADER_CANON[hn]
        best, score, _ = fuzzy_match(hn, list(_V2_HEADER_CANON.keys()), 0.75)
        if best:
            return _V2_HEADER_CANON[best]
        return normalize_text(hn).replace(" ", "_")

    @staticmethod
    def auto_detect_and_parse(file_bytes: bytes, filename: str) -> dict:
        """
        تشخیص خودکار فرمت و پارس هوشمند فایل Mapping:
        ۱) اکسل باینری (.xlsx) → openpyxl     ۲) TSV فارسی ۱۶ستونی (v2)
        ۳) TSV انگلیسی قدیمی (v1)
        خروجی: دیکشنری {df, fmt, records_count, meta, warnings, error}
        """
        result = {"df": pd.DataFrame(columns=MAP_CANON_COLS), "fmt": None,
                  "records_count": 0, "meta": {}, "warnings": [], "error": None}
        try:
            lower = filename.lower()
            if lower.endswith((".xlsx", ".xlsm", ".xltx")):
                return DynamoMappingParser.parse_xlsx_format(file_bytes, result, filename)
            text = decode_text(file_bytes)
            # تشخیص v2: هدر «# گزارش Mapping» یا وجود ستون‌های فارسی در سرستون
            sample_lines = [ln for ln in text.splitlines() if ln.strip()][:12]
            joined_head = "\n".join(sample_lines)
            if ("گزارش Mapping" in joined_head
                    or ("\t" in joined_head and ("طبقه" in joined_head or "کد فهرست بها" in joined_head))):
                return DynamoMappingParser._parse_v2_tsv(text, result, filename)
            if ("ElementId" in joined_head
                    and ("MappingMark" in joined_head or "HostElementId" in joined_head
                         or "MarkTokens" in joined_head)):
                return DynamoMappingParser.parse_txt_format(text, result, filename)
            result["error"] = ("فرمت فایل تشخیص داده نشد؛ با فرمت‌های استاندارد خروجی "
                               "اسکریپت‌های Dynamo (v1 فایل TXT یا v2 فایل XLSX/TSV شانزده‌ستونی) سازگار نیست.")
            return result
        except Exception as e:  # مدیریت کامل خطا با پیام فارسی
            _logger.exception("خطا در پارس فایل Mapping")
            result["error"] = f"خطای غیرمنتظره در خواندن فایل نگاشت: {e}"
            return result

    @staticmethod
    def _parse_v2_tsv(text: str, result: dict, filename: str) -> dict:
        """پارس فرمت TSV فارسی ۱۶ستونی (v2) — همان ساختار Mapping.xlsx به‌صورت متنی."""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            result["error"] = "فایل خالی است."
            return result
        # استخراج متادیتا از سطر اول (# گزارش Mapping پروژه ...)
        header_idx = 0
        meta = {}
        for i, ln in enumerate(lines[:6]):
            if ln.lstrip().startswith("#") or "تاریخ" in ln or "نسخه" in ln:
                parts = [p.strip() for p in ln.lstrip("#").split("\t") if p.strip()]
                meta["report_head"] = " | ".join(parts[:4])
                header_idx = i + 1
            elif "ElementId" in ln:
                header_idx = i
                break
        headers = [h.strip() for h in lines[header_idx].split("\t")]
        canon = [DynamoMappingParser._canon_v2_header(h) for h in headers]
        records = DynamoMappingParser._rows_to_records(lines, header_idx + 1, canon,
                                                        skip_comments=True)
        df = pd.DataFrame(records)
        result.update({"df": df, "fmt": "v2", "records_count": len(df),
                       "meta": meta, "warnings": []})
        # هشدار: ستون «کد فهرست بها» موجود است ولی خالی است؟
        if "fehrest_code" in df.columns and int((df["fehrest_code"].astype(str).str.strip() != "").sum()) == 0:
            result["warnings"].append(
                "ستون «کد فهرست بها» در فایل خالی است؛ تطبیق ردیف‌ها به‌صورت خودکار (قوانین + فازی) انجام می‌شود.")
        return result

    @staticmethod
    def parse_xlsx_format(file_bytes: bytes, result: dict, filename: str) -> dict:
        """پارس فرمت اکسل ۱۶ستونی جدید با openpyxl."""
        wb = None
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            ws = wb.active
            grid = []
            for row in ws.iter_rows(values_only=True):
                cells = ["" if c is None else str(c).strip() for c in row]
                if any(cells):
                    grid.append("\t".join(cells))
            if not grid:
                result["error"] = "فایل اکسل خالی است."
                return result
            # در صورت داشتن چند شیت، نخستین شیت حاوی سرستون Mapping انتخاب می‌شود
            return DynamoMappingParser._parse_v2_tsv("\n".join(grid), result, filename)
        except Exception as e:
            result["error"] = f"خطا در خواندن فایل اکسل Mapping: {e}"
            return result
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

    @staticmethod
    def parse_txt_format(text: str, result: dict, filename: str) -> dict:
        """
        پارس فرمت متنی قدیمی (v1):
        TSV انگلیسی ۵۵ستونی Rebar-محور. اطلاعات آرماتور (قطر/گرید/طول/شکل/میزبان)
        با حاش‌داری و حوزه‌بندی دقیق استخراج و به فرم کانونیکال تبدیل می‌شود.
        """
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            result["error"] = "فایل خالی است."
            return result
        header_idx = next((i for i, ln in enumerate(lines) if "ElementId" in ln), -1)
        if header_idx < 0:
            result["error"] = "سرستون ElementId یافت نشد."
            return result
        meta = {"report_head": "خروجی اسکریپت Dynamo — نسخهٔ ۱ (v1)"}
        headers = [h.strip() for h in lines[header_idx].split("\t")]
        canon = [_V1_HEADER_CANON.get(h, normalize_text(h).replace(" ", "_")) for h in headers]
        records = DynamoMappingParser._rows_to_records(lines, header_idx + 1, canon)
        df = pd.DataFrame(records)
        # واحد طول v1 میلی‌متر است → تبدیل به متر
        if "length_m" in df.columns:
            df["length_m"] = pd.to_numeric(df["length_m"], errors="coerce").fillna(0.0) / 1000.0
        result.update({"df": df, "fmt": "v1", "records_count": len(df), "meta": meta,
                       "warnings": ["فرمت v1 کمیت‌های المان را روی هر میلگرد تکرار می‌کند؛ "
                                    "در تجمیع، مقادیر میزبان با HostElementId یکتا‌سازی می‌شود."]})
        return result

    @staticmethod
    def _rows_to_records(lines, start_idx: int, canon_cols, skip_comments=False):
        """تبدیل سطرهای متنی به فهرست دیکشنری رکورد بر اساس نام‌های کانونیکال.

        skip_comments=True سطرهای خلاصه/کامنت (شروع‌شونده با #) را رد می‌کند —
        مختص فرمت v2 که سطر پایانی «# مجموع تعداد کل المان‌ها: …» را به‌عنوان
        یک رکورد با کمیت‌های صفر جذب می‌کرد (۸۳۶ رکورد به‌جای ۸۳۵)."""
        records = []
        for ln in lines[start_idx:]:
            if skip_comments and ln.lstrip().startswith("#"):
                continue
            cells = ln.split("\t")
            rec = {c: "" for c in MAP_CANON_COLS}
            # اگر ستون‌های بیشتری وجود داشت (مثل quantity در v1) آن‌ها هم نگه می‌داریم
            for j, cname in enumerate(canon_cols):
                val = cells[j] if j < len(cells) else ""
                rec[cname] = val
            # تبدیل ستون‌های عددی شناخته‌شده
            for num_col in ("volume_m3", "area_m2", "length_m", "formwork_m2",
                            "rebar_weight_kg", "diameter_mm", "host_volume_m3", "host_area_m2", "quantity"):
                if num_col in rec:
                    pv = parse_value_unit(rec[num_col])
                    rec[num_col] = pv[0] if pv else 0.0
            rec["fehrest_code"] = convert_persian_digits(str(rec.get("fehrest_code", "")).strip())
            records.append(rec)
        return records

    @staticmethod
    def merge_formats(dfs):
        """
        ادغام خروجی چند فایل Mapping (v1 و/یا v2) در یک DataFrame واحد.
        سیاست: رکوردهای v2 (Element-محور) مبنا هستند؛ اطلاعات آرماتور v1
        (قطر/گرید/طول/شکل) برای غنی‌سازی لیستوفر افزوده می‌شود.
        """
        frames = []
        for d in dfs:
            if d is not None and not d["df"].empty:
                f = d["df"].copy()
                f["source_format"] = d["fmt"]
                frames.append(f)
        if not frames:
            return pd.DataFrame(columns=MAP_CANON_COLS)
        return pd.concat(frames, ignore_index=True, sort=False)

# ════════════════════════════════════════════════════════════════
# کلاس TechnicalOfficeEngine — موتور اصلی محاسبات دفتر فنی
# منابع کمیت: Mapping (با تقدم v2 و کد فهرست‌بهای مستقیم) + Schedule ها
# ════════════════════════════════════════════════════════════════

_CHAPTER_ORDER = ["08", "06", "07", "10", "28", "01", "02", "03", "04", "05", "09", "11", "12",
                  "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25",
                  "26", "27", "29", "41", "99"]

_REBAR_BUCKET_META = {
    "070101": {"query": "تهیه بریدن خم کردن کارگذاشتن میلگرد ساده",
               "desc": "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد ساده از نوع AI با سیم‌پیچی لازم", "price": 505000.0},
    "070201": {"query": "تهیه بریدن خم کردن کارگذاشتن میلگرد آجدار قطر تا ۱۰",
               "desc": "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار AIII به قطر تا ۱۰ میلی‌متر با سیم‌پیچی لازم", "price": 522000.0},
    "070202": {"query": "تهیه بریدن خم کردن کارگذاشتن میلگرد آجدار قطر ۱۲ تا ۱۸",
               "desc": "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار AIII به قطر ۱۲ تا ۱۸ میلی‌متر با سیم‌پیچی لازم", "price": 510000.0},
    "070203": {"query": "تهیه بریدن خم کردن کارگذاشتن میلگرد آجدار قطر ۲۰ به بالا",
               "desc": "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار AIII به قطر ۲۰ میلی‌متر و بیشتر با سیم‌پیچی لازم", "price": 498000.0},
}


def structural_group(text: str, kind: str = "") -> str:
    """تشخیص گروه سازه‌ای (پی/ستون/تیر/سقف/پله/دیوار/تیرچه) از نام المان یا دسته."""
    raw = str(text).upper()
    if re.search(r"FOUNDATION|WF_|FOOTING|پی |فونداسیون|شالوده", raw):
        return "پی"
    if re.search(r"(^|[^A-Z])STR(?![A-Z])|STAIR|پله", raw):
        return "پله"
    if re.search(r"JST|JOIST|تیرچه", raw):
        return "سقف تیرچه"
    if re.search(r"COLUMN|(^|[^A-Z])C\d|ستون", raw):
        return "ستون"
    if re.search(r"BEAM|FRAMING|(^|[^A-Z])B\d|^B\d+X\d+|تیر ", raw):
        return "تیر"
    if re.search(r"SLAB|FLOOR|دال|سقف", raw):
        return "سقف"
    if re.search(r"WALL|دیوار", raw):
        return "دیوار"
    if re.search(r"^L\(|^T\(|LG|^TR\(|FOUND", raw):
        return "پی"
    if kind == "lean_concrete" or kind == "formwork_foundation":
        return "پی"
    if kind in ("joist_floor", "joist_materials"):
        return "سقف تیرچه"
    return "سایر"


# واژگان گروه سازه‌ایِ لیستوفر (ایراد ۱۱): «Floor» میزبان = دال (سقفِ یکپارچه).
# «سقف تیرچه» حفظ می‌شود (گروهی واقعی و متمایز از دال).
_REBAR_GROUP_VOCAB = {"سقف": "دال"}


def rebar_list_group(host_cat: str, text: str, kind: str = ""):
    """گروه سازه‌ای لیستوفر آرماتور (ایراد ۱۱).

    اولویت: **Host Category** المان میزبان > نام/مارک. گروه هرگز «سایر»
    نیست (قاعدهٔ صریح ایراد ۱۱)؛ در صورت عدم تشخیص «نامشخص» برمی‌گردد
    تا با هشدار متناظر نمایش داده شود (قاعدهٔ طلایی ۳: عدد/برچسب ساخته
    نمی‌شود).
    خروجی: تاپل (گروه، آیا نامشخص است)."""
    g = "سایر"
    hc = (host_cat or "").strip()
    if hc and hc.lower() != "<varies>":
        g = structural_group(hc)
    if g == "سایر":
        g = structural_group(text, kind)
    if g == "سایر":
        return "نامشخص", True
    return _REBAR_GROUP_VOCAB.get(g, g), False


def rebar_list_mark(*candidates):
    """مارک لیستوفر آرماتور (ایراد ۱۱).

    اولین مقدار غیرخالی از کاندیداهای ورودی (پارامتر Revit «Rebar
    Number»/«Mark»، سپس Schedule Mark، سپس Family Type). اگر هیچ‌کدام
    نبود **«بدون مارک»** برمی‌گردد — هرگز «—» (قاعدهٔ صریح ایراد ۱۱)."""
    for c in candidates:
        v = (str(c or "")).strip()
        if v:
            return v
    return "بدون مارک"


# ارقام فارسی/عربی → لاتین (برای تجزیهٔ مقادیر عددی در متن فارسی)
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_concrete_strength(text) -> int | None:
    """استخراج مقاومت فشاری مشخصهٔ بتن (MPa) از نام/متن متریال Revit.

    الگوهای پشتیبانی‌شده: C35، C 35، 35MPa، 35 MPa، f'c=35، fc35، fc 35،
    35 مگاپاسکال، ۳۵ مگاپاسکال. خروجی: عدد صحیح مگاپاسکال یا None.
    تقدم رسمی: پارامتر صریح Revit > نام متریال > ورودی دستی (تنظیمات).
    """
    if not text:
        return None
    t = str(text).translate(_FA_DIGITS)
    # 35 MPa / 35MPa / 35 Mpa / 35 مگاپاسکال
    m = re.search(r"(?:^|[^A-Za-z0-9'])(\d{2,3})\s*(?:MPa|Mpa|mpa|مگاپاسکال)(?:\s|$|[^A-Za-z0-9])",
                  t)
    if m:
        return int(m.group(1))
    # C35 / C 35 — اما نه ابعاد مقطع مثل «C 45×45» یا «C30/37»
    m = re.search(r"(?:^|[^A-Za-z0-9])[Cc]\s*(\d{2,3})(?![\d/×*xX])", t)
    if m:
        return int(m.group(1))
    # f'c=35 / fc35 / fc 35 (جداکنندهٔ «=» اختیاری است)
    m = re.search(r"f\s*'?\s*c\s*[=:]?\s*(\d{2,3})", t, re.I)
    if m:
        return int(m.group(1))
    return None


class IndexTable:
    """جدول شاخص‌های تعدیل فهرست‌بها (کلیات فهرست‌بهای ۱۴۰۴، بند ۲۲).

    شاخص‌ها از فایل «indices/abnieh.json» خوانده می‌شوند. هر رکور:
        period  : دورهٔ شاخص (مثلاً «1403Q4»)
        chapter : شمارهٔ فصل (دو رقم) و در صورت نیاز group (چهار رقم)
        value   : مقدار شاخص
        kind    : «قطعی» یا «موقت»
        source  : شماره/تاریخ بخشنامه
    شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل است (بنابراین مقدار ذخیره‌شده
    برای رکوردموقت یک «ضریب» نسبت به آخرین شاخص قطیری قبل از آن دوره است).

    ضریب تعدیل هر فصل = I(دورهٔ هدف) ÷ I(دورهٔ مبنا) روی مبلغ ردیف، بر
    اساس دو رقم اول کد فهرست‌بها، قبل از ضرایب زنجیرهٔ مالی اعمال می‌شود.
    """

    def __init__(self, data: dict):
        self.base_period = data.get("base_period")
        self.periods = list(data.get("periods", []))
        self.records = list(data.get("indices", []))

    @classmethod
    def load(cls, path: str = None):
        if path is None:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "indices", "abnieh.json")
        with open(path, "r", encoding="utf-8") as fh:
            return cls(json.load(fh))

    @classmethod
    def empty(cls):
        """جدول خالی — هیچ شاخصی موجود نیست (تعدیل غیرفعال)."""
        return cls({"base_period": None, "periods": [], "indices": []})

    def _records_for(self, period, chapter):
        """رکوردهای یک دوره/فصل — ترجیح با group دقیق‌تر (چهار رقم) نیست؛
        اینجا فقط فصل (دو رقم) مبنای جست‌جو است و group فقط برای اطلاعات است."""
        return [r for r in self.records
                if r.get("period") == period and r.get("chapter") == chapter]

    def _level(self, period, chapter):
        """مستوى شاخص یک فصل در یک دوره (شامل بازکردن شاخص موقت)."""
        recs = self._records_for(period, chapter)
        if not recs:
            raise ValueError(
                f"شاخص تعدیل فصل {chapter} در دورهٔ «{period}» یافت نشد. "
                f"مقادیر رسمی شاخص را از بخشنامهٔ مربوطه در فایل "
                f"«indices/abnieh.json» وارد کنید.")
        rec = recs[0]
        if rec.get("kind") == "موقت":
            # شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل
            idx = self.periods.index(period) if period in self.periods else -1
            prev_def = None
            for p in reversed(self.periods[:idx]):
                pr = self._records_for(p, chapter)
                if pr and pr[0].get("kind") == "قطعی":
                    prev_def = p
                    break
            if prev_def is None:
                raise ValueError(
                    f"شاخص موقت فصل {chapter} در دورهٔ «{period}» به یک شاخص "
                    f"قطعی در دورهٔ قبل نیاز دارد؛ هیچ شاخص قطعیی یافت نشد.")
            return float(rec.get("value", 0)) * self._level(prev_def, chapter)
        return float(rec.get("value", 0))

    def factor(self, code: str, target_period: str) -> float:
        """ضریب تعدیل یک ردیف فهرست‌بها (بر اساس دو رقم اول کد)."""
        chapter = code[:2]
        base = self.base_period
        if base is None or target_period == base:
            return 1.0
        lv = self._level(target_period, chapter)
        base_lv = self._level(base, chapter)
        if base_lv == 0:
            raise ValueError(f"شاخص دورهٔ مبنا برای فصل {chapter} صفر است.")
        return lv / base_lv

    def report(self, target_period: str):
        """گزارش شاخص هر فصل برای دورهٔ هدف: ضریب، نوع، منبع و مستوى."""
        rows = []
        for ch in sorted({r.get("chapter") for r in self.records}):
            recs = self._records_for(target_period, ch)
            rec = recs[0] if recs else None
            try:
                f = self.factor(f"{ch}0000", target_period)
            except ValueError:
                f = None
            rows.append({
                "chapter": ch,
                "factor": f,
                "kind": rec.get("kind") if rec else None,
                "source": rec.get("source") if rec else None,
                "level": self._level(target_period, ch) if rec else None,
            })
        is_provisional = any(r["kind"] == "موقت" for r in rows)
        return {
            "base_period": self.base_period,
            "target_period": target_period,
            "provisional": is_provisional,
            "chapters": rows,
        }


class TechnicalOfficeEngine:
    """موتور اصلی محاسبات دفتر فنی (تجمیع، تطبیق، زنجیرهٔ مالی)."""

    def __init__(self, fehrest_rows, settings, index_table=None):
        """ساخت موتور با پایگاه فهرست‌بها و تنظیمات کاربر.

        index_table: جدول شاخص‌های تعدیل (None → از indices/abnieh.json خوانده
        می‌شود؛ اگر فایل نبود، جدول خالی = بدون تعدیل).
        """
        self.db = fehrest_rows
        self.s = settings
        if index_table is not None:
            self.index_table = index_table
        else:
            try:
                self.index_table = IndexTable.load()
            except OSError:
                self.index_table = IndexTable.empty()

    # ── استخراج رکوردهای کمیت از جداول Schedule ──
    def _records_from_table(self, table: dict):
        """تبدیل یک جدول Revit به رکوردهای کمیت استاندارد SI."""
        recs, kind = [], table["kind"]
        for r in table["rows"]:
            if r["is_subtotal"]:
                continue
            texts, values = r["texts"], r["values"]
            ref = (texts.get("mark") or texts.get("familyType") or texts.get("category")
                   or texts.get("material") or "—")
            grp = structural_group(f"{ref} {texts.get('familyType', '')} {texts.get('category', '')}", kind)
            base = {"source": f"Schedule: {table['file_name']}", "table": table["title"],
                    "kind": kind, "ref": ref, "group": grp,
                    "material": texts.get("material", ""), "level": texts.get("level", ""),
                    # مقاومت فشاری از نام متریال (ایراد ۱): "Concrete - ... - 35 MPa" → 35
                    # فقط ستون متریال — «Family and Type» مثل «Column: C 45×45»
                    # ابعاد مقطع است و نباید مقاومت فرض شود.
                    "strength_mpa": parse_concrete_strength(texts.get("material", "")),
                    "from_mapping": False}
            if kind in ("lean_concrete", "structural_concrete") and values.get("volume", 0) > 0:
                recs.append({**base, "qty": values["volume"], "unit": "m3",
                             "detail": f"{texts.get('category', '')} {texts.get('familyType', texts.get('mark', ''))}".strip()})
            elif kind in ("formwork_foundation", "formwork_super") and values.get("area", 0) > 0:
                recs.append({**base, "qty": values["area"], "unit": "m2",
                             "detail": f"{texts.get('category', '')} {texts.get('mark', texts.get('familyType', ''))}".strip()})
            elif kind == "joist_floor" and values.get("length", 0) > 0:
                recs.append({**base, "qty": values["length"] * values.get("count", 1), "unit": "m",
                             "detail": f"تیرچه {texts.get('mark', '')} | طبقه {texts.get('level', '')}"})
            elif kind == "joist_materials" and values.get("volume", 0) > 0:
                recs.append({**base, "qty": values["volume"], "unit": "m3",
                             "detail": texts.get("material") or texts.get("familyType") or "مصالح سقف"})
            elif kind in ("rebar_detailed", "rebar_joist", "rebar_connection") and values.get("weight", 0) > 0:
                recs.append({**base, "qty": values["weight"], "unit": "kg",
                             "detail": f"{texts.get('mark', '')} {texts.get('barType', '')}".strip()})
        return recs

    # ── قرارداد تقدم منابع حجم بتن پی (فقط دامنهٔ foundation concrete) ──
    @staticmethod
    def _foundation_ref_key(ref):
        """کلید نرمالشدهٔ مرجع المان برای تطبیق بین Scheduleها؛ خالی/«—» نامعتبر است."""
        r = str(ref or "").strip()
        if not r or r == "—":
            return None
        return normalize_text(r)

    def _foundation_candidates(self, sched_recs, tables):
        """
        انتخاب یک منبع برای هر المان پی (بدون دوباره‌شماری):
        تقدم: جدول اختصاصی پی > جدول تجمیعی بتن > مقادیر استنتاجی از قالب‌بندی پی.
        • رکوردهای بتنی که ref آن‌ها در یک جدول بتن مگر وجود دارد (kind == lean_concrete)
          حذف می‌شوند تا بتن مگر وارد ردیف 080301 نشود (بدون hard-code).
        • dedup فقط per-ref و فقط در همین دامنه انجام می‌شود، نه سراسری روی کل پروژه.
        • مقادیر استنتاجی فقط برای refهایی می‌آید که منبع مستقیم ندارند.
        """
        lean_refs = {self._foundation_ref_key(r.get("ref")) for r in sched_recs
                     if r.get("kind") == "lean_concrete" and r.get("unit") == "m3"}
        lean_refs.discard(None)

        cand, table_rows, table_pi = {}, {}, {}
        for r in sched_recs:
            if r.get("kind") != "structural_concrete" or r.get("unit") != "m3":
                continue
            tkey = str(r.get("source", ""))
            table_rows[tkey] = table_rows.get(tkey, 0) + 1
            if r.get("group") != "پی":
                continue
            table_pi[tkey] = table_pi.get(tkey, 0) + 1
            k = self._foundation_ref_key(r.get("ref"))
            if k is None or k in lean_refs:
                continue
            cand.setdefault(k, {}).setdefault(tkey, []).append(r)

        # جدول اختصاصی پی: تمام رکوردهای بتنی آن از گروه «پی» هستند
        dedicated = {k for k, n in table_pi.items() if n == table_rows.get(k, 0)}

        def rank(item):
            tkey = item[0]
            return (0 if tkey in dedicated else 1,
                    table_rows.get(tkey, 0) - table_pi.get(tkey, 0), tkey)

        direct, seen = [], set()
        for k, by_table in cand.items():
            direct.extend(min(by_table.items(), key=rank)[1])
            seen.add(k)

        derived = []
        for t in tables:
            if t["kind"] != "formwork_foundation":
                continue
            for row in t["rows"]:
                if row["is_subtotal"]:
                    continue
                fam = row["texts"].get("familyType", "")
                m = re.search(r"(\d{3,4})\s*[x×]\s*(\d{3,4})", fam, re.I)
                len_m = row["values"].get("length", 0)
                if not m or not len_m:
                    continue
                k = self._foundation_ref_key(row["texts"].get("mark"))
                if k is not None and k in seen:
                    continue            # این المان از منبع مستقیم معتبر تأمین شده است
                w_mm, h_mm = float(m.group(1)), float(m.group(2))
                derived.append({
                    "source": f"Schedule: {t['file_name']}", "table": t["title"], "kind": t["kind"],
                    "ref": row["texts"].get("mark", "") or fam, "group": "پی", "material": "CONCRETE",
                    "level": "", "from_mapping": False,
                    "qty": len_m * (w_mm / 1000) * (h_mm / 1000), "unit": "m3",
                    "detail": f"حجم استنتاجی پی {row['texts'].get('mark', '')} (طول × {m.group(1)}×{m.group(2)})"})
        return direct, derived


    # ── استخراج رکوردهای کمیت از DataFrame نگاشت (هر دو فرمت) ──
    def _records_from_mapping(self, map_df: pd.DataFrame):
        """
        تبدیل DataFrame کانونیکال Mapping به رکوردهای کمیت.
        برای v1: حجم/سطح میزبان روی هر میلگرد تکراری است؛ با HostElementId/element_id
        فقط برای رکوردهای غیر-میلگردیِ دارای حجم مستقل استفاده می‌شود.
        """
        recs = []
        if map_df is None or map_df.empty:
            return recs
        df = map_df
        # رکوردهای v2: ردیف‌های Element-محور با مقادیر مستقیم
        v2 = df[df.get("source_format", "v2") == "v2"] if "source_format" in df.columns else df
        for _, row in v2.iterrows():
            cat = str(row.get("category", ""))
            fam = str(row.get("family", ""))
            label = f"{cat} {fam} {row.get('mark', '')}"
            grp = structural_group(label)
            lvl = str(row.get("level", ""))
            if "foundation" in lvl.lower() and grp != "سایر":
                grp = "پی"
            base = {"source": "Mapping v2", "table": str(row.get("element_id", "")),
                    "kind": "mapping", "ref": str(row.get("mark", "")) or fam or cat,
                    "group": grp, "material": str(row.get("material", "")),
                    "level": lvl, "from_mapping": True}
            vol = float(row.get("volume_m3", 0) or 0)
            if vol > 0:
                recs.append({**base, "qty": vol, "unit": "m3",
                             "detail": f"حجم المان {fam} | طبقه {lvl}"})
            fw = float(row.get("formwork_m2", 0) or 0)
            area = float(row.get("area_m2", 0) or 0)
            if fw > 0:
                recs.append({**base, "qty": fw, "unit": "m2",
                             "detail": f"قالب‌بندی المان {fam} | طبقه {lvl}"})
            elif area > 0:
                recs.append({**base, "qty": area, "unit": "m2",
                             "detail": f"سطح المان {fam} | طبقه {lvl}"})
            rw = float(row.get("rebar_weight_kg", 0) or 0)
            if rw > 0:
                recs.append({**base, "qty": rw, "unit": "kg",
                             "detail": f"میلگرد المان {fam} | {str(row.get('rebar_detail', ''))[:40]}"})
        # رکوردهای v1: فقط به‌عنوان غنی‌سازی آرماتور (بدون تکرار حجم میزبان)
        if "source_format" in df.columns:
            v1 = df[df["source_format"] == "v1"]
            for _, row in v1.iterrows():
                d = float(row.get("diameter_mm", 0) or 0)
                length_m = float(row.get("length_m", 0) or 0)
                if d > 0 and length_m > 0:
                    mark = str(row.get("mark", "")) or str(row.get("host_mark", ""))
                    recs.append({
                        "source": "Mapping v1", "table": str(row.get("element_id", "")),
                        "kind": "mapping", "ref": mark,
                        "group": structural_group(f"{mark} {row.get('host_family', '')}"),
                        "material": str(row.get("steel_type", "")),
                        "level": str(row.get("level", "")), "from_mapping": True,
                        "qty": length_m * rebar_unit_weight(d), "unit": "kg",
                        "detail": f"Φ{int(d)} میلگرد | {str(row.get('position', ''))[:30]} (محاسبه از طول×وزن واحد)"})
        return recs

    # ── ردیف‌های مستقیم از ستون «کد فهرست بها» (مرجعیت بالاتر از فازی) ──
    def _direct_coded_lines(self, map_df):
        """
        ساخت ردیف‌های BOQ از ستون «کد فهرست بها» فایل Mapping v2.
        مقدار هر گروه بر اساس واحدِ ردیف از ستون‌های کمیتی Mapping برمی‌دارد.
        """
        lines = []
        if map_df is None or map_df.empty or "fehrest_code" not in map_df.columns:
            return lines
        codes = map_df["fehrest_code"].astype(str).str.strip()
        coded = map_df[codes.str.match(r"^[0-9]{6}$", na=False)].assign(fehrest_code=codes)
        if coded.empty:
            return lines
        for (code, src_name), grp_df in coded.groupby([coded["fehrest_code"], coded.get("source_format", "v2")]):
            row = FehrestBahaParser.by_code(self.db, code)
            if row is None:
                best, score, _ = fuzzy_match(f"ردیف {code}", [r["desc"] for r in self.db], 0.5)
                row = {"code": code, "chapter": code[:2], "desc": best or f"ردیف {code}",
                       "unit": "مترمربع", "price": 0.0, "estimated": True}
            unit_norm = row["unit"].replace("‌", "")
            if "مترمکعب" in unit_norm:
                qty = float(pd.to_numeric(grp_df["volume_m3"], errors="coerce").fillna(0).sum())
            elif "کیلوگرم" in unit_norm:
                qty = float(pd.to_numeric(grp_df["rebar_weight_kg"], errors="coerce").fillna(0).sum())
            elif "تن" in unit_norm:
                qty = float(pd.to_numeric(grp_df["rebar_weight_kg"], errors="coerce").fillna(0).sum()) / 1000
            elif "مترطول" in unit_norm:
                qty = float(pd.to_numeric(grp_df["length_m"], errors="coerce").fillna(0).sum())
            else:
                qty = float((pd.to_numeric(grp_df["formwork_m2"], errors="coerce").fillna(0)
                             + pd.to_numeric(grp_df["area_m2"], errors="coerce").fillna(0)).sum())
            if qty <= 0:
                continue
            # لایهٔ قیمت دستی در اینجا هم اعمال می‌شود تا فراخوانی مستقیم این
            # تابع (قرارداد T14) همان رفتار compute داشته باشد. قیمتِ پیش از
            # بازنویسی در base_price برای نمایش اختلاف نگه داشته می‌شود.
            _mp = manual_price_of(self.s, f"direct-{code}-{src_name}")
            price = _mp if _mp is not None else row["price"]
            lines.append({
                "id": f"direct-{code}-{src_name}", "row_no": 0, "chapter": code[:2],
                "chapter_title": chapter_title(code[:2]), "code": code,
                "desc": row["desc"], "unit": row["unit"],
                "qty": qty,
                "price": price, "total": qty * price,
                "base_price": row["price"],
                "method": "direct-code", "confidence": 1.0,
                "sources": [], "estimated": bool(row["estimated"]),
                "needs_review": qty <= 0 or row["price"] <= 0,
                "note": f"کد مستقیم از Mapping ({src_name}) — {len(grp_df)} المان",
                "candidates": [], "detail_records": grp_df.to_dict("records"),
            })
        return lines

    # ── طرح‌های قاعده‌محور از Schedule ها ──
    def _plans(self):
        """فهرست طرح‌های قاعده‌محور (بتن/قالب/تیرچه) مثل استاندارد مترور دفتر فنی.

        کد، شرح و بهای ردیف‌های بتن و سقف تیرچه‌بلوک از فرض‌های فنی پروژه
        (مقاومت فشاری به تفکیک گروه سازه‌ای، عیار سیمان بتن مگر، ضخامت سقف)
        و جداول نگاشتِ ماژول ساخته می‌شوند — هیچ کد فهرست‌بهایی ثابت نیست.
        """
        s = self.s
        strength = s.get("concrete_strength_mpa") or {}

        def conc(pid, group_key, default_mpa):
            mpa = int(strength.get(group_key) or default_mpa)
            code, price = CONCRETE_STRENGTH_CODES.get(
                mpa, CONCRETE_STRENGTH_CODES[default_mpa])
            return {"id": pid, "target": code, "unit": "مترمکعب", "price": price,
                    "query": f"تهیه و اجرای بتن مقاومت فشاری مشخصه {fa(mpa)} مگاپاسکال",
                    "desc": f"تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته "
                            f"با مقاومت فشاری مشخصه {fa(mpa)} مگاپاسکال"}

        lean_kg = int(s.get("lean_cement_kg") or 150)
        lean_code, lean_price = LEAN_CEMENT_CODES.get(lean_kg, LEAN_CEMENT_CODES[150])
        joist_cm = int(s.get("joist_block_thickness_cm") or 25)
        joist_code, joist_price = JOIST_BLOCK_THICKNESS_CODES.get(
            joist_cm, JOIST_BLOCK_THICKNESS_CODES[25])
        # ارتفاع طبقه برای انتخاب ردیف قالب‌بندی دال (تاوه)
        _slab_h = float(s.get("slab_formwork_height_m") or 3.5)
        _slab_code, _slab_price = next(
            ((c, p) for _lo, c, p in SLAB_FORMWORK_CODES if _slab_h <= float(_lo.split()[1])),
            (SLAB_FORMWORK_CODES[-1][1], SLAB_FORMWORK_CODES[-1][2]))
        specs = [
            # ── فصل ۰۸: بتن درجا ──
            # کد ردیف بتن مگر از عیار سیمان، و کد بتن المان‌ها از مقاومت فشاری
            # مشخصهٔ همان گروه (پی/ستون-تیر/سقف/پله) انتخاب می‌شود. جداول
            # نگاشت در سطح ماژول هستند (CONCRETE_STRENGTH_CODES و ...).
            {"id": "lean", "target": lean_code,
             "query": f"تهیه و اجرای بتن با {fa(lean_kg)} کیلوگرم سیمان",
             "desc": f"تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته، با "
                     f"{fa(lean_kg)} کیلوگرم سیمان در مترمکعب بتن",
             "unit": "مترمکعب", "price": lean_price},
            conc("conc-foundation", "foundation", 20),
            conc("conc-col-beam", "column_beam", 30),
            conc("conc-slab", "slab", 25),
            conc("conc-stair", "stair", 20),
            # ── فصل ۰۶: قالب‌بندی ──
            {"id": "form-foundation", "target": "060101",
             "query": "قالب بندی با قالب فلزی پی ها و شناژهای پی",
             "desc": "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در پی\u200cها و شناژهای پی",
             "unit": "مترمربع", "price": 1150000.0},
            {"id": "form-column", "target": "060301",
             "query": "قالب بندی با قالب فلزی ستون ها با مقطع چهارضلعی",
             "desc": "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در ستون\u200cها و شناژهای قائم با مقطع چهارضلعی",
             "unit": "مترمربع", "price": 1750000.0},
            {"id": "form-beam", "target": "060501",
             "query": "قالب بندی با قالب فلزی تیرها و شناژهای افقی",
             "desc": "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در تیرها و شناژهای افقی",
             "unit": "مترمربع", "price": 1580000.0},
            {"id": "form-stair", "target": "060701",
             "query": "قالب بندی با قالب فلزی پله ها و رمپ ها",
             "desc": "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در پله\u200cها و رمپ\u200cها",
             "unit": "مترمربع", "price": 1500000.0},
            # قالب‌بندی دال/تاوه مستقل (ایراد ۲): ردیف ۰۶۰۴۰۱..۰۶۰۴۰۴ بر اساس
            # ارتفاع طبقه — همانند سایر ردیف‌های فصل ۰۶. دال‌های رویهٔ سقف
            # تیرچه‌بلوک (JSL-TOP*) مشمول نرخ ۱۰۰۳۰۵ هستند و اینجا نمی‌آیند.
            {"id": "form-slab", "target": _slab_code,
             "query": "قالب بندی با قالب فلزی در تاوه ها دال ها",
             "desc": "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در تاوه\u200cها (دال\u200cها)",
             "unit": "مترمربع", "price": _slab_price},
            # ── فصل ۱۰: سقف تیرچه‌بلوک — کد از ضخامت انتخاب می‌شود ──
            {"id": "joist-block", "target": joist_code,
             "query": f"اجرای سقف تیرچه و بلوک به ضخامت {fa(joist_cm)} سانتی متر",
             "desc": f"اجرای سقف تیرچه و بلوک به ضخامت {fa(joist_cm)} سانتی\u200cمتر با "
                     f"تیرچه پاشنه بتنی و بلوک پلی\u200cاستایرن منبسط\u200cشده، شامل تهیه "
                     f"تمام مصالح به استثنای میلگرد و تهیه تجهیزات لازم به طور کامل",
             "unit": "مترمربع", "price": joist_price},
        ]
        for sp in specs:
            sp["fallback_price"] = sp["price"]
        return specs

    def _match(self, plan):
        """
        تطبیق یک طرح با فهرست‌بها:
        بازنویسی دستی → کد دقیق → فازی → پیش‌فرض تخمینی.

        قیمت دستی در اینجا اعمال **نمی‌شود** — لایهٔ قیمت دستی (مرحلهٔ ۵.۵
        compute) نقطهٔ واحد اعمال است تا قیمتِ پیشینِ برنامه (app_price) برای
        نمایش دوگانه و درصد اختلاف حفظ شود (§۱۵-۴ بند ۳).
        """
        manual = manual_code_of(self.s, plan["id"])
        if manual:
            row = FehrestBahaParser.by_code(self.db, manual)
            if row:
                candidates = [{"code": r["code"], "desc": r["desc"], "price": r["price"], "score": s}
                              for r, s in FehrestBahaParser.search(self.db, plan["query"], top=5, min_score=0.35)]
                if not any(c["code"] == row["code"] for c in candidates):
                    candidates.insert(0, {"code": row["code"], "desc": row["desc"],
                                          "price": row["price"], "score": 1.0})
                return {"code": row["code"], "desc": row["desc"], "unit": row["unit"],
                        "price": row["price"],
                        "method": "manual", "confidence": 1.0,
                        "estimated": bool(row["estimated"]), "needs_review": False,
                        "candidates": candidates}
        exact = FehrestBahaParser.by_code(self.db, plan["target"])
        candidates = [{"code": r["code"], "desc": r["desc"], "price": r["price"], "score": s}
                      for r, s in FehrestBahaParser.search(self.db, plan["query"], top=5, min_score=0.35)]
        if exact:
            return {"code": exact["code"], "desc": exact["desc"], "unit": exact["unit"],
                    "price": exact["price"],
                    "method": "rule-exact", "confidence": 0.85 if exact["estimated"] else 0.99,
                    "estimated": bool(exact["estimated"]),
                    "needs_review": bool(exact["estimated"]),
                    "candidates": candidates}
        if candidates and candidates[0]["score"] >= 0.55:
            row = FehrestBahaParser.by_code(self.db, candidates[0]["code"])
            return {"code": row["code"], "desc": row["desc"], "unit": row["unit"],
                    "price": row["price"],
                    "method": "fuzzy", "confidence": candidates[0]["score"],
                    "estimated": bool(row["estimated"]), "needs_review": candidates[0]["score"] < 0.8,
                    "candidates": candidates}
        return {"code": plan["target"], "desc": plan["desc"], "unit": plan["unit"],
                "price": plan["fallback_price"],
                "method": "fuzzy", "confidence": 0.4, "estimated": True, "needs_review": True,
                "candidates": candidates}

    # ── تجمیع‌های قاعده‌محور از رکوردهای Schedule ──
    @staticmethod
    def _joist_floor_refs(tables):
        """مجموعهٔ مرجع المان‌های سقف تیرچه‌بلوک (از جدول Joist Floor Schedule).

        این المان‌ها طبق بند ۳ الزامات عمومی فصل دهم، شامل شمع‌بندی، داربست،
        قالب‌بندی و بتن‌ریزی هستند و نباید ردیف بتن/قالب جداگانه تولید کنند.
        مرجعِ «تیرچه رویی» (مثل JSL-TOP01) جزو این مجموعه نیست — یک دال مستقل
        است و بتن آن جداگانه حساب می‌شود.
        """
        refs = set()
        for t in tables:
            if t.get("kind") != "joist_floor":
                continue
            for r in t["rows"]:
                if r.get("is_subtotal"):
                    continue
                mk = (r["texts"].get("mark") or "").strip()
                if mk and mk != "—":
                    refs.add(mk)
        return refs

    @staticmethod
    def _joist_topping_refs(tables):
        """مرجع المان‌های «رویهٔ روی سقف تیرچه‌بلوک» (روشناژ JSL-TOP*).

        طبق بند ۹ الزامات عمومی فصل دهم، بتن تا ۵ cm روی بلوک داخل نرخ
        ۱۰۰۳۰۵ است؛ حجم رویه که معادل همان ۵ cm باشد (۰٫۰۵ × مساحت ۱۰۰۳۰۵)
        از ردیف بتن جداگانه کسر می‌شود و فقط مازاد بر آن در ۰۸۰۱۰۶ می‌ماند.
        """
        refs = set()
        for t in tables:
            if t.get("kind") != "structural_concrete":
                continue
            for r in t["rows"]:
                if r.get("is_subtotal"):
                    continue
                mk = (r["texts"].get("mark") or "").strip()
                if mk and mk.upper().startswith("JSL-TOP"):
                    refs.add(mk)
        return refs

    @staticmethod
    def _joist_system_refs(tables):
        """کل مرجع المان‌های سیستم سقف تیرچه‌بلوک: تیرچه‌ها + رویهٔ JSL-TOP*.

        مبنای کسر حجم JSL از پایهٔ اضافه‌بهای فصل ۸ (بند ۳-۵: ردیف‌های
        ۰۸۰۳۰۱/۰۸۰۳۰۲/۰۸۰۳۰۴/۰۸۰۳۱۰/۰۸۰۳۱۱ به سقف تیرچه‌بلوک تعلق نمی‌گیرد).
        """
        refs = TechnicalOfficeEngine._joist_floor_refs(tables)
        refs |= TechnicalOfficeEngine._joist_topping_refs(tables)
        return refs

    def _aggregate_plan(self, plan_id: str, sched_recs, tables):
        """مجموع کمیت هر طرح بر اساس رکوردهای استخراج‌شده از Schedule ها."""
        R = sched_recs
        # سقف تیرچه‌بلوک: بتن و قالب المان‌های تیرچه داخل نرخ ۱۰۰۳۰۵ است و
        # نباید در ردیف‌های بتن (۰۸۰۱۰۵..۰۸۰۱۰۷) یا قالب (فصل ۰۶) دوبار
        # شمرده شود.
        _joist_refs = self._joist_floor_refs(tables)
        _topping_refs = self._joist_topping_refs(tables)

        def _not_joist_element(r):
            return not (r["ref"] in _joist_refs
                        and r["kind"] in ("structural_concrete", "formwork_super"))
        if plan_id == "lean":
            src = [r for r in R if r["kind"] == "lean_concrete" and r["unit"] == "m3"]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "conc-foundation":
            # قرارداد تقدم منابع: هر المان پی فقط از یک منبع (اختصاصی > تجمیعی > استنتاجی)
            direct, derived = self._foundation_candidates(R, tables)
            src = [r for r in direct + derived if _not_joist_element(r)]
            note = ("حجم پی‌ها از ابعاد جدول قالب‌بندی پی استنتاج شد."
                    if (derived and not direct) else None)
            return sum(r["qty"] for r in src), src, note
        if plan_id == "conc-col-beam":
            src = [r for r in R if _not_joist_element(r) and r["kind"] == "structural_concrete" and
                   (r["group"] in ("ستون", "تیر") or re.search(r"COLUMN|BEAM|FRAMING", r["detail"], re.I))]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "conc-slab":
            floor = [r for r in R if _not_joist_element(r)
                     and r["kind"] == "structural_concrete" and r["group"] == "سقف"]
            # ── بقایای سقف تیرچه‌بلوک (مرحلهٔ ۱۱) ──
            # بند ۳ فصل دهم: نرخ ۱۰۰۳۰۵ شامل تمام مصالح سقف به‌جز میلگرد است
            # → بتن پاشنهٔ تیرچه (joist_materials) دیگر به ۰۸۰۱۰۶ اضافه نمی‌شود.
            # بند ۹ فصل دهم: بتن تا ۵ cm روی بلوک داخل نرخ ۱۰۰۳۰۵ است →
            # معادل ۰٫۰۵ × مساحت ۱۰۰۳۰۵ از حجم رویهٔ JSL-TOP* کسر می‌شود و
            # فقط مازاد بر آن در این ردیف می‌ماند.
            plain = [r for r in floor if r["ref"] not in _topping_refs]
            topping = [r for r in floor if r["ref"] in _topping_refs]
            topping_vol = sum(r["qty"] for r in topping)
            src = list(plain)
            note = None
            if topping_vol > 0:
                jb_len = sum(r["qty"] for r in R
                             if r["kind"] == "joist_floor" and r["unit"] == "m")
                jb_area = jb_len * self.s.get("joist_spacing", 0.55)
                allowance = 0.05 * jb_area
                deduct = min(topping_vol, allowance)
                share = deduct / topping_vol if topping_vol > 0 else 0.0
                for r in topping:
                    src.append(dict(r, qty=r["qty"] * (1.0 - share)))
                note = (f"شامل {len(topping)} المان رویهٔ سقف تیرچه‌بلوک "
                        f"({topping_vol:.3f} m³) پس از کسر سهم داخل نرخ ۱۰۰۳۰۵ "
                        f"({deduct:.3f} m³ = ۰٫۰۵ × {jb_area:.3f} m² — بند ۹ فصل دهم)")
            return sum(r["qty"] for r in src), src, note
        if plan_id == "conc-stair":
            # در جداول Revit، بتن پله هم در Category اصلی و هم در Runs تکرار می‌شود؛
            # فقط Category اصلی. شرط باید روی ref و detail به‌صورت جداگانه اعمال شود
            # (مثل engine.ts) تا در نبود ستون Mark هم درست کار کند.
            src = [r for r in R if _not_joist_element(r)
                   and r["kind"] == "structural_concrete" and r["group"] == "پله"
                   and not re.match(r"^Stairs: Runs", r["ref"], re.I)
                   and not re.match(r"^Stairs: Runs", r["detail"], re.I)]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "form-foundation":
            src = [r for r in R if r["kind"] == "formwork_foundation" and r["unit"] == "m2"]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "form-column":
            src = [r for r in R if _not_joist_element(r) and r["kind"] == "formwork_super"
                   and r["unit"] == "m2" and
                   (r["group"] == "ستون" or re.search(r"COLUMN", r["ref"] + r["detail"], re.I))]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "form-beam":
            src = [r for r in R if _not_joist_element(r) and r["kind"] == "formwork_super"
                   and r["unit"] == "m2" and
                   (r["group"] == "تیر" or re.search(r"FRAMING|BEAM", r["ref"] + r["detail"], re.I))]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "form-stair":
            src = [r for r in R if _not_joist_element(r) and r["kind"] == "formwork_super"
                   and r["unit"] == "m2" and
                   (r["group"] == "پله" or re.search(r"STAIR|RUNS", r["ref"] + r["detail"], re.I))]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "form-slab":
            # دال/تاوهٔ مستقل (ایراد ۲): دستهٔ Floors/Slab از جدول قالب‌بندی
            # روسازه، به‌استثنای المان‌های سیستم تیرچه‌بلوک (JSL و رویهٔ آن).
            src = [r for r in R if _not_joist_element(r) and r["kind"] == "formwork_super"
                   and r["unit"] == "m2" and r["group"] == "سقف"
                   and r["ref"] not in _topping_refs
                   and not re.search(r"JSL", r["ref"], re.I)]
            return sum(r["qty"] for r in src), src, None
        if plan_id == "joist-block":
            joists = [r for r in R if r["kind"] == "joist_floor" and r["unit"] == "m"]
            total_len = sum(r["qty"] for r in joists)
            area = total_len * self.s["joist_spacing"]
            note = f"مساحت = مجموع طول تیرچه‌ها ({total_len:.1f} متر) × فاصلهٔ محور {self.s['joist_spacing']} متر"
            return area, joists, note
        return 0.0, [], None

    # ── سطل‌بندی بتن بر حسب مقاومت فشاری (ایراد ۱) ──
    _CONCRETE_PLANS = ("conc-foundation", "conc-col-beam", "conc-slab", "conc-stair")
    _CONCRETE_GROUP = {"conc-foundation": "foundation", "conc-col-beam": "column_beam",
                       "conc-slab": "slab", "conc-stair": "stair"}

    def _setting_mpa(self, plan_id):
        """مقاومت فشاری انتخابی کاربر برای گروه سازه‌ای (ورودی دستی)."""
        m = self.s.get("concrete_strength_mpa") or {}
        v = m.get(self._CONCRETE_GROUP[plan_id])
        try:
            return int(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def _concrete_buckets(self, plan_id, sched_recs, tables, ref_strength):
        """تقسیم منبع یک طرح بتن بر حسب مقاومت مؤثر.

        تقدم رسمی (ایراد ۱): پارامتر صریح Revit > نام متریال > ورودی دستی.
        نام متریال در یک جدول دیگر برای همان مرجع می‌تواند مقاومت المانی را
        که جدول اختصاصی‌اش ستون متریال ندارد (مثل جدول پی) تعیین کند.
        """
        _qty, sources, plan_note = self._aggregate_plan(plan_id, sched_recs, tables)
        setting_mpa = self._setting_mpa(plan_id)
        buckets = {}
        for r in sources:
            mpa = r.get("strength_mpa") or ref_strength.get(self._foundation_ref_key(r.get("ref")))
            origin = "material" if mpa is not None else None
            if mpa is None:
                mpa = setting_mpa
                origin = "setting"
            b = buckets.setdefault(mpa, {"qty": 0.0, "src": [], "origin": origin,
                                         "note_extra": None})
            b["qty"] += r["qty"]
            b["src"].append(r)
            if origin == "material":
                b["origin"] = "material"
        # یادداشت طرح (مثلاً مستندسازی کسر رویهٔ سقف تیرچه‌بلوک) حفظ می‌شود
        if plan_note:
            for b in buckets.values():
                if not b.get("note_extra"):
                    b["note_extra"] = plan_note
        return buckets

    def _emit_concrete_line(self, plan, mpa, b, n_buckets, direct_codes, lines, warns):
        """ساخت یک ردیف فهرست‌بها برای یک سطل مقاومت + هشدارهای قانونی."""
        pid = plan["id"]
        setting_mpa = self._setting_mpa(pid)
        code, price = CONCRETE_STRENGTH_CODES.get(mpa, (None, None))
        if code is None:
            # مقاومت پیدا نشد یا در جدول نگاشت نیست → ردیف پیش‌فرض انتخاب نمی‌شود
            warns.append({
                "level": "خطا", "category": "نگاشت مقاومت بتن",
                "item": pid,
                "message": (f"مقاومت فشاری {fa(mpa) if mpa else 'نامشخص'} مگاپاسکال برای "
                            f"گروه «{self._CONCRETE_GROUP[pid]}» در جدول نگاشت ردیف‌های "
                            f"فصل ۸ (config/concrete_strength_map.json) وجود ندارد. "
                            f"{b['qty']:.2f} مترمکعب بدون ردیف قیمت مانده است."),
                "action": "کد ردیف فصل ۸ به‌صورت دستی انتخاب شود (manual_codes).",
                "ref": "فصل ۸ فهرست‌بهای ابنیه ۱۴۰۴"})
            return None
        single = n_buckets == 1
        line_id = pid if (mpa == setting_mpa or single) else f"{pid}@{mpa}"
        sub_plan = dict(plan, id=line_id, target=code, price=price,
                        query=f"تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته "
                              f"با مقاومت فشاری مشخصه {fa(mpa)} مگاپاسکال",
                        desc=f"تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته "
                             f"با مقاومت فشاری مشخصه {fa(mpa)} مگاپاسکال")
        m = self._match(sub_plan)
        if m["code"] in direct_codes:
            return None
        qty = b["qty"]
        note_parts = []
        if b["origin"] == "material":
            note_parts.append(f"مقاومت فشاری {fa(mpa)} مگاپاسکال از نام متریال Revit استخراج شد")
            if setting_mpa is not None and mpa != setting_mpa:
                warns.append({
                    "level": "اطلاع", "category": "نگاشت مقاومت بتن", "item": pid,
                    "message": (f"متریال Revit برای گروه «{self._CONCRETE_GROUP[pid]}» "
                                f"{fa(mpa)} مگاپاسکال است ولی تنظیم کاربر {fa(setting_mpa)} "
                                f"مگاپاسکال است. طبق تقدم رسمی، مقاومت متریال اعمال شد."),
                    "action": "در صورت نیاز، تنظیم گروه را تغییر دهید.",
                    "ref": "ایراد ۱ — تقدم: پارامتر Revit > نام متریال > ورودی دستی"})
        elif b["origin"] == "setting":
            note_parts.append(f"مقاومت فشاری {fa(mpa)} مگاپاسکال از تنظیمات کاربر (متریال نامشخص)")
        if b.get("note_extra"):
            note_parts.append(b["note_extra"])
        lines.append({
            "id": line_id, "row_no": 0, "chapter": m["code"][:2],
            "chapter_title": chapter_title(m["code"][:2]), "code": m["code"],
            "desc": m["desc"], "unit": m["unit"], "qty": qty,
            "price": m["price"], "total": qty * m["price"],
            "method": m["method"], "confidence": m["confidence"],
            "sources": b["src"], "estimated": m["estimated"], "needs_review": m["needs_review"],
            "note": " — ".join(note_parts) if note_parts else None,
            "candidates": m["candidates"],
            "strength_mpa": mpa, "strength_origin": b["origin"],
        })
        return line_id

    # ── ضریب منطقه‌ای (ایراد ۴) — جدول بخشنامه ۹۴/۶۹۴۱۶ ──
    def _regional_coef(self, warns):
        """ضریب منطقه‌ای از جدول S5؛ اولویت: ورودی دستی > جدول استخراج‌شده.

        خروجی: (ضریب, وضعیت, منبع). اگر نه جدول و نه دستی → ناقص.
        """
        sel = self.s.get("regional_selection") or {}
        manual = self.s.get("regional_coef")
        if manual not in (None, ""):
            return float(manual), "دستی", "ورود کاربر"
        prov = sel.get("province")
        city = sel.get("city")
        disc = sel.get("discipline") or "ابنیه"
        dist = sel.get("district")
        entries = (REGIONAL_TABLE.get("provinces", {}) or {}).get(prov) or []
        if not entries:
            warns.append({
                "level": "خطا", "category": "ضریب منطقه‌ای", "item": prov or "—",
                "message": (f"استان «{prov or 'انتخاب‌نشده'}» در جدول ضرایب منطقه‌ای "
                            f"(config/regional_coefficients.json) یافت نشد."),
                "action": "استان/شهرستان را انتخاب یا ضریب را دستی وارد کنید.",
                "ref": "بخشنامه ۹۴/۶۹۴۱۶ (S5)"})
            return None, "ناقص", None
        cands = [e for e in entries if e["city"] == city
                 and (dist in (None, "") or e["district"] == dist)]
        if not cands:
            warns.append({
                "level": "خطا", "category": "ضریب منطقه‌ای", "item": f"{prov}/{city}",
                "message": (f"شهرستان «{city}» در استان «{prov}» یافت نشد. "
                            f"بخش‌های موجود: {', '.join(sorted({e['district'] for e in entries}))}"),
                "action": "بخش صحیح را انتخاب یا ضریب را دستی وارد کنید.",
                "ref": "بخشنامه ۹۴/۶۹۴۱۶ (S5)"})
            return None, "ناقص", None
        e = cands[0]
        v = e["coefs"].get(disc)
        if v is None:
            warns.append({
                "level": "خطا", "category": "ضریب منطقه‌ای",
                "item": f"{prov}/{city}/{e['district']}/{disc}",
                "message": f"ضریب رشتهٔ «{disc}» برای این شهرستان یافت نشد.",
                "action": "رشته را تغییر دهید یا ضریب را دستی وارد کنید.",
                "ref": "بخشنامه ۹۴/۶۹۴۱۶ (S5)"})
            return None, "ناقص", None
        _reg_meta = (REGIONAL_TABLE or {}).get("meta", {})
        _page = _reg_meta.get("page")
        src = ("استخراج‌شده از بخشنامه ۹۴/۶۹۴۱۶%s، ردیف %s (%s/%s/%s)%s — نیازمند تأیید کاربر"
               % (("، صفحهٔ %s PDF" % fa(_page)) if _page else "",
                  fa(e["row"]), prov, city, e["district"],
                  "، حوزهٔ بالای ۵۰۰ متر" if e["high_altitude"] else ""))
        return v, "استخراج‌شده", src

    # ── ضریب طبقات (ایراد ۳) — پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ ──
    @staticmethod
    def _level_kind(name):
        """طبقه‌بندی تراز Revit: زیرهمکف / همکف / بالاتر (شماره).

        طبق پیوست ۲: همکف = B0 (ضریب ۰)، اولین طبقه بالاتر = F1 (ضریب ۱)،
        اولین طبقه پایین‌تر از زیرهمکف = B1 (ضریب ۱).
        """
        n = normalize_text(name).upper()
        m = re.search(r"STORY\s*(\d+)", n)
        if m:
            i = int(m.group(1))
            return ("above", i - 1) if i > 1 else ("ground", 0)
        if re.search(r"FOUNDATION|FOOTING", n):
            # تراز بالای فونداسیون (Foundation Top) طبقه نیست — پی است، نه
            # زیرهمکف. طبق تعریف پیوست ۲ فقط «طبقات» در Σ می‌آیند. قابل
            # تغییر با floors_data[name]["is_floor"] (درخواست کاربر — بند ۱).
            return ("none", 0)
        if re.search(r"BASE", n) or "زیر" in n:
            return ("below_base", 1)
        return None

    def _lean_footprint(self, sched_recs):
        """رَدپای ساختمان از بتن مگر: حجم ÷ ضخامت (توصیه برای همکف/زیرهمکف)."""
        vol, thick, found = 0.0, None, False
        for r in sched_recs:
            if r.get("kind") != "lean_concrete":
                continue
            vol += r.get("qty", 0.0) or 0.0
            fam = normalize_text(str(r.get("family") or r.get("detail")
                                     or r.get("ref") or ""))
            mm = re.search(r"(\d{2,3})\s*(MM|م\.?م|مم)", fam, re.IGNORECASE)
            if mm:
                thick, found = int(mm.group(1)) / 1000.0, True
        if vol <= 0:
            return None
        if not found or not thick:
            thick = 0.10  # پیش‌فرض اپ: بتن مگر ۱۰ cm
        return {"volume": vol, "thickness": thick, "area": vol / thick,
                "assumed_thickness": not found,
                "status": "تخمینی (دستی)"}

    def _floors_table(self, sched_recs):
        """جدول طبقات: نام | نوع | مساحت مدل | مساحت دستی | مساحت مؤثر | ضریب."""
        model_areas = {}
        for r in sched_recs:
            if r["kind"] != "formwork_super" or r.get("group") != "سقف":
                continue
            lv = (r.get("level") or "").strip()
            if not lv:
                continue
            # مساحت کف طبقه = قالب زیرین دال/رویه (جلوگیری از دوباره‌شماری:
            # المان‌های تیرچه خودشان در این دسته نیستند)
            model_areas[lv] = model_areas.get(lv, 0.0) + r["qty"]
        manual = self.s.get("floors_data") or {}
        rows = []
        seen = set()
        for r in sched_recs:
            lv = (r.get("level") or "").strip()
            if lv and lv not in seen:
                seen.add(lv)
                auto_kind = self._level_kind(lv)
                if auto_kind is None:
                    continue
                kind = auto_kind
                mv = model_areas.get(lv)
                # floors_data[lv]: عدد مساحت (قدیمی) یا رکورد
                # {"area": x, "is_floor": bool} — انتخاب دستیِ طبقه بودن تراز.
                _manual = manual.get(lv)
                if isinstance(_manual, dict):
                    uv = _manual.get("area")
                    floor_flag = _manual.get("is_floor")
                else:
                    uv = _manual
                    floor_flag = None
                uv = float(uv) if uv not in (None, "") else None
                if floor_flag is True and kind[0] == "none":
                    kind = ("below_base", 1)     # کاربر این تراز را طبقه می‌داند
                elif floor_flag is False and kind[0] != "none":
                    kind = ("none", 0)           # کاربر این تراز را غیرطبقه‌ای کرد
                rows.append({"name": lv, "kind": kind[0], "index": kind[1],
                             "auto_kind": auto_kind[0],
                             "area_model": mv, "area_manual": uv,
                             "area": uv if uv is not None else mv})
        # ترازهای بام/مرجع (تنظیم floors_roof_levels) از فرمول مستثنی می‌شوند
        roof = set(self.s.get("floors_roof_levels") or [])
        for r in rows:
            if r["name"] in roof:
                r["kind"] = "roof"
                r["index"] = 0
        # شماره‌گذاری طبقات: بالاتر از همکف ۱..n، زیرهمکف ۱..m (بام مستثنی)
        below = sorted([r for r in rows if r["kind"] == "below_base"],
                       key=lambda x: x["name"])
        for i, r in enumerate(below, start=1):
            r["index"] = i
        above = sorted([r for r in rows if r["kind"] == "above"],
                       key=lambda x: x["name"])
        for i, r in enumerate(above, start=1):
            r["index"] = i
        rows.sort(key=lambda x: (x["kind"] == "roof", x["kind"] == "above",
                                 x["kind"] == "ground", x["index"]))
        return rows

    def _floors_coef(self, sched_recs, warns):
        """ضریب طبقات بر اساس فرمول رسمی پیوست ۲.

        P = 1 + [ Σ(i×Fi) + Σ(j×Bj) ] ÷ S    (مخرج از تنظیم floors_divisor)
        همکف (B0) در صورت S می‌آید ولی در صورت سهمی ندارد (ضریب ۰).
        """
        rows = self._floors_table(sched_recs)
        manual = self.s.get("floors_coef")
        if self.s.get("floors_auto", True) is False and manual not in (None, ""):
            return float(manual), "دستی", "ورود کاربر", rows, None
        divisor_mode = self.s.get("floors_divisor") or "100×S"
        missing = [r["name"] for r in rows
                   if r["kind"] in ("above", "below_base")
                   and r["area"] in (None, "")]
        if missing and rows:
            warns.append({
                "level": "خطا", "category": "ضریب طبقات",
                "item": "، ".join(missing),
                "message": ("مساحت این طبقات در مدل Revit موجود نیست "
                            f"({len(missing)} طبقه: {', '.join(missing)}). "
                            "در این مدل فقط طبقه‌ای که المان سقف (دست Floors) دارد "
                            "مساحت خودکار می‌گیرد — بقیه را از نقشه‌های مصوب دستی "
                            "وارد کنید (تنظیمات → floors_data). رَدپای ساختمان از "
                            "بتن مگر در شیت «ضریب طبقات» به‌عنوان راهنما نمایش "
                            "داده می‌شود."),
                "action": "مساحت هر طبقه را از نقشه‌های مصوب وارد کنید.",
                "ref": "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — بندهای ۱-۱ و ۱-۳"})
            return 1.0, "ناقص", None, rows, None
        num = sum(r["index"] * (r["area"] or 0) for r in rows
                  if r["kind"] in ("above", "below_base"))
        # مخرج S = مجموع مساحتِ همهٔ طبقات (همکف هم داخل S است)؛ بام و
        # ترازهای غیرطبقه‌ای (فونداسیون) مستثنی‌اند.
        den = sum((r["area"] or 0) for r in rows
                  if r["kind"] not in ("roof", "none"))
        if den <= 0:
            warns.append({
                "level": "هشدار", "category": "ضریب طبقات", "item": "—",
                "message": "هیچ مساحت طبقه‌ای در دسترس نیست — ضریب طبقات ۱.",
                "action": "مساحت طبقات را از نقشه‌های مصوب وارد کنید.",
                "ref": "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴"})
            return 1.0, "ناقص", None, rows, None
        div = den * (100.0 if divisor_mode == "100×S" else 1.0)
        p = 1.0 + (num / div if div > 0 else 0.0)
        p_alt = 1.0 + num / (den * 100.0) if divisor_mode != "100×S" else 1.0 + num / den
        warn_dev = (divisor_mode == "S")
        src = ("محاسبه از فرمول پیوست ۲: P = 1 + [Σ(i×Fi) + Σ(j×Bj)] ÷ %s = "
               "1 + (%s ÷ %s) = %s — نیازمند تأیید کاربر"
               % (divisor_mode, fa_float(num, 2), fa_float(den, 2), fa_float(p, 6)))
        roof_rows = [r for r in rows if r["kind"] == "roof"]
        non_floor_rows = [r for r in rows if r["kind"] == "none"]
        if roof_rows:
            warns.append({
                "level": "اطلاع", "category": "ضریب طبقات",
                "item": "، ".join(r["name"] for r in roof_rows),
                "message": ("این ترازها به‌عنوان بام/مرجع (غیرطبقه) در تنظیمات "
                            "floors_roof_levels مشخص شده‌اند و از صورت و مخرج "
                            "فرمول ضریب طبقات مستثنی شده‌اند. طبق تعاریف پیوست ۲ "
                            "فقط «طبقات» (بالای همکف، همکف، و زیرهمکف) در S "
                            "وارد می‌شوند."),
                "action": "در صورت اشتباه بودن، در تنظیمات تغییر دهید.",
                "ref": "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — تعاریف F/B/S"})
        if non_floor_rows:
            warns.append({
                "level": "اطلاع", "category": "ضریب طبقات",
                "item": "، ".join(r["name"] for r in non_floor_rows),
                "message": ("این ترازها غیرطبقه‌ای هستند (مثلاً تراز بالای "
                            "فونداسیون — پی است، نه زیرهمکف) و در Σ ضریب طبقات "
                            "وارد نمی‌شوند. طبق تعاریف پیوست ۲ فقط «طبقات» در "
                            "صورت و مخرج می‌آیند."),
                "action": ("اگر یکی از این ترازها در پروژهٔ شما طبقهٔ واقعی است، "
                           "در تنظیمات → floors_data آن را به‌عنوان طبقه علامت "
                           "بزنید."),
                "ref": "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — تعریف طبقه (بند ۱)"})
        if warn_dev:
            warns.append({
                "level": "هشدار", "category": "ضریب طبقات",
                "item": "مخرج فرمول",
                "message": ("مخرج کسر در متن رسمی پیوست ۲ «۱۰۰ × S» است ولی "
                            "گزینهٔ «S» انتخاب شده که با متن رسمی بخشنامه "
                            "مغایرت دارد. مقدار P با هر دو مخرج در شیت «ضریب "
                            "طبقات» نمایش داده می‌شود."),
                "action": "مخرج رسمی «۱۰۰ × S» را تأیید کنید (تنظیمات → floors_divisor).",
                "ref": "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — متن رسمی دریافت‌شده از کاربر"})
        return p, "محاسبه‌شده", src, rows, {"divisor": divisor_mode, "num": num,
                                        "den": den, "p_alt": p_alt,
                                        "alt_label": ("100×S" if divisor_mode == "S"
                                                      else "S")}

    # ── چگالی میلگرد (ایراد ۱۴) — کنترل کیفیت مدل Revit ──
    def _rebar_density_warnings(self, lines, warns):
        """هشدار چگالی میلگرد گروه‌های سازه‌ای: وزن ÷ حجم بتن."""
        th = (REBAR_DENSITY_CFG or {}).get("thresholds_kg_m3") or {}
        manual = self.s.get("rebar_manual_weight") or {}
        # حجم بتن به تفکیک گروه (از ردیف‌های فصل ۰۸)
        vol = {}
        for l in lines:
            if not l["code"].startswith("08") or l["unit"] != "مترمکعب":
                continue
            for r in l.get("sources") or []:
                g = r.get("group")
                if g:
                    vol[g] = vol.get(g, 0) + r["qty"]
        # وزن میلگرد به تفکیک گروه (از sources ردیف‌های آرماتور)
        wt = {}
        for l in lines:
            if not l["code"].startswith("07"):
                continue
            for r in l.get("sources") or []:
                g = r.get("group")
                if g:
                    wt[g] = wt.get(g, 0) + r["qty"]
        for g, lo_hi in th.items():
            if g not in vol or vol[g] <= 0.001:
                continue
            w = manual.get(g)
            if w is not None:
                warns.append({
                    "level": "اطلاع", "category": "چگالی میلگرد", "item": g,
                    "message": (f"وزن میلگرد گروه «{g}» به‌صورت دستی وارد شده "
                                f"({fa_float(w)} کیلوگرم) — مقدار مدل کنار آن "
                                f"نمایش داده می‌شود."),
                    "action": "—", "ref": "ایراد ۱۴ — ورود کاربر"})
                continue
            if g not in wt:
                continue
            d = wt[g] / vol[g]
            lo, hi = lo_hi[0], lo_hi[1]
            if d < lo or d > hi:
                warns.append({
                    "level": "خطا", "category": "چگالی میلگرد", "item": g,
                    "message": (f"چگالی میلگرد {g} = {fa_float(d)} kg/m³؛ "
                                f"محدودهٔ متعارف {fa(lo)} تا {fa(hi)}. احتمالاً "
                                f"میلگرد در مدل Revit کامل مدل نشده. مقدار از مدل "
                                f"برداشته شده و تغییری داده نشد."),
                    "action": ("وزن یا چگالی دستی گروه را وارد کنید یا مدل را "
                               "بازبینی کنید."),
                    "ref": "ایراد ۱۴ — کنترل کیفیت مدل"})
        return {"volumes": vol, "weights": wt}

    # ── قالب بدون ردیف (ایراد ۲) — هر سطح قالب نگاشت‌نشده ──
    def _unpriced_formwork_warnings(self, lines, sched_recs, warns):
        consumed = set()
        for l in lines:
            if l["code"].startswith("06"):
                for r in l.get("sources") or []:
                    consumed.add(id(r))
        for r in sched_recs:
            if r["kind"] not in ("formwork_foundation", "formwork_super") \
                    or r.get("unit") != "m2" or r["qty"] <= 0:
                continue
            if id(r) in consumed:
                continue
            ref = r["ref"]
            if re.search(r"JSL", ref):
                warns.append({
                    "level": "اطلاع", "category": "قالب بدون ردیف", "item": ref,
                    "message": (f"{fa_float(r['qty'])} مترمربع قالب‌بندی این "
                                f"المان داخل نرخ ردیف ۱۰۰۳۰۵ (سقف تیرچه‌بلوک) است "
                                f"و در فصل ۰۶ قیمت‌گذاری نمی‌شود."),
                    "action": "—", "ref": "فصل ۱۰ فهرست‌بها — بند نرخ ۱۰۰۳۰۵"})
            else:
                warns.append({
                    "level": "هشدار", "category": "قالب بدون ردیف", "item": ref,
                    "message": (f"{fa_float(r['qty'])} مترمربع قالب‌بندی به "
                                f"هیچ ردیف فصل ۰۶ نگاشت نشد."),
                    "action": "نگاشت دستی ردیف فصل ۰۶ را بررسی کنید.",
                    "ref": "فصل ۰۶ فهرست‌بها (ایراد ۲)"})

    # ── استخراج لیستوفر آرماتور ──
    def _extract_rebar(self, tables, map_df):
        """لیستوفر آرماتور از Schedule ها (+ غنی‌سازی از Mapping v1) + تراز Grand total."""
        lines = []
        warnings = []
        bucket_kg = {}
        bucket_src = {}
        # مارک‌های آرماتور پوشش‌داده‌شده توسط Revit Schedule ها — برای جلوگیری از
        # دوباره‌شماری میلگردهای Mapping v1 که زیرمجموعهٔ همان Schedule ها هستند.
        revit_marks = set()
        # شمارش ردیف‌های فاقد مارک / گروه برای هشدار یکباره به ازای هر جدول
        # (ایراد ۱۱) — از پر شدن رجیستری با ۱۳۳ هشدار تکراری جلوگیری می‌کند.
        _no_mark = {}
        _unknown_grp = {}

        for t in tables:
            if t["kind"] not in ("rebar_detailed", "rebar_joist", "rebar_connection"):
                continue
            # ستون خام «Schedule Mark» در جداول rebar_detailed داخل col_map نیست
            # (الگوی ^mark$ فقط هدرهای دقیق «Mark» را می‌گیرد)؛ برای dedup از
            # سلول خام خوانده می‌شود تا ساختار جدول تغییر نکند.
            sm_idx = next((i for i, h in enumerate(t["headers"])
                           if h.strip().lower() == "schedule mark"), None)
            rows_sum = 0.0
            for row in t["rows"]:
                if row["is_subtotal"]:
                    continue
                weight = row["values"].get("weight", 0) or 0
                if weight <= 0:
                    continue
                mark = row["texts"].get("mark") or row["texts"].get("familyType") or "—"
                r_mark = (row["texts"].get("mark") or "").strip()
                if not r_mark and sm_idx is not None:
                    r_mark = (row["cells"][sm_idx] if sm_idx < len(row["cells"]) else "").strip()
                if r_mark:
                    revit_marks.add(normalize_text(r_mark))
                bar_type = row["texts"].get("barType") or row["texts"].get("material") or ""
                diameter = row["values"].get("diameter", 0) or 0
                if not diameter:
                    dm = re.search(r"[φΦ⌀]\s?(\d{1,2})", bar_type + " " + mark)
                    if dm:
                        diameter = float(dm.group(1))
                grade = row["texts"].get("material") or bar_type
                bucket = self._rebar_bucket(diameter or 12, grade)
                # گروه میزبان: ستون «Host Category» مبنای تشخیص بتن مسلح در ردیف
                # اختیاری ۰۸۰۳۱۰ است. در نبود آن (مثلاً جداول آرماتور تیرچه) از
                # گروه استخراج‌شدهٔ مارک استفاده می‌شود. گروه «سایر» (= نامعلوم)
                # به‌عنوان مدرک میزبان به‌شمار نمی‌آید.
                host_cat = (row["texts"].get("hostCategory") or "").strip()
                grp = structural_group(mark + " " + row["texts"].get("familyType", ""), t["kind"])
                if host_cat and host_cat.lower() != "<varies>":
                    evidence = structural_group(host_cat)
                elif grp != "سایر":
                    evidence = grp
                else:
                    evidence = ""
                # ستون‌های لیستوفر (ایراد ۱۱): مارک و گروه از میزبان، طبقه،
                # طول هر شاخه و وزن واحد محاسبه می‌شوند. گروه هرگز «سایر» و
                # مارک هرگز «—» نیست.
                _disp_mark = rebar_list_mark(r_mark, row["texts"].get("familyType"))
                _grp, _grp_unknown = rebar_list_group(host_cat,
                                                      r_mark + " " + row["texts"].get("familyType", ""),
                                                      t["kind"])
                if _disp_mark == "بدون مارک":
                    _no_mark[t["title"]] = _no_mark.get(t["title"], 0) + 1
                if _grp_unknown:
                    _unknown_grp[t["title"]] = _unknown_grp.get(t["title"], 0) + 1
                _cnt = row["values"].get("count", 0) or 1
                _len = row["values"].get("length", 0) or 0
                lines.append({
                    "mark": _disp_mark, "group": _grp, "evidence": evidence,
                    "bar_type": bar_type, "diameter": diameter,
                    "grade": "AI" if "2400" in grade else ("AIII" if "4000" in grade else "—"),
                    "shape": row["texts"].get("shape", ""),
                    "count": _cnt,
                    "total_length": _len,
                    "weight": weight, "price_code": bucket, "source": t["title"],
                    "level": (row["texts"].get("level") or "").strip(),
                    "per_bar_length": (_len / _cnt) if _cnt else 0.0,
                    "unit_weight": (weight / _len) if _len else 0.0,
                })
                bucket_kg[bucket] = bucket_kg.get(bucket, 0) + weight
                bucket_src.setdefault(bucket, []).append({
                    "source": f"Schedule: {t['file_name']}", "table": t["title"], "kind": t["kind"],
                    "ref": mark, "group": structural_group(mark, t["kind"]), "material": grade,
                    "level": "", "from_mapping": False,
                    "qty": weight, "unit": "kg", "detail": f"{bar_type} × {row['values'].get('count', '—')} شاخه"})
                rows_sum += weight
            # تراز با Grand total رسمی Revit (بدون افت وزن)
            gt_w = t["grand_total"].get("weight")
            if gt_w and rows_sum > 0 and gt_w > rows_sum * 1.02:
                diff = gt_w - rows_sum
                dominant = max(bucket_kg.items(), key=lambda kv: kv[1])[0] if bucket_kg else "070202"
                bucket_kg[dominant] = bucket_kg.get(dominant, 0) + diff
                bucket_src.setdefault(dominant, []).append({
                    "source": f"Schedule: {t['file_name']}", "table": t["title"], "kind": t["kind"],
                    "ref": "سایر شاخه‌ها", "group": "متفرقه", "material": "—", "level": "",
                    "from_mapping": False, "qty": diff, "unit": "kg",
                    "detail": f"تراز با Grand total رسمی ({gt_w:.1f} kg)"})
                warnings.append(f"جدول «{t['title']}»: اختلاف {diff:.1f} کیلوگرم با Grand total رسمی تخصیص یافت.")

        # هشدارهای لیستوفر (ایراد ۱۱): مارک ناموجود + گروه نامشخص — یکی به
        # ازای هر جدول (نه به ازای هر ردیف، تا رجیستری پر نشود).
        for _t, _n in _no_mark.items():
            warnings.append(
                f"جدول «{_t}»: {fa(_n)} ردیف آرماتور فاقد مارک هستند و به‌عنوان "
                f"«بدون مارک» ثبت شدند — پارامتر Revit «Rebar Number/Mark» "
                f"در مدل تکمیل شود (ایراد ۱۱).")
        for _t, _n in _unknown_grp.items():
            warnings.append(
                f"جدول «{_t}»: {fa(_n)} ردیف آرماتور گروه سازه‌ای مشخصی ندارند "
                f"(Host Category ناموجود) و به‌عنوان «نامشخص» ثبت شدند — ستون "
                f"«Host Category» در مدل Revit تکمیل شود (ایراد ۱۱).")

        # غنی‌سازی لیستوفر از Mapping v1 (با قطر/گرید/شکل دقیق)
        if map_df is not None and not map_df.empty and "source_format" in map_df.columns:
            v1 = map_df[map_df["source_format"] == "v1"]
            for _, row in v1.iterrows():
                d = float(row.get("diameter_mm", 0) or 0)
                length_m = float(row.get("length_m", 0) or 0)
                if d <= 0 or length_m <= 0:
                    continue
                mark = str(row.get("mark", "")) or str(row.get("host_mark", ""))
                # Revit Schedule مرجع است: میلگردی که قبلاً در Schedule پوشش
                # داده شده، دوباره از Mapping v1 اضافه نمی‌شود (جلوگیری از
                # دوباره‌شماری آرماتورهای مشترک بین خروجی Revit و داینامو).
                mark_v1 = normalize_text(str(row.get("mark", "") or "")).strip()
                if mark_v1 and mark_v1 in revit_marks:
                    continue
                grade = str(row.get("steel_type", ""))
                bucket = self._rebar_bucket(d, grade)
                weight = length_m * rebar_unit_weight(d)
                grp = structural_group(f"{mark} {row.get('host_family', '')}")
                _host = str(row.get("host_category", "") or "")
                _grp2, _unk2 = rebar_list_group(_host,
                                                f"{mark} {row.get('host_family', '')}",
                                                "mapping")
                _disp_mark2 = rebar_list_mark(str(row.get("mark", "")),
                                             str(row.get("host_mark", "")))
                if _disp_mark2 == "بدون مارک":
                    _no_mark["Mapping v1"] = _no_mark.get("Mapping v1", 0) + 1
                if _unk2:
                    _unknown_grp["Mapping v1"] = _unknown_grp.get("Mapping v1", 0) + 1
                lines.append({
                    "mark": _disp_mark2, "group": _grp2,
                    "evidence": grp if grp != "سایر" else "",
                    "bar_type": f"Φ{int(d)}", "diameter": d,
                    "grade": "AI" if "2400" in grade else ("AIII" if "4000" in grade else grade or "—"),
                    "shape": str(row.get("rebar_detail", "")), "count": 1,
                    "total_length": length_m, "weight": weight, "price_code": bucket,
                    "source": "Mapping v1",
                    "level": str(row.get("level", "") or ""),
                    "per_bar_length": length_m,
                    "unit_weight": (weight / length_m) if length_m else 0.0,
                })
                bucket_kg[bucket] = bucket_kg.get(bucket, 0) + weight
                bucket_src.setdefault(bucket, []).append({
                    "source": "Mapping v1", "table": str(row.get("element_id", "")), "kind": "mapping",
                    "ref": mark, "group": structural_group(mark), "material": grade, "level": "",
                    "from_mapping": True, "qty": weight, "unit": "kg",
                    "detail": f"Φ{int(d)} × طول {length_m:.2f} متر"})

        # ردیف‌های آرماتور مستقیم از v2
        if map_df is not None and not map_df.empty:
            v2 = map_df[map_df.get("source_format", "v2") == "v2"] if "source_format" in map_df.columns else map_df
            if "rebar_weight_kg" in v2.columns:
                rw_sum = pd.to_numeric(v2["rebar_weight_kg"], errors="coerce").fillna(0)
                for idx_val, w_val in rw_sum[rw_sum > 0].items():
                    row = v2.loc[idx_val]
                    grp = structural_group(f"{row.get('category', '')} {row.get('family', '')}")
                    _grp3, _unk3 = rebar_list_group(
                        str(row.get("host_category", "") or ""),
                        f"{row.get('category', '')} {row.get('family', '')}", "mapping")
                    _disp_mark3 = rebar_list_mark(str(row.get("mark", "")),
                                                 str(row.get("family", "")))
                    if _disp_mark3 == "بدون مارک":
                        _no_mark["Mapping v2"] = _no_mark.get("Mapping v2", 0) + 1
                    if _unk3:
                        _unknown_grp["Mapping v2"] = _unknown_grp.get("Mapping v2", 0) + 1
                    lines.append({
                        "mark": _disp_mark3,
                        "group": _grp3,
                        "evidence": grp if grp != "سایر" else "",
                        "bar_type": "—", "diameter": 0, "grade": "—",
                        "shape": "", "count": 1, "total_length": 0,
                        "weight": float(w_val), "price_code": "070202",
                        "source": "Mapping v2",
                        "level": str(row.get("level", "") or ""),
                        "per_bar_length": 0.0,
                        "unit_weight": 0.0,
                    })
                    bucket_kg["070202"] = bucket_kg.get("070202", 0) + float(w_val)
                    bucket_src.setdefault("070202", []).append({
                        "source": "Mapping v2", "table": str(row.get("element_id", "")), "kind": "mapping",
                        "ref": str(row.get("mark", "")), "group": structural_group(str(row.get("category", ""))),
                        "material": "", "level": str(row.get("level", "")),
                        "from_mapping": True, "qty": float(w_val), "unit": "kg",
                        "detail": "وزن میلگرد المان (Mapping v2)"})
        return lines, bucket_kg, bucket_src, warnings

    @staticmethod
    def _rebar_bucket(diameter: float, grade: str) -> str:
        """سینی‌بندی آرماتور بر اساس گرید فولاد و قطر → کد ردیف فهرست‌بها.

        قطر همواره بر حسب میلی‌متر تفسیر می‌شود. مقدار ستون «Bar Diameter» پس از
        to_si بر حسب متر است (مثلاً 0.018)؛ چون قطر آرماتور همواره ≥ ۱ mm است،
        هر مقدار کوچک‌تر از ۱ متر به میلی‌متر نرمال می‌شود تا آستانه‌های ۱۰/۱۸ mm
        معنا بدهند. مسیرهای regex fallback و Mapping v1 از قبل mm هستند.
        """
        d = float(diameter) if diameter else 0.0
        if 0 < d < 1:
            d *= 1000  # متر → میلی‌متر
        g = normalize_text(grade).upper()
        is_plain = bool(re.search(r"A.?I[^II]|2400|SMOOTH", g)) and "4000" not in g
        if is_plain:
            return "070101"
        if d <= 10:
            return "070201"
        if d <= 18:
            return "070202"
        return "070203"

    # ── محاسبهٔ کامل پروژه ──
    def compute(self, tables, map_df):
        """
        محاسبهٔ کامل پروژه:
        ردیف‌های مستقیم Mapping (تقدم) ← طرح‌های قاعده‌محور Schedule ← آرماتور ← زنجیرهٔ مالی.
        خروجی: دیکشنری نتیجهٔ کامل برنامه.
        """
        s = self.s
        # مهاجرت ورودی‌های دستی قدیمی به ساختار ریکاردی فاز C (یک‌بار، Idempotent)
        migrate_manual_entries(s)
        sched_recs = []
        for t in tables:
            sched_recs.extend(self._records_from_table(t))
        map_recs = self._records_from_mapping(map_df) if (map_df is not None and not map_df.empty) else []

        lines = []
        # ۱) ردیف‌های مستقیم از «کد فهرست بها» فایل Mapping (مرجعیت اول)
        direct_lines = self._direct_coded_lines(map_df)
        direct_codes = {l["code"] for l in direct_lines}
        lines.extend(direct_lines)

        # ۲) طرح‌های قاعده‌محور از Schedule ها
        plans = self._plans()
        warns = []  # ثبت مرکزی هشدارها (ایراد ۱۰) — ← ساختار در پایان compute

        # نقشهٔ مقاومت بر اساس مرجع المان (ایراد ۱): جدولی که ستون متریال
        # ندارد (مثل جدول اختصاصی پی) می‌تواند مقاومت را از جدولی دیگر برای
        # همان مرجع تهیه کند.
        ref_strength = {}
        for r in sched_recs:
            if r.get("strength_mpa"):
                k = self._foundation_ref_key(r.get("ref"))
                if k:
                    ref_strength[k] = r["strength_mpa"]
        # ── بتن مازاد بر ۵ cm روی بلوک (بند ۹ الزامات عمومی فصل دهم) ──
        # ضخامت سقف از زیر تیرچه تا ۵ cm بتن روی بلوک داخل نرخ ۱۰۰۳۰۵ است.
        # فقط بتن مازاد بر ۵ cm — بر اساس مشخصات فنی پروژه — به ردیف بتن
        # متناظر با مقاومت انتخابی افزوده می‌شود. اختلاف هندسی Revit
        # (مثلاً ۵٫۲ cm) مازاد محسوب نمی‌شود.
        joist_len = sum(r["qty"] for r in sched_recs
                        if r["kind"] == "joist_floor" and r["unit"] == "m")
        joist_area_net = joist_len * s.get("joist_spacing", 0.55)
        _top_cm = float(s.get("joist_block_top_thickness_cm") or 5)
        excess_m3 = ((_top_cm - 5) / 100.0 * joist_area_net) if _top_cm > 5 else 0.0
        excess_plan_id = None
        if excess_m3 > 0:
            _jb_mpa = int(s.get("joist_block_concrete_mpa") or 20)
            _jb_code = CONCRETE_STRENGTH_CODES.get(_jb_mpa, CONCRETE_STRENGTH_CODES[20])[0]
            # ردیف بتن متناظر با مقاومت انتخابی؛ ترتیب ترجیح: سقف > ستون‌تیر > پله > پی
            for _pid in ("conc-slab", "conc-col-beam", "conc-stair", "conc-foundation"):
                _p = next((p for p in plans if p["id"] == _pid), None)
                if _p and _p["target"] == _jb_code:
                    excess_plan_id = _pid
                    break

        for plan in plans:
            pid = plan["id"]
            # طرح‌های بتن: یک ردیف به ازای هر مقاومت مؤثر (ایراد ۱)
            if pid in TechnicalOfficeEngine._CONCRETE_PLANS:
                buckets = self._concrete_buckets(pid, sched_recs, tables, ref_strength)
                if excess_m3 > 0 and pid == excess_plan_id:
                    b = buckets.get(_jb_mpa)
                    if b is None:
                        b = {"qty": 0.0, "src": [], "origin": "setting", "note_extra": None}
                        buckets[_jb_mpa] = b
                    b["qty"] += excess_m3
                    b["note_extra"] = \
                        f"شامل بتن مازاد بر ۵ cm روی بلوک ({excess_m3:.3f} m³ — بند ۹ فصل دهم)"
                for mpa, b in buckets.items():
                    if b["qty"] <= 0.0001:
                        continue
                    self._emit_concrete_line(plan, mpa, b, len(buckets),
                                             direct_codes, lines, warns)
                continue
            qty, sources, note = self._aggregate_plan(plan["id"], sched_recs, tables)
            if plan["id"] == excess_plan_id:
                qty += excess_m3
                note = ((note + " — ") if note else "") + \
                    f"شامل بتن مازاد بر ۵ cm روی بلوک ({excess_m3:.3f} m³ — بند ۹ فصل دهم)"
            if not qty or qty <= 0.0001:
                continue
            m = self._match(plan)
            if m["code"] in direct_codes:
                # جلوگیری از دوبار‌شماری: کد مستقیم Mapping بر طرح قاعده‌محور تقدم دارد
                continue
            lines.append({
                "id": plan["id"], "row_no": 0, "chapter": m["code"][:2],
                "chapter_title": chapter_title(m["code"][:2]), "code": m["code"],
                "desc": m["desc"], "unit": m["unit"], "qty": qty,
                "price": m["price"], "total": qty * m["price"],
                "method": m["method"], "confidence": m["confidence"],
                "sources": sources, "estimated": m["estimated"], "needs_review": m["needs_review"],
                "note": note, "candidates": m["candidates"],
            })

        # ۳) آرماتور (Schedule + Mapping) — سینی‌بندی وزنی
        rebar_lines, bucket_kg, bucket_src, rb_warn = self._extract_rebar(tables, map_df)
        for bucket in ("070101", "070201", "070202", "070203"):
            kg = bucket_kg.get(bucket, 0)
            if kg <= 0.01 or bucket in direct_codes:
                continue
            meta = _REBAR_BUCKET_META[bucket]
            plan = {"id": f"rebar-{bucket}", "target": bucket, "query": meta["query"],
                    "desc": meta["desc"], "unit": "کیلوگرم",
                    "fallback_price": meta["price"]}
            m = self._match(plan)
            lines.append({
                "id": f"rebar-{bucket}", "row_no": 0, "chapter": "07",
                "chapter_title": chapter_title("07"), "code": m["code"], "desc": m["desc"],
                "unit": m["unit"], "qty": kg,
                "price": m["price"], "total": kg * m["price"],
                "method": m["method"], "confidence": m["confidence"],
                "sources": bucket_src.get(bucket, []), "estimated": m["estimated"],
                "needs_review": m["needs_review"], "note": None, "candidates": m["candidates"],
            })

        # ۴) حمل میلگرد (فصل ۲۸) — پیشنهاد خودکار
        # ردیف ۲۸۰۱۰۱ فهرست‌بهای ۱۴۰۴: «هرگاه فاصله محل تهیه تا محل کارگاه،
        # بیش از ۳۰ کیلومتر و تا ۷۵ کیلومتر باشد، برای تمام طول مسیر پس از
        # کسر ۳۰ کیلومتر» → کمیت = وزن(تن) × (مسافت − ۳۰) بر حسب تن-کیلومتر.
        total_rebar_kg = sum(bucket_kg.values())
        if total_rebar_kg > 0 and "280101" not in direct_codes:
            haul_km = s.get("haul_distance_km", 50)
            plan = {"id": "transport-rebar", "target": "280101",
                    "query": "حمل آهن آلات مصالح سنگی بیش از ۳۰ کیلومتر تا ۷۵ کیلومتر",
                    "desc": "حمل سیمان پاکتی، مصالح سنگی، آهن‌آلات، آجر و بلوک، هرگاه فاصله محل تهیه تا محل کارگاه، بیش از ۳۰ کیلومتر و تا ۷۵ کیلومتر باشد، برای تمام طول مسیر پس از کسر ۳۰ کیلومتر",
                    "unit": "تن-کیلومتر", "fallback_price": 28400.0}
            m = self._match(plan)
            tons = total_rebar_kg / 1000
            ton_km = tons * max(haul_km - 30, 0)
            lines.append({
                "id": "transport-rebar", "row_no": 0, "chapter": "28",
                "chapter_title": chapter_title("28"), "code": m["code"], "desc": m["desc"],
                "unit": m["unit"], "qty": ton_km,
                "price": m["price"], "total": ton_km * m["price"],
                "method": m["method"], "confidence": m["confidence"],
                "sources": [], "estimated": m["estimated"], "needs_review": True,
                "note": f"پیشنهاد خودکار — {tons:.1f} تن × {max(haul_km - 30, 0)} کیلومتر "
                        f"(مسافت {haul_km} کیلومتر، پس از کسر ۳۰). در صورت عدم نیاز، این ردیف را مستثنی کنید.",
                "candidates": m["candidates"],
            })

        # ۴-الف) اضافه‌بهای مقاومت بتن سقف تیرچه‌بلوک (۱۰۰۷۰۱ / ۱۰۰۷۰۲)
        # بندهای ۸ و ۹ الزامات عمومی فصل دهم فهرست‌بهای ۱۴۰۴: بتن سقف
        # تیرچه‌بلوک ۲۰ MPa فرض می‌شود؛ هرگاه مقاومت فشاری مشخصه بیش از ۲۰
        # و حداکثر ۲۵ MPa باشد → ۱۰۰۷۰۱ (۵۹٬۵۰۰ ریال/m²) و بیش از ۲۵ تا
        # ۳۰ MPa → ۱۰۰۷۰۲ (۷۶٬۵۰۰ ریال/m²) روی کل مساحت سقف. مقدار از
        # تنظیمات کاربر خوانده می‌شود (هیچ مقدار فرضی نیست) و کمیت برابر با
        # مساحت خالص ردیف ۱۰۰۳۰۵ است (بدون ضریب پرت — مرحلهٔ ۱۱ بخش ۱).
        jb_mpa = int(s.get("joist_block_concrete_mpa") or 20)
        jb_surcharge = JOIST_BLOCK_STRENGTH_SURCHARGE.get(jb_mpa)
        jb_line = next((l for l in lines if l["id"] == "joist-block"), None)
        if jb_surcharge and jb_line and jb_line["qty"] > 0 \
                and jb_surcharge[0] not in direct_codes:
            jb_code, jb_price = jb_surcharge
            plan = {"id": "joist-strength-surcharge", "target": jb_code,
                    "query": "اضافه بها سقف تیرچه و بلوک مقاومت فشاری بتن",
                    "desc": ("اضافه‌بها به ردیف‌های سقف تیرچه و بلوک، در صورتی که "
                             "مقاومت فشاری مشخصه بتن سقف، بیش از ۲۰ مگاپاسکال و "
                             "حداکثر ۲۵ مگاپاسکال باشد" if jb_code == "100701" else
                             "اضافه‌بها به ردیف‌های سقف تیرچه و بلوک، در صورتی که "
                             "مقاومت فشاری مشخصه بتن سقف، بیش از ۲۵ مگاپاسکال و "
                             "حداکثر ۳۰ مگاپاسکال باشد"),
                    "unit": "مترمربع", "fallback_price": jb_price}
            m = self._match(plan)
            q = jb_line["qty"]
            lines.append({
                "id": "joist-strength-surcharge", "row_no": 0, "chapter": "10",
                "chapter_title": chapter_title("10"), "code": m["code"], "desc": m["desc"],
                "unit": m["unit"], "qty": q,
                "price": m["price"], "total": q * m["price"],
                "method": m["method"], "confidence": m["confidence"],
                "sources": [], "estimated": m["estimated"], "needs_review": False,
                "note": f"پیشنهاد خودکار — مقاومت بتن سقف تیرچه‌بلوک {fa(jb_mpa)} MPa "
                        f"(بند ۸ الزامات عمومی فصل دهم). در صورت عدم نیاز، این ردیف را مستثنی کنید.",
                "candidates": m["candidates"],
            })

        # ۴-ب) اضافه‌بهای سختی ارتعاش بتن (۰۸۰۳۱۱) — پیشنهاد اختیاری
        # ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴: «اضافه‌بها به ردیف‌های بتن‌ریزی برای
        # سختی ارتعاش بتن، در صورتی که میلگرد به کار رفته بیش از ۱۸۰
        # کیلوگرم در مترمکعب بتن باشد». تراکم میلگرد = مجموع وزن آرماتور
        # (kg) ÷ حجم بتن‌های سازه‌ای (m³، بدون بتن‌مگر). چون از ۱۸۰ بیشتر
        # باشد، اضافه‌بها به ازای هر مترمکعب بتن سازه‌ای (مقدار خالص)
        # محاسبه می‌شود. مبنای این ردیف حجم بتن‌های سازه‌ای به‌جز سیستم سقف
        # تیرچه‌بلوک است (بند ۳-۵ فصل ۸). قیمت و آستانه از فهرست‌بهای رسمی
        # ۱۴۰۴ خوانده می‌شوند (در دادهٔ نمونه تراکم ≈ ۳۱ kg/m³ < ۱۸۰ → ردیفی
        # افزوده نمی‌شود).
        if s.get("surcharge_rebar_density"):
            _joist_sys = self._joist_system_refs(tables)
            conc_lines = [l for l in lines if l["id"].startswith("conc-")]
            struct_net = sum(src.get("qty", 0) for l in conc_lines
                             for src in l.get("sources", [])
                             if src.get("ref") not in _joist_sys)
            density = rebar_density(total_rebar_kg, struct_net)
            if struct_net > 0 and density > REBAR_DENSITY_THRESHOLD and "080311" not in direct_codes:
                plan = {"id": "surcharge-080311", "target": "080311",
                        "query": "اضافه بها سختی ارتعاش بتن میلگرد بیش از ۱۸۰ کیلوگرم مترمکعب",
                        "desc": "اضافه‌بها به ردیف‌های بتن‌ریزی برای سختی ارتعاش بتن",
                        "unit": "مترمکعب", "fallback_price": 363500.0}
                m = self._match(plan)
                lines.append({
                    "id": "surcharge-080311", "row_no": 0, "chapter": "08",
                    "chapter_title": chapter_title("08"), "code": m["code"], "desc": m["desc"],
                    "unit": m["unit"], "qty": struct_net,
                    "price": m["price"], "total": struct_net * m["price"],
                    "method": m["method"], "confidence": m["confidence"],
                    "sources": [], "estimated": m["estimated"], "needs_review": False,
                    "note": f"پیشنهاد خودکار — تراکم میلگرد {density:.1f} kg/m³ > ۱۸۰ "
                            f"(آستانهٔ فهرست‌بهای ۱۴۰۴). در صورت عدم نیاز، این ردیف را مستثنی کنید.",
                    "candidates": m["candidates"],
                })

        # ۴-ج) اضافه‌بهای بتن مسلح (۰۸۰۳۱۰) — پیشنهاد اختیاری، per-element
        # ردیف ۰۸۰۳۱۰ فهرست‌بهای ۱۴۰۴: «اضافه‌بها به ردیف‌های بتن‌ریزی، در
        # صورت مصرف بتن در بتن مسلح». مدرک «مسلح بودن» ستون «Host Mark»
        # جدول آرماتور است: وزن آرماتور هر المان میزبان ÷ حجم همان المان.
        # فقط المان‌هایی که تراکم خودشان > ۱۸۰ kg/m³ است حساب می‌شوند
        # (نه میانگین پروژه — بند ۳-۶ فصل ۸). حجم JSL (تیرچه + رویه) از
        # مبنای اضافه‌بها کسر می‌شود (بند ۳-۵: به سقف تیرچه‌بلوک تعلق
        # نمی‌گیرد). بتن مگر (lean) هرگز مسلح نیست.
        if s.get("surcharge_reinforced_concrete"):
            _joist_sys = self._joist_system_refs(tables)
            host_kg = {}
            for t in tables:
                if t["kind"] not in ("rebar_detailed", "rebar_joist", "rebar_connection"):
                    continue
                for r in t["rows"]:
                    if r["is_subtotal"]:
                        continue
                    hm = (r["texts"].get("hostMark") or "").strip()
                    kg = r["values"].get("weight", 0) or 0
                    if hm and hm.lower() != "<varies>" and kg > 0:
                        host_kg[hm] = host_kg.get(hm, 0) + kg
            qualifiers = []
            base = 0.0
            for l in lines:
                if not l["id"].startswith("conc-"):
                    continue  # بتن مگر مسلح نیست
                for src in l.get("sources", []):
                    mk = (src.get("ref") or "").strip()
                    if not mk or mk in _joist_sys:
                        continue  # حجم JSL از مبنای اضافه‌بها کسر می‌شود
                    v = src.get("qty", 0) or 0
                    kg = host_kg.get(mk, 0.0)
                    if v > 0 and kg > 0 and kg / v > REBAR_DENSITY_THRESHOLD:
                        base += v
                        qualifiers.append(mk)
            if base > 0 and "080310" not in direct_codes:
                plan = {"id": "surcharge-080310", "target": "080310",
                        "query": "اضافه بها ردیف های بتن ریزی در صورت مصرف بتن در بتن مسلح",
                        "desc": "اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت مصرف بتن در بتن مسلح",
                        "unit": "مترمکعب", "fallback_price": 145500.0}
                m = self._match(plan)
                lines.append({
                    "id": "surcharge-080310", "row_no": 0, "chapter": "08",
                    "chapter_title": chapter_title("08"), "code": m["code"], "desc": m["desc"],
                    "unit": m["unit"], "qty": base,
                    "price": m["price"], "total": base * m["price"],
                    "method": m["method"], "confidence": m["confidence"],
                    "sources": [], "estimated": m["estimated"], "needs_review": False,
                    "note": f"پیشنهاد خودکار — {len(qualifiers)} المان با تراکم میلگرد "
                            f"خودشان > ۱۸۰ kg/m³ "
                            f"({fa(len(qualifiers))} المان: {', '.join(sorted(set(qualifiers)))}). "
                            f"در صورت عدم نیاز، این ردیف را مستثنی کنید.",
                    "candidates": m["candidates"],
                })

        # ۴-د) اضافه‌بهای ضخامت کم بتن (۰۸۰۳۰۴) — پیشنهاد اختیاری
        # ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴: «اضافه‌بها به ردیف‌های بتن‌ریزی،
        # هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد». این ردیف فقط
        # به کف‌سازی بتنی روی زمین تعلق می‌گیرد (دال روی زمین، بدون
        # قالب‌بندی زیره)؛ دال معلق (گروه «سقف» با قالب‌بندی زیره) ارزیابی
        # نمی‌شود (بند ۳-۳ فصل ۸). ضخامت فقط از داده‌های خود پروژه استخراج
        # می‌شود: ردیفی که هم «حجم» و هم «مساحت» در جدول خودش دارد (مثل
        # جداول بتن مگر و بتن‌ریزی پی) → ضخامت = حجم ÷ مساحت. تیر/ستون/پله
        # ارزیابی نمی‌شوند (مساحت قالب‌بندی شامل کناره‌ها/پاهاست و
        # حجم÷مساحت برابر ضخامت نیست).
        if s.get("surcharge_thin_concrete"):
            thin_net = thin_concrete_net(tables)
            if thin_net > 0 and "080304" not in direct_codes:
                plan = {"id": "surcharge-080304", "target": "080304",
                        "query": "اضافه بها ردیف های بتن ریزی هرگاه ضخامت بتن ۱۵ سانتی متر یا کمتر",
                        "desc": "اضافه‌بها به ردیف‌های بتن‌ریزی، هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد",
                        "unit": "مترمکعب", "fallback_price": 304000.0}
                m = self._match(plan)
                lines.append({
                    "id": "surcharge-080304", "row_no": 0, "chapter": "08",
                    "chapter_title": chapter_title("08"), "code": m["code"], "desc": m["desc"],
                    "unit": m["unit"], "qty": thin_net,
                    "price": m["price"], "total": thin_net * m["price"],
                    "method": m["method"], "confidence": m["confidence"],
                    "sources": [], "estimated": m["estimated"], "needs_review": False,
                    "note": f"پیشنهاد خودکار — حجم کف‌سازی بتنی روی زمین با ضخامت "
                            f"≤ ۱۵ سانتی‌متر: {thin_net:.2f} m³. "
                            f"در صورت عدم نیاز، این ردیف را مستثنی کنید.",
                    "candidates": m["candidates"],
                })

        # ۵) مستثنی‌ها، مرتب‌سازی و شماره‌گذاری
        # ── ردیف‌های ستاره‌دار (غیرفهرستی — فاز C): ورود کامل دستی با مقدار،
        # ├── قیمت و فصل؛ در صورت‌وضعیت و شاخص تعدیل می‌آیند (§۱۵-۴ بند ۲).
        for sr in (s.get("starred_rows") or []):
            try:
                _sq = float(sr.get("qty") or 0)
                _sp = float(sr.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if _sq <= 0 or _sp <= 0:
                continue
            _ch = str(sr.get("chapter") or "")[:2] or "99"
            _code = str(sr.get("code") or "").strip() or f"starred-{_ch}"
            if not _code.endswith("*"):
                _code = _code + "*"
            lines.append({
                "id": f"starred-{_code}", "row_no": 0, "chapter": _ch,
                "chapter_title": chapter_title(_ch), "code": _code,
                "desc": str(sr.get("desc") or "ردیف غیرفهرستی (ستاره‌دار)"),
                "unit": str(sr.get("unit") or "عدد"),
                "qty": _sq, "price": _sp, "total": _sq * _sp,
                "method": "manual-starred", "confidence": 1.0,
                "sources": [], "estimated": False, "needs_review": False,
                "note": str(sr.get("note") or "ورود دستی — فاقد ردیف متناظر در فهرست‌بها"),
                "candidates": [], "starred": True, "manual": dict(sr),
                "app_price": None, "diff_pct": None,
            })

        lines = [l for l in lines if l["id"] not in excluded_ids(s)]
        lines.sort(key=lambda l: ((_CHAPTER_ORDER.index(l["chapter"]) if l["chapter"] in _CHAPTER_ORDER else 99), l["code"]))
        for i, l in enumerate(lines, 1):
            l["row_no"] = i

        # ۵.۵) لایهٔ قیمت دستی (فاز C — §۱۵-۴): اعمال اولویت
        # دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی روی هر ردیف، با نگهداری
        # قیمتِ پیشینِ برنامه و درصد اختلاف برای نمایش دوگانه و هشدار بازبینی (>۳۰٪).
        _warn_pct = float(s.get("price_diff_warn_pct") or 30.0)
        for l in lines:
            _app_price = l.get("base_price")
            if _app_price is None:
                _app_price = l["price"]
            _rec = (s.get("manual_prices") or {}).get(l["id"])
            if _rec and _rec.get("price") is not None:
                l["price"] = float(_rec["price"])
                l["total"] = l["qty"] * l["price"]
                # رکوردِ قیمت دستی روی ردیف (دسترسی UI/Excel به منبع و سند)
                l["manual"] = _rec
                # رفتار قدیمی: قیمت دستی، ردیف را تأییدشده و غیرتخمینی می‌کند
                l["estimated"] = False
                l["needs_review"] = False
                if _app_price:
                    l["diff_pct"] = (l["price"] - _app_price) / _app_price * 100.0
                    if abs(l["diff_pct"]) > _warn_pct:
                        warns.append({
                            "level": "هشدار", "category": "قیمت دستی",
                            "item": l["code"],
                            "message": (f"اختلاف قیمت دستی ردیف {l['code']} با قیمت "
                                        f"فهرست‌بها {fa_float(abs(l['diff_pct']), 1)}٪ "
                                        f"است (بیش از آستانهٔ {fa_float(_warn_pct, 0)}٪)."),
                            "action": "منبع سند را بررسی و تأیید کنید.",
                            "ref": "§۱۵-۴ بند ۳ — پنل قیمت دستی"})
                else:
                    l["diff_pct"] = None
            else:
                l["diff_pct"] = None
            l["app_price"] = _app_price if _rec else None
            l["price_status"] = price_status_of(l)

        # ۶) لایهٔ شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) — قبل از ضرایب
        # زنجیرهٔ مالی و روی مبلغ ردیف (بر اساس دو رقم اول کد). اگر دورهٔ
        # هدف برابر دورهٔ مبنا باشد، ضریب همهٔ فصل‌ها ۱ است.
        index_target = s.get("index_target_period") or self.index_table.base_period
        index_report = None
        if index_target and self.index_table.base_period \
                and index_target != self.index_table.base_period:
            for l in lines:
                f = self.index_table.factor(l["code"], index_target)
                l["index_factor"] = f
                l["total_indexed"] = l["total"] * f
            index_report = self.index_table.report(index_target)
        else:
            for l in lines:
                l["index_factor"] = 1.0
                l["total_indexed"] = l["total"]

        # ۷) زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸):
        # جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای + تجهیز و
        # برچیدن کارگاه. کسورات قانونی (۲۲٫۸٪) جزو «ناخالص پرداختی» نیستند و
        # فقط در خروجی جداگانهٔ «خالص پرداختی» محاسبه می‌شوند.
        base_total = sum(l["total_indexed"] for l in lines)
        # ضریب طبقات (ایراد ۳) و ضریب منطقه‌ای (ایراد ۴): محاسبهٔ شفاف با
        # ثبت منبع و وضعیت؛ در حالت ناقص، ضریب ۱ و برچسب «ناقص» داده می‌شود.
        floors_coef, floors_status, floors_src, floors_rows, floors_calc = \
            self._floors_coef(sched_recs, warns)
        regional_coef, regional_status, regional_src = self._regional_coef(warns)
        # اعمال ضریب طبقات فقط روی ردیف‌های مشمول (پیوست ۲ بند ۱-۳):
        # کار ساختمان به‌استثنای محوطه‌سازی و حمل‌ونقل (فصل ۲۸).
        excluded = set(s.get("floors_excluded_chapters") or
                       (FLOORS_SPEC or {}).get("apply_to_setting", {}).get("default", ["28"]))
        excluded |= {l["chapter"] for l in lines
                     if l["chapter"].isdigit() and int(l["chapter"]) >= 30}
        eligible_lines = [l for l in lines if l["chapter"] not in excluded]
        eligible_total = sum(l["total_indexed"] for l in eligible_lines)
        pf = floors_coef or 1.0
        floors_amount = eligible_total * pf + (base_total - eligible_total)
        overhead_amount = floors_amount * s["overhead_coef"]
        regional_amount = overhead_amount * (regional_coef or 1.0)
        gross_payable = regional_amount + s["site_setup_amount"]
        grand_total = gross_payable

        # خالص پرداختی (خروجی جداگانه، برچسب روشن — بر ناخالص اثر ندارد)
        insurance = gross_payable * s["insurance_pct"] / 100
        tax = gross_payable * s["tax_pct"] / 100
        good_job = gross_payable * s["good_job_pct"] / 100
        advance = s["advance_payment"]
        total_deductions = insurance + tax + good_job + advance
        net_payable = gross_payable - total_deductions

        # ۸) موتورهای فاز B: دو موتور مجزا («تعدیل پیمان» و «برآورد به‌هنگام»).
        # هر دو می‌توانند همزمان فعال باشند؛ ورودی، فرمول و خروجی هر کدام
        # جداست و روی زنجیرهٔ مالی بالا اثری ندارد.
        _chap_amt = {}
        # فاز E-9 §۳.۳ — بند ۵ بخشنامهٔ ۱۵۵۲۳۳: مبلغِ ردیف‌های دارایِ واحدِ
        # «مترمکعب کیلومتر» در فصل‌های غیر از فصل حمل، به فصل ۲۸ منتقل
        # می‌شود تا با شاخص‌های فصل حمل تعدیل شوند.
        _haul_ch = self._haul_target_chapter()
        _haul_moved = 0.0
        for _l in lines:
            _ch = _l["chapter"]
            if _ch != _haul_ch and self._is_haul_unit(_l.get("unit")):
                _ch = _haul_ch
                _haul_moved += (_l.get("total_indexed") or 0.0)
            _chap_amt[_ch] = _chap_amt.get(_ch, 0.0) \
                + (_l.get("total_indexed") or 0.0)
        adjustment = self._adjustment({
            "chapter_amounts": _chap_amt,
            "haul_moved_amount": _haul_moved,
            "floors_amount": floors_amount,
            "base_total": base_total,
            "site_setup": s["site_setup_amount"],
            "floors_info": {"value": pf, "status": floors_status,
                            "eligible_total": eligible_total,
                            "excluded_total": base_total - eligible_total},
            "advance_payment": advance,
            "overhead_coef": s["overhead_coef"],
            "regional_coef": regional_coef,
            "grand_total": grand_total,
        }, warns)

        chapter_sums = {}
        for l in lines:
            chapter_sums[l["chapter"]] = chapter_sums.get(l["chapter"], 0) + l["total_indexed"]
        chapter_rows = sorted(
            [{"chapter": ch, "title": chapter_title(ch), "total": tot} for ch, tot in chapter_sums.items()],
            key=lambda r: r["total"], reverse=True)

        # ── رجیستری مرکزی هشدارها (ایراد ۱۰) ──
        # هر ردیف needs_review باید هشدار متناظر داشته باشد (قاعدهٔ کیفی)
        for l in lines:
            if l.get("needs_review"):
                cand = l.get("candidates") or []
                warns.append({
                    "level": "هشدار", "category": "تطبیق ردیف", "item": l["code"],
                    "message": (f"تطبیق ردیف {l['code']} با روش «{l['method']}» "
                                f"(اطمینان {fa_float(l.get('confidence') or 0, 2)}) "
                                f"نیاز به بازبینی دارد."
                                + (f" کدهای پیشنهادی: {', '.join(str(c.get('code', c)) for c in cand[:3])}."
                                   if cand else "")),
                    "action": "کد ردیف را در فایل Mapping ثبت یا تأیید کنید.",
                    "ref": "ایراد ۱۰ — کنترل کیفیت تطبیق"})
        # چگالی میلگرد (ایراد ۱۴) و قالب بدون ردیف (ایراد ۲)
        self._rebar_density_warnings(lines, warns)
        self._unpriced_formwork_warnings(lines, sched_recs, warns)
        # هشدارهای متنی قدیمی (تجزیهٔ جداول / آرماتور) → ساختار مرکزی
        for w in [x for t in tables for x in t.get("warnings", [])] + list(rb_warn):
            warns.append({"level": "هشدار", "category": "تجزیهٔ جداول/آرماتور",
                          "item": "—", "message": w, "action": "—", "ref": "—"})

        quality = {
            "tables_parsed": len(tables),
            "tables_unknown": sum(1 for t in tables if t["kind"] == "unknown"),
            "mapping_records": 0 if map_df is None or map_df.empty else len(map_df),
            "rows_read": sum(len(t["rows"]) for t in tables),
            "lines_matched": len(lines),
            "lines_exact": sum(1 for l in lines if l["method"] in ("rule-exact", "manual", "direct-code")),
            "lines_fuzzy": sum(1 for l in lines if l["method"] == "fuzzy"),
            "lines_estimated": sum(1 for l in lines if l["estimated"]),
            "lines_review": sum(1 for l in lines if l["needs_review"]),
            "warnings": list(dict.fromkeys(
                [w for t in tables for w in t.get("warnings", [])] + rb_warn)),
        }

        _lvl = {}
        for w in warns:
            _lvl[w["level"]] = _lvl.get(w["level"], 0) + 1

        # ── فاز E-۵: مغایرتِ سال فهرست‌بها (انتخاب پروژه vs فایل بارگذاری‌شده) ──
        _fy_sel = convert_persian_digits(str(s.get("fehrest_year") or "")).strip()
        _fy_db = convert_persian_digits(str(s.get("fehrest_db_year") or "")).strip()
        if _fy_sel and _fy_db and _fy_sel != _fy_db:
            warns.append({
                "level": "هشدار", "category": "فهرست‌بها",
                "item": "fehrest_year_mismatch",
                "message": "سال فهرست‌بهای پروژه (%s) با سال فهرستِ "
                           "بارگذاری‌شده (%s) متفاوت است." % (_fy_sel, _fy_db),
                "action": "یا سال پروژه را در سایدبار تصحیح کنید یا "
                          "فهرست‌بهای سال %s را در تب «فهرست‌بها» "
                          "بارگذاری کنید." % _fy_sel,
                "ref": "فاز E-۵ — پروفایل پروژه",
            })

        # ── خلاصهٔ وضعیت قیمت‌ها (فاز C — §۱۵-۴ بندهای ۵ و ۶) ──
        _ps = {st: 0 for st in MANUAL_STATUSES}
        for l in lines:
            _ps[l.get("price_status") or "قطعی"] = \
                _ps.get(l.get("price_status") or "قطعی", 0) + 1
        _starred_total = sum(l["total_indexed"] for l in lines if l.get("starred"))
        _starred_pct = (_starred_total / grand_total * 100.0) if grand_total else 0.0

        return {
            "lines": lines, "rebar": rebar_lines, "chapter_sums": chapter_rows,
            "records": sched_recs + map_recs,
            "base_total": base_total,
            "floors_amount": floors_amount, "overhead_amount": overhead_amount,
            "regional_amount": regional_amount,
            "site_setup": s["site_setup_amount"],
            "gross_payable": gross_payable, "grand_total": grand_total,
            # خالص پرداختی (خروجی جداگانه، بر ناخالص اثر ندارد)
            "insurance": insurance, "tax": tax,
            "good_job": good_job, "advance_payment": advance,
            "total_deductions": total_deductions, "net_payable": net_payable,
            # موتورهای فاز B (دو موتور مجزا — روی زنجیره اثر ندارند)
            "adjustment": adjustment,
            # گزارش شاخص تعدیل (دوره، نوع و منبع هر فصل)
            "index": index_report,
            # پنل قیمت دستی (فاز C): شمارش هر سطح، جمع ستاره‌دارها
            "price_status_summary": _ps,
            "needs_price_entry": _ps.get("نیازمند ورود", 0),
            "starred_total": _starred_total,
            "starred_pct": _starred_pct,
            # ضرایب زنجیرهٔ مالی با وضعیت و منبع (ایراد ۳ و ۴)
            "coefs": {
                "floors": {"value": floors_coef, "status": floors_status,
                           "source": floors_src, "rows": floors_rows,
                           "calc": floors_calc,
                           "eligible_total": eligible_total,
                           "excluded_total": base_total - eligible_total,
                           "excluded_chapters": sorted(excluded),
                           "eligible_lines": [
                               {"code": l["code"], "desc": l["desc"],
                                "chapter": l["chapter"],
                                "total": l["total_indexed"]}
                               for l in eligible_lines],
                           "footprint": self._lean_footprint(sched_recs),
                           "floors_amount": floors_amount,
                           "formula": (FLOORS_SPEC or {}).get("formula"),
                           "clause": (FLOORS_SPEC or {}).get("apply_to")},
                "regional": {"value": regional_coef, "status": regional_status,
                             "source": regional_src},
            },
            # رجیستری مرکزی هشدارها (ایراد ۱۰)
            "warnings": warns,
            "warnings_by_level": _lvl,
            # وضعیت کلی پروژه: ناقص اگر هشدار سطح خطا یا ضریب ناقص وجود دارد
            "status": {
                "complete": not any(w["level"] == "خطا" for w in warns)
                    and floors_status != "ناقص" and regional_status != "ناقص",
                "errors": _lvl.get("خطا", 0),
                "warnings_n": _lvl.get("هشدار", 0),
                "info": _lvl.get("اطلاع", 0),
                "floors_status": floors_status,
                "regional_status": regional_status,
            },
            "quality": quality,
        }

    # ═══════ فاز B: دو موتور مجزای تعدیل ═══════
    # موتور ۱ «تعدیل پیمان»:  ΔP = k × Σ_c (It_c/Io_c − 1) × A_c
    #   شاخص هر فصل از پیوست ۳ بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳ (صفحه‌های ۶–۷)؛
    #   تجهیز/برچیدن و ردیف‌های بدون شاخص فصل: شاخص رشته‌ای (بند ۴)؛
    #   ردیف‌های «مترمکعب-کیلومتر»: شاخص فصل حمل همان رشته (بند ۵).
    # موتور ۲ «برآورد به‌هنگام»:  A_new = Σ_c A_c × It_c/Io_c
    # هر دو موتور می‌توانند همزمان فعال شوند ولی ورودی/فرمول/شیت/کارتِ
    # هر کدام کاملاً جداست و هرگز ادغام نمی‌شوند (قاعدهٔ طلایی ۵).
    # خروجی روی زنجیرهٔ مالی اصلی اثر ندارد.

    # دوره‌های شاخص قابل استخراج از config/index_bulletins.json
    _PERIOD_KEYS = (("base", "اسفند ۱۴۰۳ (مبنا)"),
                    ("q1", "سه‌ماهه اول ۱۴۰۴"), ("q2", "سه‌ماهه دوم ۱۴۰۴"),
                    ("q3", "سه‌ماهه سوم ۱۴۰۴"), ("q4", "سه‌ماهه چهارم ۱۴۰۴"))
    _PERIOD_FIELDS = {"base": "base_esfand_1403", "q1": "q1_1404",
                      "q2": "q2_1404", "q3": "q3_1404", "q4": "q4_1404"}
    # معادل سه‌ماهه‌ای هر کلید دوره («base» همان سه‌ماههٔ چهارم ۱۴۰۳ است)
    _PERIOD_QUARTERS = {"base": "1403Q4", "q1": "1404Q1", "q2": "1404Q2",
                        "q3": "1404Q3", "q4": "1404Q4"}
    _QUARTER_PERIOD = {v: k for k, v in _PERIOD_QUARTERS.items()}

    @classmethod
    def _quarter_is_provisional(cls, quarter):
        """سه‌ماهه‌های سال ۱۴۰۵ به بعد — شاخص قطعی ندارند (بند ۳).

        بندهای ۲ و ۳ بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳: کارکرد ۱۴۰۵Q1 و تمام
        سه‌ماهه‌های بعدتر که شاخص قطعی ندارند با «ضریب موقت × آخرین
        شاخص قطعی (۱۴۰۴Q4)» محاسبه می‌شوند و علی‌الحساب می‌مانند.
        """
        try:
            return int(str(quarter).split("Q")[0]) >= 1405
        except (ValueError, IndexError, AttributeError):
            return False

    # ═══════ فاز E-9 §۳.۶ — جانشانیِ خودکارِ موقت→قطعی ═══════
    # بند ۳ بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳: کارکردِ ۱۴۰۵ علی‌الحساب با «ضریب موقت ×
    # ۱۴۰۴Q4» است. هنگامی که شاخصِ قطعیِ یک سه‌ماههٔ ۱۴۰۵ اعلام و در
    # config/index_bulletins.json (بخشِ definitive_1405 با announced=true)
    # وارد شد، موتورها خودبه‌خود از آن استفاده می‌کنند؛ نیازی به تغییرِ
    # هیچ ورودیِ دیگری نیست.

    @classmethod
    def _definitive_1405_cfg(cls):
        """بخشِ شاخص‌های قطعیِ ۱۴۰۵ config/index_bulletins.json."""
        return (INDEX_BULLETINS or {}).get("definitive_1405") or {}

    @classmethod
    def _quarter_has_definitive(cls, quarter):
        """آیا شاخصِ قطعیِ این سه‌ماهه اعلام *و وارد* شده؟

        فقط announced=true کافی نیست؛ باید حداقل یک ردیفِ مقدار هم وارد
        شده باشد (قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود).
        """
        qs = cls._definitive_1405_cfg().get("quarters") or {}
        q = qs.get(str(quarter))
        if not q or q.get("announced") is not True:
            return False
        cfg = cls._definitive_1405_cfg()
        return bool(cfg.get("disciplines") or cfg.get("chapters_abnieh"))

    @staticmethod
    def _definitive_field(quarter):
        """کلیدِ فیلدِ یک سه‌ماهه در جداولِ definitive_1405 (مثلاً q1_1405)."""
        try:
            return "q%d_1405" % int(str(quarter).split("Q")[1])
        except (ValueError, IndexError):
            return None

    @classmethod
    def _definitive_chapter_index(cls, chapter, quarter):
        """شاخصِ قطعیِ یک فصل برای سه‌ماهه‌های ۱۴۰۵. → (مقدار, صفحه)."""
        field = cls._definitive_field(quarter)
        if not field:
            return None, None
        _code = str(chapter).strip().zfill(2)
        for r in cls._definitive_1405_cfg().get("chapters_abnieh") or []:
            if str(r.get("chapter")).strip().zfill(2) == _code:
                v = r.get(field)
                return (float(v), r.get("page")) \
                    if isinstance(v, (int, float)) else (None, None)
        return None, None

    @classmethod
    def _definitive_discipline_index(cls, quarter, discipline="ابنیه"):
        """شاخصِ قطعیِ یک رشته برای سه‌ماهه‌های ۱۴۰۵. → (مقدار, صفحه)."""
        field = cls._definitive_field(quarter)
        if not field:
            return None, None
        for r in cls._definitive_1405_cfg().get("disciplines") or []:
            if r.get("name") == discipline:
                v = r.get(field)
                return (float(v), r.get("page")) \
                    if isinstance(v, (int, float)) else (None, None)
        return None, None

    # ═══════ فاز E-9 §۳.۳ — بند ۵: فصلِ حملِ ردیف‌های مترمکعب‌کیلومتر ═══════
    # بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵ (صفحهٔ ۲): ردیف‌های پایه‌ای با واحدِ
    # «مترمکعب کیلومتر» که حملِ آن‌ها در فصل‌های غیر از فصل حمل منظور شده،
    # با شاخص‌های فصل حمل همان رشته تعدیل می‌شوند. پیاده‌سازی: مبلغِ این
    # ردیف‌ها هنگامِ تجمیعِ chapter_amounts به فصل ۲۸ منتقل می‌شود، در نتیجه
    # هم Io و هم It از فصل ۲۸ خوانده می‌شوند.

    @classmethod
    def _haul_clause5(cls):
        """تنظیماتِ بند ۵ از config/index_bulletins.json (clause5_haul)."""
        return (INDEX_BULLETINS or {}).get("clause5_haul") or {}

    @classmethod
    def _haul_target_chapter(cls):
        """کدِ فصلِ حمل (پیش‌فرض ۲۸)."""
        return str((cls._haul_clause5() or {}).get("haul_chapter") or "28")

    @classmethod
    def _is_haul_unit(cls, unit):
        """آیا واحدِ این ردیف، واحدِ حملِ «مترمکعب کیلومتر» است (بند ۵)؟"""
        cfg = cls._haul_clause5()
        if not cfg or cfg.get("enabled") is not True:
            return False
        _norm = str(unit or "").replace(" ", "").replace("‌", "") \
            .replace("-", "").replace("ـ", "").replace("_", "")
        for pat in cfg.get("haul_units") or []:
            p = str(pat).replace(" ", "").replace("‌", "") \
                .replace("-", "").replace("ـ", "").replace("_", "")
            if p and p in _norm:
                return True
        return False

    @classmethod
    def _monthly_cfg(cls):
        """بخشِ شاخص‌های ماهانهٔ config/index_bulletins.json (۱۴۴۳۷۴)."""
        return (INDEX_BULLETINS or {}).get("monthly") or {}

    @classmethod
    def _monthly_periods(cls):
        """دوره‌های ماهانهٔ موجود در config (برای UI)."""
        m = cls._monthly_cfg()
        return [{"key": k, "label": lbl}
                for k, lbl in (m.get("periods") or {}).items()]

    @classmethod
    def _monthly_has_data(cls, month_key):
        """آیا شاخص ماهانه وارد شده؟ (هرگز حدس زده نمی‌شود)."""
        m = cls._monthly_cfg()
        if not (m.get("chapters_abnieh") or m.get("disciplines")):
            return False
        _ch = [r for r in m.get("chapters_abnieh") or []
               if isinstance(r.get(month_key), (int, float))]
        _di = [r for r in m.get("disciplines") or []
               if isinstance(r.get(month_key), (int, float))]
        return bool(_ch or _di)

    @classmethod
    def _monthly_chapter_index(cls, chapter, month_key):
        """شاخص یک فصل در یک ماه (۱۴۴۳۷۴ — جدول monthly). → (مقدار, صفحه)."""
        _code = str(chapter).strip().zfill(2)
        for r in cls._monthly_cfg().get("chapters_abnieh") or []:
            if str(r.get("chapter")).strip().zfill(2) == _code:
                v = r.get(month_key)
                return (float(v), r.get("page")) \
                    if isinstance(v, (int, float)) else (None, None)
        return None, None

    @classmethod
    def _monthly_discipline(cls, month_key, discipline="ابنیه"):
        """شاخص رشته در یک ماه (۱۴۴۳۷۴). → (مقدار, صفحه)."""
        for r in cls._monthly_cfg().get("disciplines") or []:
            if r.get("name") == discipline:
                v = r.get(month_key)
                return (float(v), r.get("page")) \
                    if isinstance(v, (int, float)) else (None, None)
        return None, None

    @classmethod
    def _io_month_for(cls, date_text):
        """بخشنامهٔ ۱۴۴۳۷۴: مهلت تسلیم در تابستان ۱۴۰۵ ⇒ Io = خرداد ۱۴۰۵.

        تابستان ۱۴۰۵ = تیر/مرداد/شهریور (ماه‌های ۴–۶). در غیر این صورت
        Io سه‌ماهه‌ای است (قاعدهٔ پیوست ۳) و خروجی None است."""
        p = cls._parse_jalali(date_text)
        if not p:
            return None
        y, mo, _ = p
        return "khordad_1405" if (y == 1405 and 4 <= mo <= 6) else None

    @classmethod
    def index_periods(cls):
        """دوره‌های شاخص موجود در config/index_bulletins.json (برای UI)."""
        if not ((INDEX_BULLETINS or {}).get("disciplines")):
            return []
        return [{"key": k, "label": lbl} for k, lbl in cls._PERIOD_KEYS]

    @classmethod
    def _index_value(cls, period_key, discipline="ابنیه"):
        """شاخص رشتهٔ انتخابی در یک دوره (پیوست ۳، ردیف ۱). → (مقدار, صفحه)."""
        rows = [d for d in (INDEX_BULLETINS or {}).get("disciplines") or []
                if d.get("name") == discipline]
        if not rows:
            return None, None
        field = cls._PERIOD_FIELDS.get(period_key or "")
        if not field:
            return None, None
        v = rows[0].get(field)
        return (float(v), rows[0].get("page")) if isinstance(v, (int, float)) \
            else (None, None)

    @classmethod
    def _chapter_index(cls, chapter, period_key):
        """شاخص یک فصل (کد دو رقمی) در یک دوره (پیوست ۳، صفحه‌های ۶–۷).

        کدهای فصل هم به‌صورت عددی (۶) و هم رشتهٔ صفرپرشده («06») کار می‌کنند.
        خروجی: (مقدار, صفحه). اگر فصل استخراج نشده باشد (None, None).
        """
        _code = str(chapter).strip().zfill(2)
        ch_rows = [r for r in (INDEX_BULLETINS or {}).get("chapters_abnieh") or []
                   if str(r.get("chapter")).strip().zfill(2) == _code]
        if not ch_rows:
            return None, None
        field = cls._PERIOD_FIELDS.get(period_key or "")
        if not field:
            return None, None
        v = ch_rows[0].get(field)
        return (float(v), ch_rows[0].get("page")) if isinstance(v, (int, float)) \
            else (None, None)

    @classmethod
    def _chapter_index_q(cls, chapter, quarter):
        """شاخص یک فصل با کلید سه‌ماهه (قطعی‌های پیوست ۳)."""
        pk = cls._QUARTER_PERIOD.get(quarter or "")
        if not pk:
            return None, None
        return cls._chapter_index(chapter, pk)

    @staticmethod
    def _adj_pending(item, value, source, page, status, action=""):
        """یک رکورد از رجیستری «مقادیر منتظر تأیید» (شیت جداگانه)."""
        return {"item": item, "value": value, "source": source,
                "page": page, "status": status, "action": action}

    @staticmethod
    def _split_rounded(total, first, ndigits=0):
        """تفکیک گردشدهٔ یک جمع به دو بخش (دلیگیت به _split_rounded ماژول)."""
        return _split_rounded(total, first, ndigits)

    @classmethod
    def validate_meta(cls, meta):
        """اعتبارسنجی تاریخ‌های پروژه (ایراد ۱۲).

        سه تاریخ متمایز و هرگز ادغام‌نشدنی:
          - «تاریخ شروع پیمان»            ← contract_date
          - «تاریخ شروع دورهٔ صورت‌وضعیت»  ← period_start
          - «تاریخ پایان دورهٔ صورت‌وضعیت» ← period_end

        قاعده: شروع پیمان ≤ شروع دوره ≤ پایان دوره. تاریخ‌های خالی در
        این بررسی شرکت نمی‌کنند (تنها تاریخ‌های پرشده بررسی می‌شوند).
        خروجی: لیست هشدارهای مرکزی (level="خطا") — اگر خالی نباشد،
        محاسبه/خروجی باید متوقف شود (قاعدهٔ ایراد ۱۲)."""
        errs = []
        if not meta:
            return errs
        _F = (("تاریخ شروع پیمان", (meta.get("contract_date") or "").strip()),
              ("تاریخ شروع دورهٔ صورت‌وضعیت", (meta.get("period_start") or "").strip()),
              ("تاریخ پایان دورهٔ صورت‌وضعیت", (meta.get("period_end") or "").strip()))
        # ۱) هر تاریخ پرشده باید شمسیِ معتبر باشد (ارقام فارسی/لاتین)
        for _label, _v in _F:
            if _v and not cls._parse_jalali(_v):
                errs.append({
                    "level": "خطا", "category": "تاریخ‌ها", "item": _label,
                    "message": f"{_label} = «{_v}» یک تاریخ شمسی معتبر نیست "
                               f"(قالب موردنظر: ۱۴۰۵/۰۷/۰۸).",
                    "action": "تاریخ را به‌صورت شمسی (سال/ماه/روز) اصلاح کنید.",
                    "ref": "ایراد ۱۲ — اعتبارسنجی تاریخ‌ها"})
        # ۲) ترتیب: شروع پیمان ≤ شروع دوره ≤ پایان دوره
        _p = {k: cls._parse_jalali(v) for k, v in _F}
        _d = {k: (cls._abs_day(*p) if p else None) for k, p in _p.items()}
        if _d["تاریخ شروع پیمان"] is not None \
                and _d["تاریخ شروع دورهٔ صورت‌وضعیت"] is not None \
                and _d["تاریخ شروع پیمان"] > _d["تاریخ شروع دورهٔ صورت‌وضعیت"]:
            errs.append({
                "level": "خطا", "category": "تاریخ‌ها",
                "item": "ترتیب تاریخ‌ها",
                "message": "تاریخ شروع پیمان پس از تاریخ شروع دورهٔ "
                           "صورت‌وضعیت است (شروع پیمان باید ≤ شروع دوره باشد).",
                "action": "تاریخ شروع پیمان یا تاریخ شروع دوره را اصلاح کنید.",
                "ref": "ایراد ۱۲ — شروع پیمان ≤ شروع دوره ≤ پایان دوره"})
        if _d["تاریخ شروع دورهٔ صورت‌وضعیت"] is not None \
                and _d["تاریخ پایان دورهٔ صورت‌وضعیت"] is not None \
                and _d["تاریخ شروع دورهٔ صورت‌وضعیت"] > _d["تاریخ پایان دورهٔ صورت‌وضعیت"]:
            errs.append({
                "level": "خطا", "category": "تاریخ‌ها",
                "item": "ترتیب تاریخ‌ها",
                "message": "تاریخ شروع دورهٔ صورت‌وضعیت پس از تاریخ پایان "
                           "دوره است (شروع دوره باید ≤ پایان دوره باشد).",
                "action": "تاریخ شروع یا پایان دورهٔ صورت‌وضعیت را اصلاح کنید.",
                "ref": "ایراد ۱۲ — شروع پیمان ≤ شروع دوره ≤ پایان دوره"})
        if _d["تاریخ شروع پیمان"] is not None \
                and _d["تاریخ پایان دورهٔ صورت‌وضعیت"] is not None \
                and _d["تاریخ شروع پیمان"] > _d["تاریخ پایان دورهٔ صورت‌وضعیت"]:
            errs.append({
                "level": "خطا", "category": "تاریخ‌ها",
                "item": "ترتیب تاریخ‌ها",
                "message": "تاریخ شروع پیمان پس از تاریخ پایان دورهٔ "
                           "صورت‌وضعیت است.",
                "action": "تاریخ شروع پیمان یا تاریخ پایان دوره را اصلاح کنید.",
                "ref": "ایراد ۱۲ — شروع پیمان ≤ شروع دوره ≤ پایان دوره"})
        return errs

    # ───────── کمکّی‌های تاریخ شمسی و تقسیم کارکرد بین سه‌ماهه‌ها ─────────

    @staticmethod
    def _parse_jalali(text):
        """تجزیهٔ تاریخ شمسی → (سال، ماه، روز) یا None."""
        if text is None:
            return None
        m = re.match(r"^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$",
                     convert_persian_digits(str(text)).strip())
        if not m:
            return None
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1300 <= y <= 1500 and 1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return y, mo, d

    @staticmethod
    def _jalali_leap(y):
        """سال کبیسهٔ شمسی (قاعدهٔ استاندارد ۲۸۲۰-ساله)."""
        return ((y - 474) % 2820) * 682 % 2816 < 682

    @classmethod
    def _abs_day(cls, y, mo, d):
        """شمارهٔ روز از یک مبدأ ثابت — فقط برای مقایسهٔ بازه‌ها."""
        dim = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30,
               30 if cls._jalali_leap(y) else 29]
        doy = sum(dim[:mo - 1]) + d
        return (y * 365
                + sum(1 for yy in range(1300, y) if cls._jalali_leap(yy)) + doy)

    @classmethod
    def _date_quarter(cls, date_text):
        """کلید سه‌ماههٔ یک تاریخ شمسی (مثل «۱۴۰۴Q2») یا None."""
        p = cls._parse_jalali(date_text)
        if not p:
            return None
        y, mo, _ = p
        return "%dQ%d" % (y, (mo - 1) // 3 + 1)

    @classmethod
    def _work_split(cls, start_text, end_text, delay_text=None):
        """تقسیم دورهٔ انجام کار بین سه‌ماهه‌ها بر اساس روزها.

        اگر delay_text داده شود، کارکردِ قبل از آن تاریخ (دورهٔ تأخیر)
        مستثنی می‌شود. خروجی: [(کلید سه‌ماهه, کسر)] یا [].
        """
        a = cls._parse_jalali(start_text)
        b = cls._parse_jalali(end_text)
        if not a or not b:
            return []
        d0, d1 = cls._abs_day(*a), cls._abs_day(*b)
        if delay_text:
            dd = cls._parse_jalali(delay_text)
            if dd:
                d0 = max(d0, cls._abs_day(*dd))
        if d1 < d0:
            return []
        total = float(d1 - d0 + 1)
        out = []
        for cy in range(a[0], b[0] + 1):
            year_days = 366 if cls._jalali_leap(cy) else 365
            y0 = cls._abs_day(cy, 1, 1)
            # مرزهای سه‌ماهه‌ها در روزهای سال شمسی:
            # Q1 = ۱–۹۳ ، Q2 = ۹۴–۱۸۶ ، Q3 = ۱۸۷–۲۷۶ ، Q4 = ۲۷۷–۳۶۵/۳۶۶
            for qs, qe, ql in ((1, 93, 1), (94, 186, 2), (187, 276, 3),
                               (277, year_days, 4)):
                qs_a, qe_a = y0 + qs - 1, y0 + qe - 1
                ov = min(qe_a, d1) - max(qs_a, d0) + 1
                if ov > 0:
                    out.append(("%dQ%d" % (cy, ql), ov / total))
        return out

    @classmethod
    def _add_months_jalali(cls, date_text, months):
        """فاز E-6 — تاریخ شمسی + N ماه (با تطبیقِ طولِ ماه).

        خروجی: رشتهٔ تاریخ با ارقام لاتین (مصرفِ داخلی) یا None.
        منبع: بخشنامهٔ ۲۰۸۰، بند ۲-۵ (محاسبهٔ پایان مدت پیمان).
        """
        p = cls._parse_jalali(date_text)
        if not p or not months:
            return None
        y, mo, d = p
        total = y * 12 + (mo - 1) + int(months)
        ny, nm = total // 12, total % 12 + 1
        dim = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30,
               30 if cls._jalali_leap(ny) else 29]
        return "%d/%02d/%02d" % (ny, nm, min(d, dim[nm - 1]))

    @classmethod
    def _delay_classification(cls, contract_start, duration_months,
                              extensions, split, w):
        """فاز E-6 Part C گام ۳ — طبقه‌بندی تأخیرها (بندهای ۲-۵-۱..۲-۵-۳).

        مدت پیمان = مدت اولیه + تمدیدها. کارکردِ پس از مدت بر اساس نوع
        تأخیر شاخص‌گذاری می‌شود:
          مجاز       (۲-۵-۱): شاخص همان دورهٔ انجام کار (بدون بازنویسی).
          غیرمجاز    (۲-۵-۲): میانگین شاخص‌های سه‌ماهه‌های داخل مدت پیمان.
          تعیین‌نشده (۲-۵-۳): علی‌الحساب با شاخص دورهٔ منتهی به تاریخ
                               خاتمهٔ مدت (یا تمدیدِ پوشش‌دهنده).

        تفسیر granularity: هر سه‌ماهه اتمیک است — سه‌ماهه‌ای که روز شروعش
        کوچک‌تر از تاریخ خاتمهٔ مدت است، درونِ مدت محسوب می‌شود (یک
        سه‌ماهه‌ای که روی مرزِ خاتمه قرار دارد درون مدت است).

        خروجی: {contract_end, term_end, term_quarters, override}
          override[q] = {"rule": "غیرمجاز"/"تعیین‌نشده", "basis_q": ...}
        """
        res = {"contract_end": None, "term_end": None,
               "term_quarters": [], "override": {}}
        p0 = cls._parse_jalali(contract_start)
        if not p0 or not duration_months:
            return res
        c_end = cls._add_months_jalali(contract_start, duration_months)
        res["contract_end"] = c_end
        c_end_day = cls._abs_day(*cls._parse_jalali(c_end))
        t_end_day, t_end_text = c_end_day, c_end
        ranges = []  # (روز شروع، روز پایان، نوع، متنِ تاریخِ پایان)
        for ext in extensions or []:
            if not isinstance(ext, dict):
                continue
            e_date = (ext.get("date") or "").strip()
            e_months = ext.get("months") or 0
            p = cls._parse_jalali(e_date)
            if not p or not e_months:
                if e_date or e_months:
                    w.append({
                        "level": "خطا", "category": "تأخیر پیمان",
                        "item": "contract_extensions",
                        "message": "یک تمدید با تاریخ یا مدتِ نامعتبر "
                                   "نادیده گرفته شد — نیازمند اصلاح.",
                        "action": "تاریخ شمسیِ معتبر و مدتِ غیرصفر وارد کنید.",
                        "ref": "بخشنامهٔ ۲۰۸۰، بند ۲-۵-۳",
                    })
                continue
            e_end = cls._add_months_jalali(e_date, e_months)
            e_end_day = cls._abs_day(*cls._parse_jalali(e_end))
            ranges.append((cls._abs_day(*p), e_end_day,
                           ext.get("kind") or "تعیین‌نشده", e_end))
            if e_end_day > t_end_day:
                t_end_day, t_end_text = e_end_day, e_end
        res["term_end"] = t_end_text
        # سه‌ماهه‌های داخل مدت — مبنای میانگینِ ۲-۵-۲
        res["term_quarters"] = [q for q, _f in cls._work_split(
            contract_start, t_end_text)]
        # طبقه‌بندی سه‌ماهه‌های پس از مدت
        _warned_na = False
        for q, _f in split:
            _y = int(q[:4])
            _qi = int(q[-1])
            _qs_day = cls._abs_day(_y, (_qi - 1) * 3 + 1, 1)
            if _qs_day < c_end_day:
                continue  # درونِ مدت
            _kind, _basis = None, None
            for _s, _e, _k, _et in ranges:
                if _s <= _qs_day <= _e:
                    _kind = _k
                    if _k == "تعیین‌نشده":
                        _basis = cls._date_quarter(_et)
                    break
            if _kind is None:
                # پس از مدت، ولی تمدیدی آن را پوشش نمی‌دهد ⇒ علی‌الحساب
                _kind = "تعیین‌نشده"
                _basis = cls._date_quarter(t_end_text)
                w.append({
                    "level": "هشدار", "category": "تأخیر پیمان",
                    "item": "delay_uncovered",
                    "message": "کارکردِ دورهٔ «%s» پس از پایان مدت پیمان است "
                               "ولی تمدیدی آن را پوشش نمی‌دهد؛ تعدیلِ آن "
                               "علی‌الحساب با شاخص دورهٔ منتهی به تاریخ "
                               "خاتمه محاسبه شد." % q,
                    "action": "مدت و نوع تأخیرِ این دوره را در لیست تمدیدها "
                              "ثبت کنید (پس از تعیینِ دستگاه باید دوباره "
                              "محاسبه شود).",
                    "ref": "بخشنامهٔ ۲۰۸۰، بند ۲-۵-۳",
                })
            elif _kind == "تعیین‌نشده" and not _warned_na:
                _warned_na = True
                w.append({
                    "level": "اطلاع", "category": "تأخیر پیمان",
                    "item": "delay_undefined",
                    "message": "نوع تأخیرِ برخی تمدیدها «تعیین‌نشده» است؛ "
                               "تعدیل کارکردهای پس از مدت، علی‌الحساب با شاخص "
                               "دورهٔ منتهی به تاریخ خاتمهٔ تمدید محاسبه "
                               "می‌شود (۲-۵-۳).",
                    "action": "پس از تعیینِ نوع تأخیر توسط دستگاه، مقدار را "
                              "اصلاح و دوباره محاسبه کنید.",
                    "ref": "بخشنامهٔ ۲۰۸۰، بند ۲-۵-۳",
                })
            if _kind == "مجاز":
                continue  # ۲-۵-۱: شاخص همان دورهٔ انجام کار
            res["override"][q] = {"rule": _kind, "basis_q": _basis}
        return res

    def _quarter_index(self, chapter, quarter, provisional_coef):
        """شاخص یک فصل در یک سه‌ماهه؛ سه‌ماهه‌های ۱۴۰۵ به بعد بدون شاخص قطعی
        با «ضریب موقت × قطعی ۱۴۰۴Q4» (بندهای ۲ و ۳ بخشنامهٔ ۱۴۴۳۷۳).

        فاز E-9 §۳.۶: اگر شاخصِ قطعیِ سه‌ماهه اعلام شده باشد (definitive_1405)
        خودبه‌خود جایگزینِ ضریبِ موقت می‌شود.

        خروجی: (مقدار, وضعیت). وضعیت: «قطعی» / «موقت» / «ناموجود».
        """
        v, _pg = self._chapter_index_q(chapter, quarter)
        if v is not None:
            return v, "قطعی"
        if self._quarter_is_provisional(quarter):
            if self._quarter_has_definitive(quarter):
                dv, _dpg = self._definitive_chapter_index(chapter, quarter)
                if dv is not None:
                    return dv, "قطعی"
            if provisional_coef:
                v, _pg = self._chapter_index(chapter, "q4")
                if v is not None:
                    return v * float(provisional_coef), "موقت"
        return None, "ناموجود"

    def _quarter_discipline(self, quarter, provisional_coef, discipline="ابنیه"):
        """شاخص رشته در یک سه‌ماهه (تجهیز، ردیف‌های بدون شاخص فصل — بند ۴،
        و مسیر رشته‌ایِ بند ۲-۱).

        فاز E-9 §۳.۶: جانشانیِ خودکارِ موقت→قطعی (مانند _quarter_index).
        """
        pk = self._QUARTER_PERIOD.get(quarter or "")
        if pk:
            v, _pg = self._index_value(pk, discipline)
            if v is not None:
                return v, "قطعی"
            return None, "ناموجود"
        if self._quarter_is_provisional(quarter):
            if self._quarter_has_definitive(quarter):
                dv, _dpg = self._definitive_discipline_index(quarter, discipline)
                if dv is not None:
                    return dv, "قطعی"
            if provisional_coef:
                v, _pg = self._index_value("q4", discipline)
                if v is not None:
                    return v * float(provisional_coef), "موقت"
        return None, "ناموجود"

    def _provisional_coef_1405q1(self, discipline="ابنیه", chapter=None):
        """ضریب موقت سه‌ماههٔ اول ۱۴۰۵ — محاسبهٔ خودکار از CPI و m.

        فرمول (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳، پیوست ص۱):
            coef = 1 + m × (CPI[اردیبهشت ۱۴۰۵] / mean(CPI[دی، بهمن، اسفند ۱۴۰۴]) − 1)

        CPI از config/cpi_monthly.json (مرکز آمار ایران — کل خانوارهای
        کشور، ۱۴۰۰=۱۰۰) و m از config/provisional_m.json خوانده می‌شود.
        اگر شاخص ماهانهٔ موردنیاز موجود نباشد، None برمی‌گرداند تا موتور
        متوقف شود (قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود).

        خروجی: (coef, status, trace)
            coef    : float یا None
            status  : «محاسبه‌شده» / «ناموجود» / «استثنا»
            trace   : dict با اعداد ورودی (قاعدهٔ طلایی ۲ — ردیابی کامل)
        """
        cfg = PROVISIONAL_M
        meta = cfg.get("meta") or {}
        m_table = cfg.get("m_by_discipline") or {}
        # فاز E-10 §۴ — هر دو املا پذیرفته می‌شود: نامِ رسمیِ PDF
        # (کلیدِ m_aliases = canonical) یا کلیدِ config (alias).
        aliases = cfg.get("m_aliases") or {}
        key = discipline if discipline in m_table else aliases.get(discipline, discipline)
        # استثنا (مثلاً «به جز فصل ۱۵» برای راه و راهداری)
        if chapter is not None:
            for exc in cfg.get("exceptions") or []:
                if (str(chapter) == str(exc.get("chapter"))
                        and key in (exc.get("disciplines") or [])
                        and exc.get("apply") is False):
                    return None, "استثنا", {"reason": exc.get("note", "")}
        m = m_table.get(key)
        if m is None:
            return None, "ناموجود", {
                "reason": "ضریب m برای رشتهٔ %s در provisional_m.json نیست"
                          % discipline}
        cpi = CPI_MONTHLY.get("months") or {}
        num = meta.get("numerator_month") or {}
        den = meta.get("denominator_months") or []
        try:
            n_v = float(cpi[str(num["year"])][str(num["month"])])
            d_vs = [float(cpi[str(d["year"])][str(d["month"])]) for d in den]
        except (KeyError, TypeError, ValueError):
            return None, "ناموجود", {
                "reason": "شاخص ماهانهٔ موردنیاز در config/cpi_monthly.json نیست"}
        mean_d = sum(d_vs) / float(len(d_vs))
        coef = 1.0 + float(m) * (n_v / mean_d - 1.0)
        trace = {
            "discipline": discipline, "discipline_key": key, "m": float(m),
            "numerator_label": num.get("label", ""), "numerator": n_v,
            "denominator_labels": [d.get("label", "") for d in den],
            "denominator_values": d_vs,
            "denominator_mean": mean_d, "coef": coef,
            "source": "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱ + مرکز آمار ایران",
        }
        return coef, "محاسبه‌شده", trace

    # ───────── موتورها ─────────

    def _adjustment(self, ctx, warns):
        """اجرای موتورهای فاز B (هر دو می‌توانند همزمان فعال باشند).

        خروجی: {"tadil": ...|None, "baravord": ...|None} — هرگز روی
        زنجیرهٔ مالی اصلی اثر ندارد.
        """
        out = {"tadil": None, "baravord": None}
        if self.s.get("tadil_enabled"):
            out["tadil"] = self._tadil_engine(ctx, warns)
        if self.s.get("baravord_enabled"):
            out["baravord"] = self._baravord_engine(ctx, warns)

        # ── فاز E — بند ۴: شاخص قطعی ۱۴۰۵ هنوز اعلام نشده ──
        _d1405 = (INDEX_BULLETINS or {}).get("definitive_1405") or {}
        _d1405_has = bool(_d1405.get("chapters_abnieh")
                          or _d1405.get("disciplines"))

        def _any_provisional(engine_out):
            if not engine_out:
                return False
            for _ch in engine_out.get("chapters") or []:
                if _ch.get("status") == "موقت":
                    return True
                for _qr in _ch.get("quarters") or []:
                    if isinstance(_qr, (list, tuple)) and len(_qr) == 3 \
                            and _qr[2] == "موقت":
                        return True
            return False

        if not _d1405_has and (_any_provisional(out["tadil"])
                                or _any_provisional(out["baravord"])):
            warns.append({
                "level": "اطلاع", "category": "شاخص‌های ۱۴۰۵",
                "item": "definitive_1405",
                "message": "کارکرد در سه‌ماهه‌های ۱۴۰۵ (یا بعدتر) با شاخص "
                           "موقت محاسبه شده است (بند ۳ بخشنامهٔ ۱۴۴۳۷۳). "
                           "شاخص‌های قطعی این دوره‌ها هنوز اعلام نشده‌اند؛ "
                           "مبلغ این بخش علی‌الحساب است.",
                "action": "پس از اعلام بخشنامهٔ قطعی، شاخص‌ها را در بخش "
                          "definitive_1405 فایل config/index_bulletins.json "
                          "وارد کنید.",
                "ref": "فاز E — بند ۴ بخشنامهٔ ۱۴۴۳۷۳",
            })

        # ── فاز E-10 §۰ — دامنهٔ ۷۴۴۳۱۷: فقط بهره‌برداری/نگهداری/خدماتی ──
        _i744 = (INDEX_BULLETINS or {}).get("instructions_744317") or {}
        _i744_cov = {_d.get("name")
                     for _d in (_i744.get("disciplines") or [])}
        if (out["tadil"] or out["baravord"]):
            _pd = self._project_discipline()
            if _pd in _i744_cov:
                warns.append({
                    "level": "اطلاع", "category": "شاخص‌های ۱۴۰۴",
                    "item": "instructions_744317_pending_d",
                    "message": "رشتهٔ «%s» مشمول دستورالعمل ۱۴۰۳/۷۴۴۳۱۷ "
                               "است؛ ولی محاسبهٔ شاخصِ آن نیازمندِ عددِ d "
                               "(درصد رشد حداقل دستمزد روزانهٔ مصوب شورای "
                               "عالی کار) است که هنوز وارد نشده. تا آن زمان "
                               "شاخص‌های پیوست ۳ بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳ ملاک "
                               "محاسبه‌ها هستند." % _pd,
                    "action": "عدد d را در بخش instructions_744317 فایل "
                              "config/index_bulletins.json وارد کنید.",
                    "ref": "فاز E-10 §۰ — بخشنامهٔ ۷۴۴۳۱۷، صفحه ۲، بند ۵",
                })
            else:
                warns.append({
                    "level": "اطلاع", "category": "شاخص‌های ۱۴۰۴",
                    "item": "instructions_744317_na",
                    "message": "دستورالعمل ۱۴۰۳/۷۴۴۳۱۷ شامل رشتهٔ «%s» "
                               "نمی‌شود (بند ۲: صرفاً رشته‌های بهره‌برداری، "
                               "نگهداری و خدماتی مشمول آن‌اند). قاعدهٔ "
                               "ماکزیمم (بند ۵ بخشنامهٔ ۶۶۶۳۱۲) برای این "
                               "پروژه N/A است و شاخص‌های پیوست ۳ بخشنامهٔ "
                               "۱۴۰۵/۱۵۵۲۳۳ ملاک محاسبه‌ها هستند." % _pd,
                    "action": "—",
                    "ref": "فاز E-10 §۰ — بخشنامهٔ ۷۴۴۳۱۷، صفحه ۱، بند ۲",
                })

        return out

    def _adj_base_chain(self, ctx, apply_advance=False, pending=None):
        """زنجیرهٔ محاسبهٔ مبلغ پایهٔ A — نمایش شفاف قدم‌به‌قدم.

        A_basis = «با ضرایب»  ⇒ A = A۰ × بالاسری × منطقه‌ای × پیشنهادی
        (مبلغ کارکرد به قیمت پیمان)؛ «بدون ضرایب» ⇒ A = A۰ (فهرست‌بها).
        خروجی: (A, rows, applied) که applied ضریب اعمال‌شده روی A₀ است
        (مبالغ فصل‌ها باید در این ضریب ضرب شوند تا Σ A_c = A برقرار شود).
        """
        s = self.s
        base_total = float(ctx.get("base_total") or 0.0)
        fi = ctx.get("floors_info") or {}
        eligible = float(fi.get("eligible_total") or 0.0)
        excluded_amt = base_total - eligible
        pf = float(fi.get("value") or 1.0)
        floors_amt = float(ctx.get("floors_amount") or 0.0)
        rows = [
            ("جمع کل ردیف‌های فهرست‌بها", base_total,
             "مجموع مبالغ اندیس‌شدهٔ همهٔ ردیف‌ها"),
            ("ردیف‌های مستثنی از ضریب طبقات", excluded_amt,
             "فصل ۲۸ (حمل‌ونقل) و فصول ≥۳۰ — ضریب طبقات اعمال نمی‌شود"),
            ("ردیف‌های مشمول ضریب طبقات", eligible,
             "ضریب P = %s — وضعیت: %s" % (fa_float(pf, 4), fi.get("status") or "—")),
            ("مبلغ کارکرد پایه (A۰ = مشمول × P + مستثنی)", floors_amt,
             "پایهٔ تعدیل؛ شامل سربار و ضریب منطقه‌ای نیست"),
        ]
        # ── ضرایب قیمت پیمان: بالاسری × منطقه‌ای × ضریب پیشنهادی پیمانکار ──
        oh = float(ctx.get("overhead_coef") or 1.0)
        reg = float(ctx.get("regional_coef") or 1.0)
        prop = float(s.get("proposal_coef") or 1.0)
        price_mult = oh * reg * prop
        basis = s.get("A_basis") or "با ضرایب"
        with_coefs = (basis == "با ضرایب")
        A = floors_amt
        applied = 1.0
        if with_coefs and price_mult != 1.0:
            applied = applied * price_mult
            _a = A * oh
            rows.append(("× ضریب بالاسری", _a,
                         "ضریب %s — قیمت پیمان" % fa_float(oh, 4)))
            _a = _a * reg
            rows.append(("× ضریب منطقه‌ای", _a,
                         "ضریب %s" % fa_float(reg, 4)))
            A = _a * prop
            rows.append(("× ضریب پیشنهادی پیمانکار", A,
                         "دستی — ضریب %s — نیازمند تأیید" % fa_float(prop, 4)))
        if pending is not None and with_coefs:
            pending.append(self._adj_pending(
                "ضریب پیشنهادی پیمانکار", prop,
                "دستی — پروندهٔ قرارداد / مدیریت پیمان", "—",
                "دستی — نیازمند تأیید",
                "ضریب پیشنهادی پیمانکار را از پروندهٔ قرارداد وارد کنید."))
        if apply_advance and s.get("tadil_advance_mode") == "کسر پیش‌پرداخت":
            adv = float(ctx.get("advance_payment") or 0.0)
            if adv > 0:
                A = A - adv
                rows.append(("− کسر پیش‌پرداخت", A,
                             "مبلغ کارکرد پس از کسر پیش‌پرداخت (تنظیم موتور)"))
        return A, rows, applied

    @staticmethod
    def _adj_manual_get(manual, key):
        """خواندن یک شاخص دستی (دستی مقدم بر جدول بخشنامه)."""
        if not isinstance(manual, dict):
            return None
        v = manual.get(key)
        return float(v) if isinstance(v, (int, float)) and v else None

    @classmethod
    def _chain_method(cls, s, warns):
        """فاز E-6 Part C گام ۶ — مسیر شاخص: «گروهی» (۲-۲) یا «رشته‌ای» (۲-۱).

        «خودکار» از رویِ مبلغ اولیهٔ پیمان در برابرِ آستانهٔ config حل می‌شود.
        خروجی: (method, source) که method ∈ {«گروهی», «رشته‌ای»} است. هشدارها
        (آستانهٔ ۱۳۷۰ + مبلغِ وارد‌نشده) با dedup روی item ساطع می‌شوند تا
        با اجرای هر دو موتور تکرار نشوند (هر دو warns را به‌اشتراک می‌گذارند).
        """
        _im = (s.get("index_method") or "گروهی").strip()
        if _im not in ("گروهی", "رشته‌ای", "خودکار"):
            _im = "گروهی"
        if _im != "خودکار":
            return _im, "دستی"
        # هشدارِ آستانهٔ ۱۳۷۰ فقط در حالتِ خودکار (دستگاه خودش حل می‌کند)
        if not any(x.get("item") == "index_method_threshold_1370"
                   for x in warns):
            _msg = ("آستانهٔ %s ریال برای مسیر رشته‌ای/گروهی از ارقامِ سال "
                    "۱۳۷۰ بندهای ۲-۱/۲-۲ است؛ اگر در بخشنامه‌های بعدی تصحیح "
                    "شده، مقدارِ config/index_bulletins.json → bulletin_2080."
                    "threshold_rail را به‌روز کنید."
                    % fa_float(CHAIN_THRESHOLD_RIALS, 0))
            if CHAIN_THRESHOLD_MISSING:
                _msg += (" نکته: کلیدِ bulletin_2080.threshold_rail در config "
                         "نیست — مقدارِ ۳۰۰٬۰۰۰٬۰۰۰ فرض شد.")
            warns.append({"level": "اطلاع", "category": "موتور تعدیل",
                          "item": "index_method_threshold_1370",
                          "message": _msg,
                          "action": "آستانه و مبلغ اولیهٔ پیمان را بررسی کنید.",
                          "ref": "بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲"})
        _raw = s.get("contract_initial_amount")
        if isinstance(_raw, bool) or not isinstance(_raw, (int, float)):
            _raw = None
        if _raw is not None and _raw >= 0:
            if _raw < CHAIN_THRESHOLD_RIALS:
                return ("رشته‌ای",
                        "خودکار: مبلغ اولیه < آستانه (بند ۲-۱)")
            return "گروهی", "خودکار: مبلغ اولیه ≥ آستانه (بند ۲-۲)"
        if not any(x.get("item") == "index_method_no_amount" for x in warns):
            warns.append({"level": "هشدار", "category": "موتور تعدیل",
                          "item": "index_method_no_amount",
                          "message": "مسیر شاخص «خودکار» است ولی مبلغ اولیهٔ "
                                     "پیمان وارد نشده؛ مسیر گروهی (۲-۲) فرض "
                                     "می‌شود.",
                          "action": "مبلغ اولیهٔ پیمان را در بخش "
                                    "«ورودی‌های قرارداد» وارد کنید.",
                          "ref": "بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲"})
        return ("گروهی",
                "خودکار: مبلغ اولیه وارد نشده — مسیر گروهی (۲-۲)")

    def _discipline_amount_row(self, amount, d_io, split, delay, prov,
                              disc, d_it_m, do_round, neg_tz, k, missing,
                              label, status, src, span26=None, ov26=None):
        """ردیفِ مبلغی که با شاخصِ رشته تعدیل می‌شود (فاز E-6 Part C).

        تجهیز/برچیدن (بند ۴) و کارهای جدید (بندهای ۳-۱..۳-۵) هر دو از
        این منطق استفاده می‌کنند: نسبتِ It/Io برای هر سه‌ماهه با
        شاخه‌های تأخیر (۲-۵-۲/۲-۵-۳/۲-۶) و گردکردنِ بند ۸-۲.
        خروجی: {"row": {...}, "dp": ..., "dp_def": ..., "dp_095": ...}.
        """
        dp = dp_def = dp_095 = 0.0
        it_w = 0.0
        coef_rows = []
        dn = []
        for q, f in split:
            _ov = delay["override"].get(q)
            if _ov and _ov["rule"] == "غیرمجاز":
                # ۲-۵-۲: میانگین شاخص رشتهٔ داخل مدت پیمان
                _vals, _sts = [], []
                for _tq in delay["term_quarters"]:
                    if d_it_m is not None:
                        _tv, _ts = float(d_it_m), "دستی"
                    else:
                        _tv, _ts = self._quarter_discipline(_tq, prov, disc)
                    if _tv is None:
                        continue
                    _vals.append(float(_tv))
                    _sts.append(_ts)
                if not _vals:
                    missing.append((label, "It", q + " (میانگین مدت)"))
                    continue
                d_it_v = sum(_vals) / float(len(_vals))
                _d_base_st = ("موقت" if "موقت" in _sts
                              else ("دستی" if "دستی" in _sts else "قطعی"))
                d_st = _d_base_st + " (میانگین مدت — ۲-۵-۲)"
                dn.append({"q": q, "rule": "غیرمجاز",
                           "note": "میانگین شاخص‌های داخل مدت (۲-۵-۲)"})
            elif q in (ov26 or {}):
                # بند ۲-۶: میانگین شاخصِ رشتهٔ شروع تا آخرین موقت
                _vals, _sts = [], []
                for _tq in (span26 or []):
                    if d_it_m is not None:
                        _tv, _ts = float(d_it_m), "دستی"
                    else:
                        _tv, _ts = self._quarter_discipline(_tq, prov, disc)
                    if _tv is None:
                        continue
                    _vals.append(float(_tv))
                    _sts.append(_ts)
                if not _vals:
                    missing.append((label, "It", q + " (میانگین ۲-۶)"))
                    continue
                d_it_v = sum(_vals) / float(len(_vals))
                _d_base_st = ("موقت" if "موقت" in _sts
                              else ("دستی" if "دستی" in _sts else "قطعی"))
                d_st = _d_base_st + " (میانگینِ تا آخرین موقت — ۲-۶)"
                dn.append({"q": q, "rule": "۲-۶",
                           "note": "میانگین شاخص‌های شروع"
                                   " تا آخرین موقت (۲-۶)"})
            elif _ov:
                # ۲-۵-۳: علی‌الحساب با شاخص دورهٔ خاتمه
                _bq = _ov["basis_q"]
                d_it_v, d_st = (d_it_m, "دستی") if d_it_m \
                    else self._quarter_discipline(_bq, prov, disc)
                if d_it_v is None:
                    missing.append((label, "It", _bq))
                    continue
                _d_base_st = d_st
                d_st = d_st + " (علی‌الحساب — ۲-۵-۳)"
                dn.append({"q": q, "rule": "تعیین‌نشده",
                           "note": "علی‌الحساب با شاخص دورهٔ خاتمه (۲-۵-۳)"})
            else:
                d_it_v, d_st = (d_it_m, "دستی") if d_it_m \
                    else self._quarter_discipline(q, prov, disc)
                if d_it_v is None:
                    missing.append((label, "It", q))
                    continue
                _d_base_st = d_st
            ratio = float(d_it_v) / float(d_io)
            # بند ۸-۲: گردکردن ضریب
            _raw = float(k) * (ratio - 1.0)
            _used = round_coef_2080(_raw, neg_tz) if do_round else _raw
            dp += _used * amount * f
            if _d_base_st == "قطعی" and not (
                    _ov is not None and _ov["rule"] == "تعیین‌نشده"):
                dp_def += _used * amount * f
            # مبنای تبصرهٔ ۲
            _raw9 = TADIL_K_2080 * (ratio - 1.0)
            _used9 = round_coef_2080(_raw9, neg_tz) if do_round else _raw9
            dp_095 += _used9 * amount * f
            coef_rows.append((q, _raw, _used))
            it_w += float(d_it_v) * f
        row = {
            "amount": amount, "io": float(d_io), "it": it_w,
            "ratio": it_w / float(d_io) if d_io else None,
            "value": dp, "delta": dp, "delta_definitive": dp_def,
            "delta_k095": dp_095, "coef_rows": coef_rows,
            "delay_notes": dn, "status": status, "src": src,
        }
        return {"row": row, "dp": dp, "dp_def": dp_def,
                "dp_095": dp_095}

    def _project_discipline(self):
        """رشتهٔ پروژه — پیش‌فرض «ابنیه».

        فاز E-10 §۰: این مقدار برای تشخیصِ دامنهٔ دستورالعمل ۷۴۴۳۱۷
        (فقط رشته‌های بهره‌برداری/نگهداری/خدماتی) به‌کار می‌رود.
        """
        _d = ((self.s.get("regional_selection") or {}).get("discipline")
              or "ابنیه")
        return (_d or "ابنیه").strip() or "ابنیه"

    def _tadil_engine(self, ctx, warns):
        """موتور ۱ — تعدیل پیمان، فصل به فصل با شاخص هر فصل.

        ΔP = k × Σ_c (It_c/Io_c − 1) × A_c
        تجهیز/برچیدن و ردیف‌های بدون شاخص فصل: شاخص رشته‌ای (بند ۴).
        تقسیم کارکرد بین سه‌ماهه‌ها از تاریخ‌های دورهٔ قرارداد.
        """
        s = self.s
        L = "تعدیل پیمان"
        pending = []
        # ── فاز E-6 Part C گام ۶ (حرف b): مسیر شاخص (بندهای ۲-۱/۲-۲) ──
        _chain, _chain_src = self._chain_method(s, warns)
        _disc = self._project_discipline()
        # ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) ──
        new_work_row = None
        _new_base_amt = 0.0
        _new_method = (s.get("new_item_method") or "فهرست پیمان").strip()
        if _new_method not in ("فهرست پیمان", "فهرست پایه", "قیمت روز",
                               "ترکیب"):
            _new_method = "فهرست پیمان"
        _new_amt = float(s.get("new_item_amount") or 0.0)
        _new_amt_att = float(s.get("new_item_amount_attached") or 0.0)
        if _new_method == "فهرست پیمان":
            _new_amt_a, _new_amt_b = _new_amt, 0.0
        elif _new_method == "ترکیب":
            _new_amt_a, _new_amt_b = _new_amt_att, _new_amt
        else:
            _new_amt_a, _new_amt_b = 0.0, _new_amt
        dp_new = 0.0
        dp_new_def = 0.0
        dp_new_095 = 0.0

        # ── ضریب قانونی k (فاز E-6 — بخشنامهٔ ۲۰۸۰، بند ۱-۸ و تبصرهٔ ۲) ──
        # k دیگر ورودی کاربر نیست؛ از وضعیت اتمام کار مشتق می‌شود.
        # منبع واحد: ثابت TADIL_K_2080 در بالای این پرونده.
        k, k_status, k_source = _tadil_k(s)
        cwt = s.get("completed_within_term") is True
        do_round = bool(s.get("coef_rounding_2080"))
        # فاز E-10 §۳ — D-04 گزینهٔ ب: گردکردنِ ضرایبِ منفی به‌سمتِ صفر
        neg_tz = s.get("negative_coef_rounding") == "toward_zero"
        pending.append(self._adj_pending(
            "ضریب قانونی تعدیل (k)", float(k),
            k_source, "بند ۱-۸" + (" + تبصرهٔ ۲" if cwt else ""),
            k_status,
            ("اگر کار در مدت پیمان (با احتساب تمدیدهای ناشی از تغییر مقادیر) "
             "تمام و تحویل موقت شده، completed_within_term را روی «بله» "
             "تنظیم کنید تا k = ۱ شود (تبصرهٔ ۲ بند ۱-۸). مابه‌التفاوت "
             "طبق بند ۸-۴ همزمان با صورت‌وضعیت قطعی پرداخت می‌شود.")))
        # فاز E-9 §۴ — D-01 یک «دادهٔ ورودیِ الزامی» است، نه یک تصمیمِ باز:
        # تا وقتی کاربر وضعیتِ اتمام را مشخص نکرده، خروجی علی‌الحساب است و
        # یک هشدارِ مرکزی او را به فیلدِ مربوطه هدایت می‌کند.
        if s.get("completed_within_term") is None:
            warns.append({
                "level": "اطلاع", "category": "موتور تعدیل",
                "item": "completed_within_term_required",
                "message": ("وضعیتِ اتمامِ کار در مدتِ پیمان نامشخص است؛ "
                            "موتور با k = ۰٫۹۵ علی‌الحساب محاسبه می‌کند "
                            "(بند ۱-۸ بخشنامهٔ ۲۰۸۰)."),
                "action": ("این یک ورودیِ الزامی است: در تنظیماتِ پروژه، "
                           "«وضعیت اتمام کار در مدت پیمان» را مشخص کنید. "
                           "اگر کار در مدتِ پیمان (با احتسابِ تمدیدهای ناشی "
                           "از تغییر مقادیر) تمام و تحویلِ موقت شده، «بله» "
                           "را انتخاب کنید تا k = ۱ شود (تبصرهٔ ۲) و "
                           "مابه‌التفاوتِ آن طبق بند ۸-۴ جدا نمایش داده شود."),
                "ref": "بخشنامهٔ ۲۰۸۰ — بند ۱-۸، تبصرهٔ ۲ و بند ۸-۴"})

        A, chain, applied = self._adj_base_chain(ctx, apply_advance=True,
                                                 pending=pending)
        setup = float(ctx.get("site_setup") or 0.0)
        # مبالغ فصل‌ها در همان ضریبِ A ضرب می‌شوند تا Σ A_c = A برقرار شود.
        chap = {str(c): float(v) * applied
                for c, v in (ctx.get("chapter_amounts") or {}).items()}
        # فاز E-9 §۳.۳ — بند ۵: یادداشتِ مبلغِ منتقل‌شده به فصل حمل
        _haul_moved = float(ctx.get("haul_moved_amount") or 0.0)
        if _haul_moved > 0.0:
            warns.append({
                "level": "اطلاع", "category": "موتور تعدیل",
                "item": "clause5_haul",
                "message": ("مبلغ %s از ردیف‌های «مترمکعب کیلومترِ» فصل‌های "
                            "غیر از فصل حمل به فصل ۲۸ منتقل شد و با شاخص‌های "
                            "فصل حمل تعدیل می‌شود (بند ۵ بخشنامهٔ ۱۵۵۲۳۳)."
                            % fmt_money(_haul_moved)),
                "action": "تطبیقِ فهرستِ ردیف‌های حمل را با صورت‌وضعیت بررسی کنید.",
                "ref": "بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵"})

        # ── فاز E-6 Part C گام ۷ (حرف c): سقفِ قیمت قابل قبول — نامه-۶ ──
        # «در کارهایی که شاخص مبنایشان طبق ۱-۶-۱ یکم است، سقف قیمت قابل
        #  قبول حداکثر ۱۰٪ بالاتر از مبلغ برآورد بر اساس قیمت‌های پایه است
        #  و انعقاد قرارداد بیش از آن مجاز نیست.»
        # مبلغِ برآورد بر اساس قیمت‌های پایه = ctx["base_total"] (تفسیر ۱۸:
        # base_total، نه grand_total — §۱۸-۳). فقط وقتی روش ۱-۶-۱ یکم
        # (fehrest_period) انتخاب شده باشد بررسی می‌شود.
        if (s.get("base_index_method") or "proposal_period") \
                == "fehrest_period":
            _bt = float(ctx.get("base_total") or 0.0)
            _cia_raw = s.get("contract_initial_amount")
            if isinstance(_cia_raw, bool) or not isinstance(_cia_raw,
                                                            (int, float)):
                _cia = None
            else:
                _cia = float(_cia_raw)
            if _cia is not None and _bt > 0 \
                    and _cia > _bt * (1.0 + CEILING_OVER_ESTIMATE_PCT / 100.0):
                if not any(x.get("item") == "contract_price_ceiling_110"
                           for x in warns):
                    _ceil_msg = (
                        "قیمت قرارداد (%s) بیشتر از سقفِ مجاز (%s = مبلغ "
                        "برآورد بر اساس قیمت‌های پایه %s + %s%%) است؛ انعقادِ "
                        "قرارداد بیش از این سقف طبق نامه-۶ مجاز نیست."
                        % (fa_float(_cia, 0),
                           fa_float(_bt * (1.0 + CEILING_OVER_ESTIMATE_PCT
                                           / 100.0), 0),
                           fa_float(_bt, 0),
                           fa_float(CEILING_OVER_ESTIMATE_PCT, 0)))
                    if CEILING_MISSING:
                        _ceil_msg += (" نکته: کلیدِ bulletin_2080."
                                      "ceiling_over_estimate_pct در config "
                                      "نیست — مقدارِ ۱۰ فرض شد.")
                    warns.append({"level": "هشدار",
                                  "category": "موتور تعدیل",
                                  "item": "contract_price_ceiling_110",
                                  "message": _ceil_msg,
                                  "action": ("قیمت قرارداد را با مبلغ برآورد "
                                             "بر اساس قیمت‌های پایه تطبیق "
                                             "دهید یا دلیل انحراف را مستند "
                                             "کنید."),
                                  "ref": "نامه-۶"})

        # ── دورهٔ مبنا (Io) — بخشنامهٔ ۲۰۸۰، بندهای ۱-۶-۱ و ۱-۶-۲ ──
        io_q = self._PERIOD_QUARTERS.get(s.get("tadil_io_period") or "base")
        prop = s.get("proposal_date") or ""
        dead = s.get("proposal_deadline") or ""
        offer = s.get("final_offer_date") or ""
        bim = s.get("base_index_method") or "proposal_period"
        _err = None
        if bim == "fehrest_period":
            # بند ۱-۶-۱ یکم: شاخص مبنا = دورهٔ سه‌ماهه‌ای که فهرست‌بهای
            # پیمان بر اساس قیمت‌های آن تهیه شده. فقط از config با منبع؛
            # اگر نبود، موتور می‌ایستد و «نیازمند ورود» می‌دهد.
            _fy = str(s.get("fehrest_year") or "")
            _fbp = FEHREST_BASE_PERIODS.get(_fy)
            _io_date = ""
            if isinstance(_fbp, str) and _fbp in self._QUARTER_PERIOD:
                io_q = _fbp
            else:
                _err = ("دورهٔ قیمت پایهٔ فهرست‌بهای سال %s در config/" % _fy
                        + "index_bulletins.json (fehrest_base_periods) وارد"
                          " نشده است. روش اول بند ۱-۶-۱ نیازمند این دوره است.")
        else:
            # بند ۱-۶-۱ دوم و ۱-۶-۲: ملاکِ Io در ترک تشریفاتِ مناقصه،
            # تاریخ تسلیم کتبیِ پیشنهاد نهایی است؛ در غیر آن، مهلت تسلیم
            # پیشنهاد، و اگر نبود خود تاریخ تسلیم پیشنهاد (بخشنامهٔ ۱۴۴۳۷۴).
            _io_date = offer or dead or prop
            # در موتور تعدیل پیمان یکی از این تاریخ‌ها الزامی است (Io =
            # سه‌ماههٔ آن). خالی یا نامعتبر ⇒ خطا و توقف موتور؛ پیش‌فرض
            # گذاشته نمی‌شود (پیش‌فرض اسفند ۱۴۰۳ فقط برای برآورد به‌هنگام است).
            if not _io_date:
                _err = ("تاریخ تسلیم پیشنهاد (یا مهلت تسلیم، یا پیشنهاد نهایی)"
                        + " خالی است.")
            else:
                pq = self._date_quarter(_io_date)
                if pq:
                    io_q = pq
                else:
                    _err = "تاریخ تسلیم پیشنهاد نامعتبر است: «%s»." % _io_date
        # ── بخشنامهٔ ۱۴۴۳۷۴: اگر مهلت تسلیم در تابستان ۱۴۰۵ باشد، Io
        # شاخصِ ماهانهٔ خرداد ۱۴۰۵ است (نه سه‌ماهه‌ای). تا شاخص ماهانه
        # وارد نشده، موتور با خطا متوقف می‌شود (قاعدهٔ طلایی: حدس زده
        # نمی‌شود). ──
        _io_month = self._io_month_for(_io_date)
        if not _err and _io_month and not self._monthly_has_data(_io_month):
            warns.append({"level": "خطا", "category": "موتور تعدیل",
                          "item": "monthly_index_1405",
                          "message": "مهلت تسلیم پیشنهاد در تابستان ۱۴۰۵ "
                                     "است؛ طبق بخشنامهٔ ۱۴۴۳۷۴ Io باید شاخص "
                                     "ماهانهٔ خرداد ۱۴۰۵ (آحادبها) باشد، ولی "
                                     "این شاخص هنوز در config/index_bulletins.json "
                                     "وارد نشده است. موتور تعدیل پیمان متوقف شد.",
                          "action": "شاخص‌های ماهانهٔ خرداد ۱۴۰۵ را در بخش "
                                    "monthly فایل config/index_bulletins.json "
                                    "وارد کنید (هرگز حدس زده نمی‌شود).",
                          "ref": "فاز E — بخشنامهٔ ۱۴۴۳۷۴"})
            return {
                "mode": "تعدیل پیمان",
                "formula": "ΔP = k × Σ_c (It_c/Io_c − 1) × A_c",
                "error": "شاخص ماهانهٔ خرداد ۱۴۰۵ وارد نشده — موتور تعدیل "
                         "پیمان متوقف شد.",
                "coef": float(k), "io_q": io_q, "io_month": _io_month,
                "split": [],
                "index_method_resolved": {"method": _chain,
                                          "source": _chain_src},
                "base_amount": 0.0, "work_base": A, "chain": chain,
                "setup_amount": 0.0, "setup_row": None,
                "new_work_row": new_work_row,
                "chapters": [], "delta_p": 0.0, "delta_p_definitive": 0.0,
                "delta_p_provisional": 0.0, "result_amount": 0.0,
                "advance_mode": s.get("tadil_advance_mode")
                or "کل مبلغ کارکرد",
                "delay_mode": s.get("tadil_delay_mode") or "مشمول کل دوره",
                "params": {"allow_negative": bool(s.get("tadil_allow_negative")),
                           "advance_payment": float(ctx.get("advance_payment")
                                                    or 0.0),
                           "proposal_date": prop, "provisional_coef": None},
                "incomplete": True, "missing": [], "draft": True,
                "pending": pending,
                "k_status": k_status,
                "k_provisional": s.get("completed_within_term") is None,
                "work_period_missing": False,
                "source": "فاز E — ۱۴۴۳۷۴ (توقف: شاخص ماهانهٔ خرداد ۱۴۰۵)",
            }
        # ── هشدار: Io بعد از It (بند ۱-۷: شاخص دورهٔ انجام کار باید
        # بعد از دورهٔ مبنا باشد). مقایسهٔ کلیدهای سه‌ماهه (ترتیب الفبایی
        # برای فرمت YYYYQn درست است). ──
        _it_q_key = self._PERIOD_QUARTERS.get(s.get("tadil_it_period") or "q4")
        if not _err and io_q and _it_q_key and io_q > _it_q_key:
            warns.append({"level": "هشدار", "category": "موتور تعدیل",
                          "item": "io_after_it",
                          "message": ("دورهٔ مبنا (Io = %s) بعد از دورهٔ "
                                      "انجام کار (It = %s) است. شاخص مبنا "
                                      "باید دوره‌ای قبل از شروع کار باشد "
                                      "(بند ۱-۷)." % (io_q, _it_q_key)),
                          "action": ("روش شاخص مبنا یا تاریخ تسلیم پیشنهاد را "
                                      "بررسی کنید."),
                          "ref": "فاز E-6 — بند ۱-۷ بخشنامهٔ ۲۰۸۰"})
        if _err:
            warns.append({"level": "خطا", "category": "موتور تعدیل",
                          "item": "proposal_date",
                          "message": _err + " موتور تعدیل پیمان متوقف شد؛ "
                                   "بدون این تاریخ دورهٔ مبنا (Io) مشخص نیست.",
                          "action": "تاریخ تسلیم پیشنهاد (شمسی) را در سایدبار "
                                    "وارد کنید (مثل ۱۴۰۴/۰۲/۱۵).",
                          "ref": "فاز B — پیوست ۳، بند ۱-۲"})
            return {
                "mode": "تعدیل پیمان",
                "formula": "ΔP = k × Σ_c (It_c/Io_c − 1) × A_c",
                "error": _err + " موتور تعدیل پیمان متوقف شد.",
                "coef": float(k), "io_q": None, "io_month": None, "split": [],
                "index_method_resolved": {"method": _chain,
                                          "source": _chain_src},
                "base_amount": 0.0, "work_base": A, "chain": chain,
                "setup_amount": 0.0, "setup_row": None,
                "new_work_row": new_work_row,
                "chapters": [], "delta_p": 0.0, "delta_p_definitive": 0.0,
                "delta_p_provisional": 0.0,
                "result_amount": 0.0,
                "advance_mode": s.get("tadil_advance_mode")
                or "کل مبلغ کارکرد",
                "delay_mode": s.get("tadil_delay_mode") or "مشمول کل دوره",
                "params": {"allow_negative": bool(s.get("tadil_allow_negative")),
                           "advance_payment": float(ctx.get("advance_payment")
                                                    or 0.0),
                           "proposal_date": prop, "provisional_coef": None},
                "incomplete": True, "missing": [], "draft": True,
                "pending": pending,
                "k_status": k_status,
                "k_provisional": s.get("completed_within_term") is None,
                "work_period_missing": False,
                "source": "فاز B — پیوست ۳، بند ۱-۲ (توقف: تاریخ تسلیم الزامی)",
            }

        # ── شاخص موقت ۱۴۰۵Q1: اگر کاربر ضریب دستی وارد کرده باشد همان
        # معیار است؛ در غیر این صورت از CPI + m محاسبه می‌شود (بخشنامهٔ
        # ۱۴۰۵/۱۴۴۳۷۳، پیوست ص۱). هیچ‌گاه عددی حدس زده نمی‌شود. ──
        _prov_man = self._adj_manual_get({"v": s.get("provisional_coef_1405q1")}, "v")
        _prov_auto, _prov_st, _prov_tr = self._provisional_coef_1405q1("ابنیه")
        prov = _prov_man if _prov_man else _prov_auto
        if _prov_man:
            pending.append(self._adj_pending(
                "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵", _prov_man,
                "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ (PDF تصویری — متن استخراج نشد)", "—",
                "دستی — نیازمند تأیید",
                "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴)"))
        elif prov is not None:
            pending.append(self._adj_pending(
                "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵", prov,
                "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱ + مرکز آمار ایران",
                "فرمول: ۱ + m × (CPI[اردیبهشت ۱۴۰۵] ÷ میانگین CPI[دی، "
                "بهمن، اسفند ۱۴۰۴] − ۱)",
                "موقت — محاسبه‌شده از CPI (m=%s)" % fa(_prov_tr.get("m")),
                "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴). "
                "m=%s، میانگین زمستان ۱۴۰۴=%s، اردیبهشت ۱۴۰۵=%s."
                % (fa(_prov_tr.get("m")),
                   fa(round(_prov_tr.get("denominator_mean") or 0.0, 4)),
                   fa(_prov_tr.get("numerator")))))

        # ── تقسیم کارکرد بین سه‌ماهه‌ها ──
        delay_mode = s.get("tadil_delay_mode") or "مشمول کل دوره"
        delay_date = s.get("tadil_delay_date") or ""
        wstart = s.get("work_period_start") or ""
        wend = s.get("work_period_end") or ""
        split = self._work_split(
            wstart, wend,
            delay_date if delay_mode == "مستثنی کردن دورهٔ تأخیر" else None)
        # فاز E-10 §۲ — قفلِ خروجیِ نهاییِ تعدیل: وقتی دورهٔ کارکرد خالی
        # است، موتور تمامِ کارکرد را به آخرین شاخصِ قطعی منتسب می‌کند و ΔP
        # متفاوتی از حالتِ «شاخصِ هر سه‌ماهه» می‌دهد. Excel نهایی نباید ساخته
        # شود — فقط «پیش‌نویس» با واترمارک (قاعدهٔ طلایی: هدایت به فیلد).
        _wp_missing = not split
        if not split:
            _it_fb = (self._PERIOD_QUARTERS.get(s.get("tadil_it_period") or "q4")
                      or "1404Q4")
            split = [(_it_fb, 1.0)]
            # فاز E-9 §۵ — پیش‌فرضِ هدف‌محورِ It: موتورِ تعدیلِ صورت‌وضعیت
            # باید شاخص را از دورهٔ واقعیِ انجامِ کار بخواند. بدونِ آن،
            # تمامِ کارکرد به آخرین شاخصِ قطعی منتسب می‌شود و ΔP متفاوتی
            # می‌دهد (روی پروژهٔ مرجع: ۱۳٬۳۲۰٬۳۶۰٬۹۵۷٫۱۲ به‌جای
            # ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲). هشدار + هدایت به فیلد (قاعدهٔ طلایی).
            warns.append({
                "level": "هشدار", "category": "موتور تعدیل",
                "item": "work_period_missing_for_it",
                "message": ("دورهٔ انجام کار خالی است؛ موتور تمامِ کارکرد را "
                            "به %s (آخرین شاخصِ قطعی) منتسب می‌کند. ΔP با "
                            "حالتِ «شاخصِ هر سه‌ماهه» متفاوت است." % _it_fb),
                "action": ("برای تعدیلِ دقیق، «تاریخ شروع دورهٔ صورت‌وضعیت» "
                           "و «تاریخ پایان دورهٔ صورت‌وضعیت» را در تنظیماتِ "
                           "پروژه وارد کنید تا شاخصِ هر سه‌ماههٔ جداگانه اعمال "
                           "شود."),
                "ref": "فاز E-9 §۵ — بند ۱-۷ بخشنامهٔ ۲۰۸۰"})
        # ── فاز E-6 Part C گام ۳: طبقه‌بندی تأخیرها (بندهای ۲-۵-۱..۲-۵-۳) ──
        # مدت پیمان = مدت اولیه + تمدیدها. کارکردِ پس از مدت بر اساس نوع
        # تأخیر شاخص‌گذاری می‌شود (۲-۵-۱ مجاز / ۲-۵-۲ غیرمجاز / ۲-۵-۳
        # تعیین‌نشده). بدونِ مدتِ پیمان هیچ بازنویسی‌ای صورت نمی‌گیرد
        # (اعداد مرجع تغییر نمی‌کنند).
        _delay = self._delay_classification(
            s.get("contract_date") or "",
            s.get("contract_duration_months"),
            s.get("contract_extensions") or [],
            split, warns)
        # ── فاز E-6 Part C گام ۹ (حرف a): بند ۲-۶ — مابه‌التفاوتِ آخرین
        # صورت‌وضعیتِ موقت و قطعی. کارکردِ پس از آخرین موقتِ درونِ مدت
        # با میانگینِ شاخص‌های سه‌ماهه‌هایِ بینِ شروعِ پیمان و آخرین موقت
        # شاخص‌گذاری می‌شود (متنِ اصلیِ بند). تبصرهٔ ۲: تأخیر غیرمجاز →
        # ۲-۵-۲ که اولویت بالاتر دارد (delayClassification). تبصرهٔ ۱: با
        # فلگِ provisional_diff_method = own_period هر سه‌ماهه شاخصِ خودش
        # را می‌گیرد. بدونِ last_provisional_date هیچ کاری نمی‌کند
        # (اعداد مرجع تغییر نمی‌کنند).
        _span26 = []
        _ov26 = set()
        _lpd = (s.get("last_provisional_date") or "").strip()
        if _lpd and (s.get("provisional_diff_method") or "average") == "average":
            _p_lpd = self._parse_jalali(_lpd)
            _p_c0 = self._parse_jalali(s.get("contract_date") or "")
            if not _p_c0:
                warns.append({"level": "هشدار", "category": "موتور تعدیل",
                              "item": "last_provisional_date",
                              "message": "تاریخ آخرین صورت‌وضعیت موقت وارد "
                                         "شده ولی تاریخ شروع پیمان مشخص "
                                         "نیست؛ میانگینِ بند ۲-۶ قابل "
                                         "محاسبه نیست.",
                              "action": "تاریخ شروع پیمان را در بخش "
                                        "«ورودی‌های قرارداد» وارد کنید.",
                              "ref": "بخشنامهٔ ۲۰۸۰، بند ۲-۶"})
            elif not _p_lpd:
                warns.append({"level": "هشدار", "category": "موتور تعدیل",
                              "item": "last_provisional_date",
                              "message": "تاریخ آخرین صورت‌وضعیت موقت "
                                         "نامعتبر است — میانگینِ بند ۲-۶ "
                                         "نادیده گرفته شد.",
                              "action": "تاریخ را به‌صورتِ شمسیِ معتبر "
                                        "(مثل ۱۴۰۴/۰۶/۳۱) وارد کنید.",
                              "ref": "بخشنامهٔ ۲۰۸۰، بند ۲-۶"})
            else:
                _lpd_day = self._abs_day(*_p_lpd)
                _c0_day = self._abs_day(*_p_c0)
                if _lpd_day < _c0_day:
                    warns.append({"level": "هشدار",
                                  "category": "موتور تعدیل",
                                  "item": "last_provisional_date",
                                  "message": "تاریخ آخرین صورت‌وضعیت موقت "
                                             "قبل از شروع پیمان است — "
                                             "میانگینِ بند ۲-۶ نادیده "
                                             "گرفته شد.",
                                  "action": "تاریخ آخرین موقت را اصلاح کنید.",
                                  "ref": "بخشنامهٔ ۲۰۸۰، بند ۲-۶"})
                else:
                    _span26 = [q for q, _f in self._work_split(
                        s.get("contract_date") or "", _lpd)]
                    # §۱۸-۳ تفسیر ۱۰: «مدت پیمان» = مدت اولیه + تمدیدها؛
                    # کارِ بینِ contract_end و term_end (تمدیدِ مجاز) درونِ
                    # مدت است و میانگینِ ۲-۶ را می‌گیرد.
                    _t_end_day = None
                    if _delay.get("term_end"):
                        _p_te = self._parse_jalali(_delay["term_end"])
                        if _p_te:
                            _t_end_day = self._abs_day(*_p_te)
                    for q, _f in split:
                        _y = int(q[:4])
                        _qi = int(q[-1])
                        _qs_day = self._abs_day(_y, (_qi - 1) * 3 + 1, 1)
                        if _qs_day <= _lpd_day:
                            continue        # متعلق به دورهٔ موقت
                        if _t_end_day is not None and _qs_day >= _t_end_day:
                            continue        # پس از مدت (۲-۵-۳)
                        if _delay["override"].get(q):
                            continue        # تأخیرِ مشخص‌شده (۲-۵-۲/۲-۵-۳)
                        _ov26.add(q)

        man = s.get("chapter_index_manual") or {}
        dman = s.get("discipline_index_manual") or {}
        d_io_m = self._adj_manual_get(dman, "io")
        d_it_m = self._adj_manual_get(dman, "it")
        # ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستیِ رشته ──
        _d_src = _manual_src(dman)
        if (d_io_m or d_it_m) and not _d_src:
            if not any(x.get("item") == "manual_index_source_required"
                       and x.get("_code") == _disc for x in warns):
                warns.append({
                    "level": "خطا", "category": "موتور تعدیل",
                    "item": "manual_index_source_required",
                    "_code": _disc,
                    "message": ("شاخص دستی برای رشتهٔ %s وارد شده ولی "
                                "منبعِ آن (src) مشخص نشده است؛ منبع را "
                                "وارد کنید." % _disc),
                    "action": "فیلدِ src شاخص دستیِ رشته را پر کنید.",
                    "ref": "بخشنامهٔ ۲۰۸۰ — گام ۸"})
        _d_src_label = (" (%s)" % _d_src) if _d_src else ""
        # شاخص رشته برای Io (تجهیز و فصل‌های بدون شاخص)
        if d_io_m:
            d_io, d_io_page = d_io_m, "دستی%s" % _d_src_label
        elif _io_month:
            d_io, d_io_page = self._monthly_discipline(_io_month, _disc)
        else:
            d_io, d_io_page = self._index_value(
                self._QUARTER_PERIOD.get(io_q) or "base", _disc)

        # ── شاخص موقت ۱۴۰۵Q1: ضریب از CPI + m محاسبه می‌شود (بخشنامهٔ
        # ۱۴۴۳۷۳ پیوست ص۱)؛ اگر شاخص ماهانهٔ موردنیاز موجود نباشد، موتور
        # با خطا متوقف می‌شود (قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود).
        # استثنا: اگر شاخص دستی It برای همهٔ فصل‌ها (و تجهیز) وارد شده
        # باشد، ضریب موقت لازم نیست.
        _active = [c for c, v in chap.items() if abs(v) >= 0.01]
        _all_manual_it = bool(_active) and all(
            isinstance(man.get(c), dict)
            and self._adj_manual_get(man.get(c), "it") for c in _active)
        _setup_manual_ok = (setup <= 0.0) or (d_it_m is not None)
        if any(self._quarter_is_provisional(q) for q, _f in split) \
                and not prov and not (_all_manual_it and _setup_manual_ok):
            warns.append({"level": "خطا", "category": "موتور تعدیل",
                          "item": "provisional_coef_1405q1",
                          "message": "دورهٔ کارکرد به سه‌ماههٔ اول ۱۴۰۵ می‌رسد "
                                     "ولی ضریب موقت قابل محاسبه نیست — شاخص "
                                     "ماهانهٔ CPI در config/cpi_monthly.json "
                                     "ناقص است یا m رشته تعریف نشده؛ موتور "
                                     "تعدیل پیمان متوقف شد.",
                          "action": "شاخص‌های ماهانهٔ CPI را در config/cpi_monthly.json "
                                    "تکمیل کنید (یا ضریب دستی را در سایدبار وارد "
                                    "کنید یا شاخص دستی It همهٔ فصل‌ها را پر کنید).",
                          "ref": "فاز E — بخشنامهٔ ۱۴۴۳۷۳ پیوست ص۱ (CPI)"})
            return {
                "mode": "تعدیل پیمان",
                "formula": "ΔP = k × Σ_c (It_c/Io_c − 1) × A_c",
                "error": "ضریب موقت ۱۴۰۵Q1 قابل محاسبه نیست (CPI ناقص) — "
                         "موتور تعدیل پیمان متوقف شد.",
                "coef": float(k), "io_q": io_q, "io_month": _io_month, "split": split,
                "index_method_resolved": {"method": _chain,
                                          "source": _chain_src},
                "base_amount": 0.0, "work_base": A, "chain": chain,
                "setup_amount": 0.0, "setup_row": None,
                "new_work_row": new_work_row,
                "chapters": [], "delta_p": 0.0, "delta_p_definitive": 0.0,
                "delta_p_provisional": 0.0, "result_amount": 0.0,
                "advance_mode": s.get("tadil_advance_mode")
                or "کل مبلغ کارکرد",
                "delay_mode": s.get("tadil_delay_mode") or "مشمول کل دوره",
                "params": {"allow_negative": bool(s.get("tadil_allow_negative")),
                           "advance_payment": float(ctx.get("advance_payment")
                                                    or 0.0),
                           "proposal_date": prop, "provisional_coef": None},
                "incomplete": True, "missing": [], "draft": True,
                "pending": pending,
                "k_status": k_status,
                "k_provisional": s.get("completed_within_term") is None,
                "work_period_missing": _wp_missing,
                "source": "فاز E — ۱۴۴۳۷۳ پیوست ص۱ (توقف: CPI موقت ناموجود)",
            }

        # ── حلقهٔ فصل‌ها ──
        rows = []
        missing = []
        dp_total = 0.0
        dp_def_total = 0.0
        dp_total_095 = 0.0
        for code, amt in sorted(chap.items(), key=lambda kv: kv[1], reverse=True):
            if abs(amt) < 0.01:
                continue
            m = man.get(code) if isinstance(man, dict) else None
            m = m if isinstance(m, dict) else {}
            m_io = self._adj_manual_get(m, "io")
            m_it = self._adj_manual_get(m, "it")
            # ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستی اجباری است ──
            _m_src = _manual_src(m)
            if (m_io or m_it) and not _m_src:
                if not any(x.get("item") == "manual_index_source_required"
                           and x.get("_code") == code for x in warns):
                    warns.append({
                        "level": "خطا", "category": "موتور تعدیل",
                        "item": "manual_index_source_required",
                        "_code": code,
                        "message": ("شاخص دستی برای فصل %s وارد شده ولی "
                                    "منبعِ آن (src) مشخص نشده است؛ منبع را "
                                    "وارد کنید (مثلاً «نامهٔ کارفرما» یا "
                                    "«پیوست ۳، صفحهٔ ۸۲»)." % code),
                        "action": "فیلدِ src شاخص دستیِ این فصل را پر کنید.",
                        "ref": "بخشنامهٔ ۲۰۸۰ — گام ۸"})
            _m_src_label = (" (%s)" % _m_src) if _m_src else ""
            if _chain == "رشته‌ای":
                # بند ۲-۱: مسیر رشته‌ای — شاخصِ رشتهٔ پروژه (نه شاخصِ فصل)
                if _io_month:
                    io_v, io_page = self._monthly_discipline(_io_month, _disc)
                else:
                    io_v, io_page = self._index_value(
                        self._QUARTER_PERIOD.get(io_q) or "base", _disc)
            elif _io_month:
                io_v, io_page = self._monthly_chapter_index(code, _io_month)
            else:
                io_v, io_page = self._chapter_index_q(code, io_q)
            use_disc = (_chain == "رشته‌ای") or (io_v is None and not m_io)
            # ─ـ فاز E-6 Part C گام ۸ (حرف e): هشدارِ اختلافِ شاخص دستی ──
            if m_io and io_v is not None:
                _dev = abs(m_io - io_v) / io_v if io_v else 0.0
                if _dev > MANUAL_INDEX_DEVIATION_PCT:
                    if not any(
                            x.get("item") == "manual_index_deviation_20"
                            and x.get("_code") == code for x in warns):
                        warns.append({
                            "level": "هشدار", "category": "موتور تعدیل",
                            "item": "manual_index_deviation_20",
                            "_code": code,
                            "message": ("شاخص دستیِ Io فصل %s (%s) بیش از "
                                        "%s٪ با شاخصِ config (%s) اختلاف "
                                        "دارد — منبع را تأیید کنید."
                                        % (code, fa_float(m_io, 2),
                                           fa_float(
                                               MANUAL_INDEX_DEVIATION_PCT * 100,
                                               0),
                                           fa_float(io_v, 2))),
                            "action": ("منبعِ شاخص دستی را مستند کنید یا "
                                       "شاخص config را به‌روز کنید."),
                            "ref": "بخشنامهٔ ۲۰۸۰ — گام ۸"})
            if m_io:
                io_v, src = m_io, "دستی%s" % _m_src_label
            elif use_disc:
                if d_io is None:
                    missing.append((code, "Io", io_q))
                    continue
                if _chain == "رشته‌ای":
                    io_v, src = float(d_io), "شاخص رشته (مسیر ۲-۱)"
                else:
                    io_v, src = float(d_io), "شاخص رشته (بدون شاخص فصل — بند ۴)"
                    pending.append(self._adj_pending(
                    "شاخص فصل %s — Io" % code, float(d_io),
                    "پیوست ۳، ردیف ۱ (شاخص رشته)",
                    "صفحهٔ %s" % fa(d_io_page) if d_io_page else "—",
                    "فصل استخراج نشده — جایگزین با شاخص رشته، نیازمند تأیید",
                    "شاخص اختصاصی فصل %s را از جدول پیوست ۳ وارد کنید." % code))
            else:
                src = "پیوست ۳، صفحهٔ %s" % fa(io_page) if io_page else "جدول"
            dp_c = 0.0
            dp_c_def = 0.0
            dp_c_095 = 0.0
            it_w = 0.0
            st_last = "قطعی"
            q_rows = []
            coef_rows = []
            _dn = []
            for q, f in split:
                _ov = _delay["override"].get(q)
                _dn_row = None
                if _ov and _ov["rule"] == "غیرمجاز":
                    # ۲-۵-۲: میانگین شاخص‌های سه‌ماهه‌های داخل مدت پیمان
                    _vals, _sts = [], []
                    for _tq in _delay["term_quarters"]:
                        if m_it:
                            _tv, _ts = float(m_it), "دستی"
                        elif use_disc:
                            _tv, _ts = self._quarter_discipline(
                                _tq, prov, _disc)
                        else:
                            _tv, _ts = self._quarter_index(code, _tq, prov)
                        if _tv is None:
                            continue
                        _vals.append(float(_tv))
                        _sts.append(_ts)
                    if not _vals:
                        missing.append((code, "It", q + " (میانگین مدت)"))
                        continue
                    it_v = sum(_vals) / float(len(_vals))
                    _base_st = ("موقت" if "موقت" in _sts
                                else ("دستی" if "دستی" in _sts else "قطعی"))
                    it_st = _base_st + " (میانگین مدت — ۲-۵-۲)"
                    _dn_row = {"q": q, "rule": "غیرمجاز",
                               "note": "میانگین شاخص‌های داخل مدت (۲-۵-۲)"}
                elif q in _ov26:
                    # بند ۲-۶: میانگین شاخص‌های شروع تا آخرین موقت
                    _vals, _sts = [], []
                    for _tq in _span26:
                        if m_it:
                            _tv, _ts = float(m_it), "دستی"
                        elif use_disc:
                            _tv, _ts = self._quarter_discipline(
                                _tq, prov, _disc)
                        else:
                            _tv, _ts = self._quarter_index(code, _tq, prov)
                        if _tv is None:
                            continue
                        _vals.append(float(_tv))
                        _sts.append(_ts)
                    if not _vals:
                        missing.append((code, "It", q + " (میانگین ۲-۶)"))
                        continue
                    it_v = sum(_vals) / float(len(_vals))
                    _base_st = ("موقت" if "موقت" in _sts
                                else ("دستی" if "دستی" in _sts else "قطعی"))
                    it_st = _base_st + " (میانگینِ تا آخرین موقت — ۲-۶)"
                    _dn_row = {"q": q, "rule": "۲-۶",
                               "note": "میانگین شاخص‌های شروع تا "
                                       "آخرین موقت (۲-۶)"}
                elif _ov:
                    # ۲-۵-۳: علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمه
                    if m_it:
                        it_v, it_st = m_it, "دستی"
                    elif use_disc:
                        it_v, it_st = self._quarter_discipline(
                            _ov["basis_q"], prov, _disc)
                    else:
                        it_v, it_st = self._quarter_index(
                            code, _ov["basis_q"], prov)
                    if it_v is None:
                        missing.append((code, "It", _ov["basis_q"]))
                        continue
                    _base_st = it_st
                    it_st = it_st + " (علی‌الحساب — ۲-۵-۳)"
                    _dn_row = {"q": q, "rule": "تعیین‌نشده",
                               "note": "علی‌الحساب با شاخص دورهٔ خاتمه (۲-۵-۳)"}
                else:
                    # ۲-۵-۱ (مجاز) یا درونِ مدت: شاخص همان سه‌ماهه
                    if m_it:
                        it_v, it_st = m_it, "دستی"
                    elif use_disc:
                        it_v, it_st = self._quarter_discipline(q, prov, _disc)
                    else:
                        it_v, it_st = self._quarter_index(code, q, prov)
                    if it_v is None:
                        missing.append((code, "It", q))
                        continue
                    _base_st = it_st
                q_rows.append((q, float(it_v), it_st))
                ratio = float(it_v) / float(io_v)
                # بند ۸-۲: ضریب با ۳ رقم اعشار حساب، سپس به ۲ رقم گرد می‌شود
                _raw = float(k) * (ratio - 1.0)
                _used = round_coef_2080(_raw, neg_tz) if do_round else _raw
                dp_c += _used * amt * f
                # قطعی: شاخص قطعی باشد و علی‌الحساب (۲-۵-۳) نباشد
                if _base_st == "قطعی" and not (
                        _ov is not None and _ov["rule"] == "تعیین‌نشده"):
                    dp_c_def += _used * amt * f
                # مبنای تبصرهٔ ۲: همان محاسبه با k = ۰٫۹۵
                _raw9 = TADIL_K_2080 * (ratio - 1.0)
                _used9 = round_coef_2080(_raw9, neg_tz) if do_round else _raw9
                dp_c_095 += _used9 * amt * f
                coef_rows.append((q, _raw, _used))
                it_w += float(it_v) * f
                st_last = it_st
                if _dn_row is not None:
                    _dn.append(_dn_row)
            dp_total += dp_c
            dp_def_total += dp_c_def
            dp_total_095 += dp_c_095
            rows.append({
                "chapter": code, "title": chapter_title(code), "amount": amt,
                "io": float(io_v), "it": it_w,
                "ratio": it_w / float(io_v) if io_v else None,
                "value": dp_c, "delta": dp_c, "delta_definitive": dp_c_def,
                "status": st_last, "src": src, "quarters": q_rows,
                "coef_rows": coef_rows, "delta_k095": dp_c_095,
                "delay_notes": _dn,
            })

        # ── تجهیز و برچیدن کارگاه (شاخص رشته‌ای — بند ۴) ──
        setup_row = None
        dp_setup = 0.0
        dp_setup_def = 0.0
        dp_setup_095 = 0.0
        # ── تجهیز و برچیدن کارگاه (شاخص رشته‌ای — بند ۴) ──
        # منطقِ مشترکِ ردیف‌های شاخصِ رشته (تجهیز + کار جدیدِ گام ۵)
        # در `_discipline_amount_row` است تا هر دو ردیف یکسان طی شوند.
        setup_row = None
        dp_setup = 0.0
        dp_setup_def = 0.0
        dp_setup_095 = 0.0
        if setup > 0 and d_io:
            _sr = self._discipline_amount_row(
                setup, d_io, split, _delay, prov, _disc, d_it_m, do_round,
                neg_tz, k, missing, "تجهیز", "رشته‌ای (بند ۴)",
                "پیوست ۳، ردیف ۱" + (" — صفحهٔ %s" % fa(d_io_page)
                                     if d_io_page else ""),
                _span26, _ov26)
            setup_row = _sr["row"]
            dp_setup = _sr["dp"]
            dp_setup_def = _sr["dp_def"]
            dp_setup_095 = _sr["dp_095"]

        # ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) ──
        # ۳-۱: قیمت از فهرستِ ضمیمهٔ پیمان ⇒ شاخص مبنا = شاخص مبنای پیمان.
        # ۳-۲/۳-۳: فهرستِ پایه / قیمت روز ⇒ شاخص مبنا = دورهٔ آن قیمت‌ها.
        # ۳-۴: ترکیب — هر بخش طبق روشِ همان بخش (دو مبلغِ جداگانه).
        # ۳-۵: قیمتِ کار جدید بر ۰٫۹۵ تقسیم، سپس × (Io پیمان ÷ Io کار
        # جدید) تا به مبنای پیمان برسد، بعد مثل سایر ردیف‌ها با نسبتِ
        # It/Io پیمان تعدیل می‌شود (همان منطقِ تجهیز).
        if _new_amt_a > 0 or _new_amt_b > 0:
            _io_new = d_io
            _conv = 1.0
            if _new_amt_b > 0:
                _bp = (s.get("new_item_base_period") or "").strip()
                if _bp:
                    _io_new, _ = self._quarter_discipline(_bp, prov, _disc)
                else:
                    _io_new = None
                if _io_new is None or not d_io:
                    if not any(x.get("item") ==
                               "new_item_base_period_missing"
                               for x in warns):
                        warns.append({
                            "level": "خطا", "category": "موتور تعدیل",
                            "item": "new_item_base_period_missing",
                            "message": "روش قیمتِ کار جدید %s است ولی"
                                       " دورهٔ شاخص مبنا وارد نشده یا"
                                       " شاخصش ناموجود است؛ ردیفِ کار"
                                       " جدید محاسبه نشد." % _new_method,
                            "action": "دورهٔ سه‌ماههٔ مبنای کار جدید را در"
                                      " بخش «ورودی‌های قرارداد» وارد کنید.",
                            "ref": "بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳"})
                else:
                    _conv = (float(d_io) / float(_io_new)) / 0.95
                    if not any(x.get("item") == "new_item_095_conversion"
                               for x in warns):
                        warns.append({
                            "level": "اطلاع", "category": "موتور تعدیل",
                            "item": "new_item_095_conversion",
                            "message": "کار جدید: قیمت بر ۰٫۹۵ تقسیم و در"
                                       " ضریب %.6f (Io پیمان ÷ Io کار جدید)"
                                       " ضرب شد (بند ۳-۵)." % _conv,
                            "action": "در صورت نیاز، روش یا دورهٔ مبنا را"
                                      " اصلاح کنید.",
                            "ref": "بخشنامهٔ ۲۰۸۰، بند ۳-۵"})
            _new_base = _new_amt_a + _new_amt_b * _conv
            if _new_base > 0 and d_io and (
                    _new_amt_b == 0 or _io_new is not None):
                _nr = self._discipline_amount_row(
                    _new_base, d_io, split, _delay, prov, _disc, d_it_m,
                    do_round, neg_tz, k, missing, "کار جدید",
                    "کار جدید (%s)" % _new_method,
                    "بخشنامهٔ ۲۰۸۰، بندهای ۳-۱..۳-۵", _span26, _ov26)
                new_work_row = _nr["row"]
                dp_new = _nr["dp"]
                dp_new_def = _nr["dp_def"]
                dp_new_095 = _nr["dp_095"]
                new_work_row.update({
                    "method": _new_method,
                    "amount_own": _new_amt_a,
                    "amount_new": _new_amt_b,
                    "io_new": _io_new,
                    "conv": _conv,
                })

        incomplete = bool(missing)
        if incomplete:
            warns.append({"level": "خطا", "category": "موتور تعدیل", "item": L,
                          "message": "شاخص برخی فصل‌ها ناموجود است: "
                                     + "، ".join("%s (%s %s)" % (c, w, q)
                                                 for c, w, q in missing),
                          "action": "شاخص دستی آن فصل را در chapter_index_manual "
                                    "وارد کنید یا شاخص رشته را ثبت کنید.",
                          "ref": "فاز B — پیوست ۳"})

        # ── جمع و شرط‌ها ──
        delta_p = dp_total + dp_setup + dp_new
        delta_p_def = dp_def_total + dp_setup_def + dp_new_def
        # ── تبصرهٔ ۲ بند ۱-۸ + بند ۸-۴: مابه‌التفاوت k = ۰٫۹۵ → k = ۱ ──
        # اگر کار در مدت پیمان تمام شده باشد، k = ۱ است (در متغیر k
        # لحاظ شده) و مابه‌التفاوتِ آن با k = ۰٫۹۵ به‌صورت ردیفی جدا
        # همزمان با صورت‌وضعیت قطعی پرداخت می‌شود (بند ۸-۴).
        k_diff = delta_p - (dp_total_095 + dp_setup_095 + dp_new_095)
        if cwt and abs(k_diff) >= 0.005:
            delta_p_def += k_diff
        allow_neg = bool(s.get("tadil_allow_negative"))
        if delta_p < 0 and not allow_neg:
            warns.append({"level": "هشدار", "category": "موتور تعدیل", "item": L,
                          "message": "تعدیل منفی محاسبه شد ولی مجاز نیست؛ صفر اعمال شد.",
                          "action": "در صورت مجاز بودن، tadil_allow_negative را فعال کنید.",
                          "ref": "فاز B — قاعدهٔ کاربر"})
            delta_p = 0.0

        _new_base_amt = float((new_work_row or {}).get("amount") or 0.0)
        A_total = A + setup + _new_base_amt
        result_amount = A_total + delta_p
        # ── فاز E-6 Part C گام ۴: وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷) ──
        # بند ۶: خاتمه بدون قصور ⇒ طبق همین دستورالعمل، بدون تغییر.
        # بند ۷: فسخ به علت قصور پیمانکار ⇒ ۵٪ از مبلغ تعدیل کسر می‌شود.
        # کسر فقط روی «مبلغ نهایی» اعمال می‌شود؛ خودِ ΔP و تفکیک قطعی/
        # علی‌الحساب دست‌نخورده می‌مانند (قطعی + علی‌الحساب ≡ ΔP).
        _c_status = (s.get("contract_status") or "فعال").strip()
        deduction_fault = 0.0
        if _c_status == "فسخ با قصور":
            if delta_p < 0 and not s.get("fault_deduction_on_negative"):
                warns.append({"level": "هشدار", "category": "موتور تعدیل",
                              "item": L,
                              "message": "مبلغ تعدیل منفی است؛ کسر ۵٪ "
                                         "(بند ۷) اعمال نشد. در صورت نیاز، "
                                         "گزینهٔ «کسر در تعدیل منفی» را "
                                         "فعال کنید.",
                              "action": "این تفسیر در ACCEPTANCE.md §۱۸-۳ "
                                        "ثبت شده است.",
                              "ref": "بخشنامهٔ ۲۰۸۰، بند ۷"})
            else:
                deduction_fault = -0.05 * delta_p
                warns.append({"level": "هشدار", "category": "موتور تعدیل",
                              "item": L,
                              "message": "وضعیت خاتمهٔ پیمان «فسخ با قصور» "
                                         "است؛ ۵٪ از مبلغ تعدیل کسر می‌شود.",
                              "action": "اگر این اشتباه است، وضعیت خاتمه را "
                                        "در بخش «ورودی‌های قرارداد» اصلاح "
                                        "کنید.",
                              "ref": "بخشنامهٔ ۲۰۸۰، بند ۷"})
        result_amount = A_total + delta_p + deduction_fault
        approved = bool(s.get("tadil_approved"))
        if not approved:
            warns.append({"level": "اطلاع", "category": "موتور تعدیل", "item": L,
                          "message": "خروجی موتور تعدیل «پیش‌نویس» است تا مقادیر "
                                     "منبع تصویری تأیید شوند.",
                          "action": "پس از بررسی «مقادیر منتظر تأیید»، دکمهٔ تأیید را بزنید.",
                          "ref": "فاز B — قاعدهٔ کاربر"})
        adv_mode = s.get("tadil_advance_mode") or "کل مبلغ کارکرد"
        return {
            "mode": "تعدیل پیمان",
            "formula": "ΔP = k × Σ_c (It_c/Io_c − 1) × A_c",
            "coef": float(k), "io_q": io_q, "io_month": _io_month, "split": split,
            "delay_info": _delay,
            "index_method_resolved": {"method": _chain,
                                      "source": _chain_src},
            "base_amount": A_total, "work_base": A, "chain": chain,
            "setup_amount": setup, "setup_row": setup_row,
            "new_work_row": new_work_row,
            "chapters": rows, "delta_p": delta_p,
            "delta_p_definitive": delta_p_def,
            "delta_p_provisional": delta_p - delta_p_def,
            "result_amount": result_amount,
            "advance_mode": adv_mode, "delay_mode": delay_mode,
            "params": {"allow_negative": allow_neg,
                       "advance_payment": float(ctx.get("advance_payment") or 0.0),
                       "proposal_date": prop, "provisional_coef": prov},
            "k_diff": k_diff if cwt else 0.0,
            "coef_rounding": do_round,
            "completed_within_term": cwt,
            "k_status": k_status,
            "k_provisional": s.get("completed_within_term") is None,
            "work_period_missing": _wp_missing,
            "contract_status": _c_status,
            "deduction_fault": deduction_fault,
            "incomplete": incomplete, "missing": missing,
            "draft": not approved, "pending": pending,
            "source": ("تعدیل فصل به فصل با شاخص‌های پیوست ۳ بخشنامهٔ "
                       "۱۴۰۵/۱۵۵۲۳۳ (استخراج‌شده، نیازمند تأیید)؛ ضریب k از "
                       "بخشنامه ۲۰۸۰ (تصویری — پیش‌فرض اپ)"),
        }

    def _baravord_engine(self, ctx, warns):
        """موتور ۲ — برآورد به‌هنگام، فصل به فصل و بدون ضریب k.

        A_new = Σ_c A_c × It_c/Io_c  (＋ تجهیز × شاخص رشته)
        این موتور مستقل از موتور ۱ است و هرگز با آن ادغام نمی‌شود.
        """
        s = self.s
        L = "برآورد به‌هنگام"
        pending = []
        # ── فاز E-6 Part C گام ۶: مسیر شاخص (بندهای ۲-۱/۲-۲) — مثلِ موتور ۱ ──
        _chain, _chain_src = self._chain_method(s, warns)
        _disc = self._project_discipline()
        # ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) ──
        new_work_row = None
        _new_base_amt = 0.0
        _new_method = (s.get("new_item_method") or "فهرست پیمان").strip()
        if _new_method not in ("فهرست پیمان", "فهرست پایه", "قیمت روز",
                               "ترکیب"):
            _new_method = "فهرست پیمان"
        _new_amt = float(s.get("new_item_amount") or 0.0)
        _new_amt_att = float(s.get("new_item_amount_attached") or 0.0)
        if _new_method == "فهرست پیمان":
            _new_amt_a, _new_amt_b = _new_amt, 0.0
        elif _new_method == "ترکیب":
            _new_amt_a, _new_amt_b = _new_amt_att, _new_amt
        else:
            _new_amt_a, _new_amt_b = 0.0, _new_amt
        A, chain, applied = self._adj_base_chain(ctx, pending=pending)
        setup = float(ctx.get("site_setup") or 0.0)
        # مبالغ فصل‌ها در همان ضریبِ A ضرب می‌شوند تا Σ A_c = A برقرار شود.
        chap = {str(c): float(v) * applied
                for c, v in (ctx.get("chapter_amounts") or {}).items()}
        # فاز E-9 §۳.۳ — بند ۵: یادداشتِ مبلغِ منتقل‌شده به فصل حمل
        _haul_moved = float(ctx.get("haul_moved_amount") or 0.0)
        if _haul_moved > 0.0:
            warns.append({
                "level": "اطلاع", "category": "موتور برآورد به‌هنگام",
                "item": "clause5_haul",
                "message": ("مبلغ %s از ردیف‌های «مترمکعب کیلومترِ» فصل‌های "
                            "غیر از فصل حمل به فصل ۲۸ منتقل شد و با شاخص‌های "
                            "فصل حمل به‌هنگام می‌شود (بند ۵ بخشنامهٔ ۱۵۵۲۳۳)."
                            % fmt_money(_haul_moved)),
                "action": "تطبیقِ فهرستِ ردیف‌های حمل را با صورت‌وضعیت بررسی کنید.",
                "ref": "بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵"})
        io_q = self._PERIOD_QUARTERS.get(s.get("baravord_io_period") or "base")
        # ── بخشنامهٔ ۱۴۴۳۷۴: مهلت تسلیم در تابستان ۱۴۰۵ ⇒ Io ماهانه ──
        _bd = (s.get("proposal_deadline") or "").strip()
        _pd = (s.get("proposal_date") or "").strip()
        _io_date_b = _bd or _pd
        _io_month = self._io_month_for(_io_date_b) if _io_date_b else None
        if _io_month and not self._monthly_has_data(_io_month):
            warns.append({"level": "خطا", "category": "موتور برآورد",
                          "item": "monthly_index_1405",
                          "message": "مهلت تسلیم پیشنهاد در تابستان ۱۴۰۵ "
                                     "است؛ طبق بخشنامهٔ ۱۴۴۳۷۴ Io باید شاخص "
                                     "ماهانهٔ خرداد ۱۴۰۵ (آحادبها) باشد، ولی "
                                     "این شاخص هنوز در config/index_bulletins.json "
                                     "وارد نشده است. موتور برآورد به‌هنگام "
                                     "متوقف شد.",
                          "action": "شاخص‌های ماهانهٔ خرداد ۱۴۰۵ را در بخش "
                                    "monthly فایل config/index_bulletins.json "
                                    "وارد کنید (هرگز حدس زده نمی‌شود).",
                          "ref": "فاز E — بخشنامهٔ ۱۴۴۳۷۴"})
            return {
                "mode": "برآورد به‌هنگام",
                "formula": "A_new = Σ_c A_c × It_c/Io_c",
                "error": "شاخص ماهانهٔ خرداد ۱۴۰۵ وارد نشده — موتور برآورد "
                         "به‌هنگام متوقف شد.",
                "io_q": io_q, "io_month": _io_month, "it_q": None,
                "it_status": "نامشخص",
                "prov": None, "prov_manual": False, "prov_trace": {},
                "index_method_resolved": {"method": _chain,
                                          "source": _chain_src},
                "base_amount": A + setup, "work_base": A, "chain": chain,
                "setup_amount": setup, "setup_row": None,
                "new_work_row": new_work_row,
                "chapters": [], "result_amount": 0.0,
                "grand_updated": 0.0,
                "grand_current": float(ctx.get("grand_total") or 0.0),
                "applied_mult": applied,
                "incomplete": True, "missing": [], "draft": True,
                "pending": pending,
                "source": "فاز E — ۱۴۴۳۷۴ (توقف: شاخص ماهانهٔ خرداد ۱۴۰۵)",
            }
        _it_raw = s.get("baravord_it_period") or "q4"
        # گزینه‌های موقت (۱۴۰۵Q1 به بعد) فقط برای It در سایدبار قابل انتخاب
        # هستند؛ این کلیدها در _PERIOD_QUARTERS نیستند و مستقیم پاس داده
        # می‌شوند (بند ۳ بخشنامهٔ ۱۴۴۳۷۳).
        it_q = _it_raw if self._quarter_is_provisional(_it_raw) \
            else self._PERIOD_QUARTERS.get(_it_raw)
        # ── شاخص موقت ۱۴۰۵Q1: ضریب دستی کاربر معیار است؛ در غیر این صورت
        # از CPI + m محاسبه می‌شود (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳، پیوست ص۱). ──
        _prov_man = self._adj_manual_get({"v": s.get("provisional_coef_1405q1")}, "v")
        _prov_auto, _prov_st, _prov_tr = self._provisional_coef_1405q1("ابنیه")
        prov = _prov_man if _prov_man else _prov_auto
        if _prov_man:
            pending.append(self._adj_pending(
                "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵", _prov_man,
                "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ (PDF تصویری — متن استخراج نشد)", "—",
                "دستی — نیازمند تأیید",
                "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴)"))
        elif prov is not None:
            pending.append(self._adj_pending(
                "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵", prov,
                "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱ + مرکز آمار ایران",
                "فرمول: ۱ + m × (CPI[اردیبهشت ۱۴۰۵] ÷ میانگین CPI[دی، "
                "بهمن، اسفند ۱۴۰۴] − ۱)",
                "موقت — محاسبه‌شده از CPI (m=%s)" % fa(_prov_tr.get("m")),
                "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴). "
                "m=%s، میانگین زمستان ۱۴۰۴=%s، اردیبهشت ۱۴۰۵=%s."
                % (fa(_prov_tr.get("m")),
                   fa(round(_prov_tr.get("denominator_mean") or 0.0, 4)),
                   fa(_prov_tr.get("numerator")))))
        man = s.get("chapter_index_manual") or {}
        dman = s.get("discipline_index_manual") or {}
        d_io_m = self._adj_manual_get(dman, "io")
        d_it_m = self._adj_manual_get(dman, "it")
        # ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستیِ رشته ──
        _d_src = _manual_src(dman)
        if (d_io_m or d_it_m) and not _d_src:
            if not any(x.get("item") == "manual_index_source_required"
                       and x.get("_code") == _disc for x in warns):
                warns.append({
                    "level": "خطا", "category": "موتور تعدیل",
                    "item": "manual_index_source_required",
                    "_code": _disc,
                    "message": ("شاخص دستی برای رشتهٔ %s وارد شده ولی "
                                "منبعِ آن (src) مشخص نشده است؛ منبع را "
                                "وارد کنید." % _disc),
                    "action": "فیلدِ src شاخص دستیِ رشته را پر کنید.",
                    "ref": "بخشنامهٔ ۲۰۸۰ — گام ۸"})
        _d_src_label = (" (%s)" % _d_src) if _d_src else ""
        if d_io_m:
            d_io, d_io_page = d_io_m, "دستی%s" % _d_src_label
        elif _io_month:
            d_io, d_io_page = self._monthly_discipline(_io_month, _disc)
        else:
            d_io, d_io_page = self._index_value(
                self._QUARTER_PERIOD.get(io_q) or "base", _disc)

        # ── شاخص موقت ۱۴۰۵Q1 برای It: ضریب از CPI + m محاسبه می‌شود؛
        # اگر شاخص ماهانهٔ موردنیاز موجود نباشد، موتور با خطا متوقف
        # می‌شود (قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود).
        _active = [c for c, v in chap.items() if abs(v) >= 0.01]
        _all_manual_it = bool(_active) and all(
            isinstance(man.get(c), dict)
            and self._adj_manual_get(man.get(c), "it") for c in _active)
        _setup_manual_ok = (setup <= 0.0) or (d_it_m is not None)
        if self._quarter_is_provisional(it_q) and not prov \
                and not (_all_manual_it and _setup_manual_ok):
            warns.append({"level": "خطا", "category": "موتور برآورد",
                          "item": "provisional_coef_1405q1",
                          "message": "دورهٔ هدف (It) سه‌ماههٔ اول ۱۴۰۵ (موقت) "
                                     "است ولی ضریب موقت قابل محاسبه نیست — شاخص "
                                     "ماهانهٔ CPI در config/cpi_monthly.json ناقص "
                                     "است یا m رشته تعریف نشده؛ موتور برآورد "
                                     "به‌هنگام متوقف شد.",
                          "action": "شاخص‌های ماهانهٔ CPI را در config/cpi_monthly.json "
                                    "تکمیل کنید (یا ضریب دستی را در سایدبار وارد "
                                    "کنید یا شاخص دستی It همهٔ فصل‌ها را پر کنید).",
                          "ref": "فاز E — بخشنامهٔ ۱۴۴۳۷۳ پیوست ص۱ (CPI)"})
            return {
                "mode": "برآورد به‌هنگام",
                "formula": "A_new = Σ_c A_c × It_c/Io_c",
                "error": "ضریب موقت ۱۴۰۵Q1 قابل محاسبه نیست (CPI ناقص) — "
                         "موتور برآورد به‌هنگام متوقف شد.",
                "io_q": io_q, "io_month": _io_month, "it_q": it_q,
                "it_status": "موقت" if self._quarter_is_provisional(it_q) else "قطعی",
                "prov": prov, "prov_manual": bool(_prov_man),
                "prov_trace": _prov_tr,
                "index_method_resolved": {"method": _chain,
                                          "source": _chain_src},
                "base_amount": A + setup, "work_base": A, "chain": chain,
                "setup_amount": setup, "setup_row": None,
                "new_work_row": new_work_row,
                "chapters": [], "result_amount": 0.0,
                "grand_updated": 0.0,
                "grand_current": float(ctx.get("grand_total") or 0.0),
                "applied_mult": applied,
                "incomplete": True, "missing": [], "draft": True,
                "pending": pending,
                "source": "فاز E — ۱۴۴۳۷۳ پیوست ص۱ (توقف: CPI موقت ناموجود)",
            }

        rows = []
        missing = []
        a_new = 0.0
        a_new_chap = 0.0
        for code, amt in sorted(chap.items(), key=lambda kv: kv[1], reverse=True):
            if abs(amt) < 0.01:
                continue
            m = man.get(code) if isinstance(man, dict) else None
            m = m if isinstance(m, dict) else {}
            m_io = self._adj_manual_get(m, "io")
            m_it = self._adj_manual_get(m, "it")
            # ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستی اجباری است ──
            _m_src = _manual_src(m)
            if (m_io or m_it) and not _m_src:
                if not any(x.get("item") == "manual_index_source_required"
                           and x.get("_code") == code for x in warns):
                    warns.append({
                        "level": "خطا", "category": "موتور تعدیل",
                        "item": "manual_index_source_required",
                        "_code": code,
                        "message": ("شاخص دستی برای فصل %s وارد شده ولی "
                                    "منبعِ آن (src) مشخص نشده است؛ منبع را "
                                    "وارد کنید (مثلاً «نامهٔ کارفرما» یا "
                                    "«پیوست ۳، صفحهٔ ۸۲»)." % code),
                        "action": "فیلدِ src شاخص دستیِ این فصل را پر کنید.",
                        "ref": "بخشنامهٔ ۲۰۸۰ — گام ۸"})
            _m_src_label = (" (%s)" % _m_src) if _m_src else ""
            if _chain == "رشته‌ای":
                # بند ۲-۱: مسیر رشته‌ای — شاخصِ رشتهٔ پروژه (نه شاخصِ فصل)
                if _io_month:
                    io_v, io_page = self._monthly_discipline(_io_month, _disc)
                else:
                    io_v, io_page = self._index_value(
                        self._QUARTER_PERIOD.get(io_q) or "base", _disc)
            elif _io_month:
                io_v, io_page = self._monthly_chapter_index(code, _io_month)
            else:
                io_v, io_page = self._chapter_index_q(code, io_q)
            use_disc = (_chain == "رشته‌ای") or (io_v is None and not m_io)
            # ─ـ فاز E-6 Part C گام ۸ (حرف e): هشدارِ اختلافِ شاخص دستی ──
            if m_io and io_v is not None:
                _dev = abs(m_io - io_v) / io_v if io_v else 0.0
                if _dev > MANUAL_INDEX_DEVIATION_PCT:
                    if not any(
                            x.get("item") == "manual_index_deviation_20"
                            and x.get("_code") == code for x in warns):
                        warns.append({
                            "level": "هشدار", "category": "موتور تعدیل",
                            "item": "manual_index_deviation_20",
                            "_code": code,
                            "message": ("شاخص دستیِ Io فصل %s (%s) بیش از "
                                        "%s٪ با شاخصِ config (%s) اختلاف "
                                        "دارد — منبع را تأیید کنید."
                                        % (code, fa_float(m_io, 2),
                                           fa_float(
                                               MANUAL_INDEX_DEVIATION_PCT * 100,
                                               0),
                                           fa_float(io_v, 2))),
                            "action": ("منبعِ شاخص دستی را مستند کنید یا "
                                       "شاخص config را به‌روز کنید."),
                            "ref": "بخشنامهٔ ۲۰۸۰ — گام ۸"})
            if m_io:
                io_v, src = m_io, "دستی%s" % _m_src_label
            elif use_disc:
                if d_io is None:
                    missing.append((code, "Io", io_q))
                    continue
                if _chain == "رشته‌ای":
                    io_v, src = float(d_io), "شاخص رشته (مسیر ۲-۱)"
                else:
                    io_v, src = float(d_io), "شاخص رشته (بدون شاخص فصل — بند ۴)"
                    pending.append(self._adj_pending(
                    "شاخص فصل %s — Io" % code, float(d_io),
                    "پیوست ۳، ردیف ۱ (شاخص رشته)",
                    "صفحهٔ %s" % fa(d_io_page) if d_io_page else "—",
                    "فصل استخراج نشده — جایگزین با شاخص رشته، نیازمند تأیید",
                    "شاخص اختصاصی فصل %s را از جدول پیوست ۳ وارد کنید." % code))
            else:
                src = "پیوست ۳، صفحهٔ %s" % fa(io_page) if io_page else "جدول"
            if m_it:
                it_v, it_st = m_it, "دستی"
            elif use_disc:
                it_v, it_st = self._quarter_discipline(it_q, prov, _disc)
            else:
                it_v, it_st = self._quarter_index(code, it_q, prov)
            if it_v is None:
                missing.append((code, "It", it_q))
                continue
            ratio = float(it_v) / float(io_v)
            new_c = amt * ratio
            a_new += new_c
            a_new_chap += new_c
            rows.append({
                "chapter": code, "title": chapter_title(code), "amount": amt,
                "io": float(io_v), "it": float(it_v), "ratio": ratio,
                "value": new_c, "status": it_st, "src": src,
            })

        setup_row = None
        if setup > 0 and d_io:
            d_it_v, d_st = (d_it_m, "دستی") if d_it_m \
                else self._quarter_discipline(it_q, prov, _disc)
            if d_it_v is None:
                missing.append(("تجهیز", "It", it_q))
            else:
                d_ratio = float(d_it_v) / float(d_io)
                setup_row = {
                    "amount": setup, "io": float(d_io), "it": float(d_it_v),
                    "ratio": d_ratio, "value": setup * d_ratio,
                    "status": d_st, "src": "پیوست ۳، ردیف ۱",
                }
                a_new += setup_row["value"]

        # ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای
        # ۳-۱..۳-۵) — مثلِ موتور ۱: تبدیلِ ۳-۵ روی مبلغ، سپس نسبتِ
        # تک‌دورهٔ It/Io پیمان (برآورد به‌هنگام تأخیر/۲-۶ ندارد). ──
        new_work_row = None
        _new_base_amt = 0.0
        if _new_amt_a > 0 or _new_amt_b > 0:
            _io_new_b = d_io
            _conv_b = 1.0
            if _new_amt_b > 0:
                _bp = (s.get("new_item_base_period") or "").strip()
                if _bp:
                    _io_new_b, _ = self._quarter_discipline(_bp, prov, _disc)
                else:
                    _io_new_b = None
                if _io_new_b is None or not d_io:
                    if not any(x.get("item") ==
                               "new_item_base_period_missing"
                               for x in warns):
                        warns.append({
                            "level": "خطا", "category": "موتور برآورد",
                            "item": "new_item_base_period_missing",
                            "message": "روش قیمتِ کار جدید %s است ولی"
                                       " دورهٔ شاخص مبنا وارد نشده یا"
                                       " شاخصش ناموجود است؛ ردیفِ کار"
                                       " جدید محاسبه نشد." % _new_method,
                            "action": "دورهٔ سه‌ماههٔ مبنای کار جدید را در"
                                      " بخش «ورودی‌های قرارداد» وارد کنید.",
                            "ref": "بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳"})
                else:
                    _conv_b = (float(d_io) / float(_io_new_b)) / 0.95
            _new_base_amt = _new_amt_a + _new_amt_b * _conv_b
            if _new_base_amt > 0 and d_io and (
                    _new_amt_b == 0 or _io_new_b is not None):
                d_it_v, d_st = (d_it_m, "دستی") if d_it_m \
                    else self._quarter_discipline(it_q, prov, _disc)
                if d_it_v is None:
                    missing.append(("کار جدید", "It", it_q))
                else:
                    _nratio = float(d_it_v) / float(d_io)
                    new_work_row = {
                        "amount": _new_base_amt, "io": float(d_io),
                        "it": float(d_it_v), "ratio": _nratio,
                        "value": _new_base_amt * _nratio,
                        "status": "کار جدید (%s)" % _new_method,
                        "src": "بخشنامهٔ ۲۰۸۰، بندهای ۳-۱..۳-۵",
                        "method": _new_method,
                        "amount_own": _new_amt_a,
                        "amount_new": _new_amt_b,
                        "io_new": _io_new_b, "conv": _conv_b,
                    }
                    a_new += new_work_row["value"]

        # ── جمع کل به‌هنگام‌شده (قیمت پیمان) ──
        # اگر A_basis = «بدون ضرایب» باشد، ضرایبِ قیمت پس از It/Io اعمال
        # می‌شوند تا جمع به‌هنگام‌شده با جمع کل فعلی قابل مقایسه باشد.
        _oh = float(ctx.get("overhead_coef") or 1.0)
        _reg = float(ctx.get("regional_coef") or 1.0)
        _prop = float(s.get("proposal_coef") or 1.0)
        _residual = (_oh * _reg * _prop) / applied if applied else 1.0
        _setup_val = setup_row["value"] if setup_row else 0.0
        _new_val = new_work_row["value"] if new_work_row else 0.0
        grand_updated = a_new_chap * _residual + _setup_val + _new_val

        incomplete = bool(missing)
        if incomplete:
            warns.append({"level": "خطا", "category": "موتور برآورد", "item": L,
                          "message": "شاخص برخی فصل‌ها ناموجود است: "
                                     + "، ".join("%s (%s %s)" % (c, w, q)
                                                 for c, w, q in missing),
                          "action": "شاخص دستی آن فصل را در chapter_index_manual "
                                    "وارد کنید.",
                          "ref": "فاز B — پیوست ۳"})
        approved = bool(s.get("baravord_approved"))
        if not approved:
            warns.append({"level": "اطلاع", "category": "موتور برآورد", "item": L,
                          "message": "خروجی برآورد به‌هنگام «پیش‌نویس» است تا "
                                     "مقادیر استخراج‌شده تأیید شوند.",
                          "action": "پس از بررسی «مقادیر منتظر تأیید»، دکمهٔ تأیید را بزنید.",
                          "ref": "فاز B — قاعدهٔ کاربر"})
        return {
            "mode": "برآورد به‌هنگام",
            "formula": "A_new = Σ_c A_c × It_c/Io_c",
            "io_q": io_q, "io_month": _io_month, "it_q": it_q,
            "it_status": "موقت" if self._quarter_is_provisional(it_q) else "قطعی",
            "prov": prov, "prov_manual": bool(_prov_man),
            "prov_trace": _prov_tr,
            "index_method_resolved": {"method": _chain,
                                      "source": _chain_src},
            "base_amount": A + setup + _new_base_amt, "work_base": A, "chain": chain,
            "setup_amount": setup, "setup_row": setup_row,
            "new_work_row": new_work_row,
            "chapters": rows, "result_amount": a_new,
            "grand_updated": grand_updated,
            "grand_current": float(ctx.get("grand_total") or 0.0),
            "applied_mult": applied,
            "incomplete": incomplete, "missing": missing,
            "draft": not approved, "pending": pending,
            "source": ("به‌هنگام‌سازی فصل به فصل برآورد با شاخص‌های پیوست ۳ "
                       "بخشنامه ۱۴۰۵/۱۵۵۲۳۳ (استخراج‌شده، نیازمند تأیید)"),
        }



# ════════════════════════════════════════════════════════════════
# کلاس ExcelExporter — خروجی حرفه‌ای Excel با xlsxwriter
# شش برگه با هدر رسمی، راست‌به‌چپ و فرمول‌های محاسباتی
# ════════════════════════════════════════════════════════════════

_INDEX_PERIOD_LABELS = {"base": "اسفند ۱۴۰۳ (مبنا)", "q1": "سه‌ماهه اول ۱۴۰۴",
                        "q2": "سه‌ماهه دوم ۱۴۰۴", "q3": "سه‌ماهه سوم ۱۴۰۴",
                        "q4": "سه‌ماهه چهارم ۱۴۰۴"}


# ترتیب رسمی ۱۹ برگهٔ گزارش (فاز D — درخواست کاربر). برگه‌های موتورهای
# فاز B (تعدیل پیمان / برآورد به‌هنگام / بخش قطعی) فقط هنگام روشن بودن
# موتور ساخته می‌شوند؛ بقیه همیشه present هستند.
SHEET_ORDER = [
    "خلاصه و وضعیت", "مشخصات پیمان", "متره ریز",
    "خلاصهٔ مالی و برآورد", "ضرایب", "ضریب طبقات",
    "لیستوفر آرماتور", "صورت وضعیت", "سوابق صورت وضعیت",
    "تعدیل پیمان", "برآورد به‌هنگام", "بخش قطعی و علی‌الحساب",
    "شاخص‌ها", "قیمت‌های دستی", "کیفیت تطبیق",
    "هشدارها", "مقادیر منتظر تأیید", "سابقهٔ ویرایش",
    "منابع و بخشنامه‌ها",
]

# شرح کوتاه هر برگه برای فهرست برگه‌ها در صفحهٔ اول (نام، شرح)
SHEET_INDEX = [
    ("خلاصه و وضعیت", "این صفحه — شمارش وضعیت قیمت‌ها، ضرایب و خلاصهٔ مالی"),
    ("مشخصات پیمان", "مشخصات پروژه، قرارداد، صورت‌وضعیت و ضرایب قراردادی"),
    ("متره ریز", "ردیف‌های متره: کمیت، بهای واحد و مبلغ هر ردیف"),
    ("خلاصهٔ مالی و برآورد", "زنجیرهٔ مالی کامل، کسورات قانونی و خالص پرداختی"),
    ("ضرایب", "همهٔ ضرایب با مقدار، وضعیت و منبع رسمی"),
    ("ضریب طبقات", "فرمول رسمی پیوست ۲ و جدول ترازهای طبقات"),
    ("لیستوفر آرماتور", "وزن میلگرد به تفکیک گروه سازه‌ای و قطر"),
    ("صورت وضعیت", "فهرست بهای پیمان به سبک MPX (قیمت و ضرایب)"),
    ("سوابق صورت وضعیت", "تاریخچهٔ صورت‌وضعیت‌های قبلی و کارکرد تجمعی"),
    ("تعدیل پیمان", "موتور تعدیل فصل‌به‌فصل (قاعدهٔ ضریب ۰٫۹۵)"),
    ("برآورد به‌هنگام", "موتور برآورد به‌هنگام (شاخص زنجیره‌ای)"),
    ("بخش قطعی و علی‌الحساب", "بخش‌بندی مبالغ قطعی و علی‌الحساب"),
    ("شاخص‌ها", "شاخص‌های رسمی تعدیل و ضریب هر فصل"),
    ("قیمت‌های دستی", "قیمت‌های دستی/موقت و وضعیت تأیید هر کدام"),
    ("کیفیت تطبیق", "تطابق کدهای کمیت با فهرست‌بهای ۱۴۰۴"),
    ("هشدارها", "رجیستری مرکزی هشدارها و خطاها"),
    ("مقادیر منتظر تأیید", "مقادیر نیازمند تأیید کاربر"),
    ("سابقهٔ ویرایش", "تاریخچهٔ ویرایش‌های کاربر (audit trail)"),
    ("منابع و بخشنامه‌ها", "منابع رسمی، وضعیت استخراج و محل استفاده"),
]

# توضیح هر وضعیت قیمت (همان برچسب‌های شیت «خلاصهٔ مالی و برآورد»)
_PRICE_STATUS_DESC = {
    "قطعی": "تطبیق دقیق با فهرست‌بهای ۱۴۰۴",
    "موقت": "شاخص/بهای موقت — نیازمند تأیید کاربر",
    "دستی": "قیمت واردشدهٔ دستی کاربر (ثبت در «سابقهٔ ویرایش»)",
    "پیش‌فرض اپ": "قیمت پیش‌فرض برنامه — قابل تغییر در تنظیمات",
    "نیازمند ورود": "بهای رسمی ندارد — خروجی «پیش‌نویس» می‌شود",
}

# منابع رسمی استفاده‌شده (قاعدهٔ طلایی ۲: هر مقدار قابل ردیابی)
_SOURCES = [
    ("S1", "آمار رسمی", "شاخص‌های آماری هزینهٔ پروژه‌های عمرانی",
     "سازمان برنامه و بودجه — nezamfanni.ir", "—",
     "قطعی (رسمی)", "مبنای شاخص‌های دوره‌های گذشته"),
    ("S2", "بخشنامه", "شاخص‌های قطعی تعدیل آحادبها ۱۴۰۴ — پیوست ۳",
     "بخشنامه ۱۴۰۵/۱۵۵۲۳۳ (tadil1404-34.pdf)", "۱۴۰۵/۰۴/۰۲",
     "استخراج‌شده — نیازمند تأیید", "شیت «شاخص‌ها» و موتورهای تعدیل/برآورد"),
    ("S3", "بخشنامه", "ضریب موقت شاخص سه‌ماههٔ اول ۱۴۰۵",
     "بخشنامه ۱۴۴۳۷۳", "—",
     "تصویری (PDF) — فیلد دستی", "فیلد دستیِ شاخص موقت ۱۴۰۵Q1"),
    ("S4", "بخشنامه", "ضریب تبدیل مبنا (فهرست پایه → مبنا قرارداد)",
     "بخشنامه ۱۴۴۳۷۴", "—",
     "تصویری (PDF) — فیلد دستی", "فیلد دستیِ ضریب تبدیل مبنا"),
    ("S5", "بخشنامه", "ضریب منطقه‌ای کارهای ابنیه",
     "بخشنامه ۹۴/۶۹۴۱۶", "—",
     "استخراج‌شده — نیازمند تأیید", "شیت «ضرایب» — ضریب منطقه‌ای"),
    ("S6", "دستورالعمل", "دستورالعمل نحوهٔ محاسبهٔ پرداخت‌ها",
     "دستورالعمل ۱۰۱/۱۷۳۰۷۳", "—",
     "تصویری (PDF) — استخراج نشد",
     "مبنای A₀ — طبق قاعدهٔ طلایی ۳ حدس زده نمی‌شود"),
    ("S7", "بخشنامه", "قاعدهٔ ضریب k در تعدیل فصل‌به‌فصل (بند ۱-۸ و تبصرهٔ ۲)",
     "بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ — سازمان برنامه و بودجه", "۱۳۷۰/۰۶/۲۳",
     "تصویری (PDF) — فاز E-۶ (docs/sources/2080.pdf)",
     "موتور تعدیل پیمان (k = ۰٫۹۵ / ۱)"),
    ("S8", "بخشنامه", "فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه ۱۴۰۴",
     "بخشنامه ۵۰۹۵۰۴", "۱۴۰۴",
     "قطعی (رسمی)", "مبنای همهٔ قیمت‌های رسمی (شیت «متره ریز»)"),
    ("S9", "فهرست‌بها", "پیوست ۲ — تعاریف و فرمول ضریب طبقات",
     "فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴، پیوست ۲", "۱۴۰۴",
     "قطعی (رسمی)", "شیت «ضریب طبقات» — فرمول P"),
]


def _index_period_label(key) -> str:
    """برچسب فارسی یک دورهٔ شاخص از کلید آن (base/q1/.../q4)."""
    return _INDEX_PERIOD_LABELS.get(str(key or ""), str(key or "—"))


_QUARTER_LABELS = {"1403Q4": "سه‌ماههٔ چهارم ۱۴۰۳ (اسفند ۱۴۰۳ — مبنا)",
                   "1404Q1": "سه‌ماههٔ اول ۱۴۰۴", "1404Q2": "سه‌ماههٔ دوم ۱۴۰۴",
                   "1404Q3": "سه‌ماههٔ سوم ۱۴۰۴", "1404Q4": "سه‌ماههٔ چهارم ۱۴۰۴",
                   "1405Q1": "سه‌ماههٔ اول ۱۴۰۵ (موقت)",
                   "1405Q2": "سه‌ماههٔ دوم ۱۴۰۵ (موقت)",
                   "1405Q3": "سه‌ماههٔ سوم ۱۴۰۵ (موقت)",
                   "1405Q4": "سه‌ماههٔ چهارم ۱۴۰۵ (موقت)"}


def _quarter_label(key) -> str:
    """برچسب فارسی یک سه‌ماهه از کلید آن (مثل ۱۴۰۴Q2)."""
    return _QUARTER_LABELS.get(str(key or ""), str(key or "—"))


def _io_label(engine_out) -> str:
    """برچسب دورهٔ مبنا (Io): ماهانه (۱۴۴۳۷۴) یا سه‌ماهه‌ای (پیوست ۳)."""
    _m = (engine_out or {}).get("io_month")
    if _m:
        _lbl = {k: v for k, v in TechnicalOfficeEngine._monthly_periods()}
        return "%s (ماهانه — بخشنامهٔ ۱۴۴۳۷۴)" % (
            _lbl.get(_m) or _m)
    return _quarter_label((engine_out or {}).get("io_q"))


def _fa_pct(x) -> str:
    """قالب‌بندی درصد با حذف ممیزِ صفرِ اعشار: ۵.۰ → ۵، ۷.۸ → ۷٫۸.
    هم‌سان با faDigits در TypeScript (در JS ۵.۰ === ۵)."""
    xf = float(x)
    return fa(int(xf)) if xf == int(xf) else fa(xf)


def _split_rounded(total, first, ndigits=0):
    """تفکیک گردشدهٔ یک جمع به دو بخش، با این تضمین که
    «بخش اول + بخش دوم ≡ گردشدهٔ کل» برقرار باشد. باقیماندهٔ
    گردسازی به بخش دوم (علی‌الحساب) داده می‌شود.
    → (کل گردشده, بخش اول گردشده, بخش دوم گردشده)."""
    _r = round(float(total), ndigits)
    _a = round(float(first), ndigits)
    return _r, _a, _r - _a


class ExcelExporter:
    """تولید خروجی Excel با xlsxwriter (فرمت‌بندی حرفه‌ای + فرمول)."""

    def __init__(self):
        """راه‌اندازی فرمت‌های استاندارد گزارش."""
        pass

    @staticmethod
    def _formats(wb):
        """ساخت مجموعهٔ قالب‌های استاندارد گزارش (فونت Tahoma سازگار با فارسی)."""
        return {
            "title": wb.add_format({"font_name": "Tahoma", "font_size": 14, "bold": True, "align": "center",
                                    "valign": "vcenter", "font_color": "#5c4400", "bg_color": "#fde9b8"}),
            "hsub": wb.add_format({"font_name": "Tahoma", "font_size": 9, "align": "center", "valign": "vcenter",
                                   "font_color": "#444444", "bg_color": "#fbf6ea"}),
            "thead": wb.add_format({"font_name": "Tahoma", "font_size": 10, "bold": True, "align": "center",
                                    "valign": "vcenter", "bg_color": "#f0e0b0", "border": 1, "text_wrap": True}),
            "cell": wb.add_format({"font_name": "Tahoma", "font_size": 9, "valign": "vcenter",
                                   "border": 1, "text_wrap": True}),
            "cell_c": wb.add_format({"font_name": "Tahoma", "font_size": 9, "align": "center",
                                     "valign": "vcenter", "border": 1}),
            "num": wb.add_format({"font_name": "Tahoma", "font_size": 9, "num_format": "#,##0.00",
                                  "valign": "vcenter", "border": 1}),
            "money": wb.add_format({"font_name": "Tahoma", "font_size": 9, "num_format": "#,##0",
                                    "valign": "vcenter", "border": 1}),
            "money_b": wb.add_format({"font_name": "Tahoma", "font_size": 10, "bold": True, "num_format": "#,##0",
                                      "valign": "vcenter", "border": 1, "bg_color": "#fbf2d5"}),
            "label": wb.add_format({"font_name": "Tahoma", "font_size": 10, "bold": True, "valign": "vcenter",
                                    "border": 1, "bg_color": "#f7f3e8", "text_wrap": True}),
            "chapter": wb.add_format({"font_name": "Tahoma", "font_size": 10, "bold": True,
                                      "font_color": "#5c4400", "bg_color": "#fdf0cd", "border": 1, "valign": "vcenter"}),
            "net": wb.add_format({"font_name": "Tahoma", "font_size": 12, "bold": True, "num_format": "#,##0",
                                  "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#f5dd9d", "font_color": "#3d2e00"}),
            "net_l": wb.add_format({"font_name": "Tahoma", "font_size": 12, "bold": True, "align": "right",
                                    "valign": "vcenter", "border": 1, "bg_color": "#f5dd9d", "font_color": "#3d2e00"}),
            "neg": wb.add_format({"font_name": "Tahoma", "font_size": 9, "num_format": "#,##0;[Red]-#,##0",
                                  "valign": "vcenter", "border": 1}),
            # فاز B: برچسب زرد برای مقادیر پیش‌فرض اپ / استخراج‌شدهٔ نیازمند تأیید
            "warn_y": wb.add_format({"font_name": "Tahoma", "font_size": 9, "bold": True,
                                     "valign": "vcenter", "border": 1, "align": "right",
                                     "font_color": "#7a5c00", "bg_color": "#fff3cd"}),
            # ستون مخفی میلادی (ایراد ۱۳): تاریخ واقعی Excel برای محاسبات
            "date_iso": wb.add_format({"font_name": "Tahoma", "font_size": 9,
                                       "num_format": "yyyy-mm-dd", "align": "center",
                                       "valign": "vcenter", "border": 1}),
        }

    @staticmethod
    def _header_block(ws, F, meta, ncols: int) -> int:
        """نوشتن هدر رسمی صورت‌وضعیت در ابتدای برگه و بازگرداندن شمارهٔ سطر بعدی."""
        ws.right_to_left()
        ws.merge_range(0, 0, 0, ncols - 1,
                       f"صورت وضعیت {meta['report_type']} شماره {fa(meta['report_no'] or '—')} — پیمان شماره {meta['contract_no'] or '—'}",
                       F["title"])
        ws.merge_range(1, 0, 1, ncols - 1,
                       f"نام پروژه: {meta['project_name'] or '—'}    کارفرما: {meta['employer'] or '—'}    پیمانکار: {meta['contractor'] or '—'}    مشاور: {meta['consultant'] or '—'}",
                       F["hsub"])
        ws.merge_range(2, 0, 2, ncols - 1,
                       f"دورهٔ صورت‌وضعیت: از {meta['period_start'] or '—'} تا {meta['period_end'] or '—'}    محل اجرا: {meta['location'] or '—'}    شروع پیمان: {meta['contract_date'] or '—'}",
                       F["hsub"])
        ws.merge_range(3, 0, 3, ncols - 1,
                       "مبنای قیمت‌گذاری: فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه سال ۱۴۰۴ (سازمان برنامه و بودجه)    واحد پول: ریال",
                       F["hsub"])
        # فاز E-10 §۲ — واترمارکِ «پیش‌نویس – دورهٔ کارکرد وارد نشده» روی
        # همهٔ شیت‌ها: وقتی دورهٔ کارکرد خالی است، خروجیِ نهایی ممنوع است و
        # فقط پیش‌نویس مجاز می‌شود.
        # فاز E-10.1 §۳ — واترمارکِ «نسخهٔ نمایشی» هم همین‌جا می‌نشیند.
        _banners = [b for b in (meta.get("draft_banner"),
                                meta.get("demo_banner")) if b]
        for _i, _b in enumerate(_banners):
            ws.merge_range(4 + _i, 0, 4 + _i, ncols - 1, str(_b), F["warn_y"])
        return 5 + len(_banners)

    @staticmethod
    def _row(ws, r, values, fmts):
        """نوشتن یک سطر داده با فرمت‌های متناظر."""
        for c, (v, f) in enumerate(zip(values, fmts)):
            ws.write(r, c, v, f)
        return r + 1

    def export(self, meta: dict, result: dict, settings: dict, history: list) -> bytes:
        """ساخت کتاب‌کار کامل گزارش صورت‌وضعیت و بازگرداندن بایت‌های فایل xlsx."""
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True, "default_date_format": "yyyy/mm/dd"})
        F = self._formats(wb)

        # فاز E-10 §۲ — قفلِ خروجیِ نهاییِ «تعدیل صورت‌وضعیت»: وقتی دورهٔ
        # کارکرد خالی است، موتور تمامِ کارکرد را به آخرین شاخصِ قطعی منتسب
        # می‌کند و ΔP با حالتِ «شاخصِ هر سه‌ماهه» متفاوتی می‌دهد (روی
        # پروژهٔ مرجع: ۱۳٬۳۲۰٬۳۶۰٬۹۵۷٫۱۲ به‌جای ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲). خروجیِ
        # نهایی نباید ساخته شود — فقط «پیش‌نویس» با واترمارک مجاز است.
        _tadil_res = (result.get("adjustment") or {}).get("tadil") or {}
        if _tadil_res.get("work_period_missing"):
            if "پیش‌نویس" not in (meta.get("report_type") or ""):
                raise ValueError(
                    "خطا — خروجیِ نهایی ساخته نمی‌شود: «تاریخ شروع دورهٔ "
                    "صورت‌وضعیت» و «تاریخ پایان دورهٔ صورت‌وضعیت» (دورهٔ "
                    "انجامِ کار) در تنظیماتِ پروژه وارد نشده‌اند. موتورِ "
                    "تعدیل در این حالت تمامِ کارکرد را به آخرین شاخصِ قطعی "
                    "منتسب می‌کند و مبلغِ تعدیل با حالتِ «شاخصِ هر سه‌ماهه» "
                    "متفاوت است. یا آن دو تاریخ را وارد کنید، یا خروجی را "
                    "به‌صورتِ «پیش‌نویس» بگیرید (واترمارکِ «پیش‌نویس – دورهٔ "
                    "کارکرد وارد نشده» روی همهٔ شیت‌ها می‌نشیند).")
            meta = {**meta,
                    "report_type": f"پیش‌نویس — {meta.get('report_type') or 'موقت'}",
                    "draft_banner": "پیش‌نویس – دورهٔ کارکرد وارد نشده"}

        # فاز E-10.1 §۳ — حالتِ ارائه: واترمارکِ «نسخهٔ نمایشی» روی همهٔ
        # شیت‌ها. خروجیِ دمو هرگز بدون این واترمارک ساخته نمی‌شود.
        if settings.get("demo_mode"):
            meta = {**meta, "demo_banner": DEMO_BANNER}

        # اگر ردیفی «نیازمند ورود» است، خروجی «پیش‌نویس» است (§۱۵-۴ بند ۶)
        if (result.get("needs_price_entry") or 0) > 0 and \
                "پیش‌نویس" not in (meta.get("report_type") or ""):
            meta = {**meta,
                    "report_type": f"پیش‌نویس — {meta.get('report_type') or 'موقت'}"}

        # اعتبارسنجی تاریخ‌ها (ایراد ۱۲) — بنر خطا روی شیت اول اگر
        # ترتیب تاریخ‌ها نقض شده باشد (محاسبه از سمت UI قبلاً متوقف شده
        # است؛ این یک لایهٔ دفاعی برای فراخوانی مستقیم export است).
        _date_errs = TechnicalOfficeEngine.validate_meta(meta)
        if _date_errs:
            wb.set_properties({"title": "صورت‌وضعیت — پیش‌نویس (تاریخ‌ها نامعتبر)"})

        # ═════════ برگه ۴: خلاصهٔ مالی و برآورد ═════════
        ws = wb.add_worksheet("خلاصهٔ مالی و برآورد")
        ws.set_column("A:A", 8)
        ws.set_column("B:B", 58)
        ws.set_column("C:C", 26)
        row = self._header_block(ws, F, meta, 3)
        # بنر خطاهای اعتبارسنجی تاریخ‌ها (ایراد ۱۲) — در صورت وجود
        if _date_errs:
            row = self._row(ws, row,
                            ["خطا — تاریخ‌های پروژه نامعتبر است و این خروجی "
                             "«پیش‌نویس» است: "
                             + " | ".join(f"{e['item']}: {e['message']}"
                                         for e in _date_errs),
                             "", ""],
                            [F["neg"]] * 3)
        row = self._row(ws, row, ["ردیف", "شرح", "مبلغ (ریال)"], [F["thead"]] * 3)
        s = settings
        idx = result.get("index")
        idx_note = ""
        if idx and idx.get("target_period") and idx.get("target_period") != idx.get("base_period"):
            idx_note = (f" — تعدیل به دورهٔ {idx['target_period']}"
                        + (" (شاخص موقت)" if idx.get("provisional") else ""))
        _fc_info = result.get("coefs", {}).get("floors", {}) or {}
        _fc_label = f"ضریب طبقات (× {fa(_fc_info.get('value') or 1.0)})"
        if _fc_info.get("eligible_lines"):
            _fc_label += (f" — فقط {fa(len(_fc_info['eligible_lines']))} ردیف مشمول؛ "
                          f"{fa(len(_fc_info.get('excluded_chapters') or []))} فصل مستثنی")
        chain = [
            ("۱", "الف) جمع ناخالص ردیف‌های فهرست‌بها" + idx_note, result["base_total"], False),
            ("۲", _fc_label, result["floors_amount"], False),
            ("۳", f"ضریب بالاسری (× {fa(s['overhead_coef'])})", result["overhead_amount"], False),
            ("۴", f"ضریب منطقه‌ای (× {fa((result.get('coefs', {}).get('regional', {}) or {}).get('value') or 1.0)})", result["regional_amount"], False),
            ("۵", f"تجهیز و برچیدن کارگاه (مبلغ واردشده)", result["site_setup"], False),
            ("۶", "ب) مبلغ ناخالص نهایی قابل پرداخت", result["gross_payable"], True),
        ]
        for no, label, val, bold in chain:
            row = self._row(ws, row, [no, label, round(val)],
                            [F["cell_c"], F["label"] if bold else F["cell"],
                             F["money_b"] if bold else F["neg"]])
        row = self._row(ws, row, ["", "مبلغ به حروف", money_to_words(result["grand_total"])],
                        [F["cell"], F["label"], F["label"]])
        row += 1
        # ── بلوک جداگانهٔ «خالص پرداختی» (کسورات قانونی — بر ناخالص اثر ندارد) ──
        row = self._row(ws, row, ["", "خالص پرداختی (محاسبهٔ جداگانه)", ""],
                        [F["cell"], F["label"], F["label"]])
        net_chain = [
            ("۱", "مبلغ ناخالص نهایی", result["gross_payable"], False),
            ("۲", f"کسورات: بیمه ({fa(s['insurance_pct'])}٪)", -result["insurance"], False),
            ("۳", f"کسورات: مالیات ({fa(s['tax_pct'])}٪)", -result["tax"], False),
            ("۴", f"کسورات: حسن انجام کار ({fa(s['good_job_pct'])}٪)", -result["good_job"], False),
            ("۵", "کسورات: پیش‌پرداخت", -result["advance_payment"], False),
            ("۶", "مجموع کسورات", -result["total_deductions"], True),
        ]
        for no, label, val, bold in net_chain:
            row = self._row(ws, row, [no, label, round(val)],
                            [F["cell_c"], F["label"] if bold else F["cell"],
                             F["money_b"] if bold else F["neg"]])
        row = self._row(ws, row, ["۷", "خالص پرداختی پس از کسورات", round(result["net_payable"])],
                        [F["cell_c"], F["net_l"], F["net"]])
        row += 1
        row = self._row(ws, row, ["فصل", "شرح فصل", "مبلغ کل (ریال)", "سهم (٪)"], [F["thead"]] * 4)
        first_ch_row = row
        for cst in result["chapter_sums"]:
            share = (cst["total"] / result["base_total"] * 100) if result["base_total"] else 0
            row = self._row(ws, row, [f"فصل {fa(cst['chapter'])}", cst["title"], round(cst["total"]),
                                      round(share, 2)],
                            [F["cell_c"], F["cell"], F["money"], F["num"]])
        # فرمول جمع فصول و سهم — با فرمول زندهٔ Excel
        # مقدار کش‌شده (value) هم نوشته می‌شود تا بیننده‌هایی که محاسبهٔ
        # مجدد نمی‌کنند (pandas/openpyxl data_only) عدد درست ببینند.
        last_ch_row = row - 1
        ch_sum = sum(round(cst["total"]) for cst in result["chapter_sums"])
        ws.write_formula(row, 2, f"=SUM(C{first_ch_row + 1}:C{last_ch_row + 1})",
                         F["money_b"], ch_sum)
        ws.write(row, 1, "جمع مبالغ فصل‌ها", F["chapter"])
        ws.write(row, 0, "", F["chapter"])
        row += 2

        # ── خلاصهٔ وضعیت قیمت‌ها (فاز C — §۱۵-۴ بند ۶) ──
        _ps = result.get("price_status_summary") or {}
        if _ps:
            row = self._row(ws, row,
                            ["وضعیت قیمت‌ها", "تعداد ردیف‌ها", "توضیح"],
                            [F["thead"]] * 3)
            _ps_desc = {
                "قطعی": "تطبیق دقیق با فهرست‌بهای ۱۴۰۴",
                "موقت": "ردیف تخمینی/موقت — نیاز به تأیید",
                "پیش‌فرض اپ": "بدون تطبیق با فهرست‌بها — قیمت پیش‌فرض برنامه",
                "دستی": "قیمت واردشدهٔ دستی (دارای منبع و سند)",
                "نیازمند ورود": "بازبینی تطبیق — قیمت باید وارد شود",
            }
            for _st in MANUAL_STATUSES:
                if _ps.get(_st):
                    row = self._row(ws, row,
                                    [_st, _ps[_st], _ps_desc.get(_st, "")],
                                    [F["cell_c"], F["cell_c"], F["cell"]])
            _npe = result.get("needs_price_entry") or 0
            if _npe:
                row = self._row(ws, row,
                                ["پیام", f"{fa(_npe)} ردیف نیازمند ورود قیمت هستند",
                                 "خروجی تا تأیید این ردیف‌ها «پیش‌نویس» است"],
                                [F["warn_y"]] * 3)
            _st_tot = result.get("starred_total") or 0
            if _st_tot:
                row = self._row(ws, row,
                                ["ردیف‌های ستاره‌دار", round(_st_tot),
                                 f"{fa_float(result.get('starred_pct') or 0, 1)}٪ از برآورد کل"],
                                [F["cell_c"], F["money"], F["cell"]])
            row += 1

        # ═════════ برگه ۲: صورت‌وضعیت / خلاصه‌متره ═════════
        ws = wb.add_worksheet("صورت وضعیت")
        for c, w in enumerate([7, 14, 58, 22, 10, 12, 14, 16, 10, 18, 12, 10, 34,
                               14, 14, 10, 12]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 17)
        row = self._row(ws, row,
                        ["ردیف", "کد فهرست‌بها", "شرح آیتم", "فصل", "واحد", "مقدار",
                         "بهای واحد (ریال)", "بهای کل (پایه، ریال)", "ضریب تعدیل",
                         "بهای کل (به‌هنگام، ریال)", "روش تطبیق", "اطمینان٪", "ارجاع بها",
                         "بهای فهرست (ریال)", "بهای دستی (ریال)", "اختلاف ٪", "وضعیت"],
                        [F["thead"]] * 17)
        current_ch = None
        line_rows = []
        for l in result["lines"]:
            if l["chapter"] != current_ch:
                current_ch = l["chapter"]
                ws.merge_range(row, 0, row, 16,
                               f"فصل {fa(current_ch)} — {chapter_title(current_ch)}", F["chapter"])
                row += 1
            line_rows.append(row)
            _manual = l.get("manual")
            row = self._row(ws, row, [
                l["row_no"], l["code"], l["desc"] + (" [بهای تخمینی]" if l["estimated"] else ""),
                l["chapter_title"], l["unit"], l["qty"],
                round(l["price"]), round(l["total"]),
                l.get("index_factor", 1.0), round(l.get("total_indexed", l["total"])),
                _match_label(l["method"]), round(l["confidence"] * 100),
                PRICE_REFS.get(l["code"], "—"),
                # ستون‌های قیمت دستی (فاز C)
                round(l["app_price"]) if l.get("app_price") else "—",
                round(l["price"]) if _manual else "—",
                (f"{l['diff_pct']:+.1f}" if l.get("diff_pct") is not None else "—"),
                l.get("price_status") or "قطعی"],
                [F["cell_c"], F["cell_c"], F["cell"], F["cell_c"], F["cell_c"], F["num"],
                 F["money"], F["money"], F["cell_c"], F["money_b"], F["cell_c"], F["cell_c"],
                 F["cell"], F["money"], F["money"], F["cell_c"], F["cell_c"]])
        # سطر جمع کل با فرمول زندهٔ Excel + مقدار کش‌شده
        if line_rows:
            qty_col = "F"   # اندیس ۵ — «مقدار»
            tot_col = "J"   # اندیس ۹ — «بهای کل (به‌هنگام)»
            tot_sum = sum(round(l.get("total_indexed", l["total"])) for l in result["lines"])
            qty_sum = sum(l["qty"] for l in result["lines"])
            ws.write_formula(row, 9, f"=SUM({tot_col}{line_rows[0] + 1}:{tot_col}{line_rows[-1] + 1})",
                             F["money_b"], tot_sum)
            ws.write_formula(row, 5, f"=SUM({qty_col}{line_rows[0] + 1}:{qty_col}{line_rows[-1] + 1})",
                             F["num"], qty_sum)
            ws.write(row, 2, "جمع کل ردیف‌های فهرست‌بها", F["chapter"])
            for cc in (0, 1, 3, 4, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16):
                ws.write(row, cc, "", F["chapter"])

        # ═════════ برگه ۳: مترهٔ ریز (ردیابی تا منبع) ═════════
        ws = wb.add_worksheet("متره ریز")
        for c, w in enumerate([9, 10, 32, 28, 24, 12, 16, 42, 12, 10]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 10)
        row = self._row(ws, row, ["ردیف BOQ", "کد", "منبع", "جدول", "عنصر / مارک",
                                  "گروه سازه‌ای", "مصالح", "شرح", "مقدار", "واحد"], [F["thead"]] * 10)
        for l in result["lines"]:
            srcs = l.get("sources", [])
            if not isinstance(srcs, list):
                srcs = []
            if not srcs:
                srcs = [{"source": l.get("note") or "—", "table": "—", "ref": "—", "group": "—",
                         "material": "—", "detail": "—", "qty": l["qty"], "unit": l["unit"]}]
            for x in srcs:
                unit_fa = {"m3": "مترمکعب", "m2": "مترمربع", "kg": "کیلوگرم",
                           "m": "مترطول", "count": "عدد"}.get(x.get("unit"), x.get("unit", l["unit"]))
                row = self._row(ws, row, [l["row_no"], l["code"], x.get("source", "—"),
                                          x.get("table", "—"), x.get("ref", "—"), x.get("group", "—"),
                                          x.get("material", "—"), x.get("detail", "—"),
                                          x.get("qty", 0), unit_fa],
                                [F["cell_c"], F["cell_c"], F["cell"], F["cell"], F["cell"],
                                 F["cell_c"], F["cell"], F["cell"], F["num"], F["cell_c"]])

        # ═════════ برگه ۴: لیستوفر آرماتور ═════════
        ws = wb.add_worksheet("لیستوفر آرماتور")
        for c, w in enumerate([22, 14, 12, 10, 8, 13, 12, 13, 12, 16]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 10)
        row = self._row(ws, row, ["مارک", "گروه سازه‌ای", "طبقه", "قطر (mm)", "تعداد",
                                  "طول هر شاخه (m)", "طول کل (m)", "وزن واحد (kg/m)",
                                  "وزن کل (kg)", "شکل خم"], [F["thead"]] * 10)
        for r in result["rebar"]:
            row = self._row(ws, row, [r["mark"], r["group"], r.get("level", "") or "",
                                      r["diameter"] or "—",
                                      r["count"], r.get("per_bar_length", 0.0),
                                      r["total_length"], r.get("unit_weight", 0.0),
                                      r["weight"], r["shape"] or ""],
                            [F["cell"], F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["num"], F["num"], F["num"], F["num"], F["cell_c"]])
        tot_w = sum(r["weight"] for r in result["rebar"])
        tot_len = sum(r["total_length"] for r in result["rebar"])
        tot_cnt = sum(r["count"] for r in result["rebar"])
        # جمع‌های فرعی به تفکیک قطر و گروه (ایراد ۱۱)
        by_d = {}
        by_g = {}
        for r in result["rebar"]:
            by_d[r["diameter"] or 0.0] = by_d.get(r["diameter"] or 0.0, 0.0) + r["weight"]
            by_g[r["group"]] = by_g.get(r["group"], 0.0) + r["weight"]
        row += 1
        row = self._row(ws, row, ["جمع به تفکیک قطر", "", "", "", "", "", "", "", "", ""],
                        [F["chapter"]] * 10)
        for d in sorted(by_d):
            row = self._row(ws, row, ["", f"قطر {fa(f'{d:g}')} mm", "", "", "", "", "", "",
                                      by_d[d], ""],
                            [F["cell"], F["label"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["cell_c"], F["cell_c"], F["cell_c"], F["num"], F["cell_c"]])
        row = self._row(ws, row, ["جمع به تفکیک گروه", "", "", "", "", "", "", "", "", ""],
                        [F["chapter"]] * 10)
        for g in sorted(by_g):
            row = self._row(ws, row, ["", g, "", "", "", "", "", "", by_g[g], ""],
                            [F["cell"], F["label"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["cell_c"], F["cell_c"], F["cell_c"], F["num"], F["cell_c"]])
        row = self._row(ws, row, ["جمع کل", "", "", "", tot_cnt, "", tot_len, "",
                                  tot_w, ""],
                        [F["chapter"]] * 5 + [F["num"], F["chapter"], F["chapter"],
                                              F["money_b"], F["chapter"]])

        # ═════════ برگه ۵: سوابق تجمعی صورت‌وضعیت‌ها ═════════
        ws = wb.add_worksheet("سوابق صورت وضعیت")
        for c, w in enumerate([18, 10, 14, 14, 20, 20, 20, 20]):
            ws.set_column(c, c, w)
        # ستون‌های میلادی مخفی (ایراد ۱۳): متن شمسی برای نمایش + میلادی
        # واقعی برای محاسبات Excel (مرتب‌سازی/تفاضل تاریخ). ستون‌های I و J.
        ws.set_column(8, 9, 12, F["date_iso"], {"hidden": True})
        row = self._header_block(ws, F, meta, 10)
        row = self._row(ws, row, ["شماره صورت‌وضعیت", "نوع", "دوره از", "دوره تا", "ناخالص تجمعی (ریال)",
                                  "کسورات تجمعی (ریال)", "خالص تجمعی (ریال)", "کارکرد این دوره (ریال)",
                                  "دوره از (میلادی)", "دوره تا (میلادی)"], [F["thead"]] * 10)
        prev = None
        for h in history:
            current = h["net_payable"] - (prev["net_payable"] if prev else 0)
            row = self._row(ws, row, [h["report_no"], h["report_type"], h["period_start"], h["period_end"],
                                      round(h["gross_payable"]), round(h["total_deductions"]),
                                      round(h["net_payable"]), round(current)],
                            [F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["money"], F["money"], F["money"], F["money_b"]])
            # ستون‌های مخفی میلادی (ایراد ۱۳)
            _ps = jalali_to_iso(h.get("period_start"))
            _pe = jalali_to_iso(h.get("period_end"))
            if _ps:
                ws.write_datetime(row - 1, 8, datetime.strptime(_ps, "%Y-%m-%d"), F["date_iso"])
            else:
                ws.write(row - 1, 8, "", F["date_iso"])
            if _pe:
                ws.write_datetime(row - 1, 9, datetime.strptime(_pe, "%Y-%m-%d"), F["date_iso"])
            else:
                ws.write(row - 1, 9, "", F["date_iso"])
            prev = h

        # ═════════ برگه ۶: گزارش کیفیت ═════════
        ws = wb.add_worksheet("کیفیت تطبیق")
        ws.set_column("A:A", 36)
        ws.set_column("B:B", 64)
        row = self._header_block(ws, F, meta, 2)
        row = self._row(ws, row, ["شاخص", "مقدار"], [F["thead"]] * 2)
        q = result["quality"]
        for label, val in [
            ("جداول Schedule خوانده‌شده", q["tables_parsed"]),
            ("جداول نامشخص", q["tables_unknown"]),
            ("رکوردهای Mapping", q["mapping_records"]),
            ("ردیف‌های دادهٔ خوانده‌شده", q["rows_read"]),
            ("ردیف‌های مترهٔ تولیدشده", q["lines_matched"]),
            ("تطبیق دقیق/دستی/مستقیم", q["lines_exact"]),
            ("تطبیق فازی", q["lines_fuzzy"]),
            ("ردیف‌های با بهای تخمینی", q["lines_estimated"]),
            ("ردیف‌های نیازمند بررسی", q["lines_review"]),
        ]:
            row = self._row(ws, row, [label, val], [F["label"], F["cell_c"]])
        row += 1
        row = self._row(ws, row, ["هشدارها", ""], [F["chapter"], F["chapter"]])
        for w in q["warnings"]:
            row = self._row(ws, row, ["", w], [F["cell"], F["cell"]])

        # ═════════ برگه ۷: ضریب طبقات (ایراد ۳) ═════════
        fc = result.get("coefs", {}).get("floors", {})
        calc = fc.get("calc") or {}
        ws = wb.add_worksheet("ضریب طبقات")
        for c, w in enumerate([22, 18, 12, 15, 15, 15, 10, 18]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 8)
        row = self._row(ws, row,
                        ["فرمول رسمی پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴",
                         fc.get("formula", ""), "", "", "", "", "", ""],
                         [F["chapter"], F["label"], F["cell"], F["cell"],
                          F["cell"], F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["مخرج به‌کاررفته", calc.get("divisor", "100×S"),
                         "P با مخرج جایگزین: " + fa_float(calc.get("p_alt") or 1.0, 6),
                         "صورت کسر: " + fa_float(calc.get("num") or 0, 2),
                         "مخرج کسر: " + fa_float(calc.get("den") or 0, 2),
                         "", "", ""],
                         [F["label"], F["cell_c"], F["label"], F["label"],
                          F["label"], F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["ضریب نهایی P", fa_float(fc.get("value") or 1.0, 6),
                         "وضعیت: " + (fc.get("status") or "—"),
                         "منبع: " + (fc.get("source") or "—"), "", "", "", ""],
                         [F["label"], F["money_b"], F["label"], F["label"],
                          F["cell"], F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["قاعدهٔ اعمال", fc.get("clause", ""), "", "", "", "", "", ""],
                         [F["label"], F["label"], F["cell"], F["cell"],
                          F["cell"], F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["ارجاع", "فرمول: پیوست ۲ فهرست‌بهای پایه ابنیه ۱۴۰۴ "
                                  "(متن رسمی دریافت‌شده از کاربر).",
                         "", "", "", "", "", ""],
                         [F["label"], F["cell"], F["cell"], F["cell"],
                          F["cell"], F["cell"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["طبقه (تراز Revit)", "نوع", "نماد (شماره i)",
                         "مساحت مدل (m²)", "مساحت دستی (m²)", "مساحت مؤثر (m²)",
                         "ضریب", "سهم (مساحت × ضریب)"],
                        [F["thead"]] * 8)
        _KIND_LABEL = {"below_base": "زیر همکف", "ground": "همکف",
                       "above": "بالاتر از همکف", "roof": "بام/مرجع (مستثنی)",
                       "none": "غیرطبقه‌ای (مستثنی)"}
        for r in fc.get("rows") or []:
            kind = _KIND_LABEL.get(r["kind"], r["kind"])
            if r["kind"] == "ground":
                sym, fac_lbl = "B0", "۰"
            elif r["kind"] == "below_base":
                sym, fac_lbl = "B" + fa(r["index"]), fa(r["index"])
            elif r["kind"] == "above":
                sym, fac_lbl = "F" + fa(r["index"]), fa(r["index"])
            else:
                sym, fac_lbl = "—", "مستثنی"
            am = r["area_model"]
            au = r["area_manual"]
            eff = r["area"]
            row = self._row(ws, row,
                            [r["name"], kind, sym,
                             fa_float(am) if isinstance(am, (int, float)) else "—",
                             fa_float(au) if isinstance(au, (int, float)) else "—",
                             fa_float(eff) if isinstance(eff, (int, float))
                             else "نیازمند ورود دستی",
                             fac_lbl,
                             "—" if r["kind"] in ("roof", "none")
                             else fa_float(r["index"] * (eff or 0))],
                            [F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["cell_c"], F["cell_c"], F["cell_c"], F["money"]])
        fp = fc.get("footprint")
        row += 1
        if fp:
            row = self._row(ws, row,
                            ["رَدپای ساختمان (از بتن مگر)",
                             fa_float(fp["volume"], 2) + " m³ ÷ "
                             + fa_float(fp["thickness"], 2) + " m = "
                             + fa_float(fp["area"], 1) + " m²"
                             + (" (ضخامت پیش‌فرض اپ ۱۰ cm)"
                                if fp["assumed_thickness"] else ""),
                             "وضعیت: " + fp.get("status", "تخمینی"),
                             "راهنما برای مساحت همکف/زیرهمکف — مقدار دقیق "
                             "را از نقشه‌های مصوب وارد کنید", "", "", "", ""],
                            [F["label"], F["cell"], F["label"], F["label"],
                             F["cell"], F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["یادداشت", "مساحت «مدل» فقط برای ترازهایی خوانده می‌شود "
                         "که المان سقف (دست Floors) دارند؛ طبقات دیگر را از "
                         "نقشه‌های مصوب در تنظیمات → floors_data وارد کنید.", "", "", "", "", ""],
                        [F["label"], F["cell"], F["cell"], F["cell"],
                         F["cell"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["برداشت", "در جدول بالا اگر مساحت دستی وارد شده باشد، "
                         "جایگزین مساحت مدل می‌شود (مقدار مدل کنار آن باقی می‌ماند).",
                         "", "", "", "", ""],
                        [F["label"], F["cell"], F["cell"], F["cell"],
                         F["cell"], F["cell"], F["cell"]])

        row += 2
        row = self._row(ws, row,
                        ["ردیف‌های مشمول ضریب طبقات (پیوست ۲ — بند ۱-۳)",
                         "فصول مستثنی: " + "، ".join(fc.get("excluded_chapters") or []) or "—",
                         "", "", "", "", ""],
                        [F["chapter"], F["label"], F["cell"], F["cell"],
                         F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["کد ردیف", "شرح", "فصل", "مبلغ (ریال)", "", "", ""],
                        [F["thead"]] * 7)
        for el in fc.get("eligible_lines") or []:
            row = self._row(ws, row,
                            [el["code"], el["desc"], el["chapter"],
                             round(el["total"]), "", "", ""],
                            [F["cell_c"], F["cell"], F["cell_c"], F["money"],
                             F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["جمع مشمول", fa_float(fc.get("eligible_total") or 0, 0),
                         "", "", "", "", ""],
                        [F["label"], F["money_b"], F["cell"], F["cell"],
                         F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["جمع مستثنی", fa_float(fc.get("excluded_total") or 0, 0),
                         "جمع کل ردیف‌ها: " + fa_float(result["base_total"], 0),
                         "", "", "", ""],
                        [F["label"], F["money_b"], F["label"], F["cell"],
                         F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["مبلغ ضریب طبقات",
                         "مشمول × P + مستثنی = "
                         + fa_float(fc.get("eligible_total") or 0, 0) + " × "
                         + fa_float(fc.get("value") or 1.0, 6) + " + "
                         + fa_float(fc.get("excluded_total") or 0, 0) + " = "
                         + fa_float(fc.get("floors_amount") or 0, 0),
                         "", "", "", "", ""],
                        [F["label"], F["label"], F["cell"], F["cell"],
                         F["cell"], F["cell"], F["cell"]])
        row += 1

# ═════════ برگه ۸: رجیستری مرکزی هشدارها (ایراد ۱۰) ═════════

        # ═════════ برگه ۹: موتور تعدیل پیمان (فاز B — موتور اول) ═════════
        # این شیت فقط زمانی ساخته می‌شود که موتور «تعدیل پیمان» فعال باشد.
        # هرگز با شیت «برآورد به‌هنگام» ادغام نمی‌شود (قاعدهٔ طلایی ۵).
        adj = result.get("adjustment") or {}
        _tadil = adj.get("tadil")
        if _tadil:
            ws = wb.add_worksheet("تعدیل پیمان")
            for c, w in enumerate([10, 30, 22, 14, 14, 14, 24, 30]):
                ws.set_column(c, c, w)
            row = self._header_block(ws, F, meta, 8)
            _miss = "، ".join("%s (%s %s)" % (c, w, q) for c, w, q in (_tadil.get("missing") or []))
            if _tadil.get("error"):
                row = self._row(ws, row, ["توقف موتور: " + str(_tadil["error"])]
                                          + [""] * 7, [F["neg"]] * 8)
            elif _tadil.get("incomplete"):
                row = self._row(ws, row, ["ناکامل — شاخص برخی فصل‌ها ناموجود است: "
                                          + _miss + ". شاخص دستی را در سایدبار وارد کنید."]
                                          + [""] * 7, [F["neg"]] * 8)
            elif _tadil.get("draft"):
                row = self._row(ws, row, ["پیش‌نویس — مقادیر منبع تصویری (بخشنامه ۲۰۸۰ و "
                                          "شاخص موقت ۱۴۰۵) تأیید نشده‌اند؛ تا تأیید کاربر "
                                          "این خروجی رسمی نیست."] + [""] * 7, [F["warn_y"]] * 8)
            row = self._row(ws, row, ["فرمول قانونی تعدیل پیمان", _tadil.get("formula", "")]
                                     + [""] * 6, [F["chapter"]] + [F["cell"]] * 7)
            _k_note = "پیش‌فرض اپ — منبع تصویری بخشنامه ۲۰۸۰، نیازمند تأیید"
            # فاز E-10 §۲ — برچسبِ علی‌الحساب وقتی وضعیتِ اتمامِ کار در مدتِ
            # پیمان نامشخص است (k = ۰٫۹۵ — بند ۱-۸). خروجی مجاز است ولی
            # «علی‌الحساب – k = ۰٫۹۵» می‌ماند تا تکلیفِ قطعی روشن شود.
            if _tadil.get("k_provisional"):
                _k_note = ("علی‌الحساب — k = ۰٫۹۵: وضعیتِ اتمامِ کار در مدتِ "
                           "پیمان نامشخص است (بند ۱-۸). " + _k_note)
            row = self._row(ws, row, ["ضریب قانونی (k)", fa_float(_tadil.get("coef") or 0, 2),
                                      _k_note,
                                      "", "", "", "", ""],
                                     [F["label"], F["money"], F["warn_y"]] + [F["cell"]] * 5)
            row = self._row(ws, row, ["دورهٔ مبنا (Io)", _io_label(_tadil),
                                      "شاخص هر فصل از پیوست ۳ (صفحه‌های ۶–۷)", "", "", "", "", ""],
                                     [F["label"], F["label"], F["label"]] + [F["cell"]] * 5)
            _sp = _tadil.get("split") or []
            row = self._row(ws, row, ["دوره‌های انجام کار",
                                      "، ".join("%s (%s٪)" % (_quarter_label(q), fa_float(f * 100, 1))
                                                for q, f in _sp) if len(_sp) > 1
                                      else _quarter_label(_sp[0][0]) if _sp else "—",
                                      "تقسیم کارکرد بین سه‌ماهه‌ها (بر اساس روزها)",
                                      "", "", "", "", ""],
                                     [F["label"], F["label"], F["label"]] + [F["cell"]] * 5)
            row += 1
            row = self._row(ws, row, ["زنجیرهٔ مبلغ پایه (A) — مبالغ به ریال", "", "", "", "", "", "", ""],
                                     [F["chapter"]] * 8)
            for _lbl, _amt, _note in (_tadil.get("chain") or []):
                row = self._row(ws, row, [_lbl, fa_float(_amt, 0), _note, "", "", "", "", ""],
                                         [F["label"], F["money"], F["label"]] + [F["cell"]] * 5)
            row += 1
            row = self._row(ws, row, ["فصل", "عنوان فصل", "مبلغ پایه (A_c، ریال)", "شاخص Io",
                                      "شاخص It", "نسبت It/Io", "مبلغ تعدیل (ΔP_c، ریال)",
                                      "وضعیت و منبع"], [F["thead"]] * 8)
            for _r in _tadil.get("chapters") or []:
                row = self._row(ws, row,
                                [_r["chapter"], _r["title"], fa_float(_r["amount"], 0),
                                 fa_float(_r["io"], 1), fa_float(_r["it"], 1),
                                 fa_float(_r["ratio"], 4), fa_float(_r["value"], 0),
                                 _r["status"] + " — " + _r["src"]],
                                [F["label"], F["label"], F["money"], F["money"],
                                 F["money"], F["money"], F["money_b"], F["warn_y"]])
            _sr = _tadil.get("setup_row")
            if _sr:
                row = self._row(ws, row,
                                ["تجهیز", "تجهیز و برچیدن کارگاه (شاخص رشته — بند ۴)",
                                 fa_float(_sr["amount"], 0), fa_float(_sr["io"], 1),
                                 fa_float(_sr["it"], 1), fa_float(_sr["ratio"], 4),
                                 fa_float(_sr["value"], 0),
                                 _sr["status"] + " — " + _sr["src"]],
                                [F["label"], F["label"], F["money"], F["money"],
                                 F["money"], F["money"], F["money_b"], F["warn_y"]])
            _nr = _tadil.get("new_work_row")
            if _nr:
                row = self._row(ws, row,
                                ["کار جدید",
                                 "کار جدید (%s) - بندهای ۳-۱..۳-۵"
                                 % (_nr.get("method") or ""),
                                 fa_float(_nr["amount"], 0),
                                 fa_float(_nr["io"], 1),
                                 fa_float(_nr["it"], 1),
                                 fa_float(_nr["ratio"], 4),
                                 fa_float(_nr["value"], 0),
                                 _nr["status"] + " - " + _nr["src"]],
                                [F["label"], F["label"], F["money"],
                                 F["money"], F["money"], F["money"],
                                 F["money_b"], F["warn_y"]])
            row += 1
            # ── جدول فصل × سه‌ماهه: شاخص It هر فصل در هر سه‌ماههٔ کارکرد ──
            # (ستون زرد = شاخص موقت ۱۴۰۵Q1). فقط وقتی بیش از یک سه‌ماهه
            # در دورهٔ کارکرد وجود دارد.
            _spq = _tadil.get("split") or []
            if len(_spq) > 1:
                row = self._row(ws, row,
                                ["شاخص It هر فصل در هر سه‌ماههٔ کارکرد "
                                 "(ستون زرد = موقت)"] + [""] * 7,
                                [F["chapter"]] * 8)
                _qhead = ["فصل", "عنوان فصل"] \
                    + [_quarter_label(q) + " (%s٪)" % fa_float(f * 100, 1)
                       for q, f in _spq]
                _pad = max(0, 8 - len(_qhead))
                row = self._row(ws, row, _qhead + [""] * _pad,
                                [F["thead"]] * 8)
                for _r in _tadil.get("chapters") or []:
                    _qs = _r.get("quarters") or []
                    _vals = [fa_float(_iv, 1) for _q, _iv, _st in _qs]
                    _fmts = [F["warn_y"] if _st == "موقت" else F["money"]
                             for _q, _iv, _st in _qs]
                    _pad2 = max(0, 8 - 2 - len(_vals))
                    row = self._row(
                        ws, row,
                        [_r["chapter"], _r["title"]] + _vals + [""] * _pad2,
                        [F["label"], F["label"]] + _fmts
                        + [F["cell"]] * _pad2)
                row += 1
            # ── فاز E-6: جدول ضریب هر فصل در هر سه‌ماهه (بند ۸-۲) ──
            if len(_spq) > 1 and any(_r.get("coef_rows")
                                    for _r in _tadil.get("chapters") or []):
                row = self._row(ws, row,
                                ["ضریب تعدیل هر فصل در هر سه‌ماههٔ کارکرد "
                                 "(بند ۸-۲: خام با ۳ رقم، گردشده با ۲ رقم)"]
                                + [""] * 7, [F["chapter"]] * 8)
                row = self._row(ws, row,
                                ["فصل", "عنوان فصل", "سه‌ماهه",
                                 "ضریب خام", "ضریب گردشده", "ΔP این گام",
                                 "وضعیت", ""],
                                [F["thead"]] * 8)
                _fsp = dict(_spq)
                for _r in _tadil.get("chapters") or []:
                    for _q, _raw, _used in _r.get("coef_rows") or []:
                        _fq = _fsp.get(_q) or 0.0
                        row = self._row(
                            ws, row,
                            [_r["chapter"], _r["title"], _quarter_label(_q),
                             fa_float(_raw, 3), fa_float(_used, 2),
                             fa_float(_used * _r["amount"] * _fq, 0),
                             _r["status"], ""],
                            [F["label"], F["label"], F["label"],
                             F["money"], F["money"], F["money_b"],
                             F["warn_y"], F["cell"]])
                _sr2 = _tadil.get("setup_row")
                if _sr2 and _sr2.get("delta_k095") is not None:
                    for _q, _raw, _used in (_sr2.get("coef_rows") or []):
                        _fq = _fsp.get(_q) or 0.0
                        row = self._row(
                            ws, row,
                            ["تجهیز", "تجهیز و برچیدن (شاخص رشته — بند ۴)",
                             _quarter_label(_q),
                             fa_float(_raw, 3), fa_float(_used, 2),
                             fa_float(_used * _sr2["amount"] * _fq, 0),
                             "رشته‌ای", ""],
                            [F["label"], F["label"], F["label"],
                             F["money"], F["money"], F["money_b"],
                             F["warn_y"], F["cell"]])
                row += 1
            if not _tadil.get("incomplete"):
                row = self._row(ws, row, ["جمع تعدیل (شامل علی‌الحساب، ریال)",
                                          "k × Σ_c (It_c/Io_c − 1) × A_c = "
                                          + fa_float(_tadil.get("delta_p") or 0, 0),
                                          "ضریب k = " + fa_float(_tadil.get("coef") or 0, 2),
                                          "", "", "", "", ""],
                                         [F["label"], F["money_b"], F["label"]] + [F["cell"]] * 5)
                _dp_all, _dp_def, _dp_prov = _split_rounded(
                    _tadil.get("delta_p") or 0.0,
                    _tadil.get("delta_p_definitive") or 0.0)
                if abs(_dp_prov) >= 0.01:
                    row = self._row(ws, row, ["بخش قطعی (شاخص‌های قطعی ۱۴۰۴، ریال)",
                                              fa_float(_dp_def, 0),
                                              "مجموع با شاخص‌های قطعی ۱۴۰۴",
                                              "", "", "", "", ""],
                                             [F["label"], F["money"], F["label"]]
                                             + [F["cell"]] * 5)
                    row = self._row(ws, row, ["بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1، ریال)",
                                              fa_float(_dp_prov, 0),
                                              "علی‌الحساب = ضریب موقت × قطعی ۱۴۰۴Q4",
                                              "", "", "", "", ""],
                                             [F["label"], F["money"], F["warn_y"]]
                                             + [F["cell"]] * 5)
                # ── فاز E-6: مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) ──
                if abs(_tadil.get("k_diff") or 0) >= 0.01:
                    row = self._row(
                        ws, row,
                        ["مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ — همراه قطعی، بند ۸-۴، ریال)",
                         fa_float(_tadil.get("k_diff") or 0, 0),
                         "همزمان با صورت‌وضعیت قطعی پرداخت می‌شود",
                         "", "", "", "", ""],
                        [F["label"], F["money"], F["warn_y"]]
                        + [F["cell"]] * 5)
                # ── فاز E-6 Part C گام ۴: کسر ۵٪ فسخ با قصور (بند ۷) ──
                if abs(_tadil.get("deduction_fault") or 0) >= 0.01:
                    row = self._row(
                        ws, row,
                        ["کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷، ریال)",
                         fa_float(-(_tadil.get("deduction_fault") or 0), 0),
                         "۵٪ از مبلغ تعدیل کسر می‌شود",
                         "", "", "", "", ""],
                        [F["label"], F["money"], F["warn_y"]]
                        + [F["cell"]] * 5)
                row = self._row(ws, row, ["مبلغ نهایی (A + جمع تعدیل، ریال)",
                                          fa_float(_tadil.get("result_amount") or 0, 0),
                                          "وضعیت: " + ("پیش‌نویس" if _tadil.get("draft")
                                                       else "تأییدشده"),
                                          "", "", "", "", ""],
                                         [F["label"], F["money_b"], F["warn_y"]] + [F["cell"]] * 5)
                _p = _tadil.get("params") or {}
                row = self._row(ws, row, ["شرط تأخیر", str(_tadil.get("delay_mode")),
                                          "نحوهٔ پیش‌پرداخت: " + str(_tadil.get("advance_mode")),
                                          "تعدیل منفی: " + ("مجاز" if _p.get("allow_negative")
                                                             else "غیرمجاز"),
                                          "تاریخ تسلیم پیشنهاد: "
                                          + str(_p.get("proposal_date") or "—"),
                                          "ضریب موقت ۱۴۰۵: "
                                          + (fa_float(_p["provisional_coef"], 3)
                                             if _p.get("provisional_coef") else "—"),
                                          "", ""],
                                         [F["label"], F["label"], F["label"], F["label"],
                                          F["label"], F["label"], F["cell"], F["cell"]])
            row = self._row(ws, row, ["منبع و وضعیت", _tadil.get("source") or "",
                                      "", "", "", "", "", ""],
                                     [F["label"], F["label"]] + [F["cell"]] * 6)
            row += 1

        # ═════════ برگه ۱۰: موتور برآورد به‌هنگام (فاز B — موتور دوم) ═════════
        _baravord = adj.get("baravord")
        if _baravord:
            ws = wb.add_worksheet("برآورد به‌هنگام")
            for c, w in enumerate([10, 30, 22, 14, 14, 14, 24, 30]):
                ws.set_column(c, c, w)
            row = self._header_block(ws, F, meta, 8)
            _miss = "، ".join("%s (%s %s)" % (c, w, q) for c, w, q in (_baravord.get("missing") or []))
            if _baravord.get("error"):
                row = self._row(ws, row, ["توقف موتور: " + str(_baravord["error"])]
                                          + [""] * 7, [F["neg"]] * 8)
            elif _baravord.get("incomplete"):

                row = self._row(ws, row, ["ناکامل — شاخص برخی فصل‌ها ناموجود است: "
                                          + _miss + "."] + [""] * 7, [F["neg"]] * 8)
            elif _baravord.get("draft"):
                row = self._row(ws, row, ["پیش‌نویس — شاخص‌ها استخراج‌شده از PDF هستند و "
                                          "تأیید نشده‌اند."] + [""] * 7, [F["warn_y"]] * 8)
            row = self._row(ws, row, ["فرمول برآورد به‌هنگام", _baravord.get("formula", "")]
                                     + [""] * 6, [F["chapter"]] + [F["cell"]] * 7)
            row = self._row(ws, row, ["دورهٔ مبنا (Io)", _io_label(_baravord),
                                      "", "", "", "", "", ""],
                                     [F["label"], F["label"]] + [F["cell"]] * 6)
            row = self._row(ws, row, ["دورهٔ انجام کار (It)",
                                      _quarter_label(_baravord.get("it_q")), "", "", "", "", "", ""],
                                     [F["label"], F["label"]] + [F["cell"]] * 6)
            # ══ فاز E-8 §۳.۱: برچسبِ موقت/قطعی + ضریبِ موقت روی هر خروجی ══
            row = self._row(ws, row, ["وضعیت دورهٔ It",
                                      _baravord.get("it_status") or "—",
                                      "", "", "", "", "", ""],
                                     [F["label"], F["label"]] + [F["cell"]] * 6)
            _prov_v = _baravord.get("prov")
            if _prov_v is not None and _baravord.get("it_status") == "موقت":
                _pt = _baravord.get("prov_trace") or {}
                row = self._row(ws, row,
                                ["ضریب موقت (۱۴۰۵Q1)", fa_float(_prov_v, 4),
                                 ("دستی — نیازمند تأیید" if _baravord.get("prov_manual")
                                  else "محاسبه از CPI + m=%s" % fa(_pt.get("m")))
                                 + " — موقت = این ضریب × آخرین شاخص قطعی (۱۴۰۴Q4)",
                                 "", "", "", "", ""],
                                [F["label"], F["money"], F["label"]]
                                + [F["cell"]] * 5)
            row += 1
            row = self._row(ws, row, ["زنجیرهٔ مبلغ پایه (A) — مبالغ به ریال", "", "", "", "", "", "", ""],
                                     [F["chapter"]] * 8)
            for _lbl, _amt, _note in (_baravord.get("chain") or []):
                row = self._row(ws, row, [_lbl, fa_float(_amt, 0), _note, "", "", "", "", ""],
                                         [F["label"], F["money"], F["label"]] + [F["cell"]] * 5)
            row += 1
            row = self._row(ws, row, ["فصل", "عنوان فصل", "مبلغ پایه (A_c، ریال)", "شاخص Io",
                                      "شاخص It", "نسبت It/Io", "مبلغ به‌هنگام‌شده (ریال)",
                                      "وضعیت و منبع"], [F["thead"]] * 8)
            for _r in _baravord.get("chapters") or []:
                row = self._row(ws, row,
                                [_r["chapter"], _r["title"], fa_float(_r["amount"], 0),
                                 fa_float(_r["io"], 1), fa_float(_r["it"], 1),
                                 fa_float(_r["ratio"], 4), fa_float(_r["value"], 0),
                                 _r["status"] + " — " + _r["src"]],
                                [F["label"], F["label"], F["money"], F["money"],
                                 F["money"], F["money"], F["money_b"], F["warn_y"]])
            _sr = _baravord.get("setup_row")
            if _sr:
                row = self._row(ws, row,
                                ["تجهیز", "تجهیز و برچیدن کارگاه (شاخص رشته — بند ۴)",
                                 fa_float(_sr["amount"], 0), fa_float(_sr["io"], 1),
                                 fa_float(_sr["it"], 1), fa_float(_sr["ratio"], 4),
                                 fa_float(_sr["value"], 0),
                                 _sr["status"] + " — " + _sr["src"]],
                                [F["label"], F["label"], F["money"], F["money"],
                                 F["money"], F["money"], F["money_b"], F["warn_y"]])
            _nr = _baravord.get("new_work_row")
            if _nr:
                row = self._row(ws, row,
                                ["کار جدید",
                                 "کار جدید (%s) - بندهای ۳-۱..۳-۵"
                                 % (_nr.get("method") or ""),
                                 fa_float(_nr["amount"], 0),
                                 fa_float(_nr["io"], 1),
                                 fa_float(_nr["it"], 1),
                                 fa_float(_nr["ratio"], 4),
                                 fa_float(_nr["value"], 0),
                                 _nr["status"] + " - " + _nr["src"]],
                                [F["label"], F["label"], F["money"],
                                 F["money"], F["money"], F["money"],
                                 F["money_b"], F["warn_y"]])
            row += 1
            if not _baravord.get("incomplete"):
                row = self._row(ws, row, ["برآورد به‌هنگام‌شده (ریال)",
                                          "A_new = Σ_c A_c × It_c/Io_c = "
                                          + fa_float(_baravord.get("result_amount") or 0, 0),
                                          "وضعیت: " + ("پیش‌نویس" if _baravord.get("draft")
                                                       else "تأییدشده"),
                                          "", "", "", "", ""],
                                         [F["label"], F["money_b"], F["warn_y"]] + [F["cell"]] * 5)
                row = self._row(ws, row,
                                ["جمع کل به‌هنگام‌شده (قیمت پیمان)",
                                 fa_float(_baravord.get("grand_updated") or 0, 0),
                                 "بالاسری × منطقه‌ای × پیشنهادی پس از It/Io "
                                 "اعمال شد — جمع کل فعلی: "
                                 + fa_float(_baravord.get("grand_current") or 0, 0),
                                 "", "", "", "", ""],
                                [F["label"], F["money_b"], F["warn_y"]]
                                + [F["cell"]] * 5)
            row = self._row(ws, row, ["منبع و وضعیت", _baravord.get("source") or "",
                                      "", "", "", "", "", ""],
                                     [F["label"], F["label"]] + [F["cell"]] * 6)
            row += 1

        # ═════════ برگه ۱۱: تفکیک بخش قطعی و علی‌الحساب (فاز B) ═════════
        # بخش علی‌الحساب = تعدیل مربوط به دورهٔ موقت ۱۴۰۵Q1 (ضریب موقت ×
        # آخرین شاخص قطعی) — فقط برای موتور تعدیل پیمان.
        if _tadil:
            ws = wb.add_worksheet("بخش قطعی و علی‌الحساب")
            for c, w in enumerate([10, 30, 22, 22, 22, 22, 30]):
                ws.set_column(c, c, w)
            row = self._header_block(ws, F, meta, 7)
            _has_prov = any(TechnicalOfficeEngine._quarter_is_provisional(q)
                            for q, _f in (_tadil.get("split") or []))
            # گام ۶ (بندهای ۲-۱/۲-۲): مسیرِ حل‌شدهٔ شاخص
            _imr = _tadil.get("index_method_resolved")
            if _imr:
                row = self._row(ws, row,
                                ["مسیر شاخص",
                                 "%s — %s (گام ۶ — بندهای ۲-۱/۲-۲)"
                                 % (_imr["method"], _imr["source"])]
                                + [""] * 5,
                                [F["label"], F["label"]] + [F["cell"]] * 5)
            if not _has_prov:
                row = self._row(ws, row, ["در این محاسبه بخش علی‌الحساب وجود ندارد — "
                                          "دورهٔ انجام کار داخل سه‌ماهه‌های قطعی ۱۴۰۴ است "
                                          "یا ضریب موقت ۱۴۰۵Q1 وارد نشده است."]
                                          + [""] * 6, [F["label"]] * 7)

            row = self._row(ws, row, ["فصل", "عنوان فصل", "مبلغ پایه (A_c، ریال)",
                                       "بخش قطعی (ریال)", "بخش علی‌الحساب (ریال)",
                                       "جمع تعدیل (شامل علی‌الحساب، ریال)", "توضیح"],
                                      [F["thead"]] * 7)

            _td = 0.0
            _tp = 0.0
            for _r in _tadil.get("chapters") or []:
                _d = _r.get("delta") or 0.0
                _dd = _r.get("delta_definitive") or 0.0
                _td += _dd
                _tp += _d
                row = self._row(ws, row,
                                 [_r["chapter"], _r["title"], fa_float(_r["amount"], 0),
                                  fa_float(_dd, 0), fa_float(_d - _dd, 0),
                                  fa_float(_d, 0),
                                  "علی‌الحساب = ضریب موقت × قطعی ۱۴۰۴Q4" if _d != _dd
                                  else "همه قطعی"],
                                 [F["label"], F["label"], F["money"], F["money"],
                                  F["money"], F["money"], F["label"]])

            _sr = _tadil.get("setup_row")
            if _sr:
                _d = _sr.get("delta") or 0.0
                _dd = _sr.get("delta_definitive") or 0.0
                _td += _dd
                _tp += _d
                row = self._row(ws, row,
                                 ["تجهیز", "تجهیز و برچیدن (شاخص رشته)",
                                  fa_float(_sr["amount"], 0), fa_float(_dd, 0),
                                  fa_float(_d - _dd, 0), fa_float(_d, 0),
                                  "علی‌الحساب = ضریب موقت × قطعی ۱۴۰۴Q4" if _d != _dd
                                  else "همه قطعی"],
                                 [F["label"], F["label"], F["money"], F["money"],
                                  F["money"], F["money"], F["label"]])
            _nr = _tadil.get("new_work_row")
            if _nr:
                _d = _nr.get("delta") or 0.0
                _dd = _nr.get("delta_definitive") or 0.0
                _td += _dd
                _tp += _d
                row = self._row(ws, row,
                                 ["کار جدید", "کار جدید (%s) - بندهای"
                                  " ۳-۱..۳-۵" % (_nr.get("method") or ""),
                                  fa_float(_nr["amount"], 0), fa_float(_dd, 0),
                                  fa_float(_d - _dd, 0), fa_float(_d, 0),
                                  "همان منطقِ تجهیز (شاخص رشته)"],
                                 [F["label"], F["label"], F["money"],
                                  F["money"], F["money"], F["money"],
                                  F["label"]])

            # ── فاز E-6: ردیف مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) ──
            _kd = _tadil.get("k_diff") or 0.0
            if _tadil.get("completed_within_term") and abs(_kd) >= 0.01:
                _td += _kd
                row = self._row(ws, row,
                                ["تبصرهٔ ۲", "مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ بند ۱-۸)",
                                 "", fa_float(_kd, 0), "", fa_float(_kd, 0),
                                 "همزمان با صورت‌وضعیت قطعی پرداخت می‌شود (بند ۸-۴)"],
                                [F["label"], F["label"], F["money"], F["money_b"],
                                 F["money"], F["money_b"], F["warn_y"]])
            row += 1
            row = self._row(ws, row, ["جمع", "", "", fa_float(_td, 0),
                                       fa_float(_tp - _td, 0), fa_float(_tp, 0),
                                       "علی‌الحساب = جمع منهای بخش قطعی"],
                                      [F["chapter"], F["cell"], F["cell"], F["money_b"],
                                       F["money_b"], F["money_b"], F["label"]])

            row += 1

        # ═════════ برگه ۱۱: رجیستری مقادیر منتظر تأیید (فاز B) ═════════
        # هر مقدار غیررسمی + منبع + صفحهٔ PDF + وضعیت + اقدام.
        ws = wb.add_worksheet("مقادیر منتظر تأیید")
        for c, w in enumerate([34, 20, 28, 22, 28, 34]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 6)
        row = self._row(ws, row,
                        ["المان", "مقدار", "منبع (بخشنامه)", "صفحهٔ PDF",
                         "وضعیت", "اقدام"],
                        [F["thead"]] * 6)
        _seen = set()
        for _eng in ("tadil", "baravord"):
            for p in (((adj or {}).get(_eng) or {}).get("pending") or []):
                _key = (p.get("item"), str(p.get("value")))
                if _key in _seen:
                    continue
                _seen.add(_key)
                _val = fa_float(p["value"], 4) if isinstance(p.get("value"),
                                                             (int, float)) \
                    else str(p.get("value"))
                row = self._row(ws, row,
                                [p.get("item"), _val, p.get("source"), p.get("page"),
                                 p.get("status"), p.get("action")],
                                [F["label"], F["money"], F["label"], F["label"],
                                 F["warn_y"], F["label"]])
        # شاخص‌های رشتهٔ ابنیه (همهٔ دوره‌ها) — همیشه برای تطبیق نمایش داده می‌شوند
        # شاخص فصول ابنیه (پیوست ۳، صفحه‌های ۶–۷) — هر فصل در هر دوره
        row = self._row(ws, row,
                        ["شاخص فصول ابنیه — استخراج‌شده از بخشنامهٔ "
                         "۱۴۰۵/۱۵۵۲۳۳، پیوست ۳ (صفحه‌های ۶–۷)", "", "", "", "", ""],
                        [F["chapter"]] * 6)
        for _r in (INDEX_BULLETINS or {}).get("chapters_abnieh") or []:
            for _pk, _fk in (("base", "base_esfand_1403"), ("q1", "q1_1404"),
                             ("q2", "q2_1404"), ("q3", "q3_1404"),
                             ("q4", "q4_1404")):
                _v = _r.get(_fk)
                if isinstance(_v, (int, float)):
                    row = self._row(ws, row,
                                    ["فصل %s — شاخص %s"
                                     % (fa(_r.get("chapter")), _index_period_label(_pk)),
                                     fa_float(_v, 1),
                                     "بخشنامه ۱۴۰۵/۱۵۵۲۳۳ — پیوست ۳، فصل %s"
                                     % fa(_r.get("chapter")),
                                     "صفحهٔ %s PDF" % fa(_r.get("page")),
                                     "استخراج‌شده — نیازمند تأیید",
                                     "مقدار را با جدول پیوست ۳ تطبیق دهید"],
                                    [F["label"], F["money"], F["label"],
                                     F["label"], F["warn_y"], F["label"]])
        row += 1
        row += 1
        row = self._row(ws, row,
                        ["شاخص‌های قطعی رشتهٔ ابنیه — استخراج‌شده از بخشنامه "
                         "۱۴۰۵/۱۵۵۲۳۳، پیوست ۳", "", "", "", "", ""],
                        [F["chapter"]] * 6)
        _ib_meta = (INDEX_BULLETINS or {}).get("meta") or {}
        if _ib_meta.get("status"):
            row = self._row(ws, row,
                            ["وضعیت کلی جدول شاخص", _ib_meta.get("status"),
                             _ib_meta.get("bulletin"), "", "", ""],
                            [F["label"], F["warn_y"], F["label"], F["cell"],
                             F["cell"], F["cell"]])
        for _k in ("base", "q1", "q2", "q3", "q4"):
            _v, _pg = TechnicalOfficeEngine._index_value(_k)
            if _v is None:
                continue
            row = self._row(ws, row,
                            ["شاخص دورهٔ " + _index_period_label(_k),
                             fa_float(_v, 1),
                             "بخشنامه ۱۴۰۵/۱۵۵۲۳۳ — پیوست ۳، ردیف ۱ (ابنیه)",
                             "صفحهٔ %s PDF" % fa(_pg),
                             "استخراج‌شده — نیازمند تأیید",
                             "مقدار را با جدول پیوست ۳ بخشنامه تطبیق دهید"],
                            [F["label"], F["money"], F["label"], F["label"],
                             F["warn_y"], F["label"]])
        row += 1
        row = self._row(ws, row,
                        ["یادداشت", "فصل ۱۵ (سقف‌های از پیش ساخته) در جدول شاخص "
                         "فصول ابنیه موجود نیست؛ با صفحهٔ ۶ PDF تطبیق دهید.",
                         "", "", "اطلاع", ""],
                        [F["label"], F["label"], F["cell"], F["cell"],
                         F["label"], F["cell"]])
        row += 1
        # ═════════ فاز E-6 Part C گام ۱۲ (حرف g): تصمیمات منتظر تأیید ═════════
        # تک‌منبعِ حقیقت: PENDING_INTERPRETATIONS (همان که پنلِ «وضعیت ورودی‌ها»
        # و §۱۸-۳ ACCEPTANCE.md می‌خوانند). فاز E-8 §۱: شناسهٔ پایدار D-xx.
        row = self._row(ws, row,
                        ["تصمیماتِ باز — منتظر تأیید کاربر", "", "",
                         "", "", ""],
                        [F["chapter"]] * 6)
        row = self._row(ws, row,
                        ["شناسه", "موضوع", "تفسیرِ پیاده‌سازی‌شده",
                         "گزینهٔ دیگر", "اثر عددی", ""],
                        [F["thead"]] * 6)
        for _no, _subj, _impl, _alt, _eff in PENDING_INTERPRETATIONS:
            row = self._row(ws, row,
                            [_no, _subj, _impl, _alt, _eff, ""],
                            [F["cell"], F["label"], F["label"], F["label"],
                             F["label"], F["cell"]])
        row += 1

        ws = wb.add_worksheet("هشدارها")
        for c, w in enumerate([10, 22, 18, 60, 40, 34]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 6)
        st = result.get("status", {})
        row = self._row(ws, row,
                        ["وضعیت کلی",
                         "کامل" if st.get("complete") else "ناقص",
                         f"خطا: {fa(st.get('errors', 0))} — هشدار: {fa(st.get('warnings_n', 0))} "
                         f"— اطلاع: {fa(st.get('info', 0))}", "", "", ""],
                        [F["label"], F["label"], F["label"], F["cell"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row, ["سطح", "دسته", "المان/ردیف", "شرح",
                                  "اقدام پیشنهادی", "بند مرجع"], [F["thead"]] * 6)
        _LVL_FMT = {"خطا": "neg", "هشدار": "money", "اطلاع": "cell"}
        for w in result.get("warnings") or []:
            row = self._row(ws, row, [w["level"], w["category"], w["item"],
                                      w["message"], w["action"], w["ref"]],
                            [F[_LVL_FMT.get(w["level"], "cell")]] * 6)

        # ═════════ برگه ۱۰: قیمت‌های دستی (فاز C) ═════════
        # ساختارِ ماشین‌خوانا: هر بخش با یک سطر عنوانِ یکتا شروع می‌شود و
        # سپس سطر سرستون و داده‌ها. تابع parse_manual_entries_xlsx همین
        # شیت را می‌خواند (ورود از Excel بین پروژه‌ها — §۱۵-۴).
        ws = wb.add_worksheet("قیمت‌های دستی")
        for c, w in enumerate([26, 14, 14, 14, 14, 16, 12, 12, 12, 12, 16, 30]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 12)
        row = self._row(ws, row,
                        [MPX_VERSION_LABEL, MANUAL_ENTRIES_VERSION,
                         "تاریخ خروجی", jalali_now_str(),
                         "کاربر", s.get("price_user") or "", "", "", "", "", "", ""],
                        [F["label"]] * 12)
        row += 1
        mp = s.get("manual_prices") or {}
        row = self._row(ws, row, [MPX_SECTION_PRICES] + [""] * 11,
                        [F["chapter"]] * 12)
        row = self._row(ws, row,
                        ["شناسهٔ ردیف", "کد فهرست‌بها", "قیمت دستی", "قیمت فهرست",
                         "اختلاف ٪", "منبع", "شماره سند", "تاریخ سند", "وضعیت",
                         "فصل", "کاربر / تاریخ ورود", "توضیح"],
                        [F["thead"]] * 12)
        for key, rec in sorted(mp.items()):
            _ap = None
            _l = next((x for x in result["lines"] if x["id"] == key), None)
            if _l:
                _ap = _l.get("app_price") or _l["price"]
                _code = _l["code"]
            else:
                _code = rec.get("chapter") or ""
            _dp = ((rec["price"] - _ap) / _ap * 100.0) if (_ap and rec.get("price")) else None
            row = self._row(ws, row, [
                key, _code, round(rec.get("price") or 0), round(_ap) if _ap else "—",
                (f"{_dp:+.1f}" if _dp is not None else "—"),
                rec.get("source") or "", rec.get("doc_no") or "",
                rec.get("doc_date") or "", rec.get("status") or "دستی",
                rec.get("chapter") or (_l["chapter"] if _l else ""),
                f"{rec.get('user') or ''} — {rec.get('at') or ''}".strip(" —"),
                rec.get("note") or ""],
                [F["cell"], F["cell_c"], F["money"], F["money"], F["cell_c"],
                 F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                 F["cell"], F["cell"]])
        row += 1
        mc = s.get("manual_codes") or {}
        row = self._row(ws, row, [MPX_SECTION_CODES] + [""] * 11,
                        [F["chapter"]] * 12)
        row = self._row(ws, row,
                        ["شناسهٔ ردیف", "کد جایگزین", "دلیل", "کاربر", "تاریخ ورود",
                         "", "", "", "", "", "", ""],
                        [F["thead"]] * 12)
        for key, rec in sorted(mc.items()):
            if isinstance(rec, dict):
                row = self._row(ws, row, [key, rec.get("code") or "",
                                          rec.get("reason") or "", rec.get("user") or "",
                                          rec.get("at") or ""] + [""] * 7,
                                [F["cell"], F["cell_c"], F["cell"], F["cell_c"],
                                 F["cell_c"]] + [F["cell"]] * 7)
        row += 1
        ex = s.get("excluded") or []
        row = self._row(ws, row, [MPX_SECTION_EXCLUDED] + [""] * 11,
                        [F["chapter"]] * 12)
        row = self._row(ws, row,
                        ["شناسهٔ ردیف", "دلیل", "کاربر", "تاریخ ورود",
                         "", "", "", "", "", "", "", ""],
                        [F["thead"]] * 12)
        for e in ex:
            if isinstance(e, dict):
                row = self._row(ws, row, [e.get("id") or "", e.get("reason") or "",
                                          e.get("user") or "", e.get("at") or ""] + [""] * 8,
                                [F["cell"], F["cell"], F["cell_c"],
                                 F["cell_c"]] + [F["cell"]] * 8)
        row += 1
        strd = s.get("starred_rows") or []
        row = self._row(ws, row, [MPX_SECTION_STARRED] + [""] * 11,
                        [F["chapter"]] * 12)
        row = self._row(ws, row,
                        ["کد", "شرح", "واحد", "مقدار", "قیمت واحد", "فصل",
                         "منبع", "شماره سند", "تاریخ سند", "کاربر / تاریخ ورود",
                         "توضیح", ""],
                        [F["thead"]] * 12)
        for sr in strd:
            row = self._row(ws, row, [
                sr.get("code") or "", sr.get("desc") or "", sr.get("unit") or "",
                sr.get("qty") or 0, round(sr.get("price") or 0), sr.get("chapter") or "",
                sr.get("source") or "", sr.get("doc_no") or "",
                sr.get("doc_date") or "",
                f"{sr.get('user') or ''} — {sr.get('at') or ''}".strip(" —"),
                sr.get("note") or "", ""],
                [F["cell_c"], F["cell"], F["cell_c"], F["num"], F["money"],
                 F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"], F["cell"],
                 F["cell"], F["cell"]])

        # ═════════ برگه ۱۱: سابقهٔ ویرایش (Audit trail — §۱۵-۴ بند ۴) ═════════
        ws = wb.add_worksheet("سابقهٔ ویرایش")
        for c, w in enumerate([24, 18, 20, 18, 20, 20, 18, 14]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 8)
        row = self._row(ws, row,
                        ["زمان", "کاربر", "ردیف", "فیلد", "مقدار قبلی",
                         "مقدار جدید", "منبع", "نوع"],
                        [F["thead"]] * 8)
        for a in s.get("price_audit") or []:
            row = self._row(ws, row, [
                a.get("at") or "", a.get("user") or "", a.get("item") or "",
                a.get("field") or "", a.get("old") if a.get("old") is not None else "",
                a.get("new") if a.get("new") is not None else "",
                a.get("source") or "",
                AUDIT_KIND_LABELS.get(a.get("kind") or "price", "قیمت/کد")],
                [F["cell_c"], F["cell_c"], F["cell"], F["cell_c"], F["cell"],
                 F["cell"], F["cell_c"], F["cell_c"]])

        # ═════════ برگه‌های جدید فاز D (۵ شیت) ═════════
        # برگه‌ها در پایان (پیش از wb.close) به ترتیب رسمی SHEET_ORDER مرتب
        # می‌شوند؛ لذا ترتیبِ ساخته‌شدن در اینجا مهم نیست.

        _st = result.get("status") or {}
        _pss = result.get("price_status_summary") or {}
        _cf = result.get("coefs") or {}
        _fl = _cf.get("floors") or {}
        _rg = _cf.get("regional") or {}
        _ix = result.get("index")

        # ── برگه: خلاصه و وضعیت (صفحهٔ اول) ──
        ws = wb.add_worksheet("خلاصه و وضعیت")
        for c, w in enumerate([8, 42, 22, 46]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 4)
        row = self._row(ws, row, ["", "بخش ۱ — وضعیت گزارش", "", ""],
                        [F["chapter"]] * 4)
        row = self._row(ws, row,
                        ["", "وضعیت کلی",
                         "کامل" if _st.get("complete") else "ناقص",
                         "خطا: " + fa(_st.get("errors") or 0)
                         + " — هشدار: " + fa(_st.get("warnings_n") or 0)
                         + " — اطلاع: " + fa(_st.get("info") or 0)
                         + " (جزئیات در شیت «هشدارها»)"],
                        [F["cell"], F["label"], F["cell_c"], F["cell"]])
        row = self._row(ws, row,
                        ["", "نوع خروجی", meta.get("report_type") or "—",
                         "اگر «پیش‌نویس» است، حداقل یک ردیف «نیازمند ورود» "
                         "قیمت دارد (شیت «قیمت‌های دستی»)"],
                        [F["cell"], F["label"], F["cell_c"], F["cell"]])
        row = self._row(ws, row,
                        ["", "مبنای قیمت‌گذاری",
                         "فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴",
                         "سازمان برنامه و بودجه — واحد پول: ریال"],
                        [F["cell"], F["label"], F["cell_c"], F["cell"]])
        row = self._row(ws, row,
                        ["", "تعداد ردیف‌های متره",
                         fa(len(result.get("lines") or [])) + " ردیف",
                         "جزئیات کمیت و قیمت هر ردیف در شیت «متره ریز»"],
                        [F["cell"], F["label"], F["cell_c"], F["cell"]])
        row += 1

        row = self._row(ws, row, ["", "بخش ۲ — شمارش وضعیت قیمت‌ها", "", ""],
                        [F["chapter"]] * 4)
        row = self._row(ws, row,
                        ["", "وضعیت قیمت", "تعداد ردیف", "شرح"],
                        [F["cell"], F["thead"], F["thead"], F["thead"]])
        for _psk in MANUAL_STATUSES:
            row = self._row(ws, row,
                            ["", _psk, fa(_pss.get(_psk) or 0),
                             _PRICE_STATUS_DESC.get(_psk, "")],
                            [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        _npe = result.get("needs_price_entry") or 0
        if _npe:
            row = self._row(ws, row,
                            ["", "پیام", fa(_npe) + " ردیف نیازمند ورود قیمت",
                             "خروجی تا تأیید این ردیف‌ها «پیش‌نویس» است"],
                            [F["cell"], F["warn_y"], F["warn_y"], F["warn_y"]])
        row += 1

        row = self._row(ws, row, ["", "بخش ۳ — وضعیت ضرایب", "", ""],
                        [F["chapter"]] * 4)
        row = self._row(ws, row,
                        ["", "ضریب", "مقدار / وضعیت", "منبع و بند مرجع"],
                        [F["cell"], F["thead"], F["thead"], F["thead"]])
        row = self._row(ws, row,
                        ["", "ضریب طبقات (P)",
                         fa_float(_fl.get("value") or 1.0, 4) + " — "
                         + str(_st.get("floors_status") or "—"),
                         "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — فرمول P "
                         "(محاسبهٔ کامل در شیت «ضریب طبقات»)"],
                        [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        row = self._row(ws, row,
                        ["", "ضریب منطقه‌ای",
                         fa_float(_rg.get("value") or 1.0, 4) + " — "
                         + str(_st.get("regional_status") or "—"),
                         str(_rg.get("source") or "تنظیم دستی کاربر")],
                        [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        row = self._row(ws, row,
                        ["", "ضریب بالاسری",
                         fa_float(s.get("overhead_coef") or 1.0, 4),
                         "تنظیم کاربر — پیش‌فرض ۱٫۳ (عمرانی + مناقصه) — "
                         "دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸"],
                        [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        row = self._row(ws, row,
                        ["", "تجهیز و برچیدن کارگاه",
                         fa_float(s.get("site_setup_amount") or 0.0, 0),
                         "مبلغ مستقیم (ریال) — سقف ۴٪ صرفاً هشدار است"],
                        [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        if _ix:
            row = self._row(ws, row,
                            ["", "شاخص تعدیل فهرست‌بها",
                             "فعال — " + str(_ix.get("target_period") or "—"),
                             "کلیات بند ۲۲ — "
                             + ("شامل شاخص موقت است" if _ix.get("provisional")
                                else "تمام شاخص‌ها قطعی")
                             + " (جزئیات در شیت «شاخص‌ها»)"],
                            [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        else:
            row = self._row(ws, row,
                            ["", "شاخص تعدیل فهرست‌بها", "غیرفعال",
                             "دورهٔ هدف = دورهٔ مبنا (اسفند ۱۴۰۳) — همهٔ "
                             "ضرایب ۱ (کلیات بند ۲۲)"],
                            [F["cell"], F["cell_c"], F["cell_c"], F["cell"]])
        row += 1

        row = self._row(ws, row, ["", "بخش ۴ — خلاصهٔ مالی", "", ""],
                        [F["chapter"]] * 4)
        row = self._row(ws, row,
                        ["", "شرح", "مبلغ (ریال)", "یادداشت"],
                        [F["cell"], F["thead"], F["thead"], F["thead"]])
        for _lbl, _val in [
                ("جمع ردیف‌ها (به قیمت فهرست‌بها)", result.get("base_total")),
                ("ناخالص پرداختی (با ضرایب + تجهیز)", result.get("gross_payable")),
                ("جمع نهایی صورت‌وضعیت", result.get("grand_total")),
                ("خالص پرداختی (پس از کسورات قانونی)", result.get("net_payable"))]:
            row = self._row(ws, row,
                            ["", _lbl, round(_val or 0), ""],
                            [F["cell"], F["cell"], F["money"], F["cell"]])
        row = self._row(ws, row,
                        ["", "تفصیل کامل زنجیرهٔ مالی در شیت «خلاصهٔ مالی و برآورد»",
                         "", "مبلغ به حروف نیز در همان شیت"],
                        [F["cell"], F["cell"], F["cell"], F["cell"]])
        row += 1

        # حضور برگه‌ها باید قطعی و مستقل از ترتیبِ ساخته‌شدن باشد:
        # ۱۶ برگهٔ پایه همیشه هستند؛ ۳ برگهٔ موتور (فاز B) فقط هنگام
        # روشن بودن موتور ساخته می‌شوند.
        _adj = result.get("adjustment") or {}
        _ENGINE_PRESENT = {"تعدیل پیمان": bool(_adj.get("tadil")),
                           "برآورد به‌هنگام": bool(_adj.get("baravord")),
                           "بخش قطعی و علی‌الحساب": bool(_adj.get("tadil"))}
        _present = {n for n in SHEET_ORDER if _ENGINE_PRESENT.get(n, True)}
        row = self._row(ws, row, ["", "بخش ۵ — فهرست برگه‌ها", "", ""],
                        [F["chapter"]] * 4)
        row = self._row(ws, row,
                        ["شماره", "نام برگه", "شرح کوتاه", "وضعیت"],
                        [F["thead"]] * 4)
        for _i, (_nm, _ds) in enumerate(SHEET_INDEX, start=1):
            row = self._row(ws, row,
                            [fa(_i), _nm, _ds,
                             "فعال" if _nm in _present else "موتور خاموش"],
                            [F["cell_c"], F["cell_c"], F["cell"], F["cell_c"]])

        # ── برگه: مشخصات پیمان ──
        ws = wb.add_worksheet("مشخصات پیمان")
        for c, w in enumerate([8, 32, 26, 46]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 4)
        row = self._row(ws, row, ["", "بخش ۱ — مشخصات پروژه و قرارداد", "", ""],
                        [F["chapter"]] * 4)
        for _lbl, _val in [("نام پروژه", meta.get("project_name")),
                           ("کارفرما", meta.get("employer")),
                           ("پیمانکار", meta.get("contractor")),
                           ("مشاور / ناظر", meta.get("consultant")),
                           ("محل اجرا", meta.get("location")),
                           ("شماره پیمان (قرارداد)", meta.get("contract_no")),
                           ("تاریخ پیمان (شمسی)", meta.get("contract_date"))]:
            row = self._row(ws, row, ["", _lbl, _val or "—", ""],
                            [F["cell"], F["label"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row, ["", "بخش ۲ — مشخصات صورت‌وضعیت", "", ""],
                        [F["chapter"]] * 4)
        for _lbl, _val in [("شماره صورت‌وضعیت", fa(meta.get("report_no") or "—")),
                           ("نوع صورت‌وضعیت", meta.get("report_type")),
                           ("شروع دورهٔ صورت‌وضعیت", meta.get("period_start")),
                           ("پایان دورهٔ صورت‌وضعیت", meta.get("period_end"))]:
            row = self._row(ws, row, ["", _lbl, _val or "—", ""],
                            [F["cell"], F["label"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["", "بخش ۳ — مبنای قیمت‌گذاری و ضرایب قراردادی", "", ""],
                        [F["chapter"]] * 4)
        for _lbl, _val in [
                ("فهرست‌بهای مبنای قیمت‌گذاری",
                 "فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه سال ۱۴۰۴"),
                ("واحد پول", "ریال"),
                ("ضریب بالاسری",
                 fa_float(s.get("overhead_coef") or 1.0, 4) + " — تنظیم کاربر"),
                ("ضریب منطقه‌ای",
                 fa_float(_rg.get("value") or 1.0, 4) + " — "
                 + str(_st.get("regional_status") or "—")),
                ("ضریب طبقات",
                 fa_float(_fl.get("value") or 1.0, 4) + " — "
                 + str(_st.get("floors_status") or "—")),
                ("تجهیز و برچیدن کارگاه",
                 fa_float(s.get("site_setup_amount") or 0.0, 0)
                 + " ریال — مبلغ مستقیم"),
                ("کسورات بیمه",
                 _fa_pct(s.get("insurance_pct") or 0) + "٪ — فقط در خالص پرداختی"),
                ("کسورات مالیات",
                 _fa_pct(s.get("tax_pct") or 0) + "٪ — فقط در خالص پرداختی"),
                ("کسورات حسن انجام کار",
                 _fa_pct(s.get("good_job_pct") or 0) + "٪ — فقط در خالص پرداختی"),
                ("پیش‌پرداخت",
                 fa_float(s.get("advance_payment") or 0.0, 0)
                 + " ریال — فقط در خالص پرداختی")]:
            row = self._row(ws, row, ["", _lbl, _val, ""],
                            [F["cell"], F["label"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["", "بخش ۴ — اعتبارسنجی تاریخ‌ها (ایراد ۱۲)", "", ""],
                        [F["chapter"]] * 4)
        if _date_errs:
            for _e in _date_errs:
                row = self._row(ws, row,
                                ["", _e.get("item") or "—",
                                 _e.get("message") or "", "خطا"],
                                [F["cell"], F["label"], F["cell"], F["warn_y"]])
        else:
            row = self._row(ws, row,
                            ["", "ترتیب تاریخ‌ها", "معتبر است",
                             "تاریخ پیمان ≤ شروع دوره ≤ پایان دوره"],
                            [F["cell"], F["label"], F["cell"], F["cell"]])

        # ── برگه: ضرایب ──
        ws = wb.add_worksheet("ضرایب")
        for c, w in enumerate([8, 30, 20, 20, 48]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 5)
        row = self._row(ws, row,
                        ["شماره", "ضریب", "مقدار", "وضعیت", "منبع / بند مرجع"],
                        [F["thead"]] * 5)
        _coef_rows = [
            ("ضریب طبقات (P)",
             fa_float(_fl.get("value") or 1.0, 4),
             str(_st.get("floors_status") or "—"),
             "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — "
             + str(_fl.get("formula") or "فرمول P")),
            ("ضریب منطقه‌ای",
             fa_float(_rg.get("value") or 1.0, 4),
             str(_st.get("regional_status") or "—"),
             str(_rg.get("source") or "تنظیم دستی کاربر")),
            ("ضریب بالاسری",
             fa_float(s.get("overhead_coef") or 1.0, 4),
             "تنظیم کاربر",
             "دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸ — پیش‌فرض عمرانی + "
             "مناقصه: ۱٫۳ (ترک تشریفات ۱٫۲ / غیرعمرانی ۱٫۴ / ۱٫۳)"),
            ("تجهیز و برچیدن کارگاه (ریال)",
             fa_float(s.get("site_setup_amount") or 0.0, 0),
             "تنظیم کاربر",
             "مبلغ مستقیم — سقف ۴٪ صرفاً هشدار (دستورالعمل کاربرد بند ۲-۸)"),
        ]
        for _i, (_nm, _vl, _stt, _src) in enumerate(_coef_rows, start=1):
            row = self._row(ws, row,
                            [fa(_i), _nm, _vl, _stt, _src],
                            [F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["cell"]])
        if _ix:
            _ch_f = [_ch.get("factor") for _ch in _ix.get("chapters") or []
                     if _ch.get("factor") is not None]
            _f_txt = (fa_float(min(_ch_f), 4) + " تا " + fa_float(max(_ch_f), 4)) \
                if _ch_f else "—"
            row = self._row(ws, row,
                            [fa(len(_coef_rows) + 1), "شاخص تعدیل فهرست‌بها",
                             _f_txt,
                             "فعال" + (" — شامل موقت" if _ix.get("provisional")
                                       else ""),
                             "کلیات بند ۲۲ — دورهٔ مبنا: "
                             + str(_ix.get("base_period") or "—")
                             + " → هدف: " + str(_ix.get("target_period") or "—")
                             + " (جزئیات در شیت «شاخص‌ها»)"],
                            [F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["cell"]])
        else:
            row = self._row(ws, row,
                            [fa(len(_coef_rows) + 1), "شاخص تعدیل فهرست‌بها",
                             "۱٫۰۰۰۰", "غیرفعال",
                             "دورهٔ هدف = دورهٔ مبنا (اسفند ۱۴۰۳) — همهٔ "
                             "ضرایب ۱ (کلیات بند ۲۲)"],
                            [F["cell_c"], F["cell_c"], F["cell_c"], F["cell_c"],
                             F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["", "کسورات قانونی (بر ناخالص اثر ندارند — فقط در "
                             "«خالص پرداختی» محاسبه می‌شوند)", "", "", ""],
                        [F["chapter"]] * 5)
        for _lbl, _vl in [("بیمه", _fa_pct(s.get("insurance_pct") or 0) + "٪"),
                          ("مالیات", _fa_pct(s.get("tax_pct") or 0) + "٪"),
                          ("حسن انجام کار", _fa_pct(s.get("good_job_pct") or 0) + "٪"),
                          ("پیش‌پرداخت",
                           fa_float(s.get("advance_payment") or 0.0, 0) + " ریال")]:
            row = self._row(ws, row,
                            ["", _lbl, _vl, "نمایشی",
                             "قاعدهٔ طلایی ۵: کسورات جزو «ناخالص پرداختی» نیستند"],
                            [F["cell"], F["label"], F["cell_c"], F["cell_c"],
                             F["cell"]])

        # ── برگه: شاخص‌ها ──
        ws = wb.add_worksheet("شاخص‌ها")
        for c, w in enumerate([8, 24, 18, 18, 18, 18, 40]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 7)
        _ib = _load_config("index_bulletins.json", {}) or {}
        _ib_meta = _ib.get("meta") or {}
        row = self._row(ws, row,
                        ["", "بخش ۱ — شاخص‌های رسمی رشتهٔ ابنیه (پیوست ۳ "
                             "بخشنامه ۱۴۰۵/۱۵۵۲۳۳)", "", "", "", "", ""],
                        [F["chapter"]] * 7)
        if _ib_meta.get("status"):
            row = self._row(ws, row,
                            ["", "وضعیت استخراج", _ib_meta.get("status"),
                             "", "", "", ""],
                            [F["cell"], F["label"], F["warn_y"], F["cell"],
                             F["cell"], F["cell"], F["cell"]])
        row = self._row(ws, row,
                        ["ردیف", "دوره", "شاخص رشتهٔ ابنیه", "منبع", "صفحه",
                         "وضعیت", "یادداشت"],
                        [F["thead"]] * 7)
        _disc = next((d for d in _ib.get("disciplines") or []
                      if d.get("name") == "ابنیه"), None)
        if _disc:
            for _i, (_p, _k) in enumerate([
                    ("اسفند ۱۴۰۳ (مبنا)", _disc.get("base_esfand_1403")),
                    ("سه‌ماهه اول ۱۴۰۴", _disc.get("q1_1404")),
                    ("سه‌ماهه دوم ۱۴۰۴", _disc.get("q2_1404")),
                    ("سه‌ماهه سوم ۱۴۰۴", _disc.get("q3_1404")),
                    ("سه‌ماهه چهارم ۱۴۰۴", _disc.get("q4_1404"))], start=1):
                row = self._row(ws, row,
                                [fa(_disc.get("row") or 1), _p, _k,
                                 _ib_meta.get("bulletin") or "—",
                                 fa(_disc.get("page") or 4),
                                 "استخراج‌شده — نیازمند تأیید",
                                 "ستون «" + str(_p) + "»، ردیف ۱ صفحهٔ ۴"],
                                [F["cell_c"], F["cell_c"], F["num"], F["cell"],
                                 F["cell_c"], F["warn_y"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["", "بخش ۲ — شاخص فصول ابنیه (صفحهٔ ۶–۷ پیوست ۳)",
                         "", "", "", "", ""],
                        [F["chapter"]] * 7)
        row = self._row(ws, row,
                        ["فصل", "نام فصل", "مبنا (اسفند ۱۴۰۳)", "سه‌ماهه اول",
                         "سه‌ماهه دوم", "سه‌ماهه سوم", "سه‌ماهه چهارم"],
                        [F["thead"]] * 7)
        for _ch in _ib.get("chapters_abnieh") or []:
            row = self._row(ws, row,
                            [fa(_ch.get("chapter")) if _ch.get("chapter")
                             else "—",
                             _ch.get("name") or "—",
                             _ch.get("base_esfand_1403"), _ch.get("q1_1404"),
                             _ch.get("q2_1404"), _ch.get("q3_1404"),
                             _ch.get("q4_1404")],
                            [F["cell_c"], F["cell"], F["num"], F["num"],
                             F["num"], F["num"], F["num"]])
        row += 1
        if _ix:
            row = self._row(ws, row,
                            ["", "بخش ۳ — ضریب تعدیل محاسبه‌شده برای دورهٔ هدف",
                             "", "", "", "", ""],
                            [F["chapter"]] * 7)
            row = self._row(ws, row,
                            ["فصل", "ضریب تعدیل", "شاخص دورهٔ هدف", "نوع شاخص",
                             "وضعیت", "منبع", ""],
                            [F["thead"]] * 7)
            for _ch in _ix.get("chapters") or []:
                row = self._row(ws, row,
                                [fa(_ch.get("chapter") or "—"),
                                 fa_float(_ch["factor"], 4)
                                 if _ch.get("factor") is not None else "—",
                                 _ch.get("level")
                                 if _ch.get("level") is not None else "—",
                                 _ch.get("kind") or "—",
                                 "موقت" if _ch.get("kind") == "موقت" else "قطعی",
                                 _ch.get("source") or "—", ""],
                                [F["cell_c"], F["num"], F["num"], F["cell_c"],
                                 F["cell_c"], F["cell"], F["cell"]])
            row = self._row(ws, row,
                            ["", "یادداشت",
                             "دورهٔ مبنا: " + str(_ix.get("base_period") or "—")
                             + " — دورهٔ هدف: "
                             + str(_ix.get("target_period") or "—")
                             + (" — شامل شاخص موقت است"
                                if _ix.get("provisional")
                                else " — تمام شاخص‌ها قطعی"),
                             "", "", "", ""],
                            [F["cell"], F["label"], F["cell"], F["cell"],
                             F["cell"], F["cell"], F["cell"]])
        else:
            row = self._row(ws, row,
                            ["", "یادداشت",
                             "دورهٔ هدف برابر دورهٔ مبنا (اسفند ۱۴۰۳) است — "
                             "ضریب همهٔ فصل‌ها ۱ و شاخص تعدیل غیرفعال است "
                             "(کلیات بند ۲۲). برای فعال‌سازی، دورهٔ هدف را در "
                             "تنظیمات انتخاب کنید.",
                             "", "", "", ""],
                            [F["cell"], F["label"], F["cell"], F["cell"],
                             F["cell"], F["cell"], F["cell"]])

        # ── برگه: منابع و بخشنامه‌ها ──
        ws = wb.add_worksheet("منابع و بخشنامه‌ها")
        for c, w in enumerate([8, 14, 32, 30, 14, 26, 34]):
            ws.set_column(c, c, w)
        row = self._header_block(ws, F, meta, 7)
        row = self._row(ws, row,
                        ["شناسه", "نوع", "عنوان / موضوع", "شماره / مرجع",
                         "تاریخ", "وضعیت", "محل استفاده در برنامه"],
                        [F["thead"]] * 7)
        for _sid, _typ, _ttl, _ref, _dt, _sts, _use in _SOURCES:
            row = self._row(ws, row,
                            [_sid, _typ, _ttl, _ref, _dt, _sts, _use],
                            [F["cell_c"], F["cell_c"], F["cell"], F["cell"],
                             F["cell_c"],
                             F["warn_y"] if ("دستی" in _sts
                                             or "استخراج‌شده" in _sts
                                             or "استخراج نشد" in _sts)
                             else F["cell_c"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["", "بخش ۲ — ارجاع ردیف‌های قیمت به فهرست‌بهای ۱۴۰۴",
                         "", "", "", "", ""],
                        [F["chapter"]] * 7)
        row = self._row(ws, row,
                        ["کد", "ارجاع", "", "", "", "", ""],
                        [F["thead"]] * 7)
        for _code, _ref in sorted(PRICE_REFS.items()):
            row = self._row(ws, row,
                            [_code, _ref, "", "", "", "", ""],
                            [F["cell_c"], F["cell"], F["cell"], F["cell"],
                             F["cell"], F["cell"], F["cell"]])
        row += 1
        row = self._row(ws, row,
                        ["", "بخش ۳ — بندهای پیوست ۳ بخشنامه ۱۴۰۵/۱۵۵۲۳۳",
                         "", "", "", "", ""],
                        [F["chapter"]] * 7)
        row = self._row(ws, row,
                        ["بند", "متن بند", "", "", "", "صفحه", ""],
                        [F["thead"]] * 7)
        for _rl in _ib.get("rules") or []:
            row = self._row(ws, row,
                            [_rl.get("clause") or "—", _rl.get("text") or "",
                             "", "", "", fa(_rl.get("page") or 1), ""],
                            [F["cell_c"], F["cell"], F["cell"], F["cell"],
                             F["cell"], F["cell_c"], F["cell"]])

        # ═════════ مرتب‌سازی برگه‌ها به ترتیب رسمی (فاز D) ═════════
        _order = {n: i for i, n in enumerate(SHEET_ORDER)}
        wb.worksheets_objs.sort(
            key=lambda w: (_order.get(w.name, len(SHEET_ORDER)), w.name))

        wb.close()
        return buf.getvalue()


def _match_label(m: str) -> str:
    """برچسب فارسی روش تطبیق ردیف."""
    return {"rule-exact": "قانون + کد دقیق", "rule-fuzzy": "قانون فازی",
            "fuzzy": "تطبیق فازی", "manual": "تأیید دستی",
            "direct-code": "کد مستقیم Mapping"}.get(m, m)

# ════════════════════════════════════════════════════════════════
# دادهٔ نمونهٔ نمایشی (زیرمجموعهٔ کوچک‌شدهٔ خروجی‌های Schedule رویت برای تست فوری)
# ════════════════════════════════════════════════════════════════

DEMO_PROJECT_NAME = "پروژهٔ مسکونی نمونه (دمو) — اسکلت بتنی"

DEMO_SCHEDULES = [
    ("جدول ریزمتره بتن مگر.txt", '"جدول ریزمتره بتن مگر - Lean Concrete Schedule","",""\n"Mark","Family and Type","Volume"\n"","",""\n"LC-01","Foundation Slab: 100mm Foundation Slab","18.65 m³"'),
    ("جدول ریزمتره حجم بتن سازه‌ای.txt", '"جدول ریزمتره حجم بتن سازه‌ای - Structural Concrete Schedule","","",""\n"Category","Family and Type","Material: Name","Material: Volume"\n"","","",""\n"Floors","Floor: Slab20","CONCRETE","13.95 m³"\n"Floors","Floor: Slab_Topping_50mm","CONCRETE","2.58 m³"\n"Stairs","Cast-In-Place Stair: Monolithic Stair IRAN","CONCRETE","4.21 m³"\n"Stairs: Runs","Monolithic Run: 25 mm Nosing","CONCRETE","4.21 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X50-14F16","CONCRETE","11.76 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X50-14F18","CONCRETE","9.59 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X55-14F18","CONCRETE","6.50 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X55-16F18","CONCRETE","4.89 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X60-16F18","CONCRETE","1.73 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X60-18F18","CONCRETE","0.88 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X60-20F20","CONCRETE","6.35 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C45X60-24F20","CONCRETE","3.46 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C50X60-20F20","CONCRETE","2.91 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C50X60-24F20","CONCRETE","2.89 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C50X60-24F22","CONCRETE","1.79 m³"\n"Structural Columns","M_Concrete-Rectangular-Column: C50X70-28F22","CONCRETE","1.30 m³"\n"Structural Columns","M_Concrete-Square-Column: C40-8F16","CONCRETE","1.71 m³"\n"Structural Columns","M_Concrete-Square-Column: C45-12F16","CONCRETE","10.62 m³"\n"Structural Columns","M_Concrete-Square-Column: C45-12F18","CONCRETE","4.79 m³"\n"Structural Framing","M_Concrete-Rectangular Beam: B40X40","CONCRETE","2.26 m³"\n"Structural Framing","M_Concrete-Rectangular Beam: B45X45","CONCRETE","1.30 m³"\n"Structural Framing","M_Concrete-Rectangular Beam: B45X50","CONCRETE","41.37 m³"\n"Structural Framing","M_Concrete-Rectangular Beam: B45X55","CONCRETE","85.65 m³"\n"Structural Framing","M_Concrete-Rectangular Beam: B50X50","CONCRETE","11.80 m³"\n"Structural Framing","M_Concrete-Rectangular Beam: B50X55","CONCRETE","25.78 m³"\n"Grand total: 245","","","264.25 m³"'),
    ("جدول ریزمتره قالب‌بندی سازه.txt", '"جدول ریزمتره قالب‌بندی سازه - Superstructure Formwork Schedule","","",""\n"Category","Family and Type","Material: Name","Material: Area"\n"","","",""\n"Stairs: Runs","Monolithic Run: 25 mm Nosing","CONCRETE","41 m²"\n"Structural Columns"," ","CONCRETE","670 m²"\n"Structural Framing"," ","CONCRETE","1472 m²"\n"Grand total: 236","","","2184 m²"'),
    ("جدول قالب‌بندی پی.txt", '"جدول قالب‌بندی پی - Foundation Formwork Schedule","","","",""\n"Family and Type","Mark","Length","Width","Formwork Area"\n"","","","",""\n"Wall Foundation: WF_A_1800x900","L(1-2) L(1-2)","13471.04 mm","1800.00 mm","24.25 m²"\n"Wall Foundation: WF_A_1800x900","L(2-3)","13429.25 mm","1800.00 mm","24.17 m²"\n"Wall Foundation: WF_A_1800x900","L(3-4)","13345.17 mm","1800.00 mm","24.02 m²"\n"Wall Foundation: WF_A_1800x900","L(5-6)","13297.72 mm","1800.00 mm","23.94 m²"\n"Wall Foundation: WF_B_2000x900","T(A-B)-1","2400.00 mm","2000.00 mm","4.32 m²"\n"Wall Foundation: WF_B_2000x900","T(A-B)-2","6650.38 mm","2000.00 mm","11.97 m²"\n"Wall Foundation: WF_B_2000x900","T(A-B)-3","3878.10 mm","2000.00 mm","6.98 m²"\n"Wall Foundation: WF_A_1800x900","T(B-C)-1","2400.00 mm","1800.00 mm","4.32 m²"\n"Wall Foundation: WF_A_1800x900","T(B-C)-2","6650.00 mm","1800.00 mm","11.97 m²"\n"Wall Foundation: WF_A_1800x900","T(B-C)-3","4084.60 mm","1800.00 mm","7.35 m²"\n"Wall Foundation: WF_A_1800x900","T(C-D)-1","2400.00 mm","1800.00 mm","4.32 m²"\n"Wall Foundation: WF_A_1800x900","T(C-D)-2","6650.00 mm","1800.00 mm","11.97 m²"\n"Wall Foundation: WF_A_1800x900","T(C-D)-3","4290.64 mm","1800.00 mm","7.72 m²"\n"Grand total: 13","","","",""'),
    ("جدول ریزمتره سقف تیرچه بلوک.txt", '"جدول ریزمتره سقف تیرچه بلوک - Joist Floor Schedule","","","","","",""\n"Family and Type","Mark","Reference Level","Length","Count","Volume","Comments","Description"\n"","","","","","","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5697.49 mm","1","0.64 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5702.86 mm","1","0.64 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5708.24 mm","1","0.64 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5713.62 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5718.99 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5724.37 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5727.63 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5735.12 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5740.50 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5745.87 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5751.25 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5756.62 mm","1","0.65 m³","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5762.00 mm","1","0.11 m³","",""\n"Grand total: 13","","","74484.56 mm","13","7.88 m³","",""'),
    ("جدول متره بتن پاشنه و یونولیت.txt", '"جدول متره بتن پاشنه و یونولیت - Joist Concrete & EPS Block Schedule","","","",""\n"Family and Type","Mark","Material: Name","Material: Volume","Structural Usage"\n"","","","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","بتن پاشنه تیرچه","0.34 m³","Joist"\n"بتن پاشنه تیرچه: 13","","","0.34 m³",""\n"تیرچه و یونولیت222: Joist","JST-ST1","یونولیت","7.49 m³","Joist"\n"یونولیت: 13","","","7.49 m³",""\n"Grand total: 26","","","7.84 m³",""'),
    ("جدول ریزمتره آرماتورهای تیرچه.txt", '"جدول ریزمتره آرماتورهای تیرچه - Joist Rebar Schedule","","","","",""\n"Family and Type","Mark","Material: Name","Material: Volume","وزن کل آرماتور (kg)","Structural Usage"\n"","","","","","",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Rebar - Φ8","0.02 m³","129.42779","Joist"\n"Rebar - Φ8: 13","","","0.02 m³","129.42779",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Rebar - Φ10","0.02 m³","137.761047","Joist"\n"Rebar - Φ10: 13","","","0.02 m³","137.761047",""\n"تیرچه و یونولیت222: Joist","JST-ST1","Rebar - Φ12","0.01 m³","66.125303","Joist"\n"Rebar - Φ12: 13","","","0.01 m³","66.125303",""\n"Grand total: 39","","","0.04 m³","333.31414",""'),
    ("جدول ریزمتره آرماتورهای اتصال تیرچه.txt", '"جدول ریزمتره آرماتورهای اتصال تیرچه - Joist Connection Rebar Schedule","",""\n"Mark","Length","وزن آرماتورهای اتصال (kg)"\n","",""\n"JST-ST1","5697.49 mm","7.62"\n"JST-ST1","5702.86 mm","7.62"\n"JST-ST1","5708.24 mm","7.63"\n"JST-ST1","5713.62 mm","7.63"\n"JST-ST1","5718.99 mm","7.64"\n"JST-ST1","5724.37 mm","7.64"\n"JST-ST1","5727.63 mm","7.65"\n"JST-ST1","5735.12 mm","7.65"\n"JST-ST1","5740.50 mm","7.66"\n"JST-ST1","5745.87 mm","7.66"\n"JST-ST1","5751.25 mm","7.67"\n"JST-ST1","5756.62 mm","7.68"\n"JST-ST1","5762.00 mm","7.68"\n"Grand total: 13","","99.43"'),
    ("جدول ریزمتره آرماتور (بخش نمونه).txt", '"جدول ریزمتره آرماتورها - Rebar Schedule","","","","","","","","",""\n"Mark","Bar Type","Bar Diameter","Rebar Shape","Material","Count","Spacing","Total Bar Length","Volume","Total Weight"\n"","","","","","","","","","",""\n"STR-ST1-Starter-F","Φ16","16 mm","Rebar Shape 11","IR-Rebar-Fy4000","7","200 mm","76.580 m","0.0154 m³","120.87 kg"\n"STR-ST1-Starter-F","Φ16","16 mm","Rebar Shape 11","IR-Rebar-Fy4000","7","200 mm","17.290 m","0.0035 m³","27.29 kg"\n"STR-ST1-TR-B","Φ14","14 mm","M_00","IR-Rebar-Fy4000","43","200 mm","54.410 m","0.0084 m³","65.75 kg"\n"STR-ST1-TR-T","Φ14","14 mm","M_00","IR-Rebar-Fy4000","44","200 mm","55.740 m","0.0086 m³","67.36 kg"\n"TM-8","A-I-8mm","8 mm","M_00","IR-Rebar-Fy2400","43"," ","318.230 m","0.0160 m³","125.57 kg"\n"TR(1-2)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"\n"TR(1-2)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"\n"TR(2-3)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"\n"TR(2-3)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"\n"TR(3-4)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","59","200 mm","121.540 m","0.0187 m³","146.87 kg"\n"TR(3-4)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","67","200 mm","138.020 m","0.0212 m³","166.79 kg"\n"TR(4-5)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","67","200 mm","138.020 m","0.0212 m³","166.79 kg"\n"TR(4-5)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","67","200 mm","138.020 m","0.0212 m³","166.79 kg"\n"TR(A-B)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","233.160 m","0.0359 m³","281.75 kg"\n"TR(A-B)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","233.160 m","0.0359 m³","281.75 kg"\n"TR(B-C)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","95","200 mm","195.700 m","0.0301 m³","236.49 kg"\n"TR(B-C)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","86","200 mm","177.160 m","0.0273 m³","214.08 kg"\n"TR(C-D)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","212.180 m","0.0327 m³","256.40 kg"\n"TR(C-D)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","212.180 m","0.0327 m³","256.40 kg"\n"Grand total","","","","","","2315","","7720.800 m","1.5289 m³","12001.91 kg"'),
]

# ════════════════════════════════════════════════════════════════
# تنظیمات صفحهٔ Streamlit و CSS راست‌چین
# ════════════════════════════════════════════════════════════════

st.set_page_config(page_title=f"{APP_NAME} | فهرست‌بهای ابنیه ۱۴۰۴", page_icon="🏗️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&display=swap');
html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: 'Vazirmatn', Tahoma, sans-serif !important;
    direction: rtl !important;
}
[data-testid="stSidebar"] { direction: rtl !important; text-align: right !important;
    background: #0d1320 !important; border-left: 1px solid rgba(148,163,184,.15); }
[data-testid="stSidebar"] * { direction: rtl !important; text-align: right !important; }
[data-testid="stMain"] { background: linear-gradient(150deg, #0a0e14 0%, #0d1420 100%); }
[data-testid="stMain"] .block-container { padding-top: 1.6rem; max-width: 1300px; }
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
[data-testid="stMain"] h4, [data-testid="stMain"] p, [data-testid="stMain"] label,
[data-testid="stMain"] span, [data-testid="stMain"] div { color: #e9edf4; }
.hero-box {
    background: linear-gradient(135deg, rgba(242,179,61,.10), rgba(242,179,61,.03));
    border: 1px solid rgba(242,179,61,.30); border-radius: 18px;
    padding: 26px 30px; margin-bottom: 20px;
}
.hero-box h2 { color: #ffd166 !important; font-weight: 800; margin: 0 0 8px; }
.hero-box p { color: #b8c2d4 !important; line-height: 1.9; margin: 0; }
.fin-card { background: rgba(255,255,255,.03); border: 1px solid rgba(148,163,184,.18);
    border-radius: 14px; padding: 13px 18px; margin-bottom: 9px; }
.fin-add { border-right: 4px solid #2dd4bf; }
.fin-ded { border-right: 4px solid #fb7a93; }
.fin-base { border-right: 4px solid #ffd166; background: rgba(45,212,191,.05); }
.fin-net { border-right: 4px solid #ffd166; background: rgba(242,179,61,.08); }
.fin-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 2px; }
.fin-row .lbl { color: #aab4c8; font-size: 13px; }
.fin-row .val { color: #ffffff; font-weight: 700; font-size: 14px; font-variant-numeric: tabular-nums; }
.words-box { background: rgba(45,212,191,.07); border: 1px dashed rgba(45,212,191,.35);
    border-radius: 12px; padding: 12px 16px; color: #9ef0e4 !important; font-size: 13px; line-height: 2; }
div[data-testid="stMetric"] { background: rgba(255,255,255,.04);
    border: 1px solid rgba(148,163,184,.16); border-radius: 14px; padding: 10px 14px; }
div[data-testid="stMetric"] label { color: #98a2b8 !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #ffd166 !important; font-weight: 800; }
.stButton > button { border-radius: 12px !important; font-family: 'Vazirmatn', Tahoma !important;
    border: 1px solid rgba(148,163,184,.25) !important; }
.stButton > button[kind="primary"] { background: linear-gradient(135deg, #f2b33d, #d99a20) !important;
    color: #1a1410 !important; font-weight: 800 !important; border: none !important; }
.stTabs [data-baseweb="tab-list"] { gap: 5px; direction: rtl; }
.stTabs [data-baseweb="tab"] { background: rgba(255,255,255,.04); border-radius: 10px 10px 0 0;
    font-family: 'Vazirmatn' !important; }
.stTabs [aria-selected="true"] { background: rgba(242,179,61,.18) !important; }
hr { border-color: rgba(148,163,184,.2) !important; }
.small-note { font-size: 11.5px; color: #8b95ab !important; line-height: 1.8; }
.warn-y { background: rgba(255,243,205,.12); border: 1px solid rgba(255,196,64,.45);
          color: #ffd166 !important; border-radius: 9px; padding: 8px 12px;
          font-size: 12.5px; font-weight: 600; display: block; margin: 6px 0; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# Session State — مقداردهی اولیهٔ وضعیت برنامه
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# فرض‌های فنی پروژه → کدهای فهرست‌بهای ۱۴۰۴
# این جداول تنها منبع نگاشت مقادیر مجاز به کد و بهای پیش‌فرض هستند.
# مقدار انتخابی کاربر از رابط کاربری (default_settings) خوانده می‌شود و
# TechnicalOfficeEngine._plans() کد/شرح/بهای ردیف را از همین جداول می‌سازد.
# ════════════════════════════════════════════════════════════════

# مقاومت فشاری مشخصهٔ بتن (MPa) → (کد فهرست‌بها، بهای پیش‌فرض ریال)
CONCRETE_STRENGTH_CODES = {12: ("080103", 17996000.0), 16: ("080104", 18904000.0),
                           20: ("080105", 19535000.0), 25: ("080106", 20162000.0),
                           30: ("080107", 20924000.0), 35: ("080108", 21422000.0),
                           40: ("080109", 22200000.0)}
LEAN_CEMENT_CODES = {100: ("080101", 16039000.0), 150: ("080102", 17152000.0)}
# قالب‌بندی دال مستقل (تاوه) بر اساس ارتفاع طبقه (متر) → (کد، بهای پیش‌فرض)
# فصل ۰۶ فهرست‌بهای ابنیه ۱۴۰۴: 060401..060404
SLAB_FORMWORK_CODES = [("le 3.5", "060401", 4107000.0),
                       ("le 5.5", "060402", 4607000.0),
                       ("le 7.5", "060403", 5287000.0),
                       ("gt 7.5", "060404", 6091000.0)]

# ── ارجاع بهای ردیف‌ها (ایراد ۲ و ۴ مرحلهٔ ۱۳) ──
# شمارهٔ ردیف در شیت «Fehrest» فایل Excel فهرست‌بهای پایهٔ ابنیه ۱۴۰۴
# (1404 - 11 - Abnieh - Mshahrainy.xlsx). وضعیت: استخراج‌شده — نیازمند تأیید کاربر.
PRICE_REFS = {
    "060101": "فهرست‌بها ۱۴۰۴ اکسل، شیت Fehrest، ردیف ۲۴۴",
    "060301": "همان، ردیف ۲۵۰",
    "060401": "همان، ردیف ۲۵۴ — قالب‌بندی دال (تاوه) تا ارتفاع ۳/۵ متر",
    "060402": "همان، ردیف ۲۵۵ — دال بالاتر از ۳/۵ تا ۵/۵ متر",
    "060403": "همان، ردیف ۲۵۶ — دال بالاتر از ۵/۵ تا ۷/۵ متر",
    "060404": "همان، ردیف ۲۵۷ — دال بالاتر از ۷/۵ تا ۱۰ متر",
    "060501": "همان، ردیف ۲۵۹",
    "060701": "همان، ردیف ۲۶۴",
    "070101": "همان، ردیف ۲۸۹",
    "070201": "همان، ردیف ۲۹۲",
    "070202": "همان، ردیف ۲۹۳",
    "070203": "همان، ردیف ۲۹۴",
    "080102": "همان، ردیف ۳۱۹",
    "080105": "همان، ردیف ۳۲۲",
    "080106": "همان، ردیف ۳۲۳",
    "080107": "همان، ردیف ۳۲۴",
    "080108": "همان، ردیف ۳۲۵",
    "100305": "همان، ردیف ۴۴۴",
    "100306": "همان، ردیف ۴۴۵",
    "100701": "همان، ردیف ۴۵۴",
    "100702": "همان، ردیف ۴۵۵",
    "280101": "همان، ردیف ۱۴۴۹",
}


def _load_config(name: str, fallback: dict) -> dict:
    """بارگذاری یک فایل داده‌ای JSON از پوشهٔ config/ (در کنار app.py)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return fallback


# ── جداول داده‌محور قابل ویرایش در config/ (مرحلهٔ ۱۳) ──
_STRENGTH_CFG = _load_config("concrete_strength_map.json", {
    "strength_map": {str(k): {"code": v[0], "price": v[1]}
                     for k, v in CONCRETE_STRENGTH_CODES.items()},
    "lean_cement_map": {str(k): {"code": v[0], "price": v[1]}
                        for k, v in LEAN_CEMENT_CODES.items()},
})
CONCRETE_STRENGTH_CODES = {
    int(k): (v["code"], float(v["price"]))
    for k, v in _STRENGTH_CFG.get("strength_map", {}).items()}
LEAN_CEMENT_CODES = {
    int(k): (v["code"], float(v["price"]))
    for k, v in _STRENGTH_CFG.get("lean_cement_map", {}).items()}

REGIONAL_TABLE = _load_config("regional_coefficients.json", {
    "provinces": {}, "meta": {"status": "پیش‌فرض اپ — فایل config/regional_coefficients.json یافت نشد"}})
REBAR_DENSITY_CFG = _load_config("rebar_density_thresholds.json", {
    "thresholds_kg_m3": {"پی": [50, 120], "ستون": [100, 250], "تیر": [100, 200],
                         "دال": [60, 120], "پله": [60, 120]},
    "meta": {"status": "پیش‌فرض اپ"}})
FLOORS_SPEC = _load_config("floors_coefficients.json", {
    "meta": {"status": "پیش‌فرض اپ"},
    "formula": "P = ( sum(i*Fi) + sum(j*Bj) ) / S",
    "apply_to": "تمام اقلام کار ساختمان"})

# شاخص‌های قطعی تعدیل آحادبها (بخشنامه ۱۴۰۵/۱۵۵۲۳۳، پیوست ۳) — استخراج‌شده از
# PDF tadil1404-34.pdf با find_tables؛ هر رکورد صفحهٔ PDF خود را دارد.
INDEX_BULLETINS = _load_config("index_bulletins.json", {
    "meta": {"status": "پیش‌فرض اپ — فایل config/index_bulletins.json یافت نشد"},
    "disciplines": [], "chapters_abnieh": [], "rules": []})
# شاخص بهای مصرف‌کننده ماهانه (مرکز آمار ایران — ۱۴۰۰=۱۰۰)؛ مبنای
# محاسبهٔ خودکار ضریب موقت ۱۴۰۵Q1 (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳، پیوست ص۱).
CPI_MONTHLY = _load_config("cpi_monthly.json", {"months": {}})
# ضریب m به ازای رشته + فرمول و پارامترهای ضریب موقت ۱۴۰۵Q1.
PROVISIONAL_M = _load_config("provisional_m.json", {})
# دورهٔ قیمت پایهٔ هر سال فهرست‌بها (روش اولِ بند ۱-۶-۱ بخشنامهٔ ۲۰۸۰).
# مقدار = کلید سه‌ماهه (مثل «1403Q4») یا null = هنوز وارد نشده. اگر
# سالِ فهرست در این جدول نیست (یا null است)، موتور تعدیل می‌ایستد و
# «نیازمند ورود» می‌دهد (قاعدهٔ طلایی: عدد حدس زده نمی‌شود).
FEHREST_BASE_PERIODS = (INDEX_BULLETINS.get("fehrest_base_periods") or {})
# ضخامت سقف تیرچه‌بلوک (cm) → (کد، بهای پیش‌فرض)
JOIST_BLOCK_THICKNESS_CODES = {25: ("100305", 8391000.0), 30: ("100306", 9101000.0)}
# اضافه‌بهای مقاومت بتن سقف تیرچه‌بلوک (MPa) → (کد، بهای پیش‌فرض) یا None
# بند ۸ الزامات عمومی فصل دهم فهرست‌بهای ۱۴۰۴: بتن سقف ۲۰ MPa فرض شده؛
# بیش از ۲۰ تا ۲۵ MPa → ۱۰۰۷۰۱، بیش از ۲۵ تا ۳۰ MPa → ۱۰۰۷۰۲.
JOIST_BLOCK_STRENGTH_SURCHARGE = {20: None, 25: ("100701", 59500.0), 30: ("100702", 76500.0)}

# ════════════════════════════════════════════════════════════════
# فاز E-6 — بخشنامه 2080: دستورالعمل نحوه تعدیل احاد بهای پیمانها
# سند: بخشنامه شماره 1-9706/54/2080 مورخ 1370/06/23 سازمان برنامه و
# بودجه (docs/sources/2080.pdf). ارجاع بندها در کامنت‌ها و ACCEPTANCE §18.
# ════════════════════════════════════════════════════════════════
# ── فاز E-6: ضریب قانونی k و گردکردن آن (بخشنامهٔ ۲۰۸۰) ──
# منبع: docs/sources/2080.pdf (اسکن ۷ صفحه‌ای). شماره و تاریخ روی خود
# سند درج شده‌اند (صفحهٔ ۴): بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ مورخ ۱۳۷۰/۰۶/۲۳،
# صادرکننده: سازمان برنامه و بودجه (معاون رئیس‌جمهور و رئیس سازمان:
# مسعود روغنی زنجانی). کامل‌ترین متن بندها در docs/sources/2080_summary.md.
# بند ۱-۸: ضریب تعدیل = ۰٫۹۵ (شاخص دورهٔ انجام کار / شاخص مبنا − ۱)
# تبصرهٔ ۲ بند ۱-۸: اگر کار در مدت پیمان (با احتساب تغییر مدت ناشی از
# تغییر مقادیر) تمام و تحویل موقت شود، ۰٫۹۵ به ۱ تبدیل می‌شود.
# بند ۸-۴: مابه‌التفاوت ۰٫۹۵ تا ۱ همزمان با صورت‌وضعیت قطعی پرداخت می‌شود.
# بند ۸-۲: ضریب با ۳ رقم اعشار حساب، سپس به ۲ رقم گرد می‌شود.
TADIL_K_2080 = 0.95        # بند ۱-۸ — ضریب پایه
TADIL_K_COMPLETED = 1.0    # تبصرهٔ ۲ بند ۱-۸ — اتمام کار در مدت پیمان
TADIL_K_SOURCE = ("بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳) — سازمان برنامه و "
                  "بودجه، دستورالعمل تعدیل واحدهای پایهٔ پیمان — بند ۱-۸")
TADIL_K_SOURCE_COMPLETED = TADIL_K_SOURCE + " + تبصرهٔ ۲"

# ── فاز E-6 Part C گام ۱۲ (حرف g): تصمیماتِ باز «منتظر تأیید کاربر» ──
# فاز E-8 §۱: شناسهٔ ثابت و پایدار D-01..D-20 (هرگز عوض نمی‌شود).
# D-01..D-18 = تفسیرهای ابهامِ بخشنامهٔ ۲۰۸۰ (ASC §۱۸-۳).
# D-19/D-20 = دو تصمیمِ وابسته به داده (خارج از تفسیرِ ۲۰۸۰).
# تک‌منبعِ حقیقت برای پنلِ «وضعیت ورودی‌ها» (Streamlit) و شیتِ Excel
# «مقادیر منتظر تأیید». هر ورودی: (شناسه، موضوع، تفسیرِ پیاده‌سازی‌شده،
# گزینهٔ دیگر، اثر عددی). این فهرست باید با §۱۸-۳ ACCEPTANCE.md یکی باشد.
PENDING_INTERPRETATIONS = [
    ("D-01", "ضریب k ورودی کاربر نیست (بند ۱-۸)",
     "k از وضعیت اتمام کار مشتق می‌شود: ۰٫۹۵ (بند ۱-۸) یا ۱ (تبصرهٔ ۲).",
     "ورودیِ دستیِ k مثلِ نسخه‌های قدیم.",
     "k=۱ به‌جای ۰٫۹۵ ⇒ ΔP از ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲ به ۱۰٬۴۸۹٬۵۹۴٬۳۶۹٫۰۷ یعنی "
     "+۵۰۵٬۳۱۶٬۹۶۰٫۸۶ ریال (=`k_diff` بند ۸-۴)."),
    ("D-02", "گرانولاریتیِ گردکردن (بند ۸-۲)",
     "ضریبِ هر فصل در هر سه‌ماهه به‌صورتِ مجزا گرد می‌شود.",
     "گردکردنِ ضریبِ کلِ فصل.",
     "تفاوتِ جزئی در فصل‌هایی با کارکردِ ناتمام."),
    ("D-03", "تفسیر گردکردن (الف)",
     "ضریب با ۳ رقم اعشار با ROUND_HALF_UP؛ اگر رقمِ سوم ≥ ۵ بود رقمِ دوم "
     "بالا می‌رود وگرنه رقمِ سوم برداشته می‌شود.",
     "گردکردنِ مستقیم به ۲ رقم (تفسیر ب).",
     "تفاوتِ حداکثر ۰٫۰۰۵ در هر ضریب."),
    ("D-04", "ضرایب منفی",
     "بخشنامه ساکت است؛ ضرایبِ منفی مجازند و ΔP می‌تواند منفی شود.",
     "صفر کردنِ ضرایبِ منفی.",
     "در صورتِ کاهشِ شاخص، ΔP منفی نشان داده می‌شود."),
    ("D-05", "پیاده‌سازی بدون خطای شناور",
     "پایتون از Decimal روی کوتاه‌ترین نمایشِ float استفاده می‌کند.",
     "استفاده از round() سرّی.",
     "تفاوت در مرزهایِ گردکردن (مثل ۰٫۰۰۵)."),
    ("D-06", "رفتار UI",
     "فیلد عددی k حذف شد و به‌جای آن selectbox برای وضعیت اتمام کار است.",
     "نگه‌داشتنِ فیلد عددی.",
     "فقط تجربهٔ کاربری؛ اعداد تغییر نمی‌کنند."),
    ("D-07", "مبنای کسرِ ۵٪ (بند ۷)",
     "کسر = ۵٪ از کلِ ΔP (مستقل از قطعی/علی‌الحساب).",
     "۵٪ فقط از بخشِ قطعی.",
     "در سناریوی ترکیبی، کسر از کلِ ΔP بیشتر می‌شود."),
    ("D-08", "کسر در تعدیلِ منفی (بند ۷)",
     "اگر ΔP < ۰، کسر اعمال نمی‌شود (هیچ کسری از عددِ منفی کسر نمی‌شود).",
     "اعمالِ کسر در همهٔ حالات (ΔPِ منفی‌تر).",
     "در صورتِ کاهشِ شاخص، کسر صفر می‌شود."),
    ("D-09", "گرانولاریتیِ بند ۲-۶",
     "هر سه‌ماهه‌ای که روز شروعش > آخرین موقت است میانگینِ ۲-۶ را می‌گیرد.",
     "تقسیمِ وزنیِ سه‌ماههٔ مرزی به نسبتِ روزها.",
     "فقط در پروژه‌هایی با lpd نمایش داده می‌شود."),
    ("D-10", "کارِ پوشش‌شده با تمدیدِ مجاز در بند ۲-۶",
     "«مدت پیمان» = مدت اولیه + تمدیدها؛ کارِ قبل از term_end درونِ مدت "
     "محسوب می‌شود و میانگینِ ۲-۶ را می‌گیرد.",
     "شاخصِ همان دوره طبق ۲-۵-۱ (تأخیر مجاز).",
     "فقط در پروژه‌هایی با تمدیدِ مجاز + lpd."),
    ("D-11", "آستانهٔ ۳۰۰ میلیون ریال (بندهای ۲-۱/۲-۲)",
     "مقدار از config (bulletin_2080.threshold_rail) خوانده می‌شود.",
     "ثابتِ هاردکدشده.",
     "با مقدارِ فعلی: هیچ."),
    ("D-12", "مرزِ آستانه (۲-۱/۲-۲)",
     "آستانه و بیشتر ⇒ گروهی (amount >= threshold).",
     "دقیقاً برابر ⇒ رشته‌ای.",
     "فقط در پیمانِ دقیقاً ۳۰۰٬۰۰۰٬۰۰۰ ریالی."),
    ("D-13", "گرانولاریتیِ مسیر رشته‌ای (۲-۱)",
     "در مسیر رشته‌ای همهٔ فصول و تجهیز از شاخصِ رشته استفاده می‌کنند.",
     "فقط فصولی که شاخصِ گروهی ندارند.",
     "پروژهٔ مرجع ابنیه و مسیرِ پیش‌فرض گروهی است؛ اعداد ثابت می‌مانند."),
    ("D-14", "کار جدید بعد از تبدیل مثلِ تجهیز تعدیل می‌شود (۳-۱..۳-۵)",
     "بعد از تبدیل، مبلغِ کار جدید مثلِ تجهیز (بند ۴) با شاخصِ رشته و "
     "شاخه‌های تأخیر تعدیل می‌شود.",
     "فقط جبرانِ ۳-۵ بدونِ تعدیلِ مجدد.",
     "ΔP در پروژهٔ مرجع به‌جای ۰ به ۳۰۹٬۸۳۰٬۰۹۷٫۰۹ ریال می‌رسد."),
    ("D-15", "دورهٔ شاخصِ مبنا در ۳-۲/۳-۳ ناموجود",
     "اگر new_item_base_period خالی یا ناموجود باشد، ردیف ساخته نمی‌شود "
     "و هشدارِ خطا داده می‌شود.",
     "استفاده از آخرین سه‌ماههٔ موجود یا توقفِ موتور.",
     "کار جدید کاملاً نادیده گرفته می‌شود (ΔP ثابت)."),
    ("D-16", "روشِ نامعتبرِ کار جدید به ۳-۱ برمی‌گردد",
     "اگر new_item_method مجاز نباشد، موتور به «فهرست پیمان» برمی‌گردد.",
     "خطا و توقف.",
     "با فرضِ ۳-۱ ادامه می‌یابد (conv = ۱)."),
    ("D-17", "گردنشدنِ ضریبِ تبدیلِ ۳-۵ قبل از ضرب در مبلغ",
     "conv با دقتِ کامل float محاسبه و در مبلغ ضرب می‌شود؛ گردکردنِ ۸-۲ "
     "فقط روی ضرایبِ k×(It/Io−1) اعمال می‌شود.",
     "گردکردنِ conv به n رقم قبل از ضرب.",
     "تفاوت زیرریالی (conv = ۰٫۸۸۳۶۶۴۶۲۳۳۰۸۷۸۹)."),
    ("D-18", "مبنای «مبلغ برآورد» در سقفِ ۱۰٪ نامه-۶ (گام ۷)",
     "مبلغ برآورد بر اساس قیمت‌های پایه = base_total (بدون ضرایب)، نه "
     "grand_total.",
     "grand_total (شاملِ ضرایب).",
     "سقفِ ۲۵٬۵۴۰٬۲۱۹٬۴۷۰٫۷۱ به‌جای ۳۴٬۵۳۰٬۳۷۶٬۷۲۴٫۴۰ — تفاوت "
     "۸٬۹۹۰٬۱۵۷٬۲۵۳٫۶۹ ریال."),
    # ── دو تصمیمِ بازِ خارج از تفسیرِ بخشنامه (وابسته به داده) ──
    ("D-19", "شاخص کلیِ مستقل برای تجهیز/مصالح (بندهای ۱-۲/۲-۳)",
     "در مسیرِ رشته‌ای، شاخصِ رشتهٔ خودِ پروژه خوانده می‌شود؛ شاخصِ کلیِ "
     "مستقل هنوز در config وجود ندارد.",
     "استفاده از شاخصِ کلیِ مستقلِ مرکز آمار (داده نیاز است).",
     "اگر شاخصِ مستقل برابرِ شاخصِ رشته باشد اثر صفر؛ در غیر این صورت "
     "تفاوت روی هزینهٔ تجهیزِ کارگاه (ایراد I-09)."),
    ("D-20", "مصالحِ پای‌کار (بند ۲-۴)",
     "هیچ شاخصِ اختصاصی برای مصالحِ پای‌کار پیاده نشده؛ از شاخصِ رشته "
     "استفاده می‌شود.",
     "شاخصِ اختصاصیِ مصالحِ پای‌کار (کرایهٔ حمل از پایِ کارگاه).",
     "در پروژهٔ مرجع site_setup_amount = ۰ است ⇒ اثر صفر؛ در پروژه‌هایی با "
     "تجهیزِ بالا تفاوت می‌کند."),
]

# ── فاز E-6 Part C گام ۶ (حرف b): مسیر شاخص — بندهای ۲-۱/۲-۲ ──
# پیمانِ با مبلغ اولیهٔ کمتر از آستانه با شاخص رشته‌ای (۲-۱) و آستانه و
# بیشتر با شاخص‌های گروهی (۲-۲) تعدیل می‌شود. منبعِ آستانه:
# config/index_bulletins.json → bulletin_2080.threshold_rail (ارقامِ سال
# ۱۳۷۰ بندهای ۲-۱/۲-۲). اگر کلید نبود، مقدارِ ۳۰۰٬۰۰۰٬۰۰۰ فرض می‌شود و
# موتور هشدار می‌دهد (حدسِ بدونِ هشدار ممنوع است).
_B2080_CFG = (INDEX_BULLETINS.get("bulletin_2080") or {})
if isinstance(_B2080_CFG.get("threshold_rail"), (int, float)) \
        and not isinstance(_B2080_CFG.get("threshold_rail"), bool) \
        and _B2080_CFG["threshold_rail"] > 0:
    CHAIN_THRESHOLD_RIALS = float(_B2080_CFG["threshold_rail"])
    CHAIN_THRESHOLD_MISSING = False
else:
    CHAIN_THRESHOLD_RIALS = 300_000_000.0
    CHAIN_THRESHOLD_MISSING = True

# ── فاز E-6 Part C گام ۷ (حرف c): سقفِ قیمت قابل قبول — نامه-۶ ──
# «در کارهایی که شاخص مبنایشان طبق ۱-۶-۱ یکم است، سقف قیمت قابل قبول
#  حداکثر ۱۰٪ بالاتر از مبلغ برآورد بر اساس قیمت‌های پایه است.»
# منبع: config/index_bulletins.json → bulletin_2080.ceiling_over_estimate_pct.
# اگر کلید نبود، مقدارِ ۱۰٪ فرض می‌شود و موتور هشدار می‌دهد.
if isinstance(_B2080_CFG.get("ceiling_over_estimate_pct"), (int, float)) \
        and not isinstance(_B2080_CFG.get("ceiling_over_estimate_pct"), bool) \
        and _B2080_CFG["ceiling_over_estimate_pct"] > 0:
    CEILING_OVER_ESTIMATE_PCT = float(_B2080_CFG["ceiling_over_estimate_pct"])
    CEILING_MISSING = False
else:
    CEILING_OVER_ESTIMATE_PCT = 10.0
    CEILING_MISSING = True

# ── فاز E-6 Part C گام ۸ (حرف e): آستانهٔ اختلافِ شاخص دستی با config ──
# اگر شاخص دستی بیش از این کسر با شاخصِ config اختلاف داشته باشد، موتور
# هشدار می‌دهد (حدسِ خاموش ممنوع). ۰٫۲۰ = ۲۰٪.
if isinstance(_B2080_CFG.get("manual_index_deviation_pct"), (int, float)) \
        and not isinstance(_B2080_CFG.get("manual_index_deviation_pct"), bool) \
        and _B2080_CFG["manual_index_deviation_pct"] > 0:
    MANUAL_INDEX_DEVIATION_PCT = float(_B2080_CFG["manual_index_deviation_pct"])
    MANUAL_INDEX_DEVIATION_MISSING = False
else:
    MANUAL_INDEX_DEVIATION_PCT = 0.20
    MANUAL_INDEX_DEVIATION_MISSING = True


def _manual_src(manual):
    """منبعِ شاخص دستی (فیلدِ اجباریِ src — گام ۸). → متن یا None."""
    if not isinstance(manual, dict):
        return None
    src = manual.get("src")
    return src.strip() if isinstance(src, str) and src.strip() else None


def _tadil_k(s):
    """ضریب قانونی k بر اساس وضعیت اتمام کار (فاز E-6 — بند ۱-۸ و تبصرهٔ ۲).

    خروجی: (k, برچسب وضعیت، منبع)
    - completed_within_term = True  => k = ۱ (قطعی — تبصرهٔ ۲ بند ۱-۸)
    - completed_within_term = False => k = ۰٫۹۵ (قطعی — بند ۱-۸)
    - completed_within_term = None  => k = ۰٫۹۵ (علی‌الحساب — تکلیف نامشخص)
    """
    _cwt = s.get("completed_within_term")
    if _cwt is True:
        return TADIL_K_COMPLETED, "قطعی — کار در مدت پیمان تمام شد (تبصرهٔ ۲ بند ۱-۸)", \
            TADIL_K_SOURCE_COMPLETED
    if _cwt is False:
        return TADIL_K_2080, "قطعی — کار در مدت پیمان تمام نشد (بند ۱-۸)", \
            TADIL_K_SOURCE
    _lbl = "علی‌الحساب — تکلیف اتمام کار در مدت پیمان نامشخص است (بند ۱-۸)"
    return TADIL_K_2080, _lbl, TADIL_K_SOURCE


def round_coef_2080(x, neg_toward_zero=False):
    """گردکردن ضریب تعدیل طبق بند ۸-۲ بخشنامهٔ ۲۰۸۰.

    ضریب اول با ۳ رقم اعشار حساب می‌شود؛ اگر رقم سوم >= ۵ باشد رقم دوم
    یکی بالا می‌رود وگرنه رقم سوم حذف می‌شود (ضریب نهایی با ۲ رقم اعشار).

    نکته: متن بخشنامه دربارهٔ ضرایب منفی (It < Io) ساکتی است؛ طبق تصمیم
    فاز E-۶ عمل روی قدر مطلق انجام می‌شود (گرد به‌سمت بزرگتر) و علامت
    حفظ می‌شود. این تصمیم صراحتاً در ACCEPTANCE §۱۸ ثبت شده است.

    فاز E-10 §۳ (D-04 گزینهٔ ب): با neg_toward_zero=True گردکردنِ ضرایبِ
    منفی به‌سمتِ صفر انجام می‌شود (−۰٫۱۲۵۰ → −۰٫۱۲)؛ پیش‌فرض False یعنی
    گزینهٔ الف (−۰٫۱۲۵۰ → −۰٫۱۳). مقدارِ این پرچم از تنظیماتِ
    negative_coef_rounding خوانده می‌شود.
    """
    from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP
    if x is None:
        return None
    d = Decimal(str(float(x)))
    neg = d < 0
    if neg:
        d = -d
    # ۱) ضریب با ۳ رقم اعشار (نیم‌به‌بالا)
    r3 = d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    # ۲) رقم سوم اعشار تصمیم می‌گیرد: >= ۵ => رقم دوم بالا می‌رود،
    #    در غیر این صورت رقم سوم حذف می‌شود.
    third = int((r3 * 1000) % 10)
    _dir = ROUND_UP if third >= 5 else ROUND_DOWN
    if neg and neg_toward_zero and third >= 5:
        # D-04 گزینهٔ ب: ضریبِ منفی به‌سمتِ صفر گرد می‌شود
        _dir = ROUND_DOWN
    scaled = (r3 * 100).quantize(Decimal("1"), rounding=_dir)
    r2 = scaled / 100
    if neg:
        r2 = -r2
    return float(r2)



def default_settings() -> dict:
    """تنظیمات پیش‌فرض مالی و محاسباتی پروژه (مرحلهٔ ۱۱ — فهرست‌بهای ۱۴۰۴).

    هیچ ضریب «پرت مصالح» وجود ندارد: طبق کلیات بند ۳ و ۱۴ و فصل ۸ بند ۴،
    افت تراکم و اتلاف حمل/تخلیه در بهای واحد ردیف‌های فهرست‌بها لحاظ شده است.
    """
    return {
        "joist_spacing": 0.55,
        "haul_distance_km": 50,  # مسافت حمل مصالح (km) — بازهٔ ۳۰–۷۵ → ردیف ۲۸۰۱۰۱
        # ── فرض‌های فنی: کد و بهای ردیف بتن/سقف از این مقادیر ساخته می‌شود ──
        "concrete_strength_mpa": {"foundation": 20, "column_beam": 30,
                                  "slab": 25, "stair": 20},
        "lean_cement_kg": 150,        # بتن مگر: ۱۰۰ → ۰۸۰۱۰۱، ۱۵۰ → ۰۸۰۱۰۲
        "joist_block_thickness_cm": 25,  # سقف تیرچه‌بلوک: ۲۵ → ۱۰۰۳۰۵، ۳۰ → ۱۰۰۳۰۶
        "joist_block_concrete_mpa": 25,  # مقاومت بتن سقف تیرچه‌بلوک: ۲۰ → بدون اضافه‌بها، ۲۵ → ۱۰۰۷۰۱، ۳۰ → ۱۰۰۷۰۲
        "joist_block_top_thickness_cm": 5,  # ضخامت بتن روی بلوک طبق مشخصات (cm) — مازاد بر ۵ cm جداگانه
        "surcharge_rebar_density": False,  # اضافه‌بهای ۰۸۰۳۱۱ (سختی ارتعاش بتن) — اختیاری
        "surcharge_reinforced_concrete": False,  # اضافه‌بهای ۰۸۰۳۱۰ (بتن مسلح، per-element) — اختیاری
        "surcharge_thin_concrete": False,       # اضافه‌بهای ۰۸۰۳۰۴ (کف‌سازی ≤ ۱۵cm روی زمین) — اختیاری
        # ── زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸) ──
        # ترتیب: جمع ردیف‌ها × طبقات × بالاسری × منطقه‌ای + تجهیز و برچیدن
        # ضریب طبقات (ایراد ۳): floors_auto=True → فرمول پیوست ۴ از مساحت طبقات.
        # مساحت طبقات از مدل Revit تا جای ممکن؛ بقیهٔ طبقات در floors_data
        # (دستی) وارد شوند. floors_auto=False → floors_coef به‌عنوان ورودی دستی.
        "floors_coef": 1.0, "floors_auto": True, "floors_data": {},
        # مخرج فرمول پیوست ۲: «100×S» (متن رسمی دریافت‌شده) یا «S» (مغایر متن).
        "floors_divisor": "100×S",
        # فصول مستثنی از ضریب طبقات (پیوست ۲ بند ۱-۳: فقط کار ساختمان)؛
        # فصل ۲۸ (حمل و نقل) + فصل ۳۰ به بالا (محوطه‌سازی) مشمول نیستند.
        "floors_excluded_chapters": ["28"],
        # ترازهای بام/مرجع که از فرمول ضریب طبقات مستثنی‌اند (طبقه نیستند).
        # پیش‌فرض اپ: Story6 — فقط ۳ ستون (۱/۸ m³) بدون سقف/تیر ⇒ بام.
        "floors_roof_levels": ["Story6"],
        # ضریب منطقه‌ای (ایراد ۴): regional_coef خالی → جستجو در جدول بخشنامه
        # ۹۴/۶۹۴۱۶ (config/regional_coefficients.json) بر اساس regional_selection.
        # پروژهٔ مرجع: گلستان/گرگان/بخش مرکزی/ابنیه = ۱٫۰۴ (ردیف ۲۰).
        "regional_coef": None,
        "regional_selection": {"province": "گلستان", "city": "گرگان",
                               "district": "مرکزی", "discipline": "ابنیه"},
        "rebar_manual_weight": {},  # وزن دستی میلگرد هر گروه (ایراد ۱۴)
        "overhead_coef": 1.3,  # عمرانی + مناقصه (پروژهٔ ابنیه) — سایر حالت‌ها در UI
        "site_setup_amount": 0.0,  # مبلغ تجهیز و برچیدن کارگاه (ریال) — ورودی کاربر
        # ── کسورات قانونی: فقط برای خروجی جداگانهٔ «خالص پرداختی» ──
        "insurance_pct": 7.8, "tax_pct": 5.0, "good_job_pct": 10.0, "advance_payment": 0.0,
        # ── شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) ──
        # None یا «» → دورهٔ مبنا (بدون تعدیل). دورهٔ هدف از indices/abnieh.json.
        "index_target_period": None,
        # ═══ فاز B: دو موتور مجزای تعدیل (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند) ═══
        # هر دو موتور می‌توانند همزمان فعال باشند؛ ورودی، فرمول، شیت و
        # کارتِ هر کدام کاملاً جداست و روی زنجیرهٔ مالی اثری ندارد.
        "tadil_enabled": False,        # موتور ۱: تعدیل پیمان (فصل به فصل)
        "baravord_enabled": False,     # موتور ۲: برآورد به‌هنگام
        # تاریخ تسلیم پیشنهاد پیمانکار (شمسی) → Io = سه‌ماههٔ آن
        # (پیوست ۳، بند ۱-۲). خالی ⇒ دورهٔ مبنا فهرست (اسفند ۱۴۰۳).
        # ضریب پیشنهادی پیمانکار — فیلد دستی (پیش‌فرض ۱، نیازمند تأیید).
        # در A₀ ضرب می‌شود تا «مبلغ کارکرد به قیمت پیمان» به‌دست آید.
        "proposal_coef": 1.0,
        # مبنای مبلغ پایهٔ A: «با ضرایب» = قیمت پیمان
        # (A۰ × بالاسری × منطقه‌ای × پیشنهادی)، «بدون ضرایب» = قیمت فهرست‌بها.
        # نکته: دستورالعمل ۱۰۱/۱۷۳۰۷۳ فقط PDF تصویری است و بندهای آن
        # استخراج نشدند؛ طبق قاعدهٔ طلایی ۳ حدس زده نمی‌شود.
        # پیش‌فرض: «با ضرایب» (درخواست کاربر).
        "A_basis": "با ضرایب",
        "proposal_date": "",
        # مهلت تسلیم پیشنهاد (شمسی) — در ترک تشریفات خالی است و خود
        # تاریخ تسلیم ملاک است. اگر در تابستان ۱۴۰۵ باشد، Io = شاخص
        # ماهانهٔ خرداد ۱۴۰۵ (بخشنامهٔ ۱۴۴۳۷۴).
        "proposal_deadline": "",
        # شاخص دستی هر فصل: {"06": {"io": 7273.8, "it": 10632.1}, ...}
        # (دستی مقدم بر جدول پیوست ۳؛ صفر یعنی از جدول بخشنامه).
        "chapter_index_manual": {},
        # شاخص دستی رشته (تجهیز/برچیدن و ردیف‌های بدون شاخص فصل — بند ۴)
        "discipline_index_manual": {},
        # شاخص موقت ۱۴۰۵Q1 = این ضریب × آخرین شاخص قطعی (۱۴۰۴Q4).
        # منبع: بخشنامهٔ تعدیل موقت ۱۴۰۵ (PDF تصویری) ⇒ دستی، نیازمند تأیید.
        "provisional_coef_1405q1": None,
        # موتور ۱ — تعدیل پیمان: ΔP = k × Σ_c (It_c/Io_c − 1) × A_c
        # k = ۰٫۹۵ از بخشنامه ۲۰۸۰ (بند ۱-۸)؛ تبصرهٔ ۲: ۱ در صورت
        # اتمام کار در مدت پیمان. مشتق‌شده از ثابت TADIL_K_2080 (فاز E-6).
        "tadil_coef": TADIL_K_2080,
        # فاز E-6: k از وضعیت اتمام کار مشتق می‌شود (بند ۱-۸ و تبصرهٔ ۲).
        # tadil_coef فقط برای سازگاری پروفایل‌های قدیمی است و در محاسبه
        # استفاده نمی‌شود. کار در مدت پیمان تمام/تحویل موقت شده؟
        # True/False/None (None = نامشخص، علی‌الحساب با k = ۰٫۹۵).
        "completed_within_term": None,
        # گردکردن ضریب تعدیل به ۲ رقم اعشار (بند ۸-۲ بخشنامه ۲۰۸۰).
        "coef_rounding_2080": True,
        # فاز E-10 §۳ — D-04: جهتِ گردکردنِ ضرایبِ منفی (بخشنامه ساکت است).
        #   away_from_zero = روی قدر مطلق (−۰٫۱۲۵۰ → −۰٫۱۳) — گزینهٔ الف
        #   toward_zero    = مستقیمِ منفی (−۰٫۱۲۵۰ → −۰٫۱۲) — گزینهٔ ب
        "negative_coef_rounding": "away_from_zero",
        # ═══ فاز E-6 Part C: ورودی‌های قرارداد (بخشنامهٔ ۲۰۸۰) ═══
        # روش تعیین شاخص مبنا (پیوست — بندهای ۱-۶-۱ و ۱-۶-۲):
        #   proposal_period = دورهٔ تسلیم پیشنهاد (روش دوم؛ رفتار فعلی)
        #   fehrest_period  = دورهٔ تهیهٔ فهرست‌بهای پیمان (روش اول)
        #   no_base_list    = پیمان بدون استفاده از فهرست‌بها (۱-۶-۲)
        "base_index_method": "proposal_period",
        # تاریخ تسلیم کتبیِ پیشنهادِ نهایی در ترک تشریفات مناقصه
        # (بند ۱-۶-۱ دوم و ۱-۶-۲). خالی ⇒ ملاک proposal_deadline یا
        # proposal_date است.
        "final_offer_date": "",
        # مدت اولیهٔ پیمان به ماه (بند ۲-۵). None = نامشخص.
        "contract_duration_months": None,
        # تمدیدهای مدت پیمان: [{date, months, kind, doc_no}] که kind یکی
        # از «مجاز» / «غیرمجاز» / «تعیین‌نشده» است (بندهای ۲-۵-۱..۲-۵-۳).
        "contract_extensions": [],
        # وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷ پیوست):
        #   فعال | خاتمه بدون قصور | فسخ با قصور (۵٪ کسر — بند ۷)
        "contract_status": "فعال",
        # کسر ۵٪ در فسخ با قصور، وقتی مبلغ تعدیل منفی است (بند ۷).
        # پیش‌فرض False: متن بند ۷ در مورد تعدیل منفی ساکت است
        # (تفسیر — ACCEPTANCE.md §۱۸-۳).
        "fault_deduction_on_negative": False,
        # مبلغ اولیهٔ پیمان (ریال) — ملاکِ مسیرِ رشته‌ای/گروهی (۲-۱/۲-۲)
        # و سقفِ ۱۰٪ (نامه، بند ۶). None = وارد نشده.
        "contract_initial_amount": None,
        # فاز E-6 Part C گام ۵ (بندهای ۳-۱..۳-۵): کارهای جدید.
        # ۳-۱ = فهرستِ پیمان (شاخص مبنا = مبنای پیمان)؛
        # ۳-۲ = فهرستِ پایه؛ ۳-۳ = قیمت روز؛ ۳-۴ = ترکیب.
        "new_item_method": "فهرست پیمان",
        "new_item_amount": 0.0,               # مبلغ کار جدید (ریال)
        "new_item_amount_attached": 0.0,      # فقط ۳-۴: بخشِ ۳-۱
        "new_item_base_period": "",           # کلید سه‌ماهه (مثل 1404Q2)
        # مسیر شاخص تعدیل: «گروهی» (پیش‌فرض — بند ۲-۲) | «رشته‌ای»
        # (بند ۲-۱) | «خودکار» (از روی contract_initial_amount و آستانهٔ
        # ۳۰۰٬۰۰۰٬۰۰۰ ریال). پروژهٔ مرجع گروهی است.
        "index_method": "گروهی",
        # تاریخ آخرین صورت‌وضعیت موقت (بند ۲-۶). خالی = استفاده نشده.
        "last_provisional_date": "",
        # تبصرهٔ ۱ بند ۲-۶: اگر دورهٔ انجام بخشی قابل تشخیص است، با
        # شاخص همان دوره. «average» = متنِ اصلیِ بند (میانگین).
        "provisional_diff_method": "average",
        "tadil_io_period": "base", "tadil_it_period": "q4",
        "tadil_advance_mode": "کل مبلغ کارکرد",    # یا "کسر پیش‌پرداخت"
        "tadil_delay_mode": "مشمول کل دوره",       # یا "مستثنی کردن دورهٔ تأخیر"
        "tadil_delay_date": "",                     # تاریخ تحویل قرارداد (حالت تأخیر)
        "tadil_allow_negative": True,
        "tadil_approved": False,                    # تا تأیید، خروجی «پیش‌نویس» است
        # موتور ۲ — برآورد به‌هنگام: A_new = Σ_c A_c × It_c/Io_c (بدون k)
        "baravord_io_period": "base", "baravord_it_period": "q4",
        "baravord_approved": False,
        # فرادادهٔ قرارداد (دورهٔ انجام کار، از تب صورت‌وضعیت هم کامل می‌شود)
        "contract_date": "",              # تاریخ شروع پیمان (شمسی) — ایراد ۱۲
        "work_period_start": "",          # شروع دورهٔ انجام کار (شمسی)
        "work_period_end": "",            # پایان دورهٔ انجام کار (شمسی)
        "currency": "rial", "rounding": True,
        # ── پنل قیمت دستی (فاز C — ایراد ۱۵-۴) ──
        # manual_prices: شناسهٔ ردیف/طرح → رکورد قیمت دستی:
        #   {price, source, doc_no, doc_date, note, status, user, at, chapter}
        # manual_codes: شناسه → رکورد کد جایگزین فهرست‌بها:
        #   {code, reason, user, at}
        # excluded: [{"id", "reason", "user", "at"}] (قدیمی: لیست رشته‌ای id)
        # starred_rows: ردیف‌های غیرفهرستی ستاره‌دار (ورود کامل دستی).
        # price_audit: سابقهٔ ویرایش ({at, user, item, field, old, new, source}).
        "manual_prices": {}, "manual_codes": {}, "excluded": [],
        "starred_rows": [], "price_audit": [],
        "price_user": "",                # نام کاربر واردکنندهٔ قیمت‌ها
        "price_diff_warn_pct": 30.0,     # آستانهٔ هشدار اختلاف قیمت (درصد)
        "price_project_file": "",        # مسیر فایل پروژه (برای فایل کناری)
        # ── فاز E-۵: پروفایل پروژه ──
        "fehrest_year": "۱۴۰۴",          # سال فهرست‌بهای انتخابیِ این پروژه
        "fehrest_db_year": "۱۴۰۴",       # سال فهرستِ بارگذاری‌شده (تب «فهرست‌بها»)
        #legacy
        "price_overrides": {},
        # ── فاز E-10.1 §۳: حالتِ ارائه ──
        # demo_mode: واترمارکِ «نسخهٔ نمایشی» روی همهٔ خروجیِ Excel و UI.
        # پروژهٔ نمونه (examples/sample_project) به‌صورتِ پیش‌فرض روشن است.
        "demo_mode": False,
    }


# ════════════════════════════════════════════════════════════════
# پنل قیمت دستی (فاز C) — مدل داده‌ای، مهاجرت و کمک‌توابع
# ════════════════════════════════════════════════════════════════

AUDIT_KIND_LABELS = {"price": "قیمت/کد", "setting": "تنظیمات", "meta": "مشخصات"}
AUDIT_KIND_CODES = {v: k for k, v in AUDIT_KIND_LABELS.items()}

MANUAL_SOURCES = ["بخشنامه", "استعلام", "فاکتور", "توافق", "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)"]
MANUAL_STATUSES = ["قطعی", "دستی", "موقت", "پیش‌فرض اپ", "نیازمند ورود"]


def _manual_record(price, source="بخشنامه", doc_no="", doc_date="", note="",
                   status="دستی", chapter="", user="", at=""):
    """ساخت یک رکورد قیمت/کد دستی با تمام فیلدهای ردیخی‌پذیر (قاعدهٔ طلایی ۲)."""
    return {"price": float(price) if price is not None else 0.0,
            "source": source, "doc_no": doc_no, "doc_date": doc_date,
            "note": note, "status": status, "chapter": chapter,
            "user": user, "at": at}


def append_audit(s, item, field, old, new, source="", kind="price"):
    """ثبت یک رویداد در سابقهٔ ویرایش (§۱۵-۴ بند ۴ — Audit trail).

    ``kind``: «price» (قیمت/کد/استثنا) | «setting» (تنظیمات موتور) |
    «meta» (مشخصات پیمان) — ستون «نوع» در شیت سابقهٔ ویرایش.
    """
    s.setdefault("price_audit", []).append({
        "at": jalali_now_str(),
        "user": s.get("price_user") or "",
        "item": str(item), "field": str(field),
        "old": old, "new": new, "source": source or "",
        "kind": kind})


SETTING_LABELS = {
    "joist_spacing": "فاصلهٔ محور تیرچه",
    "haul_distance_km": "مسافت حمل مصالح",
    "concrete_strength_mpa": "مقاومت بتن‌ها",
    "lean_cement_kg": "بتن مگر",
    "joist_block_thickness_cm": "ضخامت تیرچه‌بلوک",
    "joist_block_concrete_mpa": "مقاومت بتن سقف",
    "joist_block_top_thickness_cm": "ضخامت بتن روی بلوک",
    "surcharge_rebar_density": "اضافه‌بهای چگالی میلگرد",
    "surcharge_reinforced_concrete": "اضافه‌بهای بتن مسلح",
    "surcharge_thin_concrete": "اضافه‌بهای بتن کف‌سازی",
    "floors_coef": "ضریب طبقات",
    "floors_auto": "محاسبهٔ خودکار ضریب طبقات",
    "floors_data": "مساحت طبقات",
    "floors_divisor": "مخرج فرمول ضریب طبقات",
    "floors_excluded_chapters": "فصول مستثنی از ضریب طبقات",
    "floors_roof_levels": "ترازهای بام",
    "regional_coef": "ضریب منطقه‌ای",
    "regional_selection": "انتخاب منطقه",
    "rebar_manual_weight": "وزن دستی میلگرد",
    "overhead_coef": "ضریب بالاسری",
    "site_setup_amount": "تجهیز و برچیدن کارگاه",
    "insurance_pct": "بیمه",
    "tax_pct": "مالیات",
    "good_job_pct": "حسن انجام کار",
    "advance_payment": "پیش‌پرداخت",
    "index_target_period": "دورهٔ هدف شاخص",
    "tadil_enabled": "فعال بودن موتور تعدیل",
    "baravord_enabled": "فعال بودن موتور برآورد",
    "proposal_coef": "ضریب پیشنهادی پیمانکار",
    "proposal_date": "تاریخ تسلیم پیشنهاد",
    "proposal_deadline": "مهلت تسلیم پیشنهاد",
    "A_basis": "مبنای مبلغ پایه",
    "chapter_index_manual": "شاخص دستی فصول",
    "discipline_index_manual": "شاخص دستی رشته",
    "provisional_coef_1405q1": "ضریب موقت ۱۴۰۵Q1",
    "tadil_coef": "ضریب k تعدیل",
    "completed_within_term": "وضعیت اتمام کار در مدت پیمان (الزامی — تبصرهٔ ۲)",
    "coef_rounding_2080": "گردکردن ضریب تعدیل (بند ۸-۲)",
    "negative_coef_rounding": "جهت گردکردن ضرایب منفی (D-04 — بخشنامه ساکت است)",
    "base_index_method": "روش شاخص مبنا (بند ۱-۶)",
    "final_offer_date": "تاریخ پیشنهاد نهایی (ترک تشریفات)",
    "contract_duration_months": "مدت اولیهٔ پیمان (ماه — بند ۲-۵)",
    "contract_extensions": "تمدیدهای مدت پیمان (بند ۲-۵)",
    "contract_status": "وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷)",
    "fault_deduction_on_negative":
    "کسر ۵٪ در فسخ با قصور، حتی با تعدیل منفی",
    "contract_initial_amount": "مبلغ اولیهٔ پیمان (ریال)",
    "new_item_method": "روش قیمتِ کار جدید (بندهای ۳-۱..۳-۵)",
    "new_item_amount": "مبلغ کار جدید (ریال)",
    "new_item_amount_attached": "مبلغ بخشِ ۳-۱ در ترکیب (ریال)",
    "new_item_base_period": "دورهٔ شاخص مبنای کار جدید (سه‌ماهه)",
    "index_method": "مسیر شاخص تعدیل (بندهای ۲-۱/۲-۲)",
    "last_provisional_date": "تاریخ آخرین صورت‌وضعیت موقت (بند ۲-۶)",
    "provisional_diff_method":
    "روش شاخصِ مابه‌التفاوتِ آخرین موقت و قطعی (بند ۲-۶)",
    "tadil_io_period": "دورهٔ Io تعدیل",
    "tadil_it_period": "دورهٔ It تعدیل",
    "tadil_advance_mode": "حالت پیش‌پرداخت تعدیل",
    "tadil_delay_mode": "حالت تأخیر تعدیل",
    "tadil_delay_date": "تاریخ تحویل قرارداد",
    "tadil_allow_negative": "اجازهٔ تعدیل منفی",
    "tadil_approved": "تأیید موتور تعدیل",
    "baravord_io_period": "دورهٔ Io برآورد",
    "baravord_it_period": "دورهٔ It برآورد",
    "baravord_approved": "تأیید موتور برآورد",
    "contract_date": "تاریخ شروع پیمان",
    "work_period_start": "شروع دورهٔ انجام کار",
    "work_period_end": "پایان دورهٔ انجام کار",
    "currency": "واحد پول نمایش",
    "rounding": "رند کردن مبالغ",
    "rebar_manual_weight": "وزن دستی میلگرد",
    "price_user": "نام کاربر واردکنندهٔ قیمت‌ها",
    "price_diff_warn_pct": "آستانهٔ هشدار اختلاف قیمت",
    "fehrest_year": "سال فهرست‌بهای پروژه",
    "fehrest_db_year": "سال فهرست بارگذاری‌شده",
    "demo_mode": "حالتِ نمایشی (واترمارکِ «نسخهٔ نمایشی»)",
}

META_LABELS = {
    "project_name": "نام پروژه",
    "employer": "کارفرما",
    "contractor": "پیمانکار",
    "consultant": "مشاور",
    "contract_no": "شماره پیمان",
    "contract_date": "تاریخ پیمان",
    "location": "محل پروژه",
    "report_no": "شماره گزارش",
    "report_type": "نوع گزارش",
    "period_start": "شروع دورهٔ گزارش",
    "period_end": "پایان دورهٔ گزارش",
}

# کلیدهایی که رویداد اختصاصیِ خود را در سابقهٔ ویرایش دارند یا خودِ سابقه‌اند
# و نباید در تفاضلِ تنظیمات دوبار ثبت شوند.
_AUDIT_DIFF_EXCLUDE = {"price_audit", "manual_prices", "manual_codes",
                       "excluded", "starred_rows", "price_project_file"}


def _audit_sig(v):
    """اثرِ پایدارِ یک مقدار برای مقایسهٔ تغییرات (شامل مقادیر تودرتو)."""
    try:
        return json.dumps(v, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        return repr(v)


def _audit_snap(obj):
    """snapshotِ کلید→اثر، برای مقایسه با پس از تغییرات."""
    return {k: _audit_sig(v) for k, v in obj.items()
            if not (k.startswith("_") or k in _AUDIT_DIFF_EXCLUDE)}


def _audit_diff_apply(obj, before, kind, labels, scope, audit_target):
    """ثبت تفاوتِ یک دیکشنری (settings/meta) با snapshotِ قبل از رندر.

    فاز E-۵: هر تغییرِ ورودیِ پروژه در سابقهٔ ویرایش ثبت می‌شود.
    رویدادها همیشه در ``audit_target`` (یعنی settings.price_audit) ثبت
    می‌شوند تا دیکشنریِ meta آلوده نشود.
    """
    for k, v in obj.items():
        if k in _AUDIT_DIFF_EXCLUDE or k.startswith("_"):
            continue
        if k not in before:
            continue
        after = _audit_sig(v)
        if before[k] != after:
            append_audit(audit_target, scope, labels.get(k, k),
                         before[k], after, "تغییر از رابط کاربری",
                         kind=kind)


def migrate_manual_entries(s):
    """مهاجرت ورودی‌های دستی قدیمی به ساختار ریکاردی فاز C.

    - ``price_overrides`` قدیمی (float) → ``manual_prices`` با منبع «ویرایش
      قدیمی (قبل از مرحلهٔ ۱۳)» و وضعیت «نیازمند تأیید» (درخواست صریح کاربر:
      ویرایش‌های قدیمی باید برچسب شوند ولی ارقام نباید تغییر کنند).
    - ``manual_codes`` قدیمی (رشته) → رکورد با دلیل «ویرایش قدیمی».
    - ``excluded`` قدیمی (لیست رشته) → رکورد بدون دلیل.

    یک‌بار اجرا می‌شود (پرچم ``_manual_migrated``) و Idempotent است.
    """
    if s.get("_manual_migrated"):
        return s
    s["_manual_migrated"] = True

    legacy_po = s.get("price_overrides") or {}
    mp = s.setdefault("manual_prices", {})
    for key, val in legacy_po.items():
        if key in mp:
            continue
        if isinstance(val, dict):
            mp[key] = val
        else:
            mp[key] = _manual_record(
                val, source="ویرایش قدیمی (قبل از مرحلهٔ ۱۳)",
                status="نیازمند تأیید",
                note="قیمت دستیِ واردشده قبل از پنل قیمت دستی فاز C")

    mc = s.setdefault("manual_codes", {})
    for key, val in list(mc.items()):
        if isinstance(val, (str, int, float)) and val:
            mc[key] = {"code": str(val), "reason": "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)",
                       "user": "", "at": ""}

    ex = s.get("excluded") or []
    s["excluded"] = [
        e if isinstance(e, dict) else {"id": str(e), "reason": "", "user": "", "at": ""}
        for e in ex
    ]
    s.setdefault("starred_rows", [])
    s.setdefault("price_audit", [])
    return s


def excluded_ids(s):
    """مجموعهٔ شناسه‌های مستثنی‌شده (پشتیبانی ساختار قدیمی رشته‌ای)."""
    return {e["id"] if isinstance(e, dict) else str(e) for e in (s.get("excluded") or [])}


def manual_code_of(s, plan_id):
    """کد فهرست‌بهای جایگزینِ دستی برای یک طرح (رشته یا رکورد)."""
    v = (s.get("manual_codes") or {}).get(plan_id)
    if isinstance(v, dict):
        return str(v.get("code") or "")
    return str(v) if v else ""


def manual_price_of(s, plan_id):
    """قیمت دستی یک طرح یا None اگر ورودی دستی وجود ندارد.

    پس از مهاجرت فقط ``manual_prices`` مرجع است؛ قبل از آن، ساختار قدیمی
    ``price_overrides`` (float) برای سازگاری با فراخوانی‌های مستقیمِ قبل از
    compute (مثل T14) خوانده می‌شود.
    """
    rec = (s.get("manual_prices") or {}).get(plan_id)
    if rec and rec.get("price") is not None:
        return float(rec["price"])
    if not s.get("_manual_migrated"):
        legacy = s.get("price_overrides") or {}
        v = legacy.get(plan_id)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def price_status_of(line):
    """وضعیت قیمت یک ردیف خروجی — اولویت: دستی > نیازمند ورود > موقت >
    پیش‌فرض اپ > قطعی (§۱۵-۴ بند ۵)."""
    if line.get("manual"):
        return "دستی"
    if line.get("needs_review"):
        return "نیازمند ورود"
    if line.get("estimated"):
        return "موقت"
    if line.get("method") == "fuzzy" and (line.get("confidence") or 0) < 0.5:
        return "پیش‌فرض اپ"
    return "قطعی"


# ── ماندگاری فایل کناری (به ازای هر پروژه، با نسخه و تاریخ + backup) ──

MANUAL_ENTRIES_VERSION = 1
MANUAL_ENTRIES_FIELDS = ("manual_prices", "manual_codes", "excluded",
                         "starred_rows", "price_audit")
# نشانگرهای بخش‌های شیت «قیمت‌های دستی» — خروجی و ورودی باید دقیقاً یکسان
# باشند (نام شیت و عنوان بخش‌ها). تغییر ندهید.
MPX_SHEET = "قیمت‌های دستی"
MPX_AUDIT_SHEET = "سابقهٔ ویرایش"
MPX_VERSION_LABEL = "نسخهٔ قالب"
MPX_SECTION_PRICES = "بخش: قیمت‌های دستی ردیف‌ها"
MPX_SECTION_CODES = "بخش: کدهای جایگزین فهرست‌بها"
MPX_SECTION_EXCLUDED = "بخش: ردیف‌های مستثنی‌شده"
MPX_SECTION_STARRED = "بخش: ردیف‌های ستاره‌دار (غیرفهرستی)"


def manual_entries_payload(s):
    """تصویرِ کامل از ورودی‌های دستی برای ذخیره در فایل کناری یا جابه‌جایی
    بین پروژه‌ها (درون/بیرون Excel)."""
    out = {
        "version": MANUAL_ENTRIES_VERSION,
        "app": "MetreYar",
        "saved_at": jalali_now_str(),
        "user": s.get("price_user") or "",
        "diff_warn_pct": s.get("price_diff_warn_pct", 30.0),
    }
    for k in MANUAL_ENTRIES_FIELDS:
        out[k] = s.get(k) if s.get(k) is not None else ({} if k != "excluded" else [])
    return out


def apply_manual_entries(s, payload):
    """بارگذاری ورودی‌های دستی از payload (فایل کناری یا Excel واردشده).

    payload مرجع است (دقیقاً همان چیزی که ذخیره شده بود). خروجی: لیست
    هشدارهای متناسب.
    """
    warns = []
    if not isinstance(payload, dict):
        return ["فایل ورودی قیمت‌ها ساختار درستی ندارد."]
    if payload.get("version") != MANUAL_ENTRIES_VERSION:
        warns.append(f"نسخهٔ فایل قیمت‌ها ({payload.get('version')}) با نسخهٔ "
                     f"برنامه ({MANUAL_ENTRIES_VERSION}) متفاوت است — ممکن است "
                     f"بخشی از داده‌ها وارد نشوند.")
    for k in MANUAL_ENTRIES_FIELDS:
        if k in payload and isinstance(payload[k], (dict, list)):
            s[k] = payload[k]
    if payload.get("diff_warn_pct"):
        s["price_diff_warn_pct"] = float(payload["diff_warn_pct"])
    s.pop("_manual_migrated", None)
    migrate_manual_entries(s)
    return warns


def save_manual_entries(path, s):
    """ذخیرهٔ ورودی‌های دستی در فایل کناری با backup از نسخهٔ قبلی."""
    import shutil
    payload = manual_entries_payload(s)
    if not path.lower().endswith(".json"):
        path = path + ".json"
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
    return path


def load_manual_entries(path, s):
    """خواندن فایل کناری → apply_manual_entries. خروجی: (path, warns)."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return path, apply_manual_entries(s, payload)


def manual_sidecar_path(project_file):
    """مسیر فایل کناریِ قیمت‌ها برای یک فایل پروژه (همان پوشه، همان نام).

    فاز E-۵: فقط برای خواندن فایل‌های قدیمی استفاده می‌شود؛ پروفایلِ جدید
    در ``profile_sidecar_path`` ذخیره می‌شود.
    """
    if not project_file:
        return ""
    return os.path.splitext(project_file)[0] + "_manual_prices.json"


# ════════════════════════════════════════════════════════════════
# فاز E-۵ — پروفایل پروژه: همهٔ ورودی‌ها در یک فایل JSON مستقل
# ════════════════════════════════════════════════════════════════

PROFILE_KIND = "metreyar_project_profile"
PROFILE_VERSION = 1


def _default_meta():
    """مشخصاتِ پیش‌فرضِ پیمان (هم‌سان با init_session_state)."""
    return {
        "project_name": "", "employer": "", "contractor": "", "consultant": "",
        "contract_no": "", "contract_date": today_jalali(), "location": "",
        "report_no": "۱", "report_type": "موقت", "period_start": "", "period_end": "",
    }


def _camel_to_snake(k):
    """تبدیل کلید camelCase (نسخهٔ TypeScript) به snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z][a-z])", "_", k).lower()


def _adopt_dict(raw, base):
    """پذیرشِ کلیدهای یک دیکشنریِ ذخیره‌شده در پروفایل.

    کلیدها می‌توانند snake_case (پایتون) یا camelCase (TypeScript) باشند.
    فقط کلیدهایی که در ``base`` شناخته‌شده‌اند پذیرفته می‌شوند و بقیه در
    لیستِ dropped برمی‌گردند (قاعدهٔ طلایی ۳: هشدار به‌جای ساختِ داده).
    """
    out = dict(base)
    known = set(base)
    dropped = []
    for k, v in (raw or {}).items():
        if k.startswith("_"):
            continue
        if k in known:
            out[k] = v
        else:
            alt = _camel_to_snake(k)
            if alt != k and alt in known:
                out[alt] = v
            else:
                dropped.append(k)
    return out, dropped


def profile_payload(s, meta):
    """پروفایل کامل پروژه: مشخصات + تنظیمات (شامل ورودی‌های دستی) +
    سابقهٔ ویرایش.

    جایگزینِ فایل کناریِ قدیمی ``_manual_prices.json`` (که فقط قیمت‌ها را
    داشت) می‌شود.
    """
    return {
        "kind": PROFILE_KIND,
        "version": PROFILE_VERSION,
        "exported_at": datetime.now().isoformat(),
        "meta": dict(meta or {}),
        "settings": dict(s or {}),
    }


def save_profile(path, s, meta):
    """ذخیرهٔ پروفایل پروژه در فایل کناری با backup از نسخهٔ قبلی."""
    import shutil
    if not path.lower().endswith(".json"):
        path = path + ".json"
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile_payload(s, meta), f, ensure_ascii=False,
                  indent=1, default=str)
    return path


def load_profile(path_or_bytes):
    """خواندن پروفایل پروژه (JSON) → (meta, settings, warns).

    فایل‌های کناریِ قدیمیِ ``_manual_prices.json`` هم تشخیص داده می‌شوند:
    در آن صورت meta برابر None است و فقط تنظیمات پر می‌شود.
    خطای تجزیه: (None, None, [پیام]).
    """
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            payload = json.loads(path_or_bytes.decode("utf-8"))
        else:
            with open(path_or_bytes, "r", encoding="utf-8") as f:
                payload = json.load(f)
    except Exception as ex:
        return None, None, ["خواندن فایل پروفایل ناموفق بود: %s" % ex]
    if not isinstance(payload, dict):
        return None, None, ["ساختار فایل پروفایل نامعتبر است."]
    warns = []
    if payload.get("kind") == PROFILE_KIND:
        if payload.get("version") != PROFILE_VERSION:
            warns.append("نسخهٔ پروفایل (%s) با نسخهٔ برنامه (%s) متفاوت "
                         "است — ممکن است بخشی از داده‌ها وارد نشوند."
                         % (payload.get("version"), PROFILE_VERSION))
        meta, _drop_m = _adopt_dict(payload.get("meta"), _default_meta())
        s, _drop_s = _adopt_dict(payload.get("settings"), default_settings())
        if _drop_s or _drop_m:
            warns.append("برخی کلیدهای پروفایل ناشناخته بودند و نادیده "
                         "گرفته شدند: %s"
                         % ", ".join(sorted(set(_drop_s + _drop_m))[:10]))
        s.pop("_manual_migrated", None)
        migrate_manual_entries(s)
        return meta, s, warns
    # فایل کناریِ قدیمیِ قیمت‌ها: فقط ورودی‌های دستی
    s = default_settings()
    warns = apply_manual_entries(s, payload)
    return None, s, warns


def profile_sidecar_path(project_file):
    """مسیر پیشنهادی پروفایل پروژه (همان پوشه و نام فایل پروژه)."""
    if not project_file:
        return ""
    return os.path.splitext(project_file)[0] + "_project_profile.json"


def copy_project(s, meta):
    """پروژهٔ جدید از روی پروژهٔ فعلی (فاز E-۵).

    فیلدهای هویتی/زمانی پاک می‌شوند: شماره/نوع گزارش، دورهٔ گزارش،
    شماره/تاریخ پیمان، تاریخ تسلیم و مهلت تسلیم پیشنهاد (Io)، ضریب
    پیشنهادی و دورهٔ انجام کار. تنظیمات فنی و قیمت‌های دستی با سوابقِ سندشان
    نگه داشته می‌شوند. سابقهٔ ویرایش از صفر شروع می‌شود و اولین رکوردش
    «کپی از پروژهٔ X» است.
    """
    src_name = (meta or {}).get("project_name") or ""
    new_meta = dict(meta or {})
    for k in ("report_no", "report_type", "period_start", "period_end",
              "contract_no", "contract_date"):
        new_meta[k] = "۱" if k == "report_no" else ""
    new_meta["project_name"] = ("کپی از " + src_name) if src_name else ""

    new_s = copy.deepcopy(s or {})
    for k in ("proposal_date", "proposal_deadline", "work_period_start",
              "work_period_end", "contract_date", "final_offer_date",
              "last_provisional_date"):
        new_s[k] = ""
    # فاز E-6 Part C: تمدیدها و وضعیت خاتمهٔ پیمانِ پروژهٔ قدیمی
    # معنی ندارند؛ مساحت طبقات هم مالِ ساختمانِ پروژهٔ قبلی است.
    # فلگ‌ها و شاخص‌های دستی نگه داشته می‌شوند (درخواست کاربر، گام ۱۰).
    new_s["contract_extensions"] = []
    new_s["contract_status"] = "فعال"
    new_s["contract_duration_months"] = None
    new_s["floors_data"] = {}
    new_s["proposal_coef"] = 1.0
    # فاز E-6: وضعیت اتمام کار پروژهٔ جدید نامشخص است (k = ۰٫۹۵)
    new_s["completed_within_term"] = None
    new_s["price_audit"] = []
    append_audit(new_s, "پروژه", "copy", src_name, new_meta["project_name"],
                 "دکمهٔ پروژهٔ جدید از روی این پروژه", kind="meta")
    return new_meta, new_s


def parse_manual_entries_xlsx(src):
    """خواندن شیت «قیمت‌های دستی» از یک فایل Excel → payload قابل اعمال.

    ورودی: مسیر فایل یا bytes (خروجی ExcelExporter.export). خروجی: payload
    هم‌ساخت با manual_entries_payload (یا None در صورت نبود شیت).
    مستقل از موتور؛ فقط داده‌ها را برمی‌گرداند.
    """
    import io as _io
    import openpyxl

    if isinstance(src, (bytes, bytearray)):
        wb = openpyxl.load_workbook(_io.BytesIO(src), data_only=True, read_only=True)
    else:
        wb = openpyxl.load_workbook(src, data_only=True, read_only=True)
    try:
        if MPX_SHEET not in wb.sheetnames:
            return None
        rows = [[(c if c is not None else "") for c in r]
                for r in wb[MPX_SHEET].iter_rows(values_only=True)]
        audit_rows = ([[ (c if c is not None else "") for c in r]
                       for r in wb[MPX_AUDIT_SHEET].iter_rows(values_only=True)]
                      if MPX_AUDIT_SHEET in wb.sheetnames else [])
    finally:
        wb.close()

    payload = {"version": MANUAL_ENTRIES_VERSION, "app": "MetreYar",
               "manual_prices": {}, "manual_codes": {},
               "excluded": [], "starred_rows": [], "price_audit": []}

    # نسخهٔ قالب (ردیف نشانگر)
    for r in rows:
        if r and str(r[0]).strip() == MPX_VERSION_LABEL:
            try:
                payload["version"] = int(r[1])
            except (TypeError, ValueError):
                pass
            break

    # بخش‌ها: عنوان → (کل payload، تابع تبدیل). داده‌ها پس از سرستون.
    sections = {
        MPX_SECTION_PRICES: ("manual_prices", _mpx_price_row, dict),
        MPX_SECTION_CODES: ("manual_codes", _mpx_code_row, dict),
        MPX_SECTION_EXCLUDED: ("excluded", _mpx_excluded_row, list),
        MPX_SECTION_STARRED: ("starred_rows", _mpx_starred_row, list),
    }

    i = 0
    while i < len(rows):
        first = str(rows[i][0]).strip() if rows[i] and rows[i][0] else ""
        if first in sections:
            field, fn, kind = sections[first]
            j = i + 2  # ردیف بعدی = سرستون
            while j < len(rows):
                fj = str(rows[j][0]).strip() if rows[j] and rows[j][0] else ""
                if fj.startswith("بخش:"):
                    break
                if fj or any(rows[j][1:]):
                    rec = fn(rows[j])
                    if rec is not None:
                        if kind is dict:
                            payload[field][rec[0]] = rec[1]
                        else:
                            payload[field].append(rec)
                j += 1
            i = j
        else:
            i += 1

    # سابقهٔ ویرایش — ردیف‌های هدر رسمی و سرستون رد می‌شوند
    _HDR_PREFIXES = ("صورت وضعیت", "نام پروژه", "دورهٔ", "مبنای")
    for r in audit_rows:
        if not r or not r[0] or str(r[0]).strip() == "زمان" \
                or str(r[0]).startswith(_HDR_PREFIXES):
            continue
        payload["price_audit"].append({
            "at": str(r[0]), "user": str(r[1] or ""), "item": str(r[2] or ""),
            "field": str(r[3] or ""), "old": r[4], "new": r[5],
            "source": str(r[6] or ""),
            "kind": AUDIT_KIND_CODES.get(str(r[7] or "").strip(), "price")})
    return payload


def _mpx_price_row(r):
    """سطر بخش قیمت‌های دستی → (شناسه, رکورد). None اگر نامعتبر."""
    if not r or not r[0]:
        return None
    try:
        price = float(r[2])
    except (TypeError, ValueError):
        return None
    return (str(r[0]).strip(), {
        "price": price, "source": str(r[5] or "بخشنامه"),
        "doc_no": str(r[6] or ""), "doc_date": str(r[7] or ""),
        "note": str(r[11] or ""), "status": str(r[8] or "دستی"),
        "chapter": str(r[9] or ""), "user": str(r[10] or "").split(" — ")[0].strip(),
        "at": str(r[10] or "").split(" — ")[-1].strip(),
    })


def _mpx_code_row(r):
    if not r or not r[0] or not r[1]:
        return None
    return (str(r[0]).strip(), {
        "code": str(r[1]).strip(), "reason": str(r[2] or ""),
        "user": str(r[3] or ""), "at": str(r[4] or "")})


def _mpx_excluded_row(r):
    if not r or not r[0]:
        return None
    return {"id": str(r[0]).strip(), "reason": str(r[1] or ""),
            "user": str(r[2] or ""), "at": str(r[3] or "")}


def _mpx_starred_row(r):
    if not r or not r[2]:
        return None
    try:
        qty = float(r[3])
        price = float(r[4])
    except (TypeError, ValueError):
        return None
    code = str(r[0] or "").strip()
    return {"code": code, "desc": str(r[1] or ""), "unit": str(r[2] or ""),
            "qty": qty, "price": price, "chapter": str(r[5] or "")[:2],
            "source": str(r[6] or "توافق"), "doc_no": str(r[7] or ""),
            "doc_date": str(r[8] or ""),
            "user": str(r[9] or "").split(" — ")[0].strip(),
            "at": str(r[9] or "").split(" — ")[-1].strip(),
            "note": str(r[10] or "")}


def _regional_options(s):
    """گزینه‌های استان/شهرستان موجود در جدول ضرایب منطقه‌ای (ایراد ۴)."""
    provs = (REGIONAL_TABLE or {}).get("provinces") or {}
    return {p: v for p, v in provs.items() if v}


def _reg_options_coef(opts, prov, s):
    """ضریب پیش‌نمایش استان/شهرستان انتخابی (برچسب selectbox)."""
    sel = s.get("regional_selection") or {}
    disc = sel.get("discipline") or "ابنیه"
    city = sel.get("city")
    entries = opts.get(prov, [])
    for e in entries:
        if e["city"] == city:
            return e["coefs"].get(disc)
    return entries[0]["coefs"].get(disc) if entries else None


# پیش‌فرض‌های بالاسری طبق دستورالعمل کاربرد (بند ۲-۷): نوع پروژه × نوع قرارداد.
OVERHEAD_PRESETS = [
    ("overhead_civil_tender", 1.3, "عمرانی — مناقصه"),
    ("overhead_civil_direct", 1.2, "عمرانی — ترک تشریفات"),
    ("overhead_noncivil_tender", 1.4, "غیرعمرانی — مناقصه"),
    ("overhead_noncivil_direct", 1.3, "غیرعمرانی — ترک تشریفات"),
]


def _default_fehrest_db():
    """پایگاه پیش‌فرض: فهرست‌بهای واقعی ۱۴۰۴ بر پایهٔ embedded (fallback).

    فایل رسمی «all 1404 fehrest.txt» در صورت موجود بودن خوانده و بر روی
    ردیف‌های embedded مرج (merge) می‌شود؛ قیمت‌های رسمی جایگزین تخمینی
    می‌شوند. اگر فایل یافت نشد، همان embedded استفاده می‌شود.
    """
    base = FehrestBahaParser.embedded()
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "fehrest baha 1404", "all 1404 fehrest.txt")
        with open(path, "r", encoding="utf-8") as fh:
            rows, _skipped = FehrestBahaParser.parse_text(fh.read())
        if rows:
            return FehrestBahaParser.merge(base, rows)
    except OSError:
        pass  # فایل رسمی در دسترس نیست — embedded کافی است
    return base


def init_session_state():
    """مقداردهی اولیهٔ یک‌بارهٔ st.session_state برای حفظ وضعیت بین تعاملات."""
    ss = st.session_state
    ss.setdefault("sched_files", [])               # فایل‌های Schedule بارگذاری‌شده (با جدول پارس‌شده)
    ss.setdefault("mapping_results", [])            # خروجی‌های پارس‌شدهٔ فایل‌های Mapping
    ss.setdefault("fehrest_db", _default_fehrest_db())
    ss.setdefault("fehrest_official", True)
    ss.setdefault("settings", default_settings())
    ss.setdefault("meta", {
        "project_name": "", "employer": "", "contractor": "", "consultant": "",
        "contract_no": "", "contract_date": today_jalali(), "location": "",
        "report_no": "۱", "report_type": "موقت", "period_start": "", "period_end": "",
    })
    ss.setdefault("history", [])
    ss.setdefault("demo_loaded", False)


def merged_mapping_df():
    """DataFrame ادغام‌شدهٔ تمام فایل‌های Mapping بارگذاری‌شده."""
    try:
        return DynamoMappingParser.merge_formats(st.session_state.mapping_results)
    except Exception as e:
        _logger.exception("خطا در ادغام Mapping")
        st.warning(f"خطا در ادغام فایل‌های نگاشت: {e}")
        return pd.DataFrame(columns=MAP_CANON_COLS)


def compute_now():
    """محاسبهٔ جریان پروژه با وضعیت فعلی منابع (Schedule + Mapping + تنظیمات)."""
    tables = [f["table"] for f in st.session_state.sched_files if f.get("table")]
    map_df = merged_mapping_df()
    has_map = map_df is not None and not map_df.empty
    if not tables and not has_map:
        return None
    # اعتبارسنجی تاریخ‌های پروژه (ایراد ۱۲): شروع پیمان ≤ شروع دوره ≤
    # پایان دوره. در صورت نقض، محاسبه متوقف می‌شود و خطا نمایش داده می‌شود.
    _meta = getattr(st.session_state, "meta", None) or {}
    _date_errs = TechnicalOfficeEngine.validate_meta(_meta)
    if _date_errs:
        for _e in _date_errs:
            st.error(f"**{_e['item']}:** {_e['message']} {_e['action']}")
        return None
    try:
        engine = TechnicalOfficeEngine(st.session_state.fehrest_db, st.session_state.settings)
        return engine.compute(tables, map_df if has_map else None)
    except Exception as e:
        _logger.exception("خطای موتور محاسبات")
        st.error(f"خطا در محاسبهٔ متره: {e}")
        return None


def load_demo():
    """بارگذاری دادهٔ نمونهٔ نمایشی (دمو — زیرمجموعهٔ پروژه، نه پروژهٔ مرجع)."""
    existing = {f["name"] for f in st.session_state.sched_files}
    for name, text in DEMO_SCHEDULES:
        if name in existing:
            continue
        st.session_state.sched_files.append({
            "name": name, "size": len(text), "text": text,
            "table": RevitScheduleParser.parse(name, text),
        })
    st.session_state.demo_loaded = True
    st.toast("دادهٔ نمونه (دمو) بارگذاری شد.", icon="✅")


# ════════════════════════════════════════════════════════════════
# رندر نوار کناری (ضرایب پیمان و کسورات قانونی)
# ════════════════════════════════════════════════════════════════

def _floors_table_ui(settings):
    """جدول طبقات برای رندر ورودی‌های دستی در سایدبار (سبک — بدون compute)."""
    tables = [f["table"] for f in st.session_state.sched_files if f.get("table")]
    if not tables:
        return []
    try:
        eng = TechnicalOfficeEngine(st.session_state.fehrest_db, settings)
        recs = []
        for t in tables:
            recs.extend(eng._records_from_table(t))
        return eng._floors_table(recs)
    except Exception:
        _logger.debug("floors table UI failed", exc_info=True)
        return []


def render_sidebar():
    """رندر نوار کناری: برند، ضرایب فهرست‌بها، کسورات قانونی و تنظیمات نمایش."""
    s = st.session_state.settings
    with st.sidebar:
        st.markdown(f"## {APP_NAME}")
        st.caption(f"نسخهٔ {APP_VERSION} · فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴")
        st.markdown("---")

        st.markdown("#### ضرایب پیمان (فهرست‌بها)")
        st.caption("زنجیره: جمع ردیف‌ها × طبقات × بالاسری × منطقه‌ای + تجهیز و برچیدن")
        # ضریب طبقات (ایراد ۳): پیش‌فرض از فرمول پیوست ۲؛ ورودی دستی اختیاری
        if st.checkbox("محاسبهٔ خودکار ضریب طبقات (فرمول پیوست ۲ — نیازمند مساحت طبقات)",
                       value=bool(s.get("floors_auto", True)), key="sb-coef-floors-auto"):
            s["floors_auto"] = True
            s["floors_coef"] = None
            _div_opts = ["100×S", "S"]
            _div_cur = s.get("floors_divisor") or "100×S"
            s["floors_divisor"] = st.selectbox(
                "مخرج فرمول پیوست ۲", _div_opts,
                index=_div_opts.index(_div_cur) if _div_cur in _div_opts else 0,
                format_func=lambda v: ("100×S (متن رسمی بخشنامه)" if v == "100×S"
                                       else "S (مغایر متن رسمی — هشدار ثبت می‌شود)"),
                key="sb-coef-floors-divisor",
                help="متن رسمی دریافت‌شده مخرج را «۱۰۰ × S» نوشته است. گزینهٔ "
                     "«S» با متن رسمی مغایرت دارد و در رجیستری هشدار ثبت "
                     "می‌شود. هر دو مقدار P در شیت «ضریب طبقات» نمایش داده "
                     "می‌شوند.")
            _ch_opts = ["06", "07", "08", "09", "10", "28"]
            _exc = s.get("floors_excluded_chapters") or ["28"]
            s["floors_excluded_chapters"] = st.multiselect(
                "فصول مستثنی از ضریب طبقات (پیوست ۲ — بند ۱-۳)",
                options=_ch_opts,
                default=[c for c in _exc if c in _ch_opts],
                key="sb-coef-floors-excluded",
                help="ضریب طبقات فقط به اقلام کار ساختمان اعمال می‌شود. "
                     "پیش‌فرض اپ: فصل ۲۸ (حمل و نقل) و فصل ۳۰ به بالا "
                     "(محوطه‌سازی) مستثنی‌اند.")
            st.caption("مساحت هر طبقه از مدل Revit خوانده می‌شود؛ طبقات بدون "
                       "مساحت را در ادامه دستی وارد کنید. ترازهایی که بام/مرجع "
                       "هستند (طبقه نیستند) را علامت بزنید تا از فرمول مستثنی شوند.")
            with st.expander("مساحت طبقات (دستی — مقدار مدل کنار هر فیلد)"):
                _ft = _floors_table_ui(s)
                if not _ft:
                    st.caption("هیچ ترازی در دادهٔ Schedule یافت نشد.")
                _KIND2 = {"below_base": "زیر همکف", "ground": "همکف",
                          "above": "بالاتر از همکف", "roof": "بام/مرجع",
                          "none": "غیرطبقه‌ای (فونداسیون)"}
                _fd = s.setdefault("floors_data", {})
                _roof = s.setdefault("floors_roof_levels", [])
                for r in _ft:
                    _nm = r["name"]
                    _is_roof = _nm in _roof or r["kind"] == "roof"
                    if st.checkbox(f"تراز {_nm} بام/مرجع است (حساب طبقه نمی‌شود)",
                                   value=_is_roof, key=f"sb-floor-roof-{_nm}"):
                        if _nm not in _roof:
                            _roof.append(_nm)
                        st.caption("از صورت و مخرج فرمول ضریب طبقات مستثنی شد.")
                        continue
                    if _nm in _roof:
                        _roof.remove(_nm)
                    _mv = r["area_model"]
                    _h = ("مقدار مدل: " + fa_float(_mv) + " مترمربع"
                          if isinstance(_mv, (int, float)) else "مقدار مدل: ندارد")
                    _cur = _fd.get(_nm)
                    _cur_area = _cur.get("area") if isinstance(_cur, dict) else _cur
                    _cur_floor = (_cur.get("is_floor") if isinstance(_cur, dict)
                                  else None)
                    _auto_floor = r["auto_kind"] != "none"
                    _is_floor = st.checkbox(
                        f"تراز {_nm} طبقه است",
                        value=_cur_floor if _cur_floor is not None else _auto_floor,
                        key=f"sb-floor-isfloor-{_nm}",
                        help=("ترازهای فونداسیون و غیرطبقه‌ای پیش‌فرض از فرمول "
                              "مستثنی‌اند؛ اگر این تراز طبقهٔ واقعی است علامت "
                              "بزنید تا در Σ بیاید."))
                    _v = st.number_input(
                        f"مساحت {_nm} ({_KIND2.get(r['kind'], r['kind'])}) — m²",
                        value=float(_cur_area) if isinstance(_cur_area, (int, float))
                        else 0.0,
                        step=1.0, format="%.1f", min_value=0.0,
                        help=_h, key=f"sb-floor-area-{_nm}")
                    _rec = {}
                    if _is_floor != _auto_floor:
                        _rec["is_floor"] = _is_floor
                    if _v > 0:
                        _rec["area"] = float(_v)
                    if _rec:
                        _fd[_nm] = _rec
                    else:
                        _fd.pop(_nm, None)
        else:
            s["floors_auto"] = False
            s["floors_coef"] = st.number_input(
                "ضریب طبقات (دستی)", value=float(s.get("floors_coef") or 1.0),
                step=0.01, format="%.2f", key="sb-coef-floors")
        _ov_labels = [lbl for _, _, lbl in OVERHEAD_PRESETS]
        _ov_vals = [v for _, v, _ in OVERHEAD_PRESETS]
        _cur_ov = float(s["overhead_coef"])
        _ov_idx = _ov_vals.index(_cur_ov) if _cur_ov in _ov_vals else len(_ov_vals)
        _sel = st.selectbox(
            "ضریب بالاسری (دستورالعمل کاربرد بند ۲-۷)",
            _ov_vals + [_cur_ov], index=_ov_idx,
            format_func=lambda v: (_ov_labels[_ov_vals.index(v)]
                                   if v in _ov_vals else f"سفارشی — {fa(v)}"),
            key="sb-coef-overhead")
        s["overhead_coef"] = float(_sel)
        # ضریب منطقه‌ای (ایراد ۴): جدول بخشنامه ۹۴/۶۹۴۱۶ به‌صورت پیش‌فرض؛
        # ورودی دستی فقط با تأیید کاربر جایگزین می‌شود.
        _reg_opts = _regional_options(s)
        if _reg_opts:
            _provs = list(_reg_opts)
            _pv = s["regional_selection"]["province"]
            _pv = _pv if _pv in _provs else _provs[0]
            s["regional_selection"]["province"] = st.selectbox(
                "استان (ضریب منطقه‌ای — بخشنامه ۹۴/۶۹۴۱۶)", _provs,
                index=_provs.index(_pv), key="sb-coef-reg-prov",
                format_func=lambda v: f"{v} ({fa_float(_reg_options_coef(_reg_opts, v, s))})")
            _cities = sorted({e["city"] for e in _reg_opts[_pv]})
            _ct = s["regional_selection"]["city"]
            _ct = _ct if _ct in _cities else _cities[0]
            s["regional_selection"]["city"] = st.selectbox(
                "شهرستان", _cities, index=_cities.index(_ct), key="sb-coef-reg-city")
            _disc = s["regional_selection"].get("discipline") or "ابنیه"
            s["regional_selection"]["discipline"] = st.selectbox(
                "رشته", ["ابنیه", "تاسیسات مکانیکی", "تاسیسات برقی", "راه و راه‌آهن",
                         "خطوط انتقال و توزیع آب", "آبیاری و زهکشی"],
                index=["ابنیه", "تاسیسات مکانیکی", "تاسیسات برقی", "راه و راه‌آهن",
                       "خطوط انتقال و توزیع آب", "آبیاری و زهکشی"].index(_disc),
                key="sb-coef-reg-disc")
            st.caption("ضریب استخراج‌شده از جدول بخشنامه ۹۴/۶۹۴۱۶ (نیازمند تأیید کاربر).")
        _reg_manual = s.get("regional_coef")
        if st.checkbox("ورود دستی ضریب منطقه‌ای (جایگزین جدول)",
                       value=(_reg_manual not in (None, "")), key="sb-coef-reg-manual"):
            s["regional_coef"] = st.number_input(
                "ضریب منطقه‌ای (دستی)", value=float(_reg_manual or 1.0),
                step=0.01, format="%.2f", key="sb-coef-regional")
        else:
            s["regional_coef"] = None
        s["site_setup_amount"] = st.number_input(
            "تجهیز و برچیدن کارگاه (ریال — مبلغ)",
            value=float(s["site_setup_amount"]), step=1000000.0, format="%.0f",
            key="sb-coef-site-setup")
        st.caption("هشدار: سقف تجهیز و برچیدن ۴٪ مبلغ قبل از آن است (دستورالعمل ۲-۸).")
        st.markdown("---")
        st.markdown("#### کسورات قانونی (فقط برای «خالص پرداختی»)")
        st.caption("کسورات بر «ناخالص نهایی» اثر ندارند و در خروجی جداگانه محاسبه می‌شوند.")
        s["insurance_pct"] = st.number_input("بیمه (٪)", value=float(s["insurance_pct"]),
                                             step=0.1, format="%.2f", key="sb-ded-insurance")
        s["tax_pct"] = st.number_input("مالیات (٪)", value=float(s["tax_pct"]),
                                       step=0.5, format="%.1f", key="sb-ded-tax")
        s["good_job_pct"] = st.number_input("حسن انجام کار (٪)", value=float(s["good_job_pct"]),
                                            step=0.5, format="%.1f", key="sb-ded-good-job")
        s["advance_payment"] = st.number_input("پیش‌پرداخت (ریال)", value=float(s["advance_payment"]),
                                               step=1000000.0, format="%.0f", key="sb-ded-advance")
        st.markdown("---")
        st.markdown("#### شاخص تعدیل فهرست‌بها (کلیات بند ۲۲)")
        _it = IndexTable.load() if os.path.exists(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "indices", "abnieh.json")) else IndexTable.empty()
        _periods = list(_it.periods)
        _tgt = s.get("index_target_period") or _it.base_period
        if _periods:
            _p_idx = _periods.index(_tgt) if _tgt in _periods else 0
            s["index_target_period"] = st.selectbox(
                "دورهٔ هدف شاخص", _periods, index=_p_idx,
                format_func=lambda p: (f"{p} (مبنا — بدون تعدیل)" if p == _it.base_period else p),
                key="sb-index-period")
        else:
            st.caption("فایل شاخص (indices/abnieh.json) یافت نشد — تعدیل غیرفعال است.")
        st.markdown("---")
        # ═══ فاز B: دو موتور مجزای تعدیل ═══
        st.markdown("#### موتورهای تعدیل (فاز B)")
        st.caption("دو موتور مستقل: «تعدیل پیمان» فصل به فصل با "
                   "ΔP = k × Σ_c (It_c/Io_c − 1) × A_c و «برآورد به‌هنگام» با "
                   "A_new = Σ_c A_c × It_c/Io_c. هر دو می‌توانند همزمان فعال "
                   "شوند ولی هرگز ادغام نمی‌شوند و روی زنجیرهٔ مالی بالا اثری "
                   "ندارند. مبالغ دقیق تا ریال نمایش داده می‌شوند.")
        s["tadil_enabled"] = st.checkbox("موتور ۱ — تعدیل پیمان (فعال)",
                                         value=bool(s.get("tadil_enabled")),
                                         key="sb-tadil-on")
        s["baravord_enabled"] = st.checkbox("موتور ۲ — برآورد به‌هنگام (فعال)",
                                            value=bool(s.get("baravord_enabled")),
                                            key="sb-baravord-on")
        _periods_b = TechnicalOfficeEngine.index_periods()
        _pl = {p["key"]: p["label"] for p in _periods_b}

        def _adj_period(setting_key, label, default_key="base",
                        allow_provisional=False):
            """انتخاب دورهٔ شاخص از جدول استخراجی پیوست ۳.

            allow_provisional=True گزینهٔ «۱۴۰۵Q1 (موقت)» را هم اضافه می‌کند
            — فقط برای دورهٔ انجام کار (It)، نه مبنا (Io).
            """
            if not _periods_b:
                st.caption("جدول شاخص (config/index_bulletins.json) یافت نشد — "
                           "شاخص‌ها را دستی وارد کنید.")
                return None
            _keys = [p["key"] for p in _periods_b]
            _labels = dict(_pl)
            if allow_provisional:
                _keys = _keys + ["1405Q1", "1405Q2", "1405Q3", "1405Q4"]
                _labels["1405Q1"] = "سه‌ماههٔ اول ۱۴۰۵ (موقت)"
                _labels["1405Q2"] = "سه‌ماههٔ دوم ۱۴۰۵ (موقت)"
                _labels["1405Q3"] = "سه‌ماههٔ سوم ۱۴۰۵ (موقت)"
                _labels["1405Q4"] = "سه‌ماههٔ چهارم ۱۴۰۵ (موقت)"
            _cur = s.get(setting_key) or default_key
            _i = _keys.index(_cur) if _cur in _keys else _keys.index(default_key)
            _sel = st.selectbox(label, _keys, index=_i,
                                format_func=lambda k: _labels[k],
                                key=f"sb-{setting_key}")
            if TechnicalOfficeEngine._quarter_is_provisional(_sel):
                st.markdown('<span class="warn-y">علی‌الحساب — بند ۳ '
                            'بخشنامهٔ ۱۴۴۳۷۳ (ضریب موقت از CPI + m)</span>',
                            unsafe_allow_html=True)
            return _sel

        s["proposal_date"] = _jalali_input("تاریخ تسلیم پیشنهاد (شمسی) — Io",
                                           "sb-proposal-date",
                                           s.get("proposal_date") or "")
        s["proposal_deadline"] = _jalali_input(
            "مهلت تسلیم پیشنهاد (شمسی) — در ترک تشریفات خالی",
            "sb-proposal-deadline",
            s.get("proposal_deadline") or "")
        st.caption("Io = سه‌ماههٔ تاریخ مهلت تسلیم (یا خود تاریخ تسلیم در "
                   "ترک تشریفات) — پیوست ۳، بند ۱-۲. برای موتور تعدیل "
                   "پیمان یکی از این دو الزامی است (خالی یا نامعتبر ⇒ "
                   "توقف موتور)؛ برای برآورد به‌هنگام پیش‌فرض اسفند ۱۴۰۳ "
                   "استفاده می‌شود. نکته (بخشنامهٔ ۱۴۴۳۷۴): اگر مهلت تسلیم "
                   "در تابستان ۱۴۰۵ باشد، Io شاخص ماهانهٔ خرداد ۱۴۰۵ است "
                   "و تا وارد شدن آن شاخص، موتورها متوقف می‌شوند.")
        s["A_basis"] = st.selectbox(
            "مبنای مبلغ پایهٔ A", ["با ضرایب", "بدون ضرایب"],
            index=0 if s.get("A_basis") != "بدون ضرایب" else 1,
            key="sb-a-basis")
        st.caption("«با ضرایب» = مبلغ کارکرد به قیمت پیمان (A۰ × بالاسری × "
                   "منطقه‌ای × ضریب پیشنهادی پیمانکار)؛ «بدون ضرایب» = "
                   "قیمت فهرست‌بها. منبع: دستورالعمل ۱۰۱/۱۷۳۰۷۳ (PDF "
                   "تصویری — بندهای آن استخراج نشدند؛ نیازمند تأیید).")
        _pc0 = s.get("proposal_coef")
        s["proposal_coef"] = st.number_input(
            "ضریب پیشنهادی پیمانکار", min_value=0.0, step=0.01,
            value=float(_pc0) if isinstance(_pc0, (int, float)) and _pc0 else 1.0,
            format="%.2f", key="sb-proposal-coef")
        st.markdown('<span class="warn-y">دستی — نیازمند تأیید (پیش‌فرض ۱)</span>',
                    unsafe_allow_html=True)

        with st.expander("شاخص دستی فصل‌ها (دستی مقدم بر جدول بخشنامه)"):
            _chaps = st.session_state.get("adj_chapters") or \
                ["06", "07", "08", "09", "10", "28"]
            st.caption("فصل‌هایی که شاخص آن‌ها از پیوست ۳ استخراج نشده یا "
                       "می‌خواهید اصلاح کنید را پر کنید؛ صفر یعنی از جدول "
                       "بخشنامه استفاده شود.")
            if not isinstance(s.get("chapter_index_manual"), dict):
                s["chapter_index_manual"] = {}
            for _ch in _chaps:
                _cur = s["chapter_index_manual"].get(_ch) or {}
                c2 = st.columns([1.2, 0.9, 0.9, 1.4])
                c2[0].caption("فصل %s — %s" % (_ch, chapter_title(_ch)))
                _cio = c2[1].number_input("Io", min_value=0.0, step=1.0,
                                          value=float(_cur.get("io") or 0.0),
                                          format="%.2f", key="sb-cio-%s" % _ch)
                _cit = c2[2].number_input("It", min_value=0.0, step=1.0,
                                          value=float(_cur.get("it") or 0.0),
                                          format="%.2f", key="sb-cit-%s" % _ch)
                # فاز E-6 Part C گام ۸: منبعِ شاخص دستی اجباری است
                _csrc = c2[3].text_input(
                    "منبع (اجباری)", value=str(_cur.get("src") or ""),
                    placeholder="مثلاً «پیوست ۳، صفحهٔ ۸۲»",
                    key="sb-csrc-%s" % _ch)
                if _cio > 0 or _cit > 0:
                    s["chapter_index_manual"][_ch] = {
                        "io": _cio or None, "it": _cit or None,
                        "src": _csrc.strip() or None}
                elif _cur.get("src"):
                    s["chapter_index_manual"][_ch] = {"src": _csrc.strip()}

        with st.expander("شاخص دستی رشته (تجهیز و ردیف‌های بدون شاخص فصل)"):
            if not isinstance(s.get("discipline_index_manual"), dict):
                s["discipline_index_manual"] = {}
            _dm = s["discipline_index_manual"]
            c2 = st.columns([1, 1, 1.4])
            _dio = c2[0].number_input("شاخص Io رشته", min_value=0.0, step=1.0,
                                      value=float(_dm.get("io") or 0.0),
                                      format="%.2f", key="sb-dio")
            _dit = c2[1].number_input("شاخص It رشته", min_value=0.0, step=1.0,
                                      value=float(_dm.get("it") or 0.0),
                                      format="%.2f", key="sb-dit")
            # فاز E-6 Part C گام ۸: منبعِ شاخص دستی اجباری است
            _dsrc = c2[2].text_input(
                "منبع رشته (اجباری)", value=str(_dm.get("src") or ""),
                placeholder="مثلاً «نامهٔ کارفرما»", key="sb-dsrc")
            if _dio > 0 or _dit > 0:
                s["discipline_index_manual"] = {"io": _dio or None,
                                                "it": _dit or None,
                                                "src": _dsrc.strip() or None}

        _pc = s.get("provisional_coef_1405q1")
        _pcv = st.number_input("ضریب شاخص موقت ۱۴۰۵Q1 (دستی)", min_value=0.0,
                               step=0.001,
                               value=float(_pc) if isinstance(_pc, (int, float)) and _pc
                               else 0.0, format="%.3f", key="sb-prov-1405q1")
        s["provisional_coef_1405q1"] = _pcv if _pcv > 0 else None
        st.caption("موقت = این ضریب × آخرین شاخص قطعی (۱۴۰۴Q4). منبع: بخشنامهٔ "
                   "۱۴۰۵/۱۴۴۳۷۳، پیوست ص۱ (فرمول از CPI + m). اگر خالی باشد، "
                   "ضریب خودکار از CPI + m محاسبه می‌شود؛ اگر شاخص ماهانهٔ CPI "
                   "ناقص باشد، موتورها متوقف می‌شوند.")
        if s["tadil_enabled"]:
            st.markdown("**موتور ۱ — تعدیل پیمان**")
            # فاز E-6: k از وضعیت اتمام کار مشتق می‌شود (بند ۱-۸ و تبصرهٔ ۲)
            _cwt_opts = ["نامشخص (علی‌الحساب، k = ۰٫۹۵)",
                         "بله، تمام و تحویل موقت شده (k = ۱)",
                         "خیر (k = ۰٫۹۵)"]
            _cwt = s.get("completed_within_term")
            _cwt_idx = 1 if _cwt is True else (2 if _cwt is False else 0)
            _cwt_sel = st.selectbox(
                "کار در مدت پیمان (با احتساب تمدیدهای ناشی از تغییر مقادیر) "
                "تمام و تحویل موقت شده؟ (تبصرهٔ ۲ بند ۱-۸)",
                _cwt_opts, index=_cwt_idx, key="sb-cwt")
            s["completed_within_term"] = {
                _cwt_opts[0]: None, _cwt_opts[1]: True,
                _cwt_opts[2]: False}[_cwt_sel]
            s["coef_rounding_2080"] = st.checkbox(
                "گردکردن ضریب تعدیل به ۲ رقم اعشار (بند ۸-۲ بخشنامهٔ ۲۰۸۰)",
                value=bool(s.get("coef_rounding_2080")),
                key="sb-coef-round-2080")
            # فاز E-10 §۳ — D-04: جهتِ گردکردنِ ضرایبِ منفی (بخشنامه ساکت است)
            s["negative_coef_rounding"] = (
                "toward_zero" if st.checkbox(
                    "گردکردن ضرایبِ منفی به‌سمتِ صفر (D-04 — −۰٫۱۲۵۰ → −۰٫۱۲)؛ "
                    "خاموش: روی قدرِ مطلق (−۰٫۱۲۵۰ → −۰٫۱۳)",
                    value=s.get("negative_coef_rounding") == "toward_zero",
                    key="sb-neg-coef-round") else "away_from_zero")
            st.caption("k = ۰٫۹۵ (بند ۱-۸) یا ۱ (تبصرهٔ ۲) — مشتق از "
                       "بخشنامهٔ ۲۰۸۰ (docs/sources/2080.pdf). "
                       "مابه‌التفاوت ۰٫۹۵ → ۱ طبق بند ۸-۴ همزمان "
                       "با صورت‌وضعیت قطعی پرداخت می‌شود.")
            # ═══ فاز E-6 Part C: ورودی‌های قرارداد (بخشنامهٔ ۲۰۸۰) ═══
            with st.expander("ورودی‌های قرارداد (بخشنامهٔ ۲۰۸۰)"):
                _bim_opts = [("proposal_period",
                              "دورهٔ تسلیم پیشنهاد (بند ۱-۶-۱ دوم)"),
                             ("fehrest_period",
                              "دورهٔ تهیهٔ فهرست‌بها (بند ۱-۶-۱ یکم)"),
                             ("no_base_list",
                              "پیمان بدون فهرست‌بها (بند ۱-۶-۲)")]
                _bim_keys = [o[0] for o in _bim_opts]
                _bim = s.get("base_index_method") or "proposal_period"
                s["base_index_method"] = st.selectbox(
                    "روش شاخص مبنا (Io)", _bim_keys,
                    format_func=lambda x: dict(_bim_opts)[x],
                    index=_bim_keys.index(_bim)
                    if _bim in _bim_keys else 0, key="sb-bim")
                s["final_offer_date"] = st.text_input(
                    "تاریخ تسلیم کتبیِ پیشنهاد نهایی — ترک تشریفات"
                    " (بند ۱-۶-۱ دوم)",
                    value=s.get("final_offer_date") or "",
                    key="sb-final-offer")
                st.caption("در ترک تشریفاتِ مناقصه، ملاکِ Io این تاریخ "
                           "است. خالی ⇒ مهلت تسلیم، و اگر آن هم نبود، "
                           "تاریخ تسلیم پیشنهاد.")
                _cs_opts = [("فعال", "فعال"),
                            ("خاتمه بدون قصور", "خاتمه بدون قصور"),
                            ("فسخ با قصور", "فسخ با قصور — ۵٪ کسر (بند ۷)")]
                _cs = s.get("contract_status") or "فعال"
                s["contract_status"] = st.selectbox(
                    "وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷)",
                    [o[0] for o in _cs_opts],
                    format_func=lambda x: dict(_cs_opts)[x],
                    index=[o[0] for o in _cs_opts].index(_cs)
                    if _cs in [o[0] for o in _cs_opts] else 0,
                    key="sb-contract-status")
                _cia = s.get("contract_initial_amount")
                if ((s.get("contract_status") or "فعال")
                        == "فسخ با قصور"):
                    s["fault_deduction_on_negative"] = st.checkbox(
                        "کسر ۵٪ حتی در صورت تعدیلِ منفی (بند ۷"
                        " — تفسیر، منتظر تأیید کاربر)",
                        value=bool(
                            s.get("fault_deduction_on_negative")),
                        key="sb-fdn")
                    st.caption("متن بند ۷ دربارهٔ تعدیل منفی"
                               " ساکت است؛ پیش‌فرض: کسر اعمال"
                               " نمی‌شود (ACCEPTANCE.md §۱۸-۳).")
                s["contract_initial_amount"] = st.number_input(
                    "مبلغ اولیهٔ پیمان (ریال) — ملاک بندهای ۲-۱/۲-۲ و "
                    "سقف ۱۰٪ (نامه، بند ۶)",
                    min_value=0.0, step=1_000_000_000.0,
                    value=float(_cia) if isinstance(_cia, (int, float))
                    and _cia else 0.0, format="%.0f", key="sb-cia"),
                s["contract_initial_amount"] = (
                    s["contract_initial_amount"] or None)
                _im_opts = [("گروهی", "گروهی (بند ۲-۲)"),
                            ("رشته‌ای", "رشته‌ای (بند ۲-۱)"),
                            ("خودکار", "خودکار از روی مبلغ اولیه")]
                _im = s.get("index_method") or "گروهی"
                s["index_method"] = st.selectbox(
                    "مسیر شاخص تعدیل", [o[0] for o in _im_opts],
                    format_func=lambda x: dict(_im_opts)[x],
                    index=[o[0] for o in _im_opts].index(_im)
                    if _im in [o[0] for o in _im_opts] else 0, key="sb-im")
                # گام ۶ (بندهای ۲-۱/۲-۲): توضیحِ مسیرِ «خودکار»
                st.caption("خودکار: مبلغ اولیهٔ پیمان کمتر از آستانهٔ"
                           " ۳۰۰٬۰۰۰٬۰۰۰ ریال ⇒ مسیر رشته‌ای (بند ۲-۱)؛"
                           " آستانه و بیشتر ⇒ مسیر گروهی (بند ۲-۲)."
                           " آستانه از config/index_bulletins.json"
                           " (bulletin_2080.threshold_rail) خوانده می‌شود.")
                _cdm = s.get("contract_duration_months")
                s["contract_duration_months"] = st.number_input(
                    "مدت اولیهٔ پیمان (ماه — بند ۲-۵)", min_value=0,
                    step=1, value=int(_cdm) if isinstance(_cdm, int) and _cdm
                    else 0, key="sb-cdm") or None
                s["last_provisional_date"] = st.text_input(
                    "تاریخ آخرین صورت‌وضعیت موقت (بند ۲-۶)",
                    value=s.get("last_provisional_date") or "",
                    key="sb-last-prov")
                _pdm_opts = [("average", "میانگین شاخص‌ها (متنِ بند)"),
                             ("own_period",
                              "شاخصِ هر سه‌ماهه (تبصرهٔ ۱)")]
                _pdm = s.get("provisional_diff_method") or "average"
                s["provisional_diff_method"] = st.selectbox(
                    "روش شاخصِ مابه‌التفاوتِ آخرین موقت و قطعی"
                    " (بند ۲-۶)",
                    [o[0] for o in _pdm_opts],
                    format_func=lambda x: dict(_pdm_opts)[x],
                    index=[o[0] for o in _pdm_opts].index(_pdm)
                    if _pdm in [o[0] for o in _pdm_opts] else 0,
                    key="sb-pdm")
                st.caption("متنِ اصلیِ بند: میانگین شاخص‌های"
                           " سه‌ماهه‌های بین شروع پیمان و آخرین"
                           " موقت. تبصرهٔ ۱: اگر دورهٔ انجام قابل"
                           " تشخیص است، شاخص همان دوره.")
                # ── فاز E-6 Part C گام ۵ (بندهای ۳-۱..۳-۵): کارهای
                # جدید — روش و مبلغ و دورهٔ شاخصِ مبنا ──
                _nim_opts = [("فهرست پیمان", "فهرست پیمان (۳-۱)"),
                             ("فهرست پایه", "فهرست پایه (۳-۲)"),
                             ("قیمت روز", "قیمت روز (۳-۳)"),
                             ("ترکیب", "ترکیب (۳-۴)")]
                _nim = s.get("new_item_method") or "فهرست پیمان"
                s["new_item_method"] = st.selectbox(
                    "روش قیمتِ کار جدید (بندهای ۳-۱..۳-۵)",
                    [o[0] for o in _nim_opts],
                    format_func=lambda x: dict(_nim_opts)[x],
                    index=[o[0] for o in _nim_opts].index(_nim)
                    if _nim in [o[0] for o in _nim_opts] else 0,
                    key="sb-nim")
                st.caption("۳-۱: شاخص مبنا همان مبنای پیمان؛",
                           " ۳-۲/۳-۳: شاخص دورهٔ آن قیمت‌ها؛ ۳-۴:",
                           " هر بخش طبق روشِ خودش. ۳-۵: قیمتِ کار",
                           " جدید بر ۰٫۹۵ تقسیم و در ضریبِ Io پیمان",
                           " ÷ Io کار جدید ضرب می‌شود تا به مبنای",
                           " پیمان برسد.")
                s["new_item_amount"] = st.number_input(
                    "مبلغ کار جدید (ریال)", min_value=0.0,
                    step=1_000_000_000.0,
                    value=float(s.get("new_item_amount") or 0.0),
                    format="%.0f", key="sb-nia")
                if _nim == "ترکیب":
                    s["new_item_amount_attached"] = st.number_input(
                        "مبلغ بخشِ ۳-۱ در ترکیب (ریال)",
                        min_value=0.0, step=1_000_000_000.0,
                        value=float(
                            s.get("new_item_amount_attached") or 0.0),
                        format="%.0f", key="sb-niaa")
                else:
                    s["new_item_amount_attached"] = 0.0
                if _nim != "فهرست پیمان":
                    _disc_ui = ((s.get("regional_selection") or {})
                                .get("discipline") or "ابنیه")
                    _bp_qs = [q for q in TechnicalOfficeEngine
                              ._PERIOD_QUARTERS.values()
                              if TechnicalOfficeEngine._index_value(
                                  TechnicalOfficeEngine
                                  ._QUARTER_PERIOD.get(q) or "base",
                                  _disc_ui)[0] is not None]
                    _bp_sel = (s.get("new_item_base_period") or
                               "").strip()
                    s["new_item_base_period"] = st.selectbox(
                        "دورهٔ شاخص مبنای کار جدید (سه‌ماهه)",
                        _bp_qs,
                        index=_bp_qs.index(_bp_sel)
                        if _bp_sel in _bp_qs else 0, key="sb-nibp")
                else:
                    s["new_item_base_period"] = ""

                # ── تمدیدهای مدت پیمان (بند ۲-۵) ──
                _old_ext = s.get("contract_extensions") or []
                _ext_n = st.number_input(
                    "تعداد تمدیدهای مدت پیمان", min_value=0, max_value=6,
                    value=len(_old_ext), step=1, key="sb-ext-n")
                _exts = []
                for _i in range(int(_ext_n)):
                    _c = _old_ext[_i] if _i < len(_old_ext) else {}
                    _er = st.columns([1.2, 0.7, 1.1, 1.1])
                    _d = _er[0].text_input("تاریخ تمدید",
                                           value=_c.get("date") or "",
                                           key="sb-ext-d-%d" % _i)
                    _m = _er[1].number_input("ماه", min_value=1,
                                             max_value=60,
                                             value=int(_c.get("months") or 1),
                                             key="sb-ext-m-%d" % _i)
                    _kk = ["مجاز", "غیرمجاز", "تعیین‌نشده"]
                    _k = _er[2].selectbox(
                        "نوع تأخیر", _kk,
                        index=_kk.index(_c.get("kind") or "مجاز")
                        if _c.get("kind") in _kk else 0,
                        key="sb-ext-k-%d" % _i)
                    _dn = _er[3].text_input("شماره سند",
                                            value=_c.get("doc_no") or "",
                                            key="sb-ext-dn-%d" % _i)
                    _exts.append({"date": _d, "months": int(_m),
                                  "kind": _k, "doc_no": _dn})
                s["contract_extensions"] = _exts
            _p = _adj_period("tadil_io_period", "دورهٔ مبنا (Io)")
            if _p:
                s["tadil_io_period"] = _p
            _p = _adj_period("tadil_it_period", "دورهٔ انجام کار (It)", "q4",
                             allow_provisional=True)
            if _p:
                s["tadil_it_period"] = _p
            s["tadil_advance_mode"] = st.selectbox(
                "نحوهٔ اعمال پیش‌پرداخت", ["کل مبلغ کارکرد", "کسر پیش‌پرداخت"],
                index=1 if s.get("tadil_advance_mode") == "کسر پیش‌پرداخت" else 0,
                key="sb-tadil-adv")
            s["tadil_delay_mode"] = st.selectbox(
                "شرط تأخیر", ["مشمول کل دوره", "مستثنی کردن دورهٔ تأخیر"],
                index=1 if s.get("tadil_delay_mode") == "مستثنی کردن دورهٔ تأخیر" else 0,
                key="sb-tadil-delay")
            if s["tadil_delay_mode"] == "مستثنی کردن دورهٔ تأخیر":
                s["tadil_delay_date"] = st.text_input(
                    "تاریخ تحویل قرارداد (شمسی)", value=s.get("tadil_delay_date") or "",
                    key="sb-tadil-delay-date")
            s["tadil_allow_negative"] = st.checkbox(
                "تعدیل منفی مجاز است", value=bool(s.get("tadil_allow_negative")),
                key="sb-tadil-neg")
            s["tadil_approved"] = st.checkbox(
                "مقادیر را بررسی و تأیید کردم (خروجی رسمی شود)",
                value=bool(s.get("tadil_approved")), key="sb-tadil-ok")
        if s["baravord_enabled"]:
            st.markdown("**موتور ۲ — برآورد به‌هنگام**")
            _p = _adj_period("baravord_io_period", "دورهٔ مبنا (Io)")
            if _p:
                s["baravord_io_period"] = _p
            _p = _adj_period("baravord_it_period", "دورهٔ انجام کار (It)", "q4",
                             allow_provisional=True)
            if _p:
                s["baravord_it_period"] = _p
            s["baravord_approved"] = st.checkbox(
                "مقادیر را بررسی و تأیید کردم (خروجی رسمی شود)",
                value=bool(s.get("baravord_approved")), key="sb-baravord-ok")
        st.markdown("---")
        st.markdown("#### نمایش")
        s["currency"] = st.radio("واحد پول نمایش", ["rial", "toman"],
                                 format_func=lambda x: "ریال" if x == "rial" else "تومان",
                                 index=0 if s["currency"] == "rial" else 1,
                                 horizontal=True, key="sb-disp-currency")
        s["rounding"] = st.checkbox("رند کردن مبالغ به ۱۰۰۰ ریال", value=bool(s["rounding"]),
                                    key="sb-disp-rounding")
        with st.expander("هندسهٔ تیرچه"):
            s["joist_spacing"] = st.select_slider("فاصلهٔ محور تیرچه (متر)",
                                                  options=[0.45, 0.5, 0.55, 0.6, 0.65, 0.7],
                                                  value=float(s["joist_spacing"]),
                                                  key="sb-joist-spacing")
        st.markdown("---")
        st.markdown("#### فرض‌های فنی پروژه")
        st.caption("کد و بهای ردیف‌های بتن و سقف تیرچه‌بلوک از این مقادیر انتخاب می‌شود")
        _cs = s["concrete_strength_mpa"]
        _cs_opts = list(CONCRETE_STRENGTH_CODES)
        for _key, _lbl in [("foundation", "مقاومت فشاری بتن پی"),
                           ("column_beam", "مقاومت فشاری بتن ستون و تیر"),
                           ("slab", "مقاومت فشاری بتن سقف"),
                           ("stair", "مقاومت فشاری بتن پله")]:
            _cur = int(_cs.get(_key, 20))
            if _cur not in CONCRETE_STRENGTH_CODES:
                _cur = 20
            _cs[_key] = st.selectbox(
                f"{_lbl} (MPa)", _cs_opts, index=_cs_opts.index(_cur),
                format_func=lambda v: f"{fa(v)} مگاپاسکال — {CONCRETE_STRENGTH_CODES[v][0]}",
                key=f"sb-strength-{_key}")
        _lean_opts = list(LEAN_CEMENT_CODES)
        _cur = int(s.get("lean_cement_kg", 150))
        if _cur not in LEAN_CEMENT_CODES:
            _cur = 150
        s["lean_cement_kg"] = st.selectbox(
            "عیار سیمان بتن مگر (kg/m³)", _lean_opts, index=_lean_opts.index(_cur),
            format_func=lambda v: f"{fa(v)} کیلوگرم — {LEAN_CEMENT_CODES[v][0]}",
            key="sb-lean-cement")
        _jb_opts = list(JOIST_BLOCK_THICKNESS_CODES)
        _cur = int(s.get("joist_block_thickness_cm", 25))
        if _cur not in JOIST_BLOCK_THICKNESS_CODES:
            _cur = 25
        s["joist_block_thickness_cm"] = st.selectbox(
            "ضخامت سقف تیرچه‌بلوک (cm)", _jb_opts, index=_jb_opts.index(_cur),
            format_func=lambda v: f"{fa(v)} سانتی‌متر — {JOIST_BLOCK_THICKNESS_CODES[v][0]}",
            key="sb-joist-thickness")
        _jbs_opts = list(JOIST_BLOCK_STRENGTH_SURCHARGE)
        _cur = int(s.get("joist_block_concrete_mpa", 25))
        if _cur not in JOIST_BLOCK_STRENGTH_SURCHARGE:
            _cur = 25
        s["joist_block_concrete_mpa"] = st.selectbox(
            "مقاومت بتن سقف تیرچه‌بلوک (MPa)", _jbs_opts, index=_jbs_opts.index(_cur),
            format_func=lambda v: f"{fa(v)} مگاپاسکال — "
                                  + ("بدون اضافه‌بها" if JOIST_BLOCK_STRENGTH_SURCHARGE[v] is None
                                     else JOIST_BLOCK_STRENGTH_SURCHARGE[v][0]),
            help="بند ۸ الزامات عمومی فصل دهم فهرست‌بهای ۱۴۰۴: بتن سقف ۲۰ MPa فرض "
                 "شده؛ ۲۵ MPa → اضافه‌بهای ۱۰۰۷۰۱ (۵۹٬۵۰۰ ریال/m²) و ۳۰ MPa → "
                 "۱۰۰۷۰۲ (۷۶٬۵۰۰ ریال/m²) روی کل مساحت سقف.",
            key="sb-joist-strength")
        _cur = float(s.get("joist_block_top_thickness_cm", 5))
        if _cur < 0 or _cur > 30:
            _cur = 5
        s["joist_block_top_thickness_cm"] = st.number_input(
            "ضخامت بتن روی بلوک طبق مشخصات (cm)", min_value=0.0, max_value=30.0,
            value=_cur, step=0.5,
            help="بند ۹ الزامات عمومی فصل دهم: ضخامت سقف از زیر تیرچه تا ۵ cm بتن "
                 "روی بلوک داخل نرخ ۱۰۰۳۰۵ است. فقط بتن مازاد بر ۵ cm (طبق مشخصات "
                 "فنی) به‌صورت جداگانه به ردیف بتن متناظر افزوده می‌شود. اختلاف "
                 "هندسی Revit (مثلاً ۵٫۲ cm) مازاد محسوب نمی‌شود.",
            key="sb-joist-top-thickness")
        # ارتفاع طبقه برای انتخاب ردیف قالب‌بندی دال/تاوه (ایراد ۲):
        # ۰۶۰۴۰۱ ≤ ۳/۵m | ۰۶۰۴۰۲ تا ۵/۵ | ۰۶۰۴۰۳ تا ۷/۵ | ۰۶۰۴۰۴ تا ۱۰
        _cur_h = float(s.get("slab_formwork_height_m", 3.5) or 3.5)
        if _cur_h < 0:
            _cur_h = 3.5
        s["slab_formwork_height_m"] = st.number_input(
            "ارتفاع طبقه برای قالب‌بندی دال/تاوه (m)", min_value=0.0,
            value=_cur_h, step=0.5, format="%.1f",
            help="فصل ۰۶ ردیف ۰۶۰۴۰۱..۰۶۰۴۰۴: نرخ بر اساس ارتفاع تا ۳/۵ متر و "
                 "سپس دسته‌های ۵/۵، ۷/۵ و ۱۰ متر متفاوت است. پروژهٔ مرجع ۳/۵ متر "
                 "پیش‌فرض است (۰۶۰۴۰۱ = ۴٬۱۰۷٬۰۰۰ ریال/m² — فهرست‌بها ۱۴۰۴ "
                 "اکسل، شیت Fehrest ردیف ۲۵۴؛ SL01 با این ارتفاع به این ردیف "
                 "می‌رود).",
            key="sb-slab-formwork-height")
        st.markdown("---")
        st.markdown("#### حمل و نقل و اضافه‌بها")
        s["haul_distance_km"] = st.number_input(
            "مسافت حمل مصالح (کیلومتر)", min_value=0, max_value=200,
            value=int(s.get("haul_distance_km", 50)), step=5,
            help="ردیف ۲۸۰۱۰۱ فهرست‌بهای ۱۴۰۴: بازهٔ ۳۰–۷۵ کیلومتر؛ "
                 "کمیت = وزن آرماتور (تن) × (مسافت − ۳۰).",
            key="sb-haul-distance")
        s["surcharge_rebar_density"] = st.checkbox(
            "افزودن اضافه‌بهای سختی ارتعاش بتن (۰۸۰۳۱۱)",
            value=bool(s.get("surcharge_rebar_density", False)),
            help="فهرست‌بهای ۱۴۰۴: هرگاه تراکم میلگرد بیش از ۱۸۰ کیلوگرم بر "
                 "مترمکعب بتن باشد، ۳۶۳٬۵۰۰ ریال به ازای هر مترمکعب بتن سازه‌ای. "
                 "تراکم خودکار از داده‌های آرماتور و بتن محاسبه می‌شود (در "
                 "دادهٔ نمونه ≈ ۳۰ kg/m³ < ۱۸۰ است و ردیفی افزوده نمی‌شود).",
            key="sb-surcharge-rebar-density")
        s["surcharge_reinforced_concrete"] = st.checkbox(
            "افزودن اضافه‌بهای بتن مسلح (۰۸۰۳۱۰)",
            value=bool(s.get("surcharge_reinforced_concrete", False)),
            help="فهرست‌بهای ۱۴۰۴: «در صورت مصرف بتن در بتن مسلح»، ۱۴۵٬۵۰۰ ریال "
                 "به ازای هر مترمکعب بتن. مسلح بودن از ستون «Host Category» جدول "
                 "آرماتور تشخیص داده می‌شود (بتن‌مگر هرگز مسلح نیست).",
            key="sb-surcharge-reinforced-concrete")
        s["surcharge_thin_concrete"] = st.checkbox(
            "افزودن اضافه‌بهای ضخامت کم بتن (۰۸۰۳۰۴)",
            value=bool(s.get("surcharge_thin_concrete", False)),
            help="فهرست‌بهای ۱۴۰۴: «هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر "
                 "باشد»، ۳۰۴٬۰۰۰ ریال به ازای هر مترمکعب. ضخامت از حجم ÷ مساحت "
                 "داده‌های خود پروژه استخراج می‌شود (بتن‌مگر و دال‌های نازک).",
            key="sb-surcharge-thin-concrete")
        st.markdown("---")
        st.caption(f"امروز به وقت ایران: {today_jalali()} — پردازش کاملاً محلی روی سیستم شماست.")


# ════════════════════════════════════════════════════════════════
# تب ۱ — داشبورد و آپلود ورودی‌ها
# ════════════════════════════════════════════════════════════════

def render_tab_upload():
    """تب داشبورد: نمای کلی وضعیت + آپلود جداول Schedule رویت."""
    st.markdown(f"""
    <div class="hero-box">
        <h2>خوش آمدید به {APP_NAME}</h2>
        <p>
        جداول Schedule خروجی Revit و فایل‌های Mapping اسکریپت‌های Dynamo را بارگذاری کنید تا
        صورت‌وضعیت رسمی بر مبنای فهرست‌بهای ابنیه ۱۴۰۴ به‌صورت خودکار تولید شود.
        سامانه فرمت فایل‌ها را خودکار تشخیص می‌دهد و روی مرورگر شما کار می‌کند — بدون ارسال داده به سرور.
        </p>
    </div>""", unsafe_allow_html=True)

    result = compute_now()
    tables = [f for f in st.session_state.sched_files if f.get("table")]
    map_df = merged_mapping_df()
    c = st.columns(5)
    c[0].metric("جداول Schedule", fa(len(tables)))
    c[1].metric("رکوردهای Mapping", fa(0 if map_df.empty else len(map_df)))
    c[2].metric("ردیف‌های فهرست‌بها", fa(len(st.session_state.fehrest_db)))
    c[3].metric("ردیف‌های BOQ", fa(len(result["lines"])) if result else "—")
    c[4].metric("خالص قابل‌پرداخت", fmt_money(result["grand_total"], "toman") if result else "—")

    st.markdown("---")
    st.markdown("##### آپلود جداول Schedule رویت")
    c1, c2 = st.columns([3, 1])
    with c1:
        ups = st.file_uploader("فایل‌های TXT/CSV خروجی Schedule های Revit (چندفایلی)",
                               type=["txt", "csv", "tsv"], accept_multiple_files=True,
                               key="tu-schedule-uploader")
    with c2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("بارگذاری دادهٔ نمونه (دمو)", type="primary", use_container_width=True,
                     key="tu-load-demo"):
            load_demo()
            st.rerun()

    if ups:
        changed = False
        existing = {f["name"] for f in st.session_state.sched_files}
        for up in ups:
            if up.name in existing:
                continue
            text = decode_text(up.getvalue())
            st.session_state.sched_files.append({
                "name": up.name, "size": up.size, "text": text,
                "table": RevitScheduleParser.parse(up.name, text),
            })
            changed = True
        if changed:
            st.rerun()

    if not tables:
        st.info("هنوز جدولی بارگذاری نشده است؛ می‌توانید با دادهٔ نمونه (دمو) شروع کنید.")
        return

    unknown = [f for f in tables if f["table"]["kind"] == "unknown"]
    if unknown:
        st.warning(f"{fa(len(unknown))} جدول نامشخص — نوع آن‌ها را دستی تعیین کنید.")

    for i, f in enumerate(st.session_state.sched_files):
        t = f["table"]
        with st.container(border=True):
            top = st.columns([3, 2, 1.4, 1])
            top[0].markdown(f"**{f['name']}**")
            top[0].caption(f"{fmt_num(f['size'] / 1024, 1)} کیلوبایت · {fa(len(t['rows']))} ردیف"
                           + (" · دارای Grand total" if t.get("grand_total") else ""))
            top[1].markdown(f"`{KIND_LABEL[t['kind']]}`")
            top[2].caption(f"اطمینان {conf_label(t['kind_conf'])}" if t["kind"] != "unknown" else "—")
            if top[3].button("حذف", key=f"tu-del-file-{i}"):
                st.session_state.sched_files.pop(i)
                st.rerun()
            if t["kind"] == "unknown":
                sel = st.selectbox("تعیین دستی نوع جدول", KINDS,
                                   index=KINDS.index("unknown"),
                                   format_func=lambda k: KIND_LABEL[k],
                                   key=f"tu-kind-select-{i}")
                if sel != "unknown":
                    t["kind"], t["kind_conf"], t["warnings"] = sel, 1.0, []
                    st.rerun()
            for w in t.get("warnings", [])[:2]:
                st.caption(f"⚠ {w}")


# ════════════════════════════════════════════════════════════════
# تب ۲ — نگاشت داینامو (تشخیص هوشمند فرمت)
# ════════════════════════════════════════════════════════════════

_FMT_BADGE = {"v1": "نسخهٔ ۱ — TSV انگلیسی (Rebar-محور)",
              "v2": "نسخهٔ ۲ — XLSX/TSV فارسی شانزده‌ستونی (Element-محور + کد فهرست‌بها)"}


def render_tab_mapping():
    """تب نگاشت داینامو: آپلود، تشخیص خودکار فرمت، پیش‌نمایش و ادغام."""
    st.markdown("### نگاشت خروجی اسکریپت‌های Dynamo")
    st.caption(
        "هر دو فرمت پشتیبانی می‌شود: خروجی قدیمی `mapping.txt` (TSV انگلیسی) و خروجی جدید "
        "`Mapping.xlsx` (شانزده‌ستونی فارسی). اگر هر دو ارسال شوند، v2 به‌عنوان منبع اصلی و v1 "
        "به‌عنوان غنی‌سازی لیستوفر آرماتور استفاده می‌شود؛ جداول Schedule نیز مکمل می‌مانند.")

    ups = st.file_uploader("فایل‌های Mapping داینامو (TXT / TSV / XLSX)",
                           type=["txt", "tsv", "csv", "xlsx"],
                           accept_multiple_files=True, key="tm-mapping-uploader")
    if ups:
        existing = {r.get("file_name") for r in st.session_state.mapping_results}
        changed = False
        for up in ups:
            if up.name in existing:
                continue
            parsed = DynamoMappingParser.auto_detect_and_parse(up.getvalue(), up.name)
            parsed["file_name"] = up.name
            st.session_state.mapping_results.append(parsed)
            changed = True
        if changed:
            st.rerun()

    if not st.session_state.mapping_results:
        st.info("هنوز فایل Mapping بارگذاری نشده است (اختیاری — بدون آن هم متره از Schedule ها محاسبه می‌شود).")
        return

    for i, r in enumerate(st.session_state.mapping_results):
        with st.container(border=True):
            cols = st.columns([3, 3, 1])
            cols[0].markdown(f"**{r.get('file_name', 'mapping')}**")
            if r.get("error"):
                cols[0].error(r["error"])
            else:
                cols[0].caption(f"{fa(r['records_count'])} رکورد" +
                                (f" · {r['meta'].get('report_head', '')[:60]}" if r["meta"] else ""))
                cols[1].markdown(f"`{_FMT_BADGE.get(r['fmt'], r['fmt'])}`")
            if cols[2].button("حذف", key=f"tm-del-{i}"):
                st.session_state.mapping_results.pop(i)
                st.rerun()
            for w in r.get("warnings", [])[:2]:
                st.caption(f"⚠ {w}")

    map_df = merged_mapping_df()
    if map_df.empty:
        return

    st.markdown("---")
    st.markdown("##### تجمیع خودکار کمیت‌های نگاشت")
    sums = st.columns(5)
    def nsum(col):
        return float(pd.to_numeric(map_df.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    v2mask = map_df.get("source_format", "v2") == "v2"
    v2df = map_df[v2mask] if "source_format" in map_df.columns else map_df
    def nsum2(col):
        return float(pd.to_numeric(v2df.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    sums[0].metric("حجم کل (v2)", f"{fmt_num(nsum2('volume_m3'), 2)} m³")
    sums[1].metric("سطح قالب (v2)", f"{fmt_num(nsum2('formwork_m2'), 1)} m²")
    sums[2].metric("وزن میلگرد (v2)", f"{fmt_num(nsum2('rebar_weight_kg'), 0)} kg")
    enriched = 0
    if "source_format" in map_df.columns:
        v1 = map_df[map_df["source_format"] == "v1"]
        if not v1.empty and "diameter_mm" in v1.columns:
            enriched = int((pd.to_numeric(v1["diameter_mm"], errors="coerce").fillna(0) > 0).sum())
    sums[3].metric("رکوردهای میلگرد غنی (v1)", fa(enriched))
    coded = 0
    if "fehrest_code" in map_df.columns:
        coded = int(map_df["fehrest_code"].astype(str).str.match(r"^[0-9]{6}$").sum())
    sums[4].metric("ردیف با کد فهرست‌بها", fa(coded))

    with st.expander("پیش‌نمایش دادهٔ ادغام‌شده (۲۰ ردیف نخست)"):
        show_cols = [c for c in ["element_id", "category", "family", "mark", "level",
                                 "volume_m3", "formwork_m2", "rebar_weight_kg",
                                 "fehrest_code", "diameter_mm", "source_format"] if c in map_df.columns]
        st.dataframe(map_df[show_cols].head(20), hide_index=True, use_container_width=True)


# ════════════════════════════════════════════════════════════════
# تب ۳ — فهرست‌بهای ۱۴۰۴
# ════════════════════════════════════════════════════════════════

def render_tab_fehrest():
    """تب فهرست‌بها: بارگذاری فایل رسمی، جست‌وجو و ویرایش بهای ردیف‌ها."""
    st.markdown("### پایگاه فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴")
    st.caption("برای ارقام کاملاً رسمی، فایل متن/CSV فهرست‌بهای سازمان برنامه را بارگذاری کنید؛ "
               "ردیف‌های رسمی جایگزین تخمینی می‌شوند. بها هر ردیف در جدول قابل ویرایش است.")
    db = st.session_state.fehrest_db

    up = st.file_uploader("بارگذاری فایل فهرست‌بها (TXT/CSV — ساختار: کد | فصل | شرح | واحد | بها)",
                          type=["txt", "csv", "tsv"], key="tf-fehrest-uploader")
    if up is not None:
        text = decode_text(up.getvalue())
        rows, skipped = FehrestBahaParser.parse_text(text)
        if rows:
            replaced = sum(1 for r in rows if FehrestBahaParser.by_code(db, r["code"]))
            st.session_state.fehrest_db = FehrestBahaParser.merge(db, rows)
            st.session_state.fehrest_official = True
            st.success(f"فهرست‌بها پذیرفته شد: {fa(len(rows))} ردیف رسمی "
                       f"({fa(replaced)} جایگزین + {fa(len(rows) - replaced)} جدید)"
                       + (f" · {fa(skipped)} سطر ناخوانا" if skipped else ""))
            st.rerun()
        else:
            st.error("هیچ ردیف معتبری یافت نشد؛ ساختار ستون‌های فایل را بررسی کنید.", icon="⚠️")

    c = st.columns(4)
    est = [r for r in db if r["estimated"]]
    c[0].metric("کل ردیف‌ها", fa(len(db)))
    c[1].metric("ردیف‌های رسمی", fa(len(db) - len(est)))
    c[2].metric("بهای تخمینی باقی‌مانده", fa(len(est)))
    c[3].metric("فایل رسمی شما", "بارگذاری شد" if st.session_state.fehrest_official else "—")

    q = st.text_input("جست‌وجو در شرح یا کد ردیف", placeholder="مثلاً: قالب فلزی پی",
                      key="tf-search")
    view = db
    if q.strip():
        nq = normalize_text(q)
        view = [r for r in db if nq in normalize_text(r["desc"] + " " + r["code"])]
    df = pd.DataFrame([{
        "کد": r["code"], "فصل": f"{r['chapter']} — {chapter_title(r['chapter'])}",
        "شرح": r["desc"], "واحد": r["unit"], "بها": int(r["price"]),
        "وضعیت": "رسمی" if not r["estimated"] else "تخمینی",
    } for r in view[:400]])
    edited = st.data_editor(
        df, hide_index=True, use_container_width=True, num_rows="fixed",
        disabled=["کد", "فصل", "شرح", "واحد", "وضعیت"],
        column_config={"بها": st.column_config.NumberColumn("بها (ریال)", format="%d")},
        key="tf-price-editor",
    )
    changed = 0
    for _, r in edited.iterrows():
        row = FehrestBahaParser.by_code(db, r["کد"])
        if row and int(row["price"]) != int(r["بها"]):
            row["price"] = float(r["بها"])
            row["estimated"] = False
            changed += 1
    if changed:
        st.toast(f"{fa(changed)} بهای واحد به‌روزرسانی شد.", icon="✏️")


# ════════════════════════════════════════════════════════════════
# تب ۴ — مترهٔ ریز و تطبیق هوشمند
# ════════════════════════════════════════════════════════════════

_MATCH_LABEL = {"rule-exact": "قانون + کد دقیق", "rule-fuzzy": "قانون فازی",
                "fuzzy": "تطبیق فازی", "manual": "تأیید دستی", "direct-code": "کد مستقیم Mapping",
                "manual-starred": "ردیف ستاره‌دار (دستی)"}


def render_tab_metre():
    """تب مترهٔ ریز: بررسی ردیف‌های BOQ، نامزدهای جایگزین، ویرایش قیمت و استثنا."""
    st.markdown("### مترهٔ ریز و تطبیق هوشمند با فهرست‌بها")
    result = compute_now()
    if not result or not result["lines"]:
        st.info("ابتدا جداول Schedule یا فایل Mapping را بارگذاری کنید.")
        return

    s = st.session_state.settings
    q = result["quality"]
    c = st.columns(5)
    c[0].metric("ردیف‌های تولیدشده", fa(q["lines_matched"]))
    c[1].metric("تطبیق دقیق/مستقیم", fa(q["lines_exact"]))
    c[2].metric("تطبیق فازی", fa(q["lines_fuzzy"]))
    c[3].metric("نیازمند بررسی", fa(q["lines_review"]))
    c[4].metric("جمع بهای پایه", fmt_money(result["base_total"], s["currency"]))

    filt = st.radio("فیلتر نمایش ردیف‌ها", ["همه", "نیازمند بررسی", "بهای تخمینی"],
                    horizontal=True, key="tme-filter")
    lines = result["lines"]
    if filt == "نیازمند بررسی":
        lines = [l for l in lines if l["needs_review"]]
    elif filt == "بهای تخمینی":
        lines = [l for l in lines if l["estimated"]]
    if not lines:
        st.success("ردیفی با این فیلتر یافت نشد — همه‌چیز سالم است.")

    cur = s["currency"]
    for l in lines:
        with st.container(border=True):
            head = st.columns([0.6, 4.4, 1.8, 1.8, 2.0])
            head[0].markdown(f"**{fa(l['row_no'])}**")
            head[1].markdown(f"`{fa(l['code'])}` — {l['desc'][:78]}" + (" …" if len(l["desc"]) > 78 else ""))
            head[1].caption(f"{_MATCH_LABEL.get(l['method'], l['method'])} · "
                            f"اطمینان {conf_label(l['confidence'])} ({fa(round(l['confidence'] * 100))}٪)"
                            + (" · بهای تخمینی" if l["estimated"] else ""))
            head[2].markdown(f"**{fmt_num(l['qty'], 2)}** {l['unit']}")
            head[3].markdown(fmt_money(l["price"], cur))
            head[4].markdown(f"**{fmt_money(l.get('total_indexed', l['total']), cur)}**")

            with st.expander("جزئیات، منابع کمیت و اصلاح تطبیق"):
                if l.get("note"):
                    st.info(str(l["note"]))
                srcs = l.get("sources", [])
                if isinstance(srcs, list) and srcs and isinstance(srcs[0], dict):
                    src_df = pd.DataFrame([{
                        "منبع": x.get("source", "—"), "جدول": x.get("table", "—"),
                        "عنصر/مارک": x.get("ref", "—"), "گروه": x.get("group", "—"),
                        "شرح": x.get("detail", "—"), "مقدار": round(float(x.get("qty", 0)), 3),
                        "واحد": {"m3": "مترمکعب", "m2": "مترمربع", "kg": "کیلوگرم", "m": "مترطول",
                                 "count": "عدد"}.get(x.get("unit"), x.get("unit", "—")),
                    } for x in srcs][:30])
                    st.dataframe(src_df, hide_index=True, use_container_width=True,
                                 height=min(38 * (len(src_df) + 1), 250))
                elif l.get("detail_records"):
                    st.caption(f"مقادیر از {fa(len(l['detail_records']))} رکورد Mapping تجمیع شده است.")

                opts = ["(تطبیق خودکار)"] + [
                    f"{cnd['code']} | {cnd['desc'][:52]} | "
                    f"{fmt_money(cnd['price'], cur, with_unit=False)} | {fa(round(cnd['score'] * 100))}٪"
                    for cnd in l.get("candidates", [])
                ]
                _mc = s["manual_codes"].get(l["id"]) or {}
                chosen_code = _mc.get("code", "") if isinstance(_mc, dict) else str(_mc)
                idx = 0
                if chosen_code:
                    for j, cnd in enumerate(l.get("candidates", []), 1):
                        if cnd["code"] == chosen_code:
                            idx = j
                            break
                sel = st.selectbox("ردیف جایگزین از فهرست‌بها", opts, index=idx,
                                   key=f"tme-cand-{l['id']}")
                if len(opts) > 1 and sel != opts[0]:
                    picked = l["candidates"][opts.index(sel) - 1]
                    if chosen_code != picked["code"]:
                        append_audit(s, l["code"], "code", chosen_code or l["code"],
                                     picked["code"], "انتخاب از تب مترهٔ ریز")
                        s["manual_codes"][l["id"]] = {
                            "code": picked["code"],
                            "reason": "انتخاب دستی از نامزدهای فهرست‌بها",
                            "user": s.get("price_user") or "",
                            "at": jalali_now_str()}
                        st.rerun()
                elif chosen_code and sel == opts[0]:
                    append_audit(s, l["code"], "code", chosen_code, l["code"],
                                 "بازگشت به تطبیق خودکار")
                    s["manual_codes"].pop(l["id"], None)
                    st.rerun()

                # ── قیمت دستی (فاز C): قیمت + منبع + شماره/تاریخ سند ──
                _mp = s["manual_prices"].get(l["id"]) or {}
                _has_mp = bool(_mp)
                _app_p = l.get("app_price") if _has_mp else None
                pc = st.columns([1.5, 1.2, 1.1, 1.1, 0.8])
                _default_p = float(_mp["price"]) if _mp.get("price") is not None else float(l["price"])
                new_price = pc[0].number_input(
                    f"بهای واحد ({'تومان' if cur == 'toman' else 'ریال'})",
                    value=_default_p, step=1000.0, format="%.0f",
                    key=f"tme-price-{l['id']}")
                _src_opts = [x for x in MANUAL_SOURCES if x != "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)"]
                _cur_src = _mp.get("source") or "بخشنامه"
                src = pc[1].selectbox("منبع", _src_opts,
                                      index=_src_opts.index(_cur_src) if _cur_src in _src_opts else 0,
                                      key=f"tme-src-{l['id']}")
                doc_no = pc[2].text_input("شماره سند", value=_mp.get("doc_no", ""),
                                         key=f"tme-doc-{l['id']}")
                doc_date = pc[3].text_input("تاریخ سند (شمسی)",
                                            value=_mp.get("doc_date", ""),
                                            placeholder="۱۴۰۵/۰۴/۱۲",
                                            key=f"tme-date-{l['id']}")
                if pc[4].button("ثبت", key=f"tme-save-{l['id']}"):
                    _bad = None
                    if doc_date and not TechnicalOfficeEngine._parse_jalali(doc_date):
                        _bad = f"تاریخ سند «{doc_date}» شمسی معتبر نیست (مثال: ۱۴۰۵/۰۴/۱۲)."
                    if _bad:
                        st.error(_bad)
                    else:
                        append_audit(s, l["code"], "price",
                                     _mp.get("price") if _mp else l["price"],
                                     new_price, src)
                        s["manual_prices"][l["id"]] = _manual_record(
                            new_price, source=src, doc_no=doc_no, doc_date=doc_date,
                            note=_mp.get("note", ""), status="دستی",
                            chapter=l["chapter"],
                            user=s.get("price_user") or "",
                            at=jalali_now_str())
                        st.rerun()
                if _has_mp:
                    _dp = l.get("diff_pct")
                    st.caption(f"قیمت فهرست‌بها: {fmt_money(_app_p, cur)}"
                               + (f" · اختلاف: {fa_float(_dp, 1)}٪"
                                  + (" — **بیش از آستانهٔ بازبینی**"
                                     if _dp is not None and abs(_dp) > float(s.get('price_diff_warn_pct') or 30.0)
                                     else "")
                                  if _dp is not None else ""))
                    if st.button("حذف قیمت دستی (بازگشت به قیمت فهرست‌بها)",
                                 key=f"tme-del-{l['id']}"):
                        append_audit(s, l["code"], "price", _mp.get("price"),
                                     l.get("app_price") or l["price"], "حذف قیمت دستی")
                        s["manual_prices"].pop(l["id"], None)
                        st.rerun()

                c1, c2 = st.columns([3, 1])
                if c2.button("بازگشت به تطبیق خودکار", key=f"tme-reset-{l['id']}",
                             disabled=(l["id"] not in s["manual_codes"]
                                       and l["id"] not in s["manual_prices"])):
                    s["manual_codes"].pop(l["id"], None)
                    s["manual_prices"].pop(l["id"], None)
                    st.rerun()
                _ex_ids = excluded_ids(s)
                excl = c1.checkbox("استثنا از صورت‌وضعیت", value=l["id"] in _ex_ids,
                                   key=f"tme-excl-{l['id']}")
                if excl and l["id"] not in _ex_ids:
                    append_audit(s, l["code"], "exclude", False, True, "استثنا دستی")
                    s["excluded"].append({
                        "id": l["id"], "reason": "استثنا از تب مترهٔ ریز",
                        "user": s.get("price_user") or "", "at": jalali_now_str()})
                    st.rerun()

    _ex = s.get("excluded") or []
    if _ex:
        st.warning(f"{fa(len(_ex))} ردیف از صورت‌وضعیت مستثنا شده‌اند: "
                   + "، ".join((e["id"] if isinstance(e, dict) else str(e)) for e in _ex))
        if st.button("بازگردانی همهٔ ردیف‌های مستثنی‌شده", key="tme-restore-all"):
            append_audit(s, "همهٔ ردیف‌ها", "exclude", len(_ex), 0, "بازگردانی دسته‌جمعی")
            s["excluded"] = []
            st.rerun()


# ════════════════════════════════════════════════════════════════
# تب ۵ — صورت‌وضعیت (با تاریخ شمسی و سوابق تجمعی)
# ════════════════════════════════════════════════════════════════

def _fin_chain_html(rows, net_label, net_value, words, cur, rounding=True):
    """ساخت جدول HTML صورت‌جمع مالی (راست‌به‌چپ و رنگ‌بندی‌شده).

    اگر net_label برابر None باشد، سطر جمع پایانی و «به حروف» چاپ نمی‌شود
    (برای زنجیرهٔ ناخالص که جمع آن در سطر «ب)» خودش آمده است).
    """
    parts = ['<div style="direction:rtl">']
    for label, val, kind in rows:
        cls = {"add": "fin-add", "ded": "fin-ded", "base": "fin-base"}.get(kind, "fin-add")
        parts.append(f'<div class="fin-card {cls}"><div class="fin-row">'
                     f'<span class="lbl">{label}</span><span class="val">{fmt_money(val, cur, rounding)}</span></div></div>')
    if net_label is not None:
        parts.append(f'<div class="fin-card fin-net" style="padding:18px"><div class="fin-row">'
                     f'<span class="lbl" style="font-size:15px;font-weight:800">{net_label}</span>'
                     f'<span class="val" style="font-size:19px;color:#ffd166">{fmt_money(net_value, cur)}</span></div></div>')
        parts.append(f'<div class="words-box"><b>به حروف:</b> {words}</div>')
    parts.append("</div>")
    return "".join(parts)


def _jalali_input(label: str, key: str, value: str) -> str:
    """فیلد ورودی تاریخ شمسی با اعتبارسنجی لحظه‌ای (بدون کتابخانه خارجی)."""
    v = st.text_input(label, value=value, placeholder="۱۴۰۴/۰۳/۳۱", key=key)
    if v.strip() and not is_valid_jalali_date(v):
        st.error(f"قالب «{label}» نامعتبر است (نمونهٔ صحیح: ۱۴۰۴/۰۳/۳۱؟) — تصحیح کنید.", icon="⚠️")
    return v


def render_tab_manual_prices():
    """تب پنل قیمت دستی (فاز C — §۱۵-۴).

    محلِ واحدِ ورود قیمت‌های دستی، ردیف‌های ستاره‌دار، فایل کناری و سابقهٔ
    ویرایش. ویرایشِ مقادیر در تب «مترهٔ ریز» اینجا ذخیره می‌شود.
    """
    st.markdown("### پنل قیمت دستی")
    s = st.session_state.settings
    result = compute_now()
    if not result or not result["lines"]:
        st.info("ابتدا جداول Schedule یا فایل Mapping را بارگذاری کنید.")
        return
    cur = s["currency"]

    # ══ ۱) تنظیمات و فایل کناری ══
    with st.container(border=True):
        hc = st.columns([1.3, 0.9, 1.9, 1.0, 1.0, 1.0])
        s["price_user"] = hc[0].text_input("نام کاربر", value=s.get("price_user", ""),
                                           placeholder="دفتر فنی", key="mp-user")
        s["price_diff_warn_pct"] = hc[1].number_input(
            "آستانهٔ هشدار اختلاف (٪)",
            value=float(s.get("price_diff_warn_pct", 30.0)),
            step=5.0, min_value=1.0, max_value=200.0, key="mp-wpct")
        s["price_project_file"] = hc[2].text_input(
            "مسیر فایل پروژه (برای پروفایل پروژه)",
            value=s.get("price_project_file", ""),
            placeholder="C:\\Projects\\MyProject.rvt یا مسیر فایل پروژه",
            key="mp-projfile")
        _side = profile_sidecar_path(s.get("price_project_file") or "")
        if _side:
            hc[3].caption(f"فایل پروفایل:\n`{_side}`")
        if hc[4].button("💾 ذخیره پروفایل پروژه", key="mp-save-side",
                        disabled=not _side):
            _p = save_profile(_side, s, st.session_state.meta)
            append_audit(s, "پروفایل پروژه", "save", None, _p,
                         "ذخیره پروفایل")
            st.success(f"پروفایل پروژه در {_p} ذخیره شد"
                       + (" (از نسخهٔ قبلی backup گرفته شد)." if os.path.exists(_p + ".bak")
                          else "."))
            st.rerun()
        if hc[5].button("📂 بارگذاری از فایل پروفایل", key="mp-load-side",
                        disabled=not (_side and os.path.exists(_side))):
            _nm, _ns, _w = load_profile(_side)
            if _ns is None:
                for _w1 in _w:
                    st.error(_w1)
            else:
                for _w1 in _w:
                    st.warning(_w1)
                st.session_state.settings.clear()
                st.session_state.settings.update(_ns)
                if _nm:
                    st.session_state.meta.clear()
                    st.session_state.meta.update(_nm)
                append_audit(st.session_state.settings,
                             "پروفایل پروژه", "load", None, _side,
                             "بارگذاری پروفایل", kind="meta")
                st.success("پروفایل پروژه بارگذاری شد."
                           + ("" if _nm else " (فایل کناری قدیمی — فقط قیمت‌ها)"))
                st.rerun()

        # ── فاز E-۵: دانلود/بارگذاری پروفایل + پروژه جدید ──
        pc2 = st.columns([1, 1, 1])
        _prof_json = json.dumps(
            profile_payload(s, st.session_state.meta),
            ensure_ascii=False, indent=1, default=str).encode("utf-8")
        _prof_name = "MetreYarProfile_Sh%s.json" % convert_persian_digits(
            st.session_state.meta.get("report_no") or "0")
        pc2[0].download_button("⬇️ دانلود پروفایل (JSON)",
                               data=_prof_json, file_name=_prof_name,
                               mime="application/json",
                               use_container_width=True,
                               key="mp-dl-profile")
        _up = pc2[1].file_uploader("⬆️ بارگذاری پروفایل (JSON)",
                                   type=["json"], key="mp-up-profile")
        if _up is not None:
            _nm, _ns, _w = load_profile(_up.getvalue())
            if _ns is None:
                for _w1 in _w:
                    st.error(_w1)
            else:
                for _w1 in _w:
                    st.warning(_w1)
                st.session_state.settings.clear()
                st.session_state.settings.update(_ns)
                if _nm:
                    st.session_state.meta.clear()
                    st.session_state.meta.update(_nm)
                append_audit(st.session_state.settings,
                             "پروفایل پروژه", "load", None, _up.name,
                             "بارگذاری پروفایل", kind="meta")
                st.success(f"پروفایل از {_up.name} بارگذاری شد.")
                st.rerun()
        if pc2[2].button("📑 پروژهٔ جدید از روی این پروژه",
                         key="mp-copy-project", use_container_width=True):
            _nm, _ns = copy_project(s, st.session_state.meta)
            st.session_state.meta.clear()
            st.session_state.meta.update(_nm)
            st.session_state.settings.clear()
            st.session_state.settings.update(_ns)
            st.toast("پروژهٔ جدید از روی این پروژه ساخته شد.")
            st.rerun()

        up = st.file_uploader("ورود قیمت‌ها از یک فایل Excel (شیت «قیمت‌های دستی»)",
                              type=["xlsx"], key="mp-import-xlsx")
        if up is not None:
            try:
                _payload = parse_manual_entries_xlsx(up.getvalue())
            except Exception as ex:  # فایل خراب
                st.error(f"خواندن فایل Excel ناموفق بود: {ex}")
                _payload = None
            if _payload is None:
                st.warning("در این فایل شیت «قیمت‌های دستی» پیدا نشد.")
            else:
                _w = apply_manual_entries(s, _payload)
                for _w1 in _w:
                    st.warning(_w1)
                append_audit(s, "فایل Excel", "import", None,
                             f"{len(_payload.get('manual_prices') or {})} قیمت",
                             "ورود از Excel")
                st.success("قیمت‌ها از Excel وارد شدند.")
                st.rerun()

    # ══ ۲) وضعیت کلی قیمت‌ها ══
    _ps = result.get("price_status_summary") or {}
    if _ps:
        mc = st.columns(len(MANUAL_STATUSES) + 1)
        _icons = {"قطعی": "✅", "موقت": "⏳", "پیش‌فرض اپ": "⚙️",
                  "دستی": "✏️", "نیازمند ورود": "⚠️"}
        for i, _st in enumerate(MANUAL_STATUSES):
            mc[i].metric(f"{_icons.get(_st, '')} {_st}", fa(_ps.get(_st, 0)))
        _st_tot = result.get("starred_total") or 0
        mc[len(MANUAL_STATUSES)].metric(
            "⭐ ستاره‌دار",
            fmt_money(_st_tot, cur, with_unit=False),
            f"{fa_float(result.get('starred_pct') or 0, 1)}٪ از برآورد")
        _npe = result.get("needs_price_entry") or 0
        if _npe:
            st.warning(f"⚠️ {fa(_npe)} ردیف «نیازمند ورود» هستند — خروجی تا تأیید "
                       f"آن‌ها «پیش‌نویس» است (بازبینی در تب «مترهٔ ریز»).")

    # ══ ۳) ردیف‌های ستاره‌دار (غیرفهرستی) ══
    with st.container(border=True):
        st.markdown("**افزودن ردیف ستاره‌دار** (غیرفهرستی — ورود کامل دستی)")
        with st.form("mp-starred-form", clear_on_submit=True):
            f1 = st.columns([1, 3, 1, 1])
            code = f1[0].text_input("کد (اختیاری)", placeholder="۹۹۰۱۰۱",
                                    key="mp-st-code")
            desc = f1[1].text_input("شرح ردیف*", placeholder="قفل‌سازی و یراق‌آلات درب‌ها",
                                    key="mp-st-desc")
            unit = f1[2].selectbox("واحد",
                                   ["عدد", "مترطول", "مترمربع", "مترمکعب", "کیلوگرم", "تن", "فقره"],
                                   key="mp-st-unit")
            ch_opts = [c for c in _CHAPTER_ORDER] + ["31", "33", "99"]
            ch_opts = list(dict.fromkeys(ch_opts))
            chapter = f1[3].selectbox(
                "فصل (برای شاخص تعدیل)",
                [f"{c} — {chapter_title(c)}" for c in ch_opts],
                index=ch_opts.index("31") if "31" in ch_opts else 0,
                key="mp-st-chapter")
            _ch = chapter.split(" — ")[0]

            mode = st.radio("روش ورود مقدار (ریزمتره)",
                            ["عدد مستقیم", "تعداد × طول × عرض × ارتفاع"],
                            horizontal=True, key="mp-st-mode")
            if mode == "عدد مستقیم":
                g1 = st.columns([1, 1])
                qty = g1[0].number_input("مقدار*", min_value=0.0, step=1.0,
                                         format="%.2f", key="mp-st-qty")
                note = g1[1].text_input("توضیح محل/کاربرد", key="mp-st-note")
            else:
                g2 = st.columns(4)
                cnt = g2[0].number_input("تعداد*", min_value=0.0, step=1.0,
                                         key="mp-st-cnt")
                ln = g2[1].number_input("طول (متر)", min_value=0.0, step=0.1,
                                        key="mp-st-ln")
                wd = g2[2].number_input("عرض (متر)", min_value=0.0, step=0.1,
                                        key="mp-st-wd")
                ht = g2[3].number_input("ارتفاع/ضخامت (متر)", min_value=0.0, step=0.1,
                                        key="mp-st-ht")
                qty = cnt * ln * wd * ht
                st.caption(f"مقدار محاسبه‌شده: **{fmt_num(qty, 2)}** {unit}")
                note = st.text_input("توضیح محل/کاربرد", key="mp-st-note")

            f2 = st.columns([1.2, 1, 1.1, 1.1, 1])
            price = f2[0].number_input(
                f"بهای واحد ({'تومان' if cur == 'toman' else 'ریال'})*",
                min_value=0.0, step=1000.0, format="%.0f", key="mp-st-price")
            src = f2[1].selectbox("منبع*",
                                  [x for x in MANUAL_SOURCES
                                   if x != "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)"],
                                  key="mp-st-src")
            doc_no = f2[2].text_input("شماره سند", key="mp-st-doc")
            doc_date = f2[3].text_input("تاریخ سند (شمسی)", placeholder="۱۴۰۵/۰۴/۱۲",
                                        key="mp-st-date")
            submitted = f2[4].form_submit_button("➕ افزودن ردیف", type="primary")

            if submitted:
                _errs = []
                if not desc.strip():
                    _errs.append("شرح ردیف الزامی است.")
                if qty <= 0:
                    _errs.append("مقدار باید بزرگتر از صفر باشد.")
                if price <= 0:
                    _errs.append("بهای واحد باید بزرگتر از صفر باشد.")
                if doc_date and not TechnicalOfficeEngine._parse_jalali(doc_date):
                    _errs.append(f"تاریخ سند «{doc_date}» شمسی معتبر نیست.")
                if _errs:
                    for _e in _errs:
                        st.error(_e)
                else:
                    s.setdefault("starred_rows", []).append({
                        "code": code.strip(), "desc": desc.strip(),
                        "unit": unit, "qty": float(qty), "price": float(price),
                        "chapter": _ch, "source": src, "doc_no": doc_no,
                        "doc_date": doc_date, "note": note,
                        "user": s.get("price_user") or "",
                        "at": jalali_now_str()})
                    append_audit(s, code.strip() or "(ستاره‌دار)", "starred_row",
                                 None, f"{qty} × {price}", src)
                    st.success(f"ردیف ستاره‌دار اضافه شد: {fmt_money(qty * price, cur)}")
                    st.rerun()

        _srows = s.get("starred_rows") or []
        if _srows:
            st.markdown("**ردیف‌های ستاره‌دار ثبت‌شده**")
            for i, sr in enumerate(_srows):
                rc = st.columns([0.8, 4.0, 1.0, 1.3, 1.3, 0.8])
                rc[0].markdown(f"`{fa(sr.get('code') or '—')}*`")
                rc[1].markdown(sr.get("desc", "")
                               + (f" ({sr.get('note')})" if sr.get("note") else ""))
                rc[1].caption(f"{sr.get('source', '—')} · {sr.get('doc_no') or 'بدون سند'}"
                              + f" · {sr.get('doc_date') or 'بدون تاریخ'}"
                              + f" · فصل {fa(sr.get('chapter') or '—')}")
                rc[2].markdown(f"{fmt_num(sr.get('qty', 0), 2)} {sr.get('unit', '')}")
                rc[3].markdown(fmt_money(sr.get("price", 0), cur))
                rc[4].markdown(f"**{fmt_money((sr.get('qty', 0) or 0) * (sr.get('price', 0) or 0), cur)}**")
                if rc[5].button("حذف", key=f"mp-st-del-{i}"):
                    append_audit(s, sr.get("code") or "(ستاره‌دار)",
                                 "starred_row",
                                 f"{sr.get('qty')} × {sr.get('price')}", None,
                                 "حذف دستی")
                    s["starred_rows"].pop(i)
                    st.rerun()

    # ══ ۴) سابقهٔ ویرایش ══
    _audit = s.get("price_audit") or []
    with st.container(border=True):
        st.markdown(f"**سابقهٔ ویرایش** — {fa(len(_audit))} رویداد"
                    + (" (جدیدترین در بالا)" if _audit else ""))
        if _audit:
            st.dataframe(pd.DataFrame([{
                "زمان": a.get("at", ""),
                "کاربر": a.get("user", ""),
                "ردیف": a.get("item", ""),
                "فیلد": a.get("field", ""),
                "مقدار قبلی": a.get("old", ""),
                "مقدار جدید": a.get("new", ""),
                "منبع": a.get("source", ""),
            } for a in reversed(_audit)]),
                hide_index=True, use_container_width=True,
                height=min(34 * (len(_audit) + 1), 300))


def render_tab_statement():
    """تب صورت‌وضعیت: متادیتای سند، زنجیرهٔ مالی، به حروف و سوابق تجمعی."""
    st.markdown("### صورت‌وضعیت رسمی (فارسی و راست‌چین)")
    result = compute_now()

    meta = st.session_state.meta
    s = st.session_state.settings
    if result and result.get("chapter_rows"):
        st.session_state["adj_chapters"] = [r["chapter"]
                                            for r in result["chapter_rows"]]

    st.markdown("##### مشخصات پروژه و سند")
    c = st.columns(4)
    meta["project_name"] = c[0].text_input("نام پروژه", value=meta["project_name"],
                                           key="ts-project-name",
                                           placeholder="مثلاً: مجتمع مسکونی ساحلی — فاز اسکلت")
    meta["contract_no"] = c[1].text_input("شماره قرارداد", value=meta["contract_no"],
                                          key="ts-contract-no")
    meta["employer"] = c[2].text_input("نام کارفرما", value=meta["employer"], key="ts-employer")
    meta["contractor"] = c[3].text_input("نام پیمانکار", value=meta["contractor"], key="ts-contractor")
    c = st.columns(4)
    meta["consultant"] = c[0].text_input("نام مشاور", value=meta["consultant"], key="ts-consultant")
    meta["location"] = c[1].text_input("محل اجرا", value=meta["location"], key="ts-location")
    meta["contract_date"] = _jalali_input("تاریخ شروع پیمان (شمسی)", "ts-contract-date",
                                          meta["contract_date"])
    meta["report_type"] = c[3].selectbox("نوع صورت‌وضعیت", ["موقت", "قطعی"],
                                         index=0 if meta["report_type"] == "موقت" else 1,
                                         key="ts-report-type")
    c = st.columns(4)
    meta["report_no"] = c[0].text_input("شمارهٔ صورت‌وضعیت", value=meta["report_no"],
                                        key="ts-report-no")
    meta["period_start"] = _jalali_input("تاریخ شروع دورهٔ صورت‌وضعیت (شمسی)", "ts-period-start",
                                         meta["period_start"])
    meta["period_end"] = _jalali_input("تاریخ پایان دورهٔ صورت‌وضعیت (شمسی)", "ts-period-end",
                                       meta["period_end"])
    c[3].caption(f"امروز به وقت ایران: {today_jalali()}")
    s["work_period_start"] = meta["period_start"]
    s["work_period_end"] = meta["period_end"]
    # فاز E-6 Part C گام ۳: تاریخ شروع پیمان ملاکِ محاسبهٔ پایان مدت
    # است (بند ۲-۵) — مثلِ دورهٔ صورت‌وضعیت از meta خوانده می‌شود.
    s["contract_date"] = meta["contract_date"]

    if not result or not result["lines"]:
        st.info("پس از بارگذاری جداول، صورت‌جمع مالی در این بخش نمایش داده می‌شود.")
        return

    st.markdown("---")
    cur = s["currency"]
    idx = result.get("index")
    idx_note = ""
    if idx and idx.get("target_period") and idx.get("target_period") != idx.get("base_period"):
        idx_note = (f" — تعدیل به دورهٔ {idx['target_period']}"
                    + (" (شاخص موقت)" if idx.get("provisional") else ""))
    _fc_main = result.get("coefs", {}).get("floors", {}) or {}
    _fc_lbl = (f"ضریب طبقات (× {fa(_fc_main.get('value') or 1.0)})")
    if _fc_main.get("eligible_lines"):
        _fc_lbl += (f" — فقط {fa(len(_fc_main['eligible_lines']))} ردیف مشمول؛ "
                    f"{fa(len(_fc_main.get('excluded_chapters') or []))} فصل مستثنی")
    rows = [
        ("الف) جمع ناخالص ردیف‌های فهرست‌بها" + idx_note, result["base_total"], "base"),
        (_fc_lbl, result["floors_amount"], "add"),
        (f"ضریب بالاسری (× {fa(s['overhead_coef'])})", result["overhead_amount"], "add"),
        (f"ضریب منطقه‌ای (× {fa((result.get('coefs', {}).get('regional', {}) or {}).get('value') or 1.0)})", result["regional_amount"], "add"),
        ("تجهیز و برچیدن کارگاه (مبلغ)", result["site_setup"], "add"),
        ("ب) مبلغ ناخالص نهایی قابل پرداخت", result["gross_payable"], "base"),
    ]
    st.markdown(_fin_chain_html(rows, None, None, None, cur),
                unsafe_allow_html=True)

    # ارجاع منبع ضرایب (ایراد ۲/۳/۴ مرحلهٔ ۱۳)
    with st.expander("منبع و ارجاع ضرایب"):
        _co = result.get("coefs", {})
        for _key, _lbl in [("floors", "ضریب طبقات"), ("regional", "ضریب منطقه‌ای")]:
            _ci = _co.get(_key) or {}
            st.caption(f"**{_lbl}** — {_ci.get('source') or '—'}"
                       + (f" [وضعیت: {_ci.get('status')}]" if _ci.get("status") else ""))
        st.caption("ارجاع بهای ردیف‌ها: ستون «ارجاع بها» در شیت «صورت وضعیت» "
                   "خروجی Excel.")

    # هشدار سقف ۴٪ تجهیز و برچیدن (دستورالعمل کاربرد بند ۲-۸)
    if result["regional_amount"] > 0:
        _cap = 0.04 * result["regional_amount"]
        if result["site_setup"] > _cap:
            st.warning("هشدار: مبلغ تجهیز و برچیدن کارگاه بیش از ۴٪ مبلغ قبل از آن "
                       f"({fmt_money(_cap, cur)}) است (دستورالعمل کاربرد بند ۲-۸).")

    # گزارش شاخص تعدیل (دوره، نوع و منبع هر فصل)
    if idx and idx.get("target_period") and idx.get("target_period") != idx.get("base_period"):
        with st.expander("گزارش شاخص تعدیل فهرست‌بها"):
            st.caption(f"دورهٔ مبنا: {idx['base_period']} — دورهٔ هدف: {idx['target_period']}"
                       + (" — شاخص موقت" if idx.get("provisional") else ""))
            ch_rows = [{"فصل": fa(r["chapter"]), "ضریب": round(r["factor"], 4) if r["factor"] else "—",
                        "نوع شاخص": r.get("kind") or "—", "منبع (بخشنامه)": r.get("source") or "—"}
                       for r in idx.get("chapters", []) if r.get("factor") not in (None, 1.0)]
            if ch_rows:
                st.dataframe(pd.DataFrame(ch_rows), hide_index=True,
                             use_container_width=True)
            else:
                st.caption("ضریب همهٔ فصل‌ها در این دوره برابر ۱ است.")

    # ═══ فاز B: موتورهای تعدیل (دو موتور مجزا — روی زنجیره بالا اثر ندارند) ═══
    # هر دو موتور می‌توانند همزمان فعال باشند؛ کارت، جزئیات و شیت هر کدام جداست.
    _adj = result.get("adjustment") or {}
    for _eng_key, _eng_name in (("tadil", "موتور ۱ — تعدیل پیمان"),
                                ("baravord", "موتور ۲ — برآورد به‌هنگام")):
        _e = _adj.get(_eng_key)
        if not _e:
            continue
        _draft = bool(_e.get("draft"))
        st.markdown("##### %s (فاز B)" % _eng_name)
        # گام ۶ (بندهای ۲-۱/۲-۲): مسیرِ حل‌شدهٔ شاخص
        _imr = _e.get("index_method_resolved")
        if _imr:
            st.caption("مسیر شاخصِ حل‌شده: %s — %s (گام ۶ — بندهای ۲-۱/۲-۲)"
                       % (_imr["method"], _imr["source"]))
        if _e.get("error"):
            st.error("⛔ %s" % _e["error"])
        if _e.get("incomplete"):
            st.error("این موتور ناکامل است — شاخص برخی فصل‌ها ناموجود است: %s. "
                     "شاخص دستی آن‌ها را در سایدبار وارد کنید."
                     % "، ".join("%s (%s %s)" % tuple(m) for m in _e["missing"]))
        if _draft:
            st.markdown('<div class="warn-y">پیش‌نویس — مقادیر استخراج‌شده/منبع '
                        'تصویری هنوز تأیید نشده‌اند. این خروجی تا تأیید شما '
                        'رسمی نیست.</div>', unsafe_allow_html=True)
        # فاز E-10 §۲ — واترمارکِ «پیش‌نویس – دورهٔ کارکرد وارد نشده» روی UI
        if _eng_key == "tadil" and _e.get("work_period_missing"):
            st.markdown('<div class="warn-y">پیش‌نویس – دورهٔ کارکرد وارد '
                        'نشده. موتورِ تعدیل تمامِ کارکرد را به آخرین شاخصِ '
                        'قطعی منتسب می‌کند و ΔP با حالتِ «شاخصِ هر سه‌ماهه» '
                        'متفاوت است؛ خروجیِ نهاییِ Excel ساخته نمی‌شود '
                        '(فقط پیش‌نویس).</div>', unsafe_allow_html=True)
        # فاز E-10 §۲ — برچسبِ «علی‌الحساب – k = ۰٫۹۵»
        if _eng_key == "tadil" and _e.get("k_provisional"):
            st.markdown('<div class="warn-y">علی‌الحساب – k = ۰٫۹۵ — '
                        'وضعیتِ اتمامِ کار در مدتِ پیمان نامشخص است (بند ۱-۸ '
                        'بخشنامهٔ ۲۰۸۰). خروجی مجاز است، ولی تا مشخص‌شدنِ '
                        'تکلیفِ قطعی، علی‌الحساب می‌ماند.</div>', unsafe_allow_html=True)
        # زنجیرهٔ مبلغ پایه (A) — قدم‌به‌قدم و دقیق تا ریال
        st.markdown(_fin_chain_html(
            [(_lbl, _amt, "base") for _lbl, _amt, _n in _e["chain"]],
            None, None, None, cur, rounding=False), unsafe_allow_html=True)
        # جزئیات فصل به فصل
        _ch = _e.get("chapters") or []
        if _ch:
            _vcol = "مبلغ تعدیل (ΔP_c)" if _eng_key == "tadil" else "مبلغ به‌هنگام‌شده"
            with st.expander("جزئیات فصل به فصل (%s ردیف)" % fa(len(_ch))):
                st.dataframe(pd.DataFrame([
                    {"فصل": _r["chapter"], "عنوان": _r["title"],
                     "مبلغ پایه": fmt_money(_r["amount"], cur, rounding=False),
                     "شاخص Io": fa_float(_r["io"], 1), "شاخص It": fa_float(_r["it"], 1),
                     "نسبت It/Io": fa_float(_r["ratio"], 4),
                     _vcol: fmt_money(_r["value"], cur, rounding=False),
                     "وضعیت": _r["status"]} for _r in _ch
                ]), hide_index=True, use_container_width=True)
        _split_q = _e.get("split") or []
        if _eng_key == "tadil" and len(_split_q) > 1 and _ch:
            with st.expander("شاخص It هر فصل در هر سه‌ماههٔ کارکرد"):
                _qrows = []
                for _r in _ch:
                    _d = {"فصل": _r["chapter"], "عنوان": _r["title"]}
                    for _q, _iv, _st in (_r.get("quarters") or []):
                        _d[_quarter_label(_q)] = fa_float(_iv, 1) \
                            + (" (موقت)" if _st == "موقت" else "")
                    _qrows.append(_d)
                st.dataframe(pd.DataFrame(_qrows), hide_index=True,
                             use_container_width=True)
                st.caption("وزن هر سه‌ماهه از کل کارکرد: %s — ستون موقت با "
                           "ضریب موقت ۱۴۰۵Q1 محاسبه شده است (زرد در Excel)."
                           % "، ".join("%s (%s٪)" % (_quarter_label(q),
                                                     fa_float(f * 100, 1))
                                       for q, f in _split_q))
        # زنجیرهٔ نهایی موتور
        if _eng_key == "tadil":
            _adj_rows = [
                ("مبلغ پایهٔ مشمول شامل تجهیز (A)", _e["base_amount"], "base"),
                ("جمع تعدیل (شامل علی‌الحساب) = k × Σ_c (It_c/Io_c − 1) × A_c",
                 _e["delta_p"], "add"),
                ("مبلغ نهایی (A + جمع تعدیل)", _e["result_amount"], "net"),
            ]
            # تفکیک بخش قطعی و علی‌الحساب — فقط وقتی بخش علی‌الحساب
            # غیرصفر است (کارکرد به دورهٔ موقت ۱۴۰۵Q1 رسیده باشد).
            # باقیماندهٔ گردسازی به بخش علی‌الحساب می‌رسد تا
            # قطعی + علی‌الحساب ≡ ΔP گردشده برقرار باشد.
            _dp_all, _dp_def, _dp_prov = _split_rounded(
                _e["delta_p"], _e.get("delta_p_definitive") or 0.0)
            if abs(_dp_prov) >= 0.01:
                _adj_rows.append(
                    ("بخش قطعی (شاخص‌های قطعی ۱۴۰۴)",
                     _dp_def, "add"))
                _adj_rows.append(("بخش علی‌الحساب (شاخص موقت ۱۴۰۵ — بند ۳)",
                                  _dp_prov, "add"))
            # ── فاز E-6: مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) ──
            if abs(_e.get("k_diff") or 0) >= 0.01:
                _adj_rows.append((
                    "مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ — همراه قطعی، بند ۸-۴)",
                    _e["k_diff"], "add"))
            # ── فاز E-6 Part C گام ۴: کسر ۵٪ (بند ۷) ──
            if abs(_e.get("deduction_fault") or 0) >= 0.01:
                _adj_rows.append((
                    "کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷)",
                    -_e["deduction_fault"], "ded"))
        else:
            _adj_rows = [
                ("مبلغ پایه شامل تجهیز (A)", _e["base_amount"], "base"),
                ("به‌هنگام‌سازی فصل به فصل با نسبت‌های It/Io",
                 _e["result_amount"] - _e["base_amount"], "add"),
                ("برآورد به‌هنگام‌شده", _e["result_amount"], "net"),
            ]
            if _e.get("grand_updated") is not None:
                _coef_diff = _e["grand_updated"] - _e["result_amount"]
                # اگر A_basis = «با ضرایب» باشد، ضرایب از قبل داخل A_c هستند و
                # این ردیف صفر می‌شود؛ فقط در حالت «بدون ضرایب» نشان داده می‌شود.
                if abs(_coef_diff) >= 0.01:
                    _adj_rows.append(
                        ("اعمال ضرایب قیمت پیمان (بالاسری × منطقه‌ای × پیشنهادی)",
                         _coef_diff, "add"))
                _adj_rows.append(
                    ("جمع کل به‌هنگام‌شده (قیمت پیمان)", _e["grand_updated"], "net"))
                _adj_rows.append(
                    ("جمع کل فعلی (زنجیرهٔ اصلی — بدون به‌هنگام‌سازی)",
                     _e["grand_current"], "base"))
        _final_amt = _e.get("grand_updated")
        if _final_amt is None:
            _final_amt = _e["result_amount"]
        st.markdown(_fin_chain_html(
            _adj_rows,
            "مبلغ نهایی %s%s" % (_e["mode"], " — پیش‌نویس" if _draft else ""),
            _final_amt,
            money_to_words(_final_amt), cur, rounding=False),
            unsafe_allow_html=True)
        _cap = "فرمول: %s | Io: %s | It: %s" % (
            _e.get("formula"), _io_label(_e), _quarter_label(_e.get("it_q")))
        # ══ فاز E-8 §۳.۱: وضعیت موقت/قطعی + ضریبِ موقتِ برآورد ══
        if _e.get("it_status"):
            _cap += " (%s)" % _e["it_status"]
        if _e.get("prov") is not None and _e.get("it_status") == "موقت":
            _cap += " | ضریب موقت ۱۴۰۵Q1: %s%s" % (
                fa_float(_e["prov"], 4),
                " (دستی)" if _e.get("prov_manual") else "")
        st.caption(_cap)
        _sp = _e.get("split") or []
        if len(_sp) > 1:
            st.caption("تقسیم کارکرد بین سه‌ماهه‌ها: %s"
                       % "، ".join("%s (%s٪)" % (_quarter_label(q),
                                                 fa_float(f * 100, 1))
                                   for q, f in _sp))
        if _eng_key == "tadil":
            _p = _e.get("params") or {}
            st.caption("ضریب k = %s | شرط تأخیر: %s | پیش‌پرداخت: %s | "
                       "تعدیل منفی: %s"
                       % (fa_float(_e.get("coef") or 0, 2), _e.get("delay_mode"),
                          _e.get("advance_mode"),
                          "مجاز" if _p.get("allow_negative") else "غیرمجاز"))
        if _e.get("pending"):
            with st.expander("مقادیر منتظر تأیید — %s" % _e["mode"]):
                st.dataframe(pd.DataFrame(_e["pending"]), hide_index=True,
                             use_container_width=True)

    # ═════════ فاز E-6 Part C گام ۱۲ (حرف g): پنلِ «وضعیت ورودی‌ها» ═════════
    # ورودی‌های ناقص (از هشدارها) + تفسیرهای «منتظر تأیید کاربر» در یک نگاه.
    with st.expander("وضعیت ورودی‌ها (گام ۱۲ — فاز E-6)"):
        _warns = result.get("warnings") or []
        _errs = [x for x in _warns if x.get("level") == "خطا"]
        _ws = [x for x in _warns if x.get("level") == "هشدار"]
        if _errs:
            st.markdown("**⛔ ورودی‌های ناقص (خطا — تا اصلاح رسمی نیست):**")
            st.dataframe(pd.DataFrame([
                {"المان": x.get("item"), "شرح": x.get("message"),
                 "اقدام": x.get("action"), "بند": x.get("ref")}
                for x in _errs]), hide_index=True, use_container_width=True)
        else:
            st.markdown("✅ **هیچ ورودیِ ناقصی نیست.**")
        if _ws:
            st.markdown("**⚠ هشدارها (نیازمند بررسی):**")
            st.dataframe(pd.DataFrame([
                {"المان": x.get("item"), "شرح": x.get("message"),
                 "اقدام": x.get("action"), "بند": x.get("ref")}
                for x in _ws]), hide_index=True, use_container_width=True)
        st.markdown("**تصمیماتِ باز — منتظر تأیید کاربر** "
                    "(%s مورد — جزئیات در §۱۸-۳ ACCEPTANCE.md):"
                    % fa(len(PENDING_INTERPRETATIONS)))
        st.dataframe(pd.DataFrame([
            {"شناسه": _no, "موضوع": _s, "تفسیرِ پیاده‌شده": _i,
             "گزینهٔ دیگر": _a, "اثر عددی": _e2}
            for _no, _s, _i, _a, _e2 in PENDING_INTERPRETATIONS]),
            hide_index=True, use_container_width=True)
    # بلوک جداگانهٔ «خالص پرداختی» — بر ناخالص اثر ندارد
    st.markdown("##### محاسبهٔ جداگانهٔ خالص پرداختی (کسورات قانونی)")
    net_rows = [
        ("مبلغ ناخالص نهایی", result["gross_payable"], "base"),
        (f"کسورات: بیمه ({fa(s['insurance_pct'])}٪)", -result["insurance"], "ded"),
        (f"کسورات: مالیات ({fa(s['tax_pct'])}٪)", -result["tax"], "ded"),
        (f"کسورات: حسن انجام کار ({fa(s['good_job_pct'])}٪)", -result["good_job"], "ded"),
        ("کسورات: پیش‌پرداخت", -result["advance_payment"], "ded"),
        ("مجموع کسورات", -result["total_deductions"], "ded"),
    ]
    st.markdown(_fin_chain_html(net_rows, "خالص پرداختی پس از کسورات",
                                result["net_payable"],
                                money_to_words(result["net_payable"]), cur),
                unsafe_allow_html=True)

    c = st.columns([1, 2])
    with c[0]:
        if st.button(f"ثبت صورت‌وضعیت شماره {fa(meta['report_no'] or '—')} در سوابق",
                     type="primary", use_container_width=True, key="ts-save-history"):
            prev = st.session_state.history[-1] if st.session_state.history else None
            st.session_state.history.append({
                "report_no": meta["report_no"], "report_type": meta["report_type"],
                "period_start": meta["period_start"], "period_end": meta["period_end"],
                "gross_payable": result["gross_payable"],
                "total_deductions": result["total_deductions"],
                "net_payable": result["net_payable"],
                "current_work": result["net_payable"] - (prev["net_payable"] if prev else 0),
            })
            st.toast("در سوابق تجمعی ثبت شد.", icon="✅")
            st.rerun()

    st.markdown("##### سوابق صورت‌وضعیت‌ها (تجمعی)")
    if not st.session_state.history:
        st.caption("هنوز صورت‌وضعیتی ثبت نشده است؛ پس از محاسبهٔ هر دوره، دکمهٔ ثبت را بزنید.")
    else:
        hist_rows, prev = [], None
        for h in st.session_state.history:
            current = h["net_payable"] - (prev["net_payable"] if prev else 0)
            hist_rows.append({
                "شماره": fa(h["report_no"]), "نوع": h["report_type"],
                "دوره از": h["period_start"] or "—", "دوره تا": h["period_end"] or "—",
                "ناخالص تجمعی": fmt_money(h["gross_payable"], cur),
                "خالص تجمعی": fmt_money(h["net_payable"], cur),
                "کارکرد این دوره": fmt_money(current, cur),
            })
            prev = h
        st.dataframe(pd.DataFrame(hist_rows), hide_index=True, use_container_width=True)
        del_options = ["—"] + [
            f"شماره {fa(h['report_no'])} ({h['report_type']})" for h in st.session_state.history]
        del_idx = st.selectbox("حذف رکورد از سوابق (اختیاری)", del_options,
                               key="ts-history-del-select")
        if del_idx != "—" and st.button("حذف رکورد انتخاب‌شده", key="ts-history-del-btn"):
            for idx_h, h in enumerate(st.session_state.history):
                if f"شماره {fa(h['report_no'])} ({h['report_type']})" == del_idx:
                    st.session_state.history.pop(idx_h)
                    break
            st.rerun()

    st.markdown("##### سهم فصل‌های فهرست‌بها از بهای پایه")
    ch_df = pd.DataFrame([{"فصل": f"{fa(cst['chapter'])} {cst['title']}",
                           "بها (میلیارد تومان)": round(cst["total"] / 1e10, 3)}
                          for cst in result["chapter_sums"]])
    st.bar_chart(ch_df.set_index("فصل"), color="#f2b33d")


# ════════════════════════════════════════════════════════════════
# تب ۶ — گزارش‌گیری و خروجی Excel
# ════════════════════════════════════════════════════════════════

def render_tab_export():
    """تب خروجی: دانلود Excel شش‌برگه، JSON بایگانی و خلاصهٔ کیفیت."""
    st.markdown("### گزارش‌گیری و خروجی نهایی")
    result = compute_now()
    if not result or not result["lines"]:
        st.info("هنوز داده‌ای برای برون‌بری وجود ندارد.")
        return
    meta = st.session_state.meta
    s = st.session_state.settings
    cur = s["currency"]

    # فاز E-10 §۲ — قفلِ خروجیِ نهاییِ «تعدیل صورت‌وضعیت»: وقتی دورهٔ
    # کارکرد خالی است، خروجیِ نهاییِ Excel نباید ساخته شود؛ فقط
    # «پیش‌نویس» با واترمارکِ «پیش‌نویس – دورهٔ کارکرد وارد نشده».
    _tadil_out = (result.get("adjustment") or {}).get("tadil") or {}
    _wp_missing = bool(_tadil_out.get("work_period_missing"))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### کتاب‌کار Excel کامل (.xlsx)")
        st.caption("شش برگه راست‌به‌چپ با هدر رسمی، فرمول‌های جمع زنده و قالب‌بندی فارسی.")
        _draft_req = False
        if _wp_missing:
            st.error("دورهٔ کارکرد (دورهٔ انجامِ کار) وارد نشده است — "
                     "خروجیِ نهاییِ Excel ساخته نمی‌شود، چون موتورِ تعدیل "
                     "تمامِ کارکرد را به آخرین شاخصِ قطعی منتسب می‌کند و "
                     "مبلغِ تعدیل با حالتِ «شاخصِ هر سه‌ماهه» متفاوت است. "
                     "«تاریخ شروع دورهٔ صورت‌وضعیت» و «تاریخ پایان دورهٔ "
                     "صورت‌وضعیت» را در تنظیماتِ پروژه وارد کنید.")
            _draft_req = st.checkbox(
                "در عوض، خروجیِ پیش‌نویس می‌خواهم (واترمارک «پیش‌نویس – "
                "دورهٔ کارکرد وارد نشده» روی همهٔ شیت‌ها و خلاصهٔ مالی)",
                key="te-wp-draft")
            _meta = ({**meta,
                      "report_type": "پیش‌نویس — %s" % (meta.get("report_type") or "موقت")}
                     if _draft_req else meta)
        else:
            _meta = meta
        try:
            data = ExcelExporter().export(_meta, result, s, st.session_state.history)
            stamp = datetime.now().strftime("%Y%m%d")
            st.download_button(
                "دانلود Excel صورت‌وضعیت%s" % (" — پیش‌نویس" if _draft_req else ""),
                data=data,
                file_name=f"SooratVaziat_Sh{convert_persian_digits(meta['report_no'] or '0')}_{stamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", use_container_width=True, key="te-download-xlsx",
            )
        except Exception as e:
            _logger.exception("خطای تولید Excel")
            st.error(f"خطا در تولید فایل Excel: {e}")
    with c2:
        st.markdown("##### پشتیبان داده (JSON) + چاپ")
        st.caption("کل خروجی پروژه برای آرشیو. برای نسخهٔ کاغذی، فایل Excel را چاپ کنید — "
                   "هدر و قالب‌بندی رسمی آماده است.")
        snapshot = {
            "meta": meta, "settings": dict(s), "history": st.session_state.history,
            "financial": {k: v for k, v in result.items() if k not in ("lines", "rebar", "records")},
            "lines": result["lines"], "rebar": result["rebar"],
            "exported_at": datetime.now().isoformat(),
        }
        st.download_button("دانلود JSON بایگانی",
                           data=json.dumps(snapshot, ensure_ascii=False, indent=1, default=str).encode("utf-8"),
                           file_name=f"MetreYar_{datetime.now().strftime('%Y%m%d')}.json",
                           mime="application/json", use_container_width=True, key="te-download-json")
        st.metric("مبلغ خالص قابل‌پرداخت", fmt_money(result["grand_total"], cur))

    st.markdown("---")
    q = result["quality"]
    st.markdown("##### گزارش کیفیت تطبیق")
    c = st.columns(4)
    c[0].metric("جداول پردازش‌شده", fa(q["tables_parsed"]))
    c[1].metric("رکوردهای Mapping", fa(q["mapping_records"]))
    c[2].metric("تطبیق دقیق/مستقیم", fa(q["lines_exact"]))
    c[3].metric("بهای تخمینی باقی‌مانده", fa(q["lines_estimated"]))
    if q["lines_estimated"] == 0 and q["lines_review"] == 0:
        st.success("همهٔ ردیف‌ها با بهای رسمی/تأییدشده تطبیق داده شده‌اند؛ گزارش آمادهٔ ارائه به کارفرماست.")
    else:
        st.warning("برای نهایی‌سازی، ردیف‌های «تخمینی»/«نیازمند بررسی» را در تب مترهٔ ریز اصلاح یا "
                   "فایل رسمی فهرست‌بها را بارگذاری کنید.")

    # ── رجیستری مرکزی هشدارها (ایراد ۱۰) ──
    warns = result.get("warnings") or []
    status = result.get("status") or {}
    if warns or status:
        st.markdown("##### رجیستری هشدارها")
        c2 = st.columns(4)
        c2[0].metric("وضعیت پروژه",
                     "کامل ✔" if status.get("complete") else "ناقص")
        c2[1].metric("خطا", fa(status.get("errors", 0)))
        c2[2].metric("هشدار", fa(status.get("warnings_n", 0)))
        c2[3].metric("اطلاع", fa(status.get("info", 0)))
        _LVL_ICON = {"خطا": "⛔", "هشدار": "⚠️", "اطلاع": "ℹ️"}
        shown = 0
        for w in warns:
            icon = _LVL_ICON.get(w["level"], "•")
            msg = (f"{icon} **[{w['level']}] {w['category']}** — "
                   f"{w.get('item') or '—'}: {w['message']}")
            if w["level"] == "خطا":
                st.error(msg)
            elif w["level"] == "هشدار":
                st.warning(msg)
            else:
                st.info(msg)
            shown += 1
            if shown >= 12:
                st.caption(f"… و {fa(len(warns) - shown)} هشدار دیگر (در خروجی Excel، شیت «هشدارها»).")
                break


# ════════════════════════════════════════════════════════════════
# تابع اصلی برنامه
# ════════════════════════════════════════════════════════════════

def main():
    """نقطهٔ ورود اصلی برنامه: مقداردهی، سایدبار و شش تب اصلی."""
    init_session_state()
    # ── فاز E-۵: snapshot از ورودی‌های پروژه پیش از رندر ──
    _snap_s = _audit_snap(st.session_state.settings)
    _snap_m = _audit_snap(st.session_state.meta)
    render_sidebar()

    st.title("🏗️ متره‌یار — سامانهٔ جامع دفتر فنی هوشمند")
    st.caption(f"نسخهٔ {APP_VERSION} · Revit/Dynamo → فهرست‌بهای ابنیه ۱۴۰۴ → صورت‌وضعیت رسمی")

    # فاز E-10.1 §۳ — بنرِ حالتِ نمایشی روی همهٔ تب‌ها (یاترمارکِ Excel
    # در ExcelExporter می‌نشیند؛ این برای خودِ UI است).
    if st.session_state.settings.get("demo_mode"):
        st.warning(DEMO_BANNER, icon="🎭")

    tabs = st.tabs([
        "📊 داشبورد",
        "🔗 نگاشت داینامو",
        "📚 فهرست‌بها ۱۴۰۴",
        "📐 مترهٔ ریز",
        "💲 قیمت‌های دستی",
        "📝 صورت‌وضعیت",
        "📤 خروجی",
    ])

    with tabs[0]:
        render_tab_upload()
    with tabs[1]:
        render_tab_mapping()
    with tabs[2]:
        render_tab_fehrest()
    with tabs[3]:
        render_tab_metre()
    with tabs[4]:
        render_tab_manual_prices()
    with tabs[5]:
        render_tab_statement()
    with tabs[6]:
        render_tab_export()

    # ── فاز E-۵: ثبت تغییراتِ ورودی‌های پروژه در سابقهٔ ویرایش ──
    _audit_diff_apply(st.session_state.settings, _snap_s, "setting",
                      SETTING_LABELS, "تنظیمات پروژه",
                      st.session_state.settings)
    _audit_diff_apply(st.session_state.meta, _snap_m, "meta",
                      META_LABELS, "مشخصات پیمان",
                      st.session_state.settings)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # لایهٔ آخر مدیریت خطا با پیام فارسی
        _logger.exception("خطای بحرانی برنامه")
        st.error(f"خطای غیرمنتظره در اجرای برنامه: {e}")
        st.info("لطفاً فایل‌های ورودی و تنظیمات را بررسی کنید و دوباره تلاش نمایید.")



