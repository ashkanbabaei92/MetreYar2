# متره‌یار ۳.۰ — دفتر فنی خودکار پروژه‌های ساختمانی ایران

<!-- default-label: [REF] -->


[فارسی](#فارسی) · [English](#english)

---

## فارسی

ترجمهٔ خروجی **Revit/Dynamo** به **صورت‌وضعیت رسمی** بر مبنای
**فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه ۱۴۰۴** سازمان برنامه و بودجه — همراه با
موتورهای **تعدیل پیمان** و **برآورد به‌هنگام** بر اساس بخشنامه‌های جاری.

> **وضعیت: `v1.0-rc1` — فریز (۱۴۰۵/۰۷/۱۴).** همهٔ تصمیماتِ طراحی با
> استناد به متنِ بخشنامه بسته شده‌اند. **تا رسیدنِ دادهٔ واقعی هیچ
> قابلیتِ جدیدی اضافه نمی‌شود** → `docs/NEXT_STEPS.md`.

### مسئله

 متره‌یاریِ دستی از خروجی‌های Revit کند، مستعد خطا و غیرقابل‌ردیابی است.
رنگ کردن صورت‌وضعیت نیازمند محاسبهٔ تعدیلِ قیمت بر اساس بخشنامه‌های
متعدد است که موتوری برای آن‌ها وجود داشت. متره‌یار ۳.۰ این زنجیره را
خودکار می‌کند: از جدول‌های Revit تا فایل Excel آمادهٔ امضا.

### دامنه — چه بخشنامه‌هایی پوشش داده می‌شود

| سند | موضوع | وضعیت |
|---|---|---|
| **بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰** (۱۳۷۰/۰۶/۲۳) | دستورالعمل تعدیل واحدهای پایهٔ پیمان | ✅ موتورِ کامل «تعدیل پیمان» + ماتریس تطابق ۴۳ بند |
| **بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳** (پیوست ۳) | شاخص‌های قطعیِ فصولِ ابنیه ۱۴۰۴Q1–Q2 | ✅ در `config/index_bulletins.json` |
| **بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳** | ضریب موقت ۱۴۰۵Q1 (CPI + m) | ✅ محاسبهٔ خودکار از `config/cpi_monthly.json` |
| **بخشنامهٔ ۹۴/۶۹۴۱۶** (صفحه ۸۲) | ضریب منطقه‌ای (۱٫۰۴ گرگان) | ✅ در `config/regional_coefficients.json` |

**خارج از دامنه (عمدی):** بندهای **۵-۲** (روش خاصِ مصوبِ سازمان — نیازمند
تصویب شورای عالی فنی)، **۵-۳** (پیمان با بخش ارزی — نیازمند همان روش مصوب)،
**نامه-۲ تا نامه-۵** (تصمیمات اداری/حقوقی دستگاه اجرایی). بندهای **۲-۳**
(شاخص کلیِ مستقل) و **۲-۴** (مصالح پای‌کار) کد دارند ولی **منتظر داده‌اند** —
تا رسیدنِ داده هیچ عددی حدس زده نمی‌شود (قاعدهٔ طلایی).

### معماری

```
                     ┌────────────────────────────────────────────┐
   data/export revit │  ۱۰ جدول Schedule (بتن/قالب/آرماتور/تیرچه)  │
   (خروجی Revit)     └───────────────┬────────────────────────────┘
                                     │  RevitScheduleParser
                                     ▼
                     ┌────────────────────────────────────────────┐
   data/dynamo       │  نگاشت کد فهرست‌بها (Dynamo mapping v2)      │
                                     └───────────────┬────────────┘
                                     │  DynamoMappingParser
                                     ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                    موتور تطبیق فازی + فیزیکی                     │
   │   (Token-Set Ratio + امتیاز اشتراک عددی: عیار/قطر/ابعاد)          │
   └─────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                      کمیت‌ها + فهرست‌بهای ۱۴۰۴                    │
   │            (data/fehrest baha 1404 — بهای رسمی، قابل‌جایگزینی)     │
   └─────────────────────────────────────────────────────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
   ┌──────────────────────────┐   ┌──────────────────────────────────┐
   │  زنجیرهٔ مالی             │   │  موتور تعدیل پیمان (بخشنامه ۲۰۸۰) │
   │  base → ضرایب → کسورات   │   │  ΔP = k×Σ(It/Io−1)×A              │
   └──────────────────────────┘   │  + موتور برآورد به‌هنگام (مستقل)   │
                                  └──────────────────────────────────┘
                                     │
                                     ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  Excel ۱۹ شیت (xlsxwriter، RTL، هدر رسمی) + JSON + گزارش‌های UI  │
   └─────────────────────────────────────────────────────────────────┘
```

دو پیاده‌سازی **کاملاً موازی و همیشه برابر**:

- **Python** — `app.py` (تک‌فایل Streamlit) — نسخهٔ کامل + UI
- **TypeScript** — `src/lib/` — همان موتورها برای وب (React/Vite)

### اجرا (۲ دستور)

```bash
pip install streamlit pandas openpyxl xlsxwriter
streamlit run app.py
# گام ۲: فایل فهرست‌بها (اختیاری)  →  گام ۳: جداول Revit + نگاشت Dynamo
# گام ۴: تنظیمات  →  گام ۵: تأیید تطبیق  →  گام ۶: گزارش و دانلود Excel
```

اجرا با پروژهٔ نمونه: دکمهٔ «آزمایش با پروژهٔ نمونه (دمو)» در داشبورد، یا
`examples/sample_project/` برای پروفایل + Excelِ ازپیش‌تولیدشده.

### کیفیت

- **۸۹۴ تست Python + ۸۴۳ تست TypeScript** — موتورها bit-identical (آزمون T112).
- نسخهٔ **v1.0-rc1** فریز شده؛ گیتِ کاملِ `run_all_tests.ps1` سبز است.
- **۴۳ بند بخشنامه ۲۰۸۰:** ۳۲ پیاده‌شده + آزمون‌شده، ۲ ناقص (داده)، ۱ نبودِ
  داده، ۷ خارج از دامنه (با دلیل).
- **۱۲ تصمیمِ باز + ۱ دادهٔ ورودیِ الزامی (D-01)** که در آن‌ها بخشنامه صریح نیست → `docs/PENDING_DECISIONS.md`
  (هرکدام با اثر عددیِ دقیق روی پروژهٔ مرجع).
- هر عدد قابل‌ردیابی است: شاخص‌ها ← صفحهٔ PDF، ضرایب ← شمارهٔ بند.
- اجرای تست‌ها: `.\run_all_tests.ps1` (کامل، ~۳۵ دقیقه) یا
  `.\run_fast_tests.ps1` (سریع، ~۲٫۳ دقیقه).
### فرضیات و تصمیم‌های باز

- **k = ۰٫۹۵** (بند ۱-۸) با تبدیل به ۱ در اتمامِ مدت (تبصرهٔ ۲ + بند ۸-۴).
- شاخص موقت ۱۴۰۵Q1 از CPI مرکز آمار + m=۰٫۷ محاسبه می‌شود.
- ۱۲ تصمیمِ باز + ۱ دادهٔ ورودیِ الزامی (D-01 — فاز E-9 §۴) → `docs/PENDING_DECISIONS.md`؛ ۶ گزینهٔ ب دیگر با **نقلِ مستقیمِ متنِ بخشنامه** رد شده‌اند (E-10 §۳) و D-11 در D-13 ادغام شده است.
  (+ `docs/DECISION_SHEET.md` برگهٔ تصمیم برای مشاور).
- شاخص کلیِ مستقل (بند ۲-۳ → D-19) و مصالح پای‌کار (بند ۲-۴ → D-20) منتظر داده‌اند.

### اسناد

- `ACCEPTANCE.md` — چک‌لیست تحویل: ماتریس بندها، اعداد مرجع، ریشه‌یابی‌ها
- `docs/PENDING_DECISIONS.md` — ۱۹ تصمیمِ باز + ۱ دادهٔ ورودیِ الزامی + ۱۸ ایراد + سه تصمیم دارای اثر عددی
- `docs/DECISION_SHEET.md` — برگهٔ تصمیم (فارسیِ ساده، مرتب بر اساسِ اثرِ ریالی) + نسخهٔ Word
- `docs/DATA_REQUEST.md` — اسناد و داده‌های موردنیاز از شرکت برای بستنِ تصمیمات و اعتبارسنجی
- `docs/DECISION_MEETING.md` (+ `.docx`) — بستهٔ جلسهٔ تصمیم: ۵ تصمیمِ اول، تحلیل حساسیتِ سه سناریو، نمودارِ tornado
- `docs/REFERENCE_NUMBERS.md` — اعدادِ مرجعِ پروژه با جدولِ نسخه‌دار
- `docs/NEXT_STEPS.md` — گام‌های بعد از فریزِ v1.0-rc1 (منتظر دادهٔ واقعی)
- `ARCHITECTURE.md` — معماری، schema تنظیمات، جریان‌های قرارداد
- `docs/test_parity.md` — حسابرسی تست‌های py در برابر ts
- `docs/sources/2080_summary.md` — متن وفادار بخشنامهٔ ۲۰۸۰
- `templates/reference_statement_template.xlsx` — قالبِ صورت‌وضعیتِ مرجع برای پر کردن
- `CHANGELOG.md` — تاریخچهٔ نسخه‌ها

---

## English

**MetreYar 3.0** — an automated technical-office pipeline that turns
Revit/Dynamo exports into official Iranian construction payment certificates
(صورت‌وضعیت) priced against the **1404 national standard work-item price list**
(فهرست‌بهای واحد پایه), with full contract price-adjustment engines.

**Problem:** manual quantity-takeoff from Revit schedules is slow,
error-prone and unauditable. Price adjustment requires applying several
circular government bulletins for which no engine existed.

**Scope — bulletins implemented:**

| Bulletin | Topic | Status |
|---|---|---|
| 1-9706/54/2080 (1370) | Base-price adjustment rules | ✅ full engine + 43-clause compliance matrix |
| 1405/155233 (Annex 3) | Definitive 1404Q1–Q2 chapter indices | ✅ `config/index_bulletins.json` |
| 1405/144373 | Provisional 1405Q1 coefficient (CPI + m) | ✅ computed from `config/cpi_monthly.json` |
| 94/69416 (p. 82) | Regional coefficient (1.04 Gorgan) | ✅ `config/regional_coefficients.json` |

**Deliberately out of scope:** clauses 5-2 (organisation-approved special
method — requires High Technical Council approval), 5-3 (foreign-currency
contracts — same), and letter clauses 2–5 (administrative/legal employer
decisions). Clauses 2-3 (independent general index) and 2-4 (site materials)
are coded but **await external data** — no number is ever guessed.

**Architecture:** two parallel, permanently-equal implementations —
`app.py` (Python/Streamlit) and `src/lib/` (TypeScript/Vite). Revit
schedules + Dynamo mappings are parsed, quantities are matched to the 1404
price list by a fuzzy+physical matcher, then two independent engines
compute contract adjustment (ΔP) and updated estimate (A_new). Output is a
19-sheet RTL Excel workbook plus JSON.

**Run:**

```bash
pip install streamlit pandas openpyxl xlsxwriter
streamlit run app.py
```

A ready-made anonymous sample project (profile + generated Excel) is in
`examples/sample_project/` — its amounts are scaled by a fixed 0.8 factor for
anonymization, so validate it with
`python tools/validate_against_reference.py --xlsx examples/sample_project/sample_output.xlsx --scale 0.8`.

**Quality:** 780 Python + 742 TypeScript tests; engines are bit-identical
(test T112); every reference number is traceable to a PDF page or clause
number; 18 interpretations where the bulletin is not explicit are documented
with exact numeric effects in `docs/PENDING_DECISIONS.md`.
