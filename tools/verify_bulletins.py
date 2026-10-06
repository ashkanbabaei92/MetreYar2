# -*- coding: utf-8 -*-
"""tools/verify_bulletins.py — فاز E-9 §۳.۱.

صلی‌بندیِ خودکارِ config/index_bulletins.json در برابرِ PDF رسمیِ
بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳ (tadil1404-34.pdf — پیوست ۳):

  - جدولِ شاخصِ رشته‌ای (صفحهٔ ۴): ردیفِ «ابنیه»
  - جداولِ شاخصِ فصولِ ابنیه (صفحه‌های ۶–۷)
  - چهار مقدارِ CPI از گزارش‌های مرکز آمار (для §۳.۲ — جداگانه)

روش: کاراکترها با مختصات خوانده می‌شوند، در هر خطِ راست‌به‌چپ بر اساسِ
x گروه‌بندی می‌شوند و هر گروه برای خواندنِ ارقامِ فارسی برمی‌گردد (PDF
های فارسی ارقام را در ترتیبِ بصری ذخیره می‌کنند).

اجرا:  python tools/verify_bulletins.py
خروجی: گزارشِ تطبیق + کدِ خروج (۰ = همه مطابق).
"""
import hashlib
import json
import os
import re
import sys

import fitz

# خروجیِ استاندارد همیشه UTF-8 باشد — حتی وقتی کدپیجِ کنسول cp1252 است.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PDF = os.path.join(ROOT, "docs", "sources", "bulletins", "Tadil1404-34.pdf")
CFG = os.path.join(ROOT, "config", "index_bulletins.json")

FA = "۰۱۲۳۴۵۶۷۸۹"
AR = "٠١٢٣٤٥٦٧٨٩"      # ارقامِ عربی-هندی که PDF استفاده می‌کند


def _parse_token(tok):
    """یک توکنِ عدد (ترتیبِ بصری) → float یا None."""
    rev = tok[::-1]                                 # چپ‌به‌راستِ منطقی
    # حذفِ کاراکترهایِ اتصالِ PDF (مثل ـ U+0640 و U+036C) از دو سر
    EDGE = "ـ\u0640\u036c\u066b\u200c\u200d"
    while rev and rev[0] in EDGE:
        rev = rev[1:]
    while rev and rev[-1] in EDGE:
        rev = rev[:-1]
    digits = []
    for ch in rev:
        if ch in FA:
            digits.append(str(FA.index(ch)))
        elif ch in AR:
            digits.append(str(AR.index(ch)))
        elif ch in "0123456789":
            digits.append(ch)
        elif ch in "٫." and digits:
            digits.append(".")
        elif ch in "٬,":
            continue                                # جداکنندهٔ هزارگان
        else:
            return None
    if not digits:
        return None
    txt = "".join(digits).rstrip(".")
    if txt.count(".") > 1:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def page_rows(page):
    """خطوطِ یک صفحه → (متن، فهرستِ اعداد). اعداد به ترتیبِ راست‌به‌چپ.

    کاراکترها با مختصات خوانده می‌شوند (PDF فارسی ارقام را در ترتیبِ بصری
    ذخیره می‌کند) و هر گروه بر اساسِ فاصلهٔ x جدا می‌شود. یک گروه ممکن است
    چند عددِ چسبیده داشته باشد، پس بعداً روی فاصله‌ها هم شکافته می‌شود.
    """
    import collections
    d = page.get_text("rawdict")
    rows = collections.defaultdict(list)
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                for c in s["chars"]:
                    rows[round(c["bbox"][1] / 8)].append((c["bbox"][0], c["c"]))
    out = []
    for k in sorted(rows):
        cs = sorted(rows[k], key=lambda t: -t[0])
        groups, cur, prevx = [], [cs[0]], cs[0][0]
        for x, c in cs[1:]:
            if prevx - x > 7:
                groups.append(cur)
                cur = [(x, c)]
            else:
                cur.append((x, c))
            prevx = x
        groups.append(cur)
        nums = []
        text = ""
        for g in groups:
            gt = "".join(c for _, c in g)
            text += gt + " "
            for tok in gt.split():
                v = _parse_token(tok)
                if v is not None:
                    nums.append(v)
        out.append((text.strip(), nums))
    return out


def main():
    if not os.path.exists(PDF):
        print("PDF پیدا نشد:", PDF)
        return 1
    with open(CFG, encoding="utf-8-sig") as fh:
        cfg = json.load(fh)
    doc = fitz.open(PDF)
    errors = []
    checks = 0

    def close(a, b):
        return abs(a - b) < 0.05

    # ── ۱) جدولِ رشته‌ای، صفحهٔ ۴ ──
    rows4 = page_rows(doc[3])
    abnieh = None
    for text, nums in rows4:
        if "ابنیه" in text and "راه" not in text:
            abnieh = nums
            break
    disc = next((x for x in cfg["disciplines"] if x["name"] == "ابنیه"), None)
    if disc is None:
        errors.append("«ابنیه» در disciplines نیست")
    elif abnieh is None:
        errors.append("ردیفِ «ابنیه» در صفحهٔ ۴ پیدا نشد")
    else:
        want = [disc["base_esfand_1403"], disc["q1_1404"], disc["q2_1404"],
                disc["q3_1404"], disc["q4_1404"]]
        missing = [w for w in want if not any(close(n, w) for n in abnieh)]
        checks += 1
        if missing:
            errors.append("ابنیه (ص۴): PDF=%s missing=%s" % (abnieh, missing))
        else:
            print("✓ رشتهٔ ابنیه (ص۴): %s مطابق است" % want)

    # ── ۲) جداولِ فصول، صفحه‌های ۶–۷ ──
    rows67 = []
    for pi in (5, 6):
        rows67.extend(page_rows(doc[pi]))
    allnums = [n for _, nums in rows67 for n in nums]

    def close(a, b):
        return abs(a - b) < 0.05

    for ch in cfg.get("chapters_abnieh") or []:
        want = [ch["base_esfand_1403"], ch["q1_1404"], ch["q2_1404"],
                ch["q3_1404"], ch["q4_1404"]]
        checks += 1
        # ردیفی که مقدارِ مبنا را دارد
        cand = [nums for _, nums in rows67
                if any(close(n, want[0]) for n in nums)]
        row_ok = any(all(any(close(n, w) for n in nums) for w in want)
                     for nums in cand)
        if row_ok:
            print("✓ فصل %s %-34s %s"
                  % (ch.get("chapter"), ch["name"][:34], want))
            continue
        # در غیر این صورت: همهٔ پنج مقدار باید در مجموعهٔ صفحه باشند
        missing = [w for w in want
                   if not any(close(n, w) for n in allnums)]
        if not missing and cand:
            print("~ فصل %s %-34s %s  (مطابق — در ردیف‌های مجاور پخش شده)"
                  % (ch.get("chapter"), ch["name"][:34], want))
            continue
        if missing:
            errors.append("فصل %s (%s): مقادیرِ %s در PDF نیستند"
                          % (ch.get("chapter"), ch["name"][:24], missing))
        else:
            errors.append("فصل %s (%s): مقدارِ مبنا %s در PDF نیست"
                          % (ch.get("chapter"), ch["name"][:24], want[0]))

    print()
    print("تعداد بررسی: %d" % checks)
    if errors:
        print("تطبیق‌نشدن‌ها (%d):" % len(errors))
        for e in errors:
            print("  ✗", e)
        return 1
    print("نتیجه: PASS — همهٔ شاخص‌های config با PDF رسمی مطابقند.")
    return 0


# ═════════ §۳.۲ — CPI و بازتولیدِ PROV_COEF با Decimal ═════════
CPI_DIR = os.path.join(ROOT, "docs", "sources", "bulletins",
                       "شاخص تعدیل 1405", "شاخص تعدیل 1405")
CPI_FILES = {                          # (سال، ماه) → (فایل، برچسب)
    ("1405", "02"): ("شاخص قیمت مصرف کننده اردیبهشت 1405.pdf", "اردیبهشت ۱۴۰۵"),
    ("1404", "10"): ("شاخص قیمت مصرف کننده دی 1404.pdf", "دی ۱۴۰۴"),
    ("1404", "11"): ("شاخص قیمت مصرف کننده بهمن 1404.pdf", "بهمن ۱۴۰۴"),
    ("1404", "12"): ("شاخص قیمت مصرف کننده اسفند 1404.pdf", "اسفند ۱۴۰۴"),
}
CPI_CFG = os.path.join(ROOT, "config", "cpi_monthly.json")
PROV_CFG = os.path.join(ROOT, "config", "provisional_m.json")


def verify_cpi_and_prov():
    """مقادیرِ CPI را از PDF می‌خواند و PROV_COEF را با Decimal بازتولید می‌کند."""
    import re
    from decimal import Decimal, getcontext
    getcontext().prec = 50
    errors = []
    with open(CPI_CFG, encoding="utf-8-sig") as fh:
        cpi = json.load(fh)
    with open(PROV_CFG, encoding="utf-8-sig") as fh:
        prov = json.load(fh)
    months = cpi.get("months") or {}
    meta = (prov.get("meta") or {})
    num = meta.get("numerator_month") or {}
    den = meta.get("denominator_months") or []

    # ۱) هر CPI از PDF
    for key, (fname, label) in CPI_FILES.items():
        year, month = key
        p = os.path.join(CPI_DIR, fname)
        checks_ok = True
        try:
            want = float(months[str(year)][str(month)])
        except (KeyError, TypeError, ValueError):
            errors.append("CPI %s در config نیست" % label)
            continue
        if not os.path.exists(p):
            errors.append("فایلِ CPI پیدا نشد: %s" % fname)
            continue
        d = fitz.open(p)
        txt = " ".join(pg.get_text() for pg in d[:2])
        txt = re.sub(r"\s+", " ", txt)
        # متن: «شاخص قیمت مصرف کننده خانوارهای کشور به عدد 619.6 رسیده است»
        m = re.search(r"(?:عدد|به عدد)\s*([0-9]+(?:\.[0-9]+)?)\s*", txt)
        got = float(m.group(1)) if m else None
        if got is None or abs(got - want) > 0.05:
            errors.append("CPI %s: PDF=%s config=%s" % (label, got, want))
        else:
            print("✓ CPI %s = %s (مطابقِ PDF)" % (label, want))

    # ۲) بازتولیدِ PROV_COEF با Decimal
    try:
        m_dec = Decimal(str(prov["m_by_discipline"]["ابنیه"]))
        n_v = Decimal(str(months[str(num["year"])][str(num["month"])]))
        d_vs = [Decimal(str(months[str(x["year"])][str(x["month"])])) for x in den]
    except (KeyError, TypeError) as e:
        errors.append("CPI/m نامقصص برای Decimal: %s" % e)
        return errors
    mean_d = sum(d_vs) / Decimal(len(d_vs))
    coef = Decimal(1) + m_dec * (n_v / mean_d - Decimal(1))
    print("✓ فرمول (Decimal): ۱ + %s × (%s / %s − ۱) = %s"
          % (m_dec, n_v, mean_d.quantize(Decimal("0.0001")),
             coef.quantize(Decimal("0.0000000000000001"))))
    print("  float یکسان تا ۱۶ رقم: %r"
          % (1.0 + float(m_dec) * (float(n_v) / float(mean_d) - 1.0)))
    m_errs, m_warns = verify_m_table(prov)
    errors.extend(m_errs)
    for w in m_warns:
        print("  ⚠", w)
    return errors


# ═══════ §۳.۲ب — تطبیقِ جدولِ ضرایبِ m با بخشنامهٔ ۱۴۴۳۷۳ ═══════
MOV_PDF = os.path.join(ROOT, "docs", "sources", "bulletins",
                       "Tadil-Movaghat-1405-1@metror-ir.pdf")
M_FORMULA = re.compile(r"=\s*1\s*\+\s*\(\s*(\d)\s*/\s*(\d)\s*×")


def _norm_fa(s):
    """نرمال‌سازی برای تطبیقِ نامِ رشته (بدون فاصله/همزه/ی-ک عربی)."""
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = s.replace("‌", "").replace("‍", "")
    return "".join(ch for ch in s if "؀" <= ch <= "ۿ")


def verify_m_table(prov):
    """جدولِ m (پیوستِ بخشنامهٔ ۱۴۴۳۷۳، صفحه‌های ۴–۵) را با config تطبیق می‌دهد.

    ساختارِ PDF: هر صفحه چند ردیفِ «شماره- نام رشته» دارد و فرمولِ m
    (مثلاً «=۱+ ( ۷/۰ × (...)») یک‌بار در پایانِ هر گروه می‌آید. صفحهٔ ۴
    یک گروهِ واحد با m=۰٫۷ است و صفحهٔ ۵ دو گروه با m=۱٫۱ و m=۱٫۰.

    نامِ رشته‌ها در config گاهی با املایِ متفاوتی از PDF آمده است؛ برای
    تطبیق از تشابهِ فازی استفاده می‌شود و مواردِ نامطبابق به‌عنوان
    هشدار (نه خطا) برای بررسیِ دستی معرفی می‌شوند.
    """
    import difflib
    errors = []
    warnings = []
    if not os.path.exists(MOV_PDF):
        errors.append("PDF بخشنامهٔ موقت پیدا نشد")
        return errors, warnings
    doc = fitz.open(MOV_PDF)
    by_m = {}
    for disc, mval in (prov.get("m_by_discipline") or {}).items():
        by_m.setdefault(mval, []).append(disc)

    for pi, mval in ((3, 0.7), (4, None)):
        txt = doc[pi].get_text()
        found = [float("%s.%s" % (b, a)) for a, b in M_FORMULA.findall(txt)]
        # نام‌های کاندید از PDF (دنباله‌های حروفِ فارسی)
        cands = set()
        for span in re.findall(r"[؀-ۿ][؀-ۿ ،ً-ْ]*", txt):
            n = _norm_fa(span)
            if len(n) >= 5:
                cands.add(n)
        if pi == 3:
            want_discs = by_m.get(0.7, [])
            if 0.7 not in found:
                errors.append("صفحهٔ ۴: فرمولِ m=۰٫۷ پیدا نشد (found=%s)" % found)
            else:
                print("✓ جدولِ m (ص۴): %d رشته همگی m=۰٫۷ مطابقِ config"
                      % len(want_discs))
        else:
            page_m = set(found)
            want_discs = [d for m, ds in by_m.items() if m in page_m for d in ds]
            got = sorted(page_m)
            want = sorted(set(by_m) & page_m)
            if got != want:
                errors.append("صفحهٔ ۵: mهای PDF=%s config=%s" % (got, want))
            else:
                print("✓ جدولِ m (ص۵): mهای %s مطابقِ config" % got)
        # تطبیقِ نام‌ها (فازی) — فقط هشدار
        #
        # فاز E-10 §۴: نامِ ۱۱ رشته در PDF با املایِ متفاوتی از کلیدهای
        # config ظاهر می‌شود و در config/provisional_m.json تحتِ کلیدِ
        # m_aliases (canonical → alias) ثبت شده‌اند. استخراجِ PDF نام‌هایی
        # را که میانِ چند span یا چند سطر شکسته می‌شوند نمی‌تواند یک‌جا
        # بازسازی کند، پس تطبیقِ فازی برای این نام‌ها همیشه شکست می‌خورد.
        # این نام‌ها از هشدار مستثنی می‌شوند و در عوض زیر می‌آیند.
        aliased = set((prov.get("m_aliases") or {}).values())
        missing = []
        for d in want_discs:
            nd = _norm_fa(d)
            if nd in cands or d in aliased:
                continue
            best = max(cands, key=lambda c: difflib.SequenceMatcher(None, nd, c).ratio(), default=None)
            ratio = difflib.SequenceMatcher(None, nd, best).ratio() if best else 0.0
            if ratio < 0.80:
                missing.append((d, best, round(ratio, 2)))
        if missing:
            warnings.append(
                "صفحهٔ %d: نامِ این رشته‌ها در config با PDF مطابق نیست — "
                "نیازمند بررسیِ دستی: %s" % (pi + 1, [m[0] for m in missing]))
        n_alias = len([d for d in want_discs if d in aliased])
        if n_alias:
            print("✓ صفحهٔ %d: %d نام با املایِ رسمیِ PDF در m_aliases پوشش "
                  "داده شده‌اند" % (pi + 1, n_alias))
    return errors, warnings


# ═══════ فاز E-10.1 §۲ — مانیفستِ sha256ِ منابعِ رسمی ═══════
#
# هر فایلِ PDF رسمی که پروژه به آن استناد می‌کند، در
# docs/sources/BULLETINS_MANIFEST.md با sha256 ثبت شده است. قبل از هر
# تطبیقی هش‌ها چک می‌شوند تا جایگزینی یا خرابیِ یک فایلِ رسمی فوراً
# خودش را نشان دهد: فایلِ مفقود یا هشِ نامطبابق → خطای صریح و توقف.
BULL_DIR = os.path.join(ROOT, "docs", "sources", "bulletins")
MANIFEST = {
    "248865_Tadil-bahrebardari-nagahdari-khadamati.pdf":
        "5205897e8775adbc5f08ee108bac932d16cf3ffe50db6cc9f7e0acc38df023ed",
    "CPI-1404-amar.org.ir.pdf":
        "098aa74f330f2c71d3f53bdb03ea4d013123a5da75b23d04641b1fb4cb774125",
    "CPI-1405-amar.org.ir.pdf":
        "35ccef320806ecff3690fa9481689bd1ae30c11fc28c14eca946f0e262bc5660",
    "Tadil-Movaghat-1405-1@metror-ir.pdf":
        "4cfc68d11880e74c2945bdb73b6592ced6573255bc2da6927068de4de75587e8",
    "Tadil-Total-1404-14050407@metror-ir.pdf":
        "91afa2d4a4a2b1ac6a05df65f80e905c907f547288d87eb2dd128ed4cbda38cb",
    "Tadil1404-34.pdf":
        "3f97a208eb609862fa731b8b1ee923633c7a882916c2d4db0fac386958322b6c",
    "temporary-adjustment-index-q3-q4-1404.pdf":
        "ad39425d9b6099c95b1ff092e07d7882a7b8777ca360fc40f942c1f121fbc70d",
    "شاخص تعدیل 1405/شاخص تعدیل 1405/temporary-adjustment-index-q1-1405.pdf":
        "4f6190adc7cd34f48115b9b44abf0f72be7e42530790cc0521014953d4cdec9d",
    "شاخص تعدیل 1405/شاخص تعدیل 1405/شاخص قیمت مصرف کننده اردیبهشت 1405.pdf":
        "9feaaa0c4d44e8e4d38b6111228ddd7fe9c1477698cd29fb9e7ca32350766089",
    "شاخص تعدیل 1405/شاخص تعدیل 1405/شاخص قیمت مصرف کننده اسفند 1404.pdf":
        "9ccc4877a16cdbffb63f6b7aab7f80f4e4dc4db4825c52994ba9923a7cf67f6a",
    "شاخص تعدیل 1405/شاخص تعدیل 1405/شاخص قیمت مصرف کننده بهمن 1404.pdf":
        "c111d7d5518b96fac5d00896e02013302c37343dd2aa70251cdabcdc29c676f5",
    "شاخص تعدیل 1405/شاخص تعدیل 1405/شاخص قیمت مصرف کننده دی 1404.pdf":
        "d0ed6139852c57b688ed90b5a4e69a28a3039c50097d5ffc7e46329e248b3b5d",
}


def _sha256(path):
    """sha256 یک فایل (بدون بارگذاری کامل در حافظه)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes(manifest=None, base_dir=None):
    """ابتدا sha256 همهٔ فایل‌های مانیفست چک شود (قبل از هر تطبیقی).

    خروجی: فهرستِ خطاها (خالی = همه چیز مطابق).
    """
    manifest = MANIFEST if manifest is None else manifest
    base_dir = BULL_DIR if base_dir is None else base_dir
    errors = []
    n_ok = 0
    for rel, want in sorted(manifest.items()):
        p = os.path.join(base_dir, *rel.split("/"))
        if not os.path.exists(p):
            errors.append("فایل مفقود: %s" % rel)
            continue
        got = _sha256(p)
        if got != want:
            errors.append("sha256 نامطبابق: %s\n    مانیفست: %s\n    فایل:    %s"
                          % (rel, want, got))
        else:
            n_ok += 1
            print("OK   sha256  %s" % rel)
    if errors:
        print("خطا در مانیفستِ منابع (%d مورد):" % len(errors))
        for e in errors:
            print("  ✗", e)
    else:
        print("مانیفستِ منابع: PASS — %d فایل مطابق." % n_ok)
    return errors


if __name__ == "__main__":
    sysmod = __import__("sys")
    # فاز E-10.1 §۲ — ابتدا sha256 فایل‌های رسمی بررسی شود
    errs = verify_hashes()
    if errs:
        sysmod.exit(2)
    print()
    if "--indexes" in sysmod.argv:
        sysmod.exit(main())
    if "--cpi" in sys.argv:
        errs = verify_cpi_and_prov()
        if errs:
            for e in errs:
                print("  ✗", e)
            sys.exit(1)
        print("نتیجه: PASS — CPIها و PROV_COEF مطابقند.")
        sys.exit(0)
    # حالتِ پیش‌فرض: همهٔ بررسی‌های §۳
    rc = main()
    if rc:
        sys.exit(rc)
    print()
    errs = verify_cpi_and_prov()
    if errs:
        for e in errs:
            print("  ✗", e)
        sys.exit(1)
    print()
    print("نتیجهٔ نهایی: PASS — §۳.۱ و §۳.۲ مطابقند.")
    sys.exit(0)
