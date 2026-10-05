// ─────────────────────────────────────────────────────────────
// برون‌بری گزارش‌ها: کتاب‌کار Excel چندبرگه با هدر رسمی صورت‌وضعیت
// شامل مشخصات پروژه، شماره و تاریخ دورهٔ صورت‌وضعیت، زنجیرهٔ
// ضرایب/کسورات و برگهٔ سوابق تجمعی صورت‌وضعیت‌ها
// ─────────────────────────────────────────────────────────────
import * as XLSX from "xlsx";
import type { ProjectMeta, ProjectResult, ProjectSettings, StatusReportRecord } from "./types";
import { chapterTitle } from "../data/fehrest";
import { moneyToWords } from "./farsi";
import { neumaier } from "./engine";
import {
  indexValue,
  periodLabel,
  ioLabel,
  quarterLabel,
  quarterIsProvisional,
  splitRounded,
  PENDING_INTERPRETATIONS,
} from "./adjustment";
import { faDigits } from "./normalize";
import { validateMeta, jalaliToISO } from "./adjustment";
import INDEX_BULLETINS from "../../config/index_bulletins.json";
import { AUDIT_KIND_LABELS, MANUAL_STATUSES } from "./types";
import type { ManualPriceRecord } from "./types";
import { jalaliNowStr } from "./farsi";
import { faFloat } from "./floors";
import {
  MANUAL_ENTRIES_VERSION,
  MPX_AUDIT_SHEET,
  MPX_SECTION_CODES,
  MPX_SECTION_EXCLUDED,
  MPX_SECTION_PRICES,
  MPX_SECTION_STARRED,
  MPX_SHEET,
  MPX_VERSION_LABEL,
} from "./manualEntries";

// ── ارجاع بهای ردیف‌ها (ایراد ۲ و ۴ مرحلهٔ ۱۳) — هم‌سان با PRICE_REFS در
// app.py. شمارهٔ ردیف در شیت «Fehrest» فایل Excel فهرست‌بهای پایهٔ ابنیه
// ۱۴۰۴. وضعیت: استخراج‌شده — نیازمند تأیید کاربر. ──
const PRICE_REFS: Record<string, string> = {
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
};

// ── ترتیب رسمی ۱۹ برگهٔ گزارش (فاز D — درخواست کاربر). برگه‌های موتورهای
// فاز B (تعدیل پیمان / برآورد به‌هنگام / بخش قطعی) فقط هنگام روشن بودن
// موتور ساخته می‌شوند؛ بقیه همیشه present هستند. هم‌سان با SHEET_ORDER در
// app.py. ──
const SHEET_ORDER = [
  "خلاصه و وضعیت", "مشخصات پیمان", "متره ریز",
  "خلاصهٔ مالی و برآورد", "ضرایب", "ضریب طبقات",
  "لیستوفر آرماتور", "صورت وضعیت", "سوابق صورت وضعیت",
  "تعدیل پیمان", "برآورد به‌هنگام", "بخش قطعی و علی‌الحساب",
  "شاخص‌ها", "قیمت‌های دستی", "کیفیت تطبیق",
  "هشدارها", "مقادیر منتظر تأیید", "سابقهٔ ویرایش",
  "منابع و بخشنامه‌ها",
];

// شرح کوتاه هر برگه برای فهرست برگه‌ها در صفحهٔ اول (نام، شرح)
const SHEET_INDEX: [string, string][] = [
  ["خلاصه و وضعیت", "این صفحه — شمارش وضعیت قیمت‌ها، ضرایب و خلاصهٔ مالی"],
  ["مشخصات پیمان", "مشخصات پروژه، قرارداد، صورت‌وضعیت و ضرایب قراردادی"],
  ["متره ریز", "ردیف‌های متره: کمیت، بهای واحد و مبلغ هر ردیف"],
  ["خلاصهٔ مالی و برآورد", "زنجیرهٔ مالی کامل، کسورات قانونی و خالص پرداختی"],
  ["ضرایب", "همهٔ ضرایب با مقدار، وضعیت و منبع رسمی"],
  ["ضریب طبقات", "فرمول رسمی پیوست ۲ و جدول ترازهای طبقات"],
  ["لیستوفر آرماتور", "وزن میلگرد به تفکیک گروه سازه‌ای و قطر"],
  ["صورت وضعیت", "فهرست بهای پیمان به سبک MPX (قیمت و ضرایب)"],
  ["سوابق صورت وضعیت", "تاریخچهٔ صورت‌وضعیت‌های قبلی و کارکرد تجمعی"],
  ["تعدیل پیمان", "موتور تعدیل فصل‌به‌فصل (قاعدهٔ ضریب ۰٫۹۵)"],
  ["برآورد به‌هنگام", "موتور برآورد به‌هنگام (شاخص زنجیره‌ای)"],
  ["بخش قطعی و علی‌الحساب", "بخش‌بندی مبالغ قطعی و علی‌الحساب"],
  ["شاخص‌ها", "شاخص‌های رسمی تعدیل و ضریب هر فصل"],
  ["قیمت‌های دستی", "قیمت‌های دستی/موقت و وضعیت تأیید هر کدام"],
  ["کیفیت تطبیق", "تطابق کدهای کمیت با فهرست‌بهای ۱۴۰۴"],
  ["هشدارها", "رجیستری مرکزی هشدارها و خطاها"],
  ["مقادیر منتظر تأیید", "مقادیر نیازمند تأیید کاربر"],
  ["سابقهٔ ویرایش", "تاریخچهٔ ویرایش‌های کاربر (audit trail)"],
  ["منابع و بخشنامه‌ها", "منابع رسمی، وضعیت استخراج و محل استفاده"],
];

// توضیح هر وضعیت قیمت (همان برچسب‌های شیت «خلاصهٔ مالی و برآورد»)
const PRICE_STATUS_DESC: Record<string, string> = {
  "قطعی": "تطبیق دقیق با فهرست‌بهای ۱۴۰۴",
  "موقت": "شاخص/بهای موقت — نیازمند تأیید کاربر",
  "دستی": "قیمت واردشدهٔ دستی کاربر (ثبت در «سابقهٔ ویرایش»)",
  "پیش‌فرض اپ": "قیمت پیش‌فرض برنامه — قابل تغییر در تنظیمات",
  "نیازمند ورود": "بهای رسمی ندارد — خروجی «پیش‌نویس» می‌شود",
};

// منابع رسمی استفاده‌شده (قاعدهٔ طلایی ۲: هر مقدار قابل ردیابی)
const SOURCES: [string, string, string, string, string, string, string][] = [
  ["S1", "آمار رسمی", "شاخص‌های آماری هزینهٔ پروژه‌های عمرانی",
   "سازمان برنامه و بودجه — nezamfanni.ir", "—",
   "قطعی (رسمی)", "مبنای شاخص‌های دوره‌های گذشته"],
  ["S2", "بخشنامه", "شاخص‌های قطعی تعدیل آحادبها ۱۴۰۴ — پیوست ۳",
   "بخشنامه ۱۴۰۵/۱۵۵۲۳۳ (tadil1404-34.pdf)", "۱۴۰۵/۰۴/۰۲",
   "استخراج‌شده — نیازمند تأیید", "شیت «شاخص‌ها» و موتورهای تعدیل/برآورد"],
  ["S3", "بخشنامه", "ضریب موقت شاخص سه‌ماههٔ اول ۱۴۰۵",
   "بخشنامه ۱۴۴۳۷۳", "—",
   "تصویری (PDF) — فیلد دستی", "فیلد دستیِ شاخص موقت ۱۴۰۵Q1"],
  ["S4", "بخشنامه", "ضریب تبدیل مبنا (فهرست پایه → مبنا قرارداد)",
   "بخشنامه ۱۴۴۳۷۴", "—",
   "تصویری (PDF) — فیلد دستی", "فیلد دستیِ ضریب تبدیل مبنا"],
  ["S5", "بخشنامه", "ضریب منطقه‌ای کارهای ابنیه",
   "بخشنامه ۹۴/۶۹۴۱۶", "—",
   "استخراج‌شده — نیازمند تأیید", "شیت «ضرایب» — ضریب منطقه‌ای"],
  ["S6", "دستورالعمل", "دستورالعمل نحوهٔ محاسبهٔ پرداخت‌ها",
   "دستورالعمل ۱۰۱/۱۷۳۰۷۳", "—",
   "تصویری (PDF) — استخراج نشد",
   "مبنای A₀ — طبق قاعدهٔ طلایی ۳ حدس زده نمی‌شود"],
  ["S7", "بخشنامه", "قاعدهٔ ضریب k در تعدیل فصل‌به‌فصل (بند ۱-۸ و تبصرهٔ ۲)",
   "بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ — سازمان برنامه و بودجه", "۱۳۷۰/۰۶/۲۳",
   "تصویری (PDF) — فاز E-۶ (docs/sources/2080.pdf)",
   "موتور تعدیل پیمان (k = ۰٫۹۵ / ۱)"],
  ["S8", "بخشنامه", "فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه ۱۴۰۴",
   "بخشنامه ۵۰۹۵۰۴", "۱۴۰۴",
   "قطعی (رسمی)", "مبنای همهٔ قیمت‌های رسمی (شیت «متره ریز»)"],
  ["S9", "فهرست‌بها", "پیوست ۲ — تعاریف و فرمول ضریب طبقات",
   "فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴، پیوست ۲", "۱۴۰۴",
   "قطعی (رسمی)", "شیت «ضریب طبقات» — فرمول P"],
];

function sheetFromAoA(aoa: (string | number | Cell | Date)[][], widths: number[], merges?: XLSX.Range[]) {
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  (ws as any)["!cols"] = widths.map((wch) => ({ wch }));
  if (!(ws as any)["!views"]) (ws as any)["!views"] = [{}];
  (ws as any)["!views"][0].RTL = true;
  if (merges) (ws as any)["!merges"] = merges;
  return ws;
}

// قالب‌های عددی (پاریتی با _formats در app.py — xlsxwriter).
// SheetJS نسخهٔ community فقط قالب عدد (z) را پشتیبانی می‌کند؛
// استایل‌های فونت/رنگ/بک‌گراند نیاز به نسخهٔ Pro دارند (مستند شده، دور زده نمی‌شود).
const NUMF = {
  money: "#,##0",
  moneyNeg: "#,##0;[Red]-#,##0",
  num2: "#,##0.00",
};

type Cell = string | number | { t: "n"; v: number; f?: string; z?: string };

/** سلول پولی با قالب عددی و در صورت وجود فرمول زندهٔ Excel */
function moneyCell(v: number, formula?: string): Cell {
  return { t: "n", v: Math.round(v), f: formula,
           z: v < 0 ? NUMF.moneyNeg : NUMF.money };
}

/** سلول کمیت با دو رقم اعشار + قالب عددی.
 * مقدار خام نوشته می‌شود (مانند app.py)؛ قالب z نمایش را گرد می‌کند. */
function num2Cell(v: number, formula?: string): Cell {
  return { t: "n", v, f: formula, z: NUMF.num2 };
}

/** سلول عددی با n رقم اعشار + قالب عددی. */
function numCell(v: number, decimals: number): Cell {
  return { t: "n", v, z: `${decimals > 0 ? "#,##0." : "#,##0"}${"0".repeat(decimals)}` };
}

/** هدر رسمی مشترک تمام برگه‌ها */
function headerBlock(meta: ProjectMeta): (string | number)[][] {
  return [
    [`صورت وضعیت ${meta.reportType} شماره ${meta.reportNo} — پیمان شماره ${meta.contractNo || "—"}`],
    [`نام پروژه: ${meta.projectName || "—"}    کارفرما: ${meta.employer || "—"}    پیمانکار: ${meta.contractor || "—"}    مشاور: ${meta.consultant || "—"}`],
    [`دورهٔ صورت‌وضعیت: از ${meta.periodStart || "—"} تا ${meta.periodEnd || "—"}    محل اجرا: ${meta.location || "—"}    شروع پیمان: ${meta.contractDate || "—"}`],
    [`مبنای قیمت‌گذاری: فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه سال ۱۴۰۴ (سازمان برنامه و بودجه)    واحد پول: ریال`],
    [],
  ];
}

/** ساخت کتاب‌کار کامل گزارش پروژه */
export function exportWorkbook(
  meta0: ProjectMeta,
  result: ProjectResult,
  settings: ProjectSettings,
  history: StatusReportRecord[],
): void {
  const wb = XLSX.utils.book_new();

  // اگر ردیفی «نیازمند ورود» است، خروجی «پیش‌نویس» است (§۱۵-۴ بند ۶)
  const meta: ProjectMeta = (result.needsPriceEntry ?? 0) > 0 &&
    !(meta0.reportType ?? "").includes("پیش‌نویس")
    ? { ...meta0, reportType: `پیش‌نویس — ${meta0.reportType || "موقت"}` }
    : meta0;

  // ── برگه ۱: خلاصهٔ مالی ──
  // زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸):
  // جمع ردیف‌ها × طبقات × بالاسری × منطقه‌ای + تجهیز و برچیدن.
  const idx = result.index;
  let idxNote = "";
  if (idx && idx.targetPeriod && idx.targetPeriod !== idx.basePeriod) {
    idxNote = ` — تعدیل به دورهٔ ${idx.targetPeriod}` + (idx.provisional ? " (شاخص موقت)" : "");
  }
  const financial: Cell[][] = [
    ...headerBlock(meta),
    // بنر خطاهای اعتبارسنجی تاریخ‌ها (ایراد ۱۲) — در صورت وجود
    ...(validateMeta(meta).length
      ? [[`خطا — تاریخ‌های پروژه نامعتبر است و این خروجی «پیش‌نویس» است: ` +
          validateMeta(meta).map((e) => `${e.item}: ${e.message}`).join(" | "), "", ""] as Cell[]]
      : []),
    ["ردیف", "شرح", "مبلغ (ریال)"],
    ["۱", `الف) جمع ناخالص ردیف‌های فهرست‌بها${idxNote}`, moneyCell(result.baseTotal)],
    ["۲", `ضریب طبقات (× ${settings.floorsCoef})`, moneyCell(result.floorsAmount)],
    ["۳", `ضریب بالاسری (× ${settings.overheadCoef})`, moneyCell(result.overheadAmount)],
    ["۴", `ضریب منطقه‌ای (× ${settings.regionalCoef})`, moneyCell(result.regionalAmount)],
    ["۵", "تجهیز و برچیدن کارگاه (مبلغ واردشده)", moneyCell(result.siteSetup)],
    ["۶", "ب) مبلغ ناخالص نهایی قابل پرداخت", moneyCell(result.grossPayable)],
    ["مبلغ به حروف", moneyToWords(Math.round(result.grandTotal)), ""],
    [],
    // ── بلوک جداگانهٔ «خالص پرداختی» (کسورات قانونی — بر ناخالص اثر ندارد) ──
    ["", "خالص پرداختی (محاسبهٔ جداگانه)", ""],
    ["۱", "مبلغ ناخالص نهایی", moneyCell(result.grossPayable)],
    ["۲", `کسورات: بیمه (${settings.insurancePct}٪)`, moneyCell(-result.insurance)],
    ["۳", `کسورات: مالیات (${settings.taxPct}٪)`, moneyCell(-result.tax)],
    ["۴", `کسورات: حسن انجام کار (${settings.goodJobPct}٪)`, moneyCell(-result.goodJob)],
    ["۵", "کسورات: پیش‌پرداخت", moneyCell(-result.advancePayment)],
    ["۶", "مجموع کسورات", moneyCell(-result.totalDeductions)],
    ["۷", "خالص پرداختی پس از کسورات", moneyCell(result.netPayable)],
    [],
    ["فصل", "شرح فصل", "مبلغ کل (ریال)"],
  ];
  const chFirst = financial.length; // اولین سطر دادهٔ فصل (0-based)
  for (const c of result.chapterSums) {
    financial.push([
      `فصل ${c.chapter}`,
      c.title,
      moneyCell(c.total),
    ]);
  }
  const chLast = financial.length - 1;
  // سطر جمع فصول با فرمول زندهٔ Excel (مانند app.py) + مقدار کش‌شده
  if (result.chapterSums.length) {
    const chSum = neumaier(result.chapterSums.map((c) => Math.round(c.total)));
    const chRange = XLSX.utils.encode_range({ s: { r: chFirst, c: 2 }, e: { r: chLast, c: 2 } });
    financial.push(["", "جمع مبالغ فصل‌ها", moneyCell(chSum, `SUM(${chRange})`)]);
  }
  // ── خلاصهٔ وضعیت قیمت‌ها (فاز C — §۱۵-۴ بند ۶) ──
  const ps = result.priceStatusSummary ?? {};
  if (Object.keys(ps).length) {
    financial.push([]);
    financial.push(["وضعیت قیمت‌ها", "تعداد ردیف‌ها", "توضیح"]);
    const psDesc: Record<string, string> = {
      "قطعی": "تطبیق دقیق با فهرست‌بهای ۱۴۰۴",
      "موقت": "ردیف تخمینی/موقت — نیاز به تأیید",
      "پیش‌فرض اپ": "بدون تطبیق با فهرست‌بها — قیمت پیش‌فرض برنامه",
      "دستی": "قیمت واردشدهٔ دستی (دارای منبع و سند)",
      "نیازمند ورود": "بازبینی تطبیق — قیمت باید وارد شود",
    };
    for (const st of MANUAL_STATUSES) {
      if (ps[st]) financial.push([st, ps[st], psDesc[st] ?? ""]);
    }
    if (result.needsPriceEntry) {
      financial.push([
        "پیام",
        `${faDigits(result.needsPriceEntry)} ردیف نیازمند ورود قیمت هستند`,
        "خروجی تا تأیید این ردیف‌ها «پیش‌نویس» است",
      ]);
    }
    if (result.starredTotal) {
      financial.push([
        "ردیف‌های ستاره‌دار",
        moneyCell(result.starredTotal),
        `${faFloat(result.starredPct ?? 0, 1)}٪ از برآورد کل`,
      ]);
    }
  }
  XLSX.utils.book_append_sheet(wb, sheetFromAoA(financial, [8, 58, 26]), "خلاصهٔ مالی و برآورد");

  // ── برگه ۲: صورت‌وضعیت / خلاصه‌متره ──
  const boq: Cell[][] = [
    ...headerBlock(meta),
    ["ردیف", "کد فهرست‌بها", "شرح آیتم", "فصل", "واحد", "مقدار", "بهای واحد (ریال)", "بهای کل (پایه، ریال)", "ضریب تعدیل", "بهای کل (به‌هنگام، ریال)", "روش تطبیق", "اطمینان٪", "ارجاع بها", "بهای فهرست (ریال)", "بهای دستی (ریال)", "اختلاف ٪", "وضعیت"],
  ];
  const boqMerges: XLSX.Range[] = [];
  let currentCh: string | null = null;
  let lineFirst = -1; // اولین سطر خطوط (۰-based) — بعد از سطر merge فصل
  for (const l of result.lines) {
    // سطر جداکنندهٔ فصل (مانند merge_range در app.py) — باعث می‌شود
    // آدرس فرمول‌های جمع در دو زبان دقیقاً یکسان باشد.
    if (l.chapter !== currentCh) {
      currentCh = l.chapter;
      boqMerges.push({ s: { r: boq.length, c: 0 }, e: { r: boq.length, c: 16 } });
      boq.push([`فصل ${faDigits(l.chapter)} — ${chapterTitle(l.chapter)}`]);
      if (lineFirst < 0) lineFirst = boq.length;
    }
    const manual = l.manual as ManualPriceRecord | undefined;
    boq.push([
      l.rowNo, l.code, l.desc + (l.estimatedPrice ? " [بهای تخمینی]" : ""),
      chapterTitle(l.chapter), l.unit, l.qty,
      moneyCell(l.price), moneyCell(l.total),
      l.indexFactor, moneyCell(l.totalIndexed),
      matchLabel(l.matchMethod), Math.round(l.confidence * 100),
      PRICE_REFS[l.code] ?? "—",
      // ستون‌های قیمت دستی (فاز C)
      l.appPrice ? moneyCell(l.appPrice) : "—",
      manual ? moneyCell(l.price) : "—",
      l.diffPct == null ? "—" : `${l.diffPct >= 0 ? "+" : ""}${l.diffPct.toFixed(1)}`,
      l.priceStatus ?? "قطعی",
    ]);
  }
  const lineLast = boq.length - 1;
  // سطر جمع کل با فرمول زندهٔ Excel (مانند app.py) + مقدار کش‌شده
  // مقدار: ستون F (اندیس ۵)؛ مبلغ به‌هنگام: ستون J (اندیس ۹).
  if (result.lines.length) {
    const qtySum = neumaier(result.lines.map((l) => l.qty));
    const totSum = neumaier(result.lines.map((l) => Math.round(l.totalIndexed)));
    const fRange = XLSX.utils.encode_range({ s: { r: lineFirst, c: 5 }, e: { r: lineLast, c: 5 } });
    const jRange = XLSX.utils.encode_range({ s: { r: lineFirst, c: 9 }, e: { r: lineLast, c: 9 } });
    boq.push(["", "", "جمع کل ردیف‌های فهرست‌بها", "", "",
      num2Cell(qtySum, `SUM(${fRange})`), "", "", "",
      moneyCell(totSum, `SUM(${jRange})`), "", "", "", "", "", ""]);
  }
  XLSX.utils.book_append_sheet(wb, sheetFromAoA(boq, [7, 14, 58, 22, 10, 12, 14, 16, 10, 18, 12, 10, 34, 14, 14, 10, 12], boqMerges), "صورت وضعیت");

  // ── برگه ۳: ریزمتره (ردیابی تا سطح منبع) ──
  const detail: (string | number)[][] = [
    ...headerBlock(meta),
    ["ردیف BOQ", "کد", "فایل منبع", "جدول منبع", "عنصر / مارک", "گروه سازه‌ای", "مصالح", "شرح", "مقدار", "واحد"],
  ];
  for (const l of result.lines) {
    for (const s of l.sources) {
      detail.push([l.rowNo, l.code, s.fileName, s.tableTitle, s.ref, s.group, s.material, s.detail, round2(s.qty), unitFa(s.unit)]);
    }
    if (!l.sources.length) detail.push([l.rowNo, l.code, l.note ?? "—", "—", "—", "—", "—", "—", round2(l.qty), l.unit]);
  }
  XLSX.utils.book_append_sheet(wb, sheetFromAoA(detail, [9, 10, 34, 30, 26, 12, 18, 40, 12, 10]), "متره ریز");

  // ── برگه ۴: لیستوفر آرماتور (ایراد ۱۱) ──
  // ستون‌ها: مارک | گروه سازه‌ای | طبقه | قطر | تعداد | طول هر شاخه | طول کل |
  // وزن واحد | وزن کل | شکل خم. گروه هرگز «سایر» و مارک هرگز «—» نیست.
  const byD = new Map<number, number>();
  const byG = new Map<string, number>();
  for (const r of result.rebar) {
    const d = r.diameter || 0;
    byD.set(d, (byD.get(d) ?? 0) + r.weight);
    byG.set(r.group, (byG.get(r.group) ?? 0) + r.weight);
  }
  const rebar: (string | number)[][] = [
    ...headerBlock(meta),
    ["مارک", "گروه سازه‌ای", "طبقه", "قطر (mm)", "تعداد", "طول هر شاخه (m)", "طول کل (m)", "وزن واحد (kg/m)", "وزن کل (kg)", "شکل خم"],
    ...result.rebar.map((r) => [
      r.mark, r.group, r.level ?? "", r.diameter || "—", r.count,
      round2(r.perBarLength), round2(r.totalLength), round2(r.unitWeight),
      round2(r.weight), r.shape,
    ]),
    [],
    ["جمع به تفکیک قطر", "", "", "", "", "", "", "", "", ""],
    ...[...byD.keys()].sort((a, b) => a - b).map((d) => [
      "", `قطر ${faDigits(String(d % 1 === 0 ? d : d.toFixed(1)))} mm`, "", "", "", "", "", "",
      round2(byD.get(d) ?? 0), "",
    ]),
    ["جمع به تفکیک گروه", "", "", "", "", "", "", "", "", ""],
    ...[...byG.keys()].sort().map((g) => [
      "", g, "", "", "", "", "", "", round2(byG.get(g) ?? 0), "",
    ]),
    [],
    ["جمع کل", "", "", "",
      result.rebar.reduce((a, r) => a + r.count, 0), "",
      round2(neumaier(result.rebar.map((r) => r.totalLength))), "",
      round2(neumaier(result.rebar.map((r) => r.weight))), ""],
  ];
  XLSX.utils.book_append_sheet(wb, sheetFromAoA(rebar, [22, 14, 12, 10, 8, 13, 12, 13, 12, 16]), "لیستوفر آرماتور");

  // ── برگه ۵: سوابق تجمعی صورت‌وضعیت‌ها ──
  // ستون‌های میلادی مخفی (ایراد ۱۳): متن شمسی برای نمایش + میلادی واقعی
  // برای محاسبات Excel (مرتب‌سازی/تفاضل تاریخ).
  const hist: (string | number | Date)[][] = [
    ...headerBlock(meta),
    ["شماره صورت‌وضعیت", "نوع", "دوره از", "دوره تا", "ناخالص تجمعی (ریال)", "کسورات تجمعی (ریال)", "خالص تجمعی (ریال)", "کارکرد این دوره (ریال)", "دوره از (میلادی)", "دوره تا (میلادی)"],
    ...history.map((h): (string | number | Date)[] => {
      const ps = jalaliToISO(h.periodStart);
      const pe = jalaliToISO(h.periodEnd);
      return [
        h.reportNo, h.reportType, h.periodStart, h.periodEnd,
        round0(h.grossPayable), round0(h.totalDeductions), round0(h.netPayable), round0(h.currentWork),
        ps ? new Date(`${ps}T00:00:00`) : "",
        pe ? new Date(`${pe}T00:00:00`) : "",
      ];
    }),
  ];
  const histWs = sheetFromAoA(hist, [18, 10, 14, 14, 20, 20, 20, 20, 12, 12]);
  // ستون‌های I و J مخفی هستند (فقط برای محاسبات — ایراد ۱۳)
  (histWs as any)["!cols"][8] = { ...(histWs as any)["!cols"][8], hidden: true };
  (histWs as any)["!cols"][9] = { ...(histWs as any)["!cols"][9], hidden: true };
  XLSX.utils.book_append_sheet(wb, histWs, "سوابق صورت وضعیت");

  // ── برگه ۶: گزارش کیفیت تطبیق ──
  const q = result.quality;
  const quality: (string | number)[][] = [
    ...headerBlock(meta),
    ["شاخص", "مقدار"],
    ["جداول خوانده‌شده", q.tablesParsed],
    ["جداول نامشخص", q.tablesUnknown],
    ["ردیف‌های دادهٔ خوانده‌شده", q.rowsRead],
    ["ردیف‌های مترهٔ تولیدشده", q.linesMatched],
    ["تطبیق دقیق/دستی", q.linesExact],
    ["تطبیق فازی", q.linesFuzzy],
    ["ردیف‌های با بهای تخمینی", q.linesEstimatedPrice],
    ["ردیف‌های نیازمند بررسی", q.linesNeedReview],
    [],
    ["هشدارها", ""],
    ...q.warnings.map((w) => ["", w]),
  ];
  XLSX.utils.book_append_sheet(wb, sheetFromAoA(quality, [34, 60]), "کیفیت تطبیق");

  // ═════════ برگه ۷: ضریب طبقات (ایراد ۳ — پیوست ۲) ═════════
  // هم‌سان با app.py:ExcelExporter.export برگهٔ «ضریب طبقات».
  {
    const fc = result.coefs?.floors;
    const calc = fc?.calc ?? null;
    const f: Cell[][] = [...headerBlock(meta)];
    f.push(["فرمول رسمی پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴", fc?.formula ?? "", "", "", "", "", "", ""]);
    f.push([
      "مخرج به‌کاررفته", calc?.divisor ?? "100×S",
      "P با مخرج جایگزین: " + faFloat(calc?.pAlt ?? 1.0, 6),
      "صورت کسر: " + faFloat(calc?.num ?? 0, 2),
      "مخرج کسر: " + faFloat(calc?.den ?? 0, 2),
      "", "", "",
    ]);
    f.push([
      "ضریب نهایی P", faFloat(fc?.value ?? 1.0, 6),
      "وضعیت: " + (fc?.status || "—"),
      "منبع: " + (fc?.source ?? "—"), "", "", "", "",
    ]);
    f.push(["قاعدهٔ اعمال", fc?.clause ?? "", "", "", "", "", "", ""]);
    f.push([
      "ارجاع", "فرمول: پیوست ۲ فهرست‌بهای پایه ابنیه ۱۴۰۴ (متن رسمی دریافت‌شده از کاربر).",
      "", "", "", "", "", "",
    ]);
    f.push([]);
    f.push([
      "طبقه (تراز Revit)", "نوع", "نماد (شماره i)",
      "مساحت مدل (m²)", "مساحت دستی (m²)", "مساحت مؤثر (m²)",
      "ضریب", "سهم (مساحت × ضریب)",
    ]);
    const KIND_LABEL: Record<string, string> = {
      below_base: "زیر همکف", ground: "همکف",
      above: "بالاتر از همکف", roof: "بام/مرجع (مستثنی)",
      none: "غیرطبقه‌ای (مستثنی)",
    };
    for (const r of fc?.rows ?? []) {
      const kind = KIND_LABEL[r.kind] ?? r.kind;
      let sym: string, facLbl: string;
      if (r.kind === "ground") [sym, facLbl] = ["B0", "۰"];
      else if (r.kind === "below_base") [sym, facLbl] = [`B${faDigits(r.index)}`, faDigits(r.index)];
      else if (r.kind === "above") [sym, facLbl] = [`F${faDigits(r.index)}`, faDigits(r.index)];
      else [sym, facLbl] = ["—", "مستثنی"];
      const eff = r.area;
      f.push([
        r.name, kind, sym,
        typeof r.areaModel === "number" ? faFloat(r.areaModel) : "—",
        typeof r.areaManual === "number" ? faFloat(r.areaManual) : "—",
        typeof eff === "number" ? faFloat(eff) : "نیازمند ورود دستی",
        facLbl,
        r.kind === "roof" || r.kind === "none"
          ? "—"
          : faFloat(r.index * (eff ?? 0)),
      ]);
    }
    const fp = fc?.footprint;
    f.push([]);
    if (fp) {
      f.push([
        "رَدپای ساختمان (از بتن مگر)",
        `${faFloat(fp.volume, 2)} m³ ÷ ${faFloat(fp.thickness, 2)} m = ${faFloat(fp.area, 1)} m²` +
          (fp.assumedThickness ? " (ضخامت پیش‌فرض اپ ۱۰ cm)" : ""),
        "وضعیت: " + (fp.status ?? "تخمینی"),
        "راهنما برای مساحت همکف/زیرهمکف — مقدار دقیق را از نقشه‌های مصوب وارد کنید",
        "", "", "", "",
      ]);
    }
    f.push([
      "یادداشت", "مساحت «مدل» فقط برای ترازهایی خوانده می‌شود که المان سقف (دست Floors) دارند؛ طبقات دیگر را از نقشه‌های مصوب در تنظیمات → floors_data وارد کنید.",
      "", "", "", "", "", "",
    ]);
    f.push([]);
    f.push([
      "برداشت", "در جدول بالا اگر مساحت دستی وارد شده باشد، جایگزین مساحت مدل می‌شود (مقدار مدل کنار آن باقی می‌ماند).",
      "", "", "", "", "", "",
    ]);
    f.push([]);
    f.push([
      "ردیف‌های مشمول ضریب طبقات (پیوست ۲ — بند ۱-۳)",
      "فصول مستثنی: " + ((fc?.excludedChapters ?? []).join("، ") || "—"),
      "", "", "", "", "", "",
    ]);
    f.push(["کد ردیف", "شرح", "فصل", "مبلغ (ریال)", "", "", "", ""]);
    for (const el of fc?.eligibleLines ?? []) {
      f.push([el.code, el.desc, el.chapter, moneyCell(el.total), "", "", "", ""]);
    }
    f.push([
      "جمع مشمول", faFloat(fc?.eligibleTotal ?? 0, 0), "", "", "", "", "", "",
    ]);
    f.push([
      "جمع مستثنی", faFloat(fc?.excludedTotal ?? 0, 0),
      "جمع کل ردیف‌ها: " + faFloat(result.baseTotal, 0), "", "", "", "", "",
    ]);
    f.push([
      "مبلغ ضریب طبقات",
      `مشمول × P + مستثنی = ${faFloat(fc?.eligibleTotal ?? 0, 0)} × ${faFloat(fc?.value ?? 1.0, 6)} + ${faFloat(fc?.excludedTotal ?? 0, 0)} = ${faFloat(fc?.floorsAmount ?? 0, 0)}`,
      "", "", "", "", "", "",
    ]);
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(f, [22, 18, 12, 15, 15, 15, 10, 18]), "ضریب طبقات");
  }

  // ═════════ برگه ۷: موتور تعدیل پیمان (فاز B — موتور اول) ═════════
  // فقط اگر موتور فعال باشد. هرگز با شیت «برآورد به‌هنگام» ادغام نمی‌شود
  // (قاعدهٔ طلایی ۵).
  const adj = result.adjustment;
  const tadil = adj?.tadil;
  if (tadil) {
    const t: Cell[][] = [...headerBlock(meta)];
    const miss = (tadil.missing ?? [])
      .map(([c, w, q]) => `${c} (${w} ${q})`).join("، ");
    if (tadil.error) {
      t.push([`توقف موتور: ${tadil.error}`, "", "", "", "", "", "", ""]);
    } else if (tadil.incomplete) {
      t.push([`ناکامل — شاخص برخی فصل‌ها ناموجود است: ${miss}. شاخص دستی را در تنظیمات وارد کنید.`, "", "", "", "", "", "", ""]);
    } else if (tadil.draft) {
      t.push(["پیش‌نویس — مقادیر منبع تصویری (بخشنامه ۲۰۸۰ و شاخص موقت ۱۴۰۵) تأیید نشده‌اند؛ تا تأیید کاربر این خروجی رسمی نیست.", "", "", "", "", "", "", ""]);
    }
    t.push(["فرمول قانونی تعدیل پیمان", tadil.formula, "", "", "", "", "", ""]);
    t.push(["ضریب قانونی (k)", numCell(tadil.coef, 2),
            "پیش‌فرض اپ — منبع تصویری بخشنامه ۲۰۸۰، نیازمند تأیید", "", "", "", "", ""]);
    t.push(["دورهٔ مبنا (Io)", ioLabel(tadil),
            "شاخص هر فصل از پیوست ۳ (صفحه‌های ۶–۷)", "", "", "", "", ""]);
    const sp = tadil.split ?? [];
    t.push(["دوره‌های انجام کار",
            sp.length > 1
              ? sp.map(([q, f]) => `${quarterLabel(q)} (${(f * 100).toFixed(1)}٪)`).join("، ")
              : sp.length === 1 ? quarterLabel(sp[0][0]) : "—",
            "تقسیم کارکرد بین سه‌ماهه‌ها (بر اساس روزها)", "", "", "", "", ""]);
    t.push([]);
    t.push(["زنجیرهٔ مبلغ پایه (A) — مبالغ به ریال", "", "", "", "", "", "", ""]);
    for (const c2 of tadil.chain) {
      t.push([c2[0], moneyCell(c2[1]), c2[2], "", "", "", "", ""]);
    }
    t.push([]);
    t.push(["فصل", "عنوان فصل", "مبلغ پایه (A_c، ریال)", "شاخص Io", "شاخص It",
            "نسبت It/Io", "مبلغ تعدیل (ΔP_c، ریال)", "وضعیت و منبع"]);
    for (const r of tadil.chapters) {
      t.push([r.chapter, r.title, moneyCell(r.amount),
              numCell(r.io, 1), r.it !== null ? numCell(r.it, 1) : "—",
              r.ratio !== null ? numCell(r.ratio, 4) : "—",
              moneyCell(r.value), `${r.status} — ${r.src}`]);
    }
    const sr = tadil.setup_row;
    if (sr) {
      t.push(["تجهیز", "تجهیز و برچیدن کارگاه (شاخص رشته — بند ۴)",
              moneyCell(sr.amount), numCell(sr.io, 1), numCell(sr.it, 1),
              sr.ratio !== null ? numCell(sr.ratio, 4) : "—",
              moneyCell(sr.value), `${sr.status} — ${sr.src}`]);
    }
    const nr = tadil.new_work_row;
    if (nr) {
      t.push(["کار جدید", `کار جدید (${nr.method ?? ""}) - بندهای ۳-۱..۳-۵`,
              moneyCell(nr.amount), numCell(nr.io, 1), numCell(nr.it, 1),
              nr.ratio !== null ? numCell(nr.ratio, 4) : "—",
              moneyCell(nr.value), `${nr.status} - ${nr.src}`]);
    }
    t.push([]);
    // ── جدول فصل × سه‌ماهه: شاخص It هر فصل در هر سه‌ماههٔ کارکرد ──
    if (sp.length > 1) {
      t.push(["شاخص It هر فصل در هر سه‌ماههٔ کارکرد (ستون زرد = موقت)", "", "", "", "", "", "", ""]);
      t.push(["فصل", "عنوان فصل", ...sp.map(([q, f]) => `${quarterLabel(q)} (${(f * 100).toFixed(1)}٪)`),
              ...Array.from({ length: Math.max(0, 6 - sp.length) }, () => "")]);
      for (const r of tadil.chapters) {
        const qs = r.quarters ?? [];
        t.push([r.chapter, r.title,
                ...qs.map((q) => numCell(q[1], 1)),
                ...Array.from({ length: Math.max(0, 6 - qs.length) }, () => "")]);
      }
      t.push([]);
    }
    // ── فاز E-6: جدول ضریب هر فصل در هر سه‌ماهه (بند ۸-۲) ──
    if (sp.length > 1 && tadil.chapters.some((r) => (r.coef_rows ?? []).length > 0)) {
      t.push(["ضریب تعدیل هر فصل در هر سه‌ماههٔ کارکرد (بند ۸-۲: خام با ۳ رقم، گردشده با ۲ رقم)",
              "", "", "", "", "", "", ""]);
      t.push(["فصل", "عنوان فصل", "سه‌ماهه", "ضریب خام", "ضریب گردشده",
              "ΔP این گام", "وضعیت", ""]);
      const fsp = new Map(sp);
      for (const r of tadil.chapters) {
        for (const [q, raw, used] of r.coef_rows ?? []) {
          const fq = fsp.get(q) ?? 0;
          t.push([r.chapter, r.title, quarterLabel(q),
                  numCell(raw, 3), numCell(used, 2),
                  numCell(used * r.amount * fq, 0), r.status, ""]);
        }
      }
      const sr = tadil.setup_row;
      if (sr && sr.delta_k095 !== null && sr.delta_k095 !== undefined) {
        for (const [q, raw, used] of sr.coef_rows ?? []) {
          const fq = fsp.get(q) ?? 0;
          t.push(["تجهیز", "تجهیز و برچیدن (شاخص رشته — بند ۴)", quarterLabel(q),
                  numCell(raw, 3), numCell(used, 2),
                  numCell(used * sr.amount * fq, 0), "رشته‌ای", ""]);
        }
      }
      t.push([]);
    }
    if (!tadil.incomplete) {
      t.push(["جمع تعدیل (شامل علی‌الحساب، ریال)",
              `k × Σ_c (It_c/Io_c − 1) × A_c = ${Math.round(tadil.delta_p).toLocaleString("en-US")}`,
              `ضریب k = ${tadil.coef.toFixed(2)}`, "", "", "", "", ""]);
      const [, dpDef, dpProv] = splitRounded(tadil.delta_p, tadil.delta_p_definitive, 0);
      if (Math.abs(dpProv) >= 1) {
        t.push(["بخش قطعی (شاخص‌های قطعی ۱۴۰۴، ریال)", moneyCell(dpDef),
                "مجموع با شاخص‌های قطعی ۱۴۰۴", "", "", "", "", ""]);
        t.push(["بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1، ریال)", moneyCell(dpProv),
                "علی‌الحساب = ضریب موقت × قطعی ۱۴۰۴Q4", "", "", "", "", ""]);
      }
      // ── فاز E-6: مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) ──
      if (Math.abs(tadil.k_diff) >= 0.01) {
        t.push(["مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ — همراه قطعی، بند ۸-۴، ریال)",
                moneyCell(tadil.k_diff),
                "همزمان با صورت‌وضعیت قطعی پرداخت می‌شود", "", "", "", "", ""]);
      }
      // ── فاز E-6 Part C گام ۴: کسر ۵٪ فسخ با قصور (بند ۷) ──
      if (Math.abs(tadil.deduction_fault) >= 0.01) {
        t.push(["کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷، ریال)",
                moneyCell(-tadil.deduction_fault),
                "۵٪ از مبلغ تعدیل کسر می‌شود", "", "", "", "", ""]);
      }
      t.push(["مبلغ نهایی (A + جمع تعدیل، ریال)", moneyCell(tadil.result_amount),
              `وضعیت: ${tadil.draft ? "پیش‌نویس" : "تأییدشده"}`, "", "", "", "", ""]);
      const p = tadil.params;
      t.push(["شرط تأخیر", tadil.delay_mode,
              `نحوهٔ پیش‌پرداخت: ${tadil.advance_mode}`,
              `تعدیل منفی: ${p.allow_negative ? "مجاز" : "غیرمجاز"}`,
              `تاریخ تسلیم پیشنهاد: ${p.proposal_date || "—"}`,
              `ضریب موقت ۱۴۰۵: ${p.provisional_coef !== null ? p.provisional_coef.toFixed(3) : "—"}`,
              "", ""]);
    }
    t.push(["منبع و وضعیت", tadil.source, "", "", "", "", "", ""]);
    t.push([]);
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(t, [10, 30, 22, 14, 14, 14, 24, 30]), "تعدیل پیمان");
  }

  // ═════════ برگه ۸: موتور برآورد به‌هنگام (فاز B — موتور دوم) ═════════
  const baravord = adj?.baravord;
  if (baravord) {
    const b: Cell[][] = [...headerBlock(meta)];
    const miss = (baravord.missing ?? [])
      .map(([c, w, q]) => `${c} (${w} ${q})`).join("، ");
    if (baravord.error) {
      b.push([`توقف موتور: ${baravord.error}`, "", "", "", "", "", "", ""]);
    } else if (baravord.incomplete) {
      b.push([`ناکامل — شاخص برخی فصل‌ها ناموجود است: ${miss}.`, "", "", "", "", "", "", ""]);
    } else if (baravord.draft) {
      b.push(["پیش‌نویس — شاخص‌ها استخراج‌شده از PDF هستند و تأیید نشده‌اند.", "", "", "", "", "", "", ""]);
    }
    b.push(["فرمول برآورد به‌هنگام", baravord.formula, "", "", "", "", "", ""]);
    b.push(["دورهٔ مبنا (Io)", ioLabel(baravord), "", "", "", "", "", ""]);
    b.push(["دورهٔ انجام کار (It)", quarterLabel(baravord.it_q), "", "", "", "", "", ""]);
    b.push([]);
    b.push(["زنجیرهٔ مبلغ پایه (A) — مبالغ به ریال", "", "", "", "", "", "", ""]);
    for (const c2 of baravord.chain) {
      b.push([c2[0], moneyCell(c2[1]), c2[2], "", "", "", "", ""]);
    }
    b.push([]);
    b.push(["فصل", "عنوان فصل", "مبلغ پایه (A_c، ریال)", "شاخص Io", "شاخص It",
            "نسبت It/Io", "مبلغ به‌هنگام‌شده (ریال)", "وضعیت و منبع"]);
    for (const r of baravord.chapters) {
      b.push([r.chapter, r.title, moneyCell(r.amount),
              numCell(r.io, 1), r.it !== null ? numCell(r.it, 1) : "—",
              r.ratio !== null ? numCell(r.ratio, 4) : "—",
              moneyCell(r.value), `${r.status} — ${r.src}`]);
    }
    const sr = baravord.setup_row;
    if (sr) {
      b.push(["تجهیز", "تجهیز و برچیدن کارگاه (شاخص رشته — بند ۴)",
              moneyCell(sr.amount), numCell(sr.io, 1), numCell(sr.it, 1),
              sr.ratio !== null ? numCell(sr.ratio, 4) : "—",
              moneyCell(sr.value), `${sr.status} — ${sr.src}`]);
    }
    const nrb = baravord.new_work_row;
    if (nrb) {
      b.push(["کار جدید", `کار جدید (${nrb.method ?? ""}) - بندهای ۳-۱..۳-۵`,
              moneyCell(nrb.amount), numCell(nrb.io, 1), numCell(nrb.it, 1),
              nrb.ratio !== null ? numCell(nrb.ratio, 4) : "—",
              moneyCell(nrb.value), `${nrb.status} - ${nrb.src}`]);
    }
    b.push([]);
    if (!baravord.incomplete) {
      b.push(["برآورد به‌هنگام‌شده (ریال)",
              `A_new = Σ_c A_c × It_c/Io_c = ${Math.round(baravord.result_amount).toLocaleString("en-US")}`,
              `وضعیت: ${baravord.draft ? "پیش‌نویس" : "تأییدشده"}`, "", "", "", "", ""]);
      b.push(["جمع کل به‌هنگام‌شده (قیمت پیمان)", moneyCell(baravord.grand_updated),
              `بالاسری × منطقه‌ای × پیشنهادی پس از It/Io اعمال شد — جمع کل فعلی: ${Math.round(baravord.grand_current).toLocaleString("en-US")}`,
              "", "", "", "", ""]);
    }
    b.push(["منبع و وضعیت", baravord.source, "", "", "", "", "", ""]);
    b.push([]);
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(b, [10, 30, 22, 14, 14, 14, 24, 30]), "برآورد به‌هنگام");
  }

  // ═════════ برگه ۹: تفکیک بخش قطعی و علی‌الحساب (فاز B) ═════════
  // بخش علی‌الحساب = تعدیل مربوط به دورهٔ موقت ۱۴۰۵Q1 — فقط موتور تعدیل پیمان.
  if (tadil) {
    const d: Cell[][] = [...headerBlock(meta)];
    const hasProv = (tadil.split ?? []).some(([q]) => quarterIsProvisional(q));
    if (!hasProv) {
      d.push(["در این محاسبه بخش علی‌الحساب وجود ندارد — دورهٔ انجام کار داخل سه‌ماهه‌های قطعی ۱۴۰۴ است یا ضریب موقت ۱۴۰۵Q1 وارد نشده است.", "", "", "", "", "", ""]);
    }
    d.push(["فصل", "عنوان فصل", "مبلغ پایه (A_c، ریال)", "بخش قطعی (ریال)",
            "بخش علی‌الحساب (ریال)",
            "جمع تعدیل (شامل علی‌الحساب، ریال)", "توضیح"]);
    let td = 0;
    let tp = 0;
    for (const r of tadil.chapters) {
      const dl = r.delta ?? 0;
      const dd = r.deltaDefinitive ?? 0;
      td += dd;
      tp += dl;
      d.push([r.chapter, r.title, moneyCell(r.amount), moneyCell(dd),
              moneyCell(dl - dd), moneyCell(dl),
              dl !== dd ? "علی‌الحساب = ضریب موقت × قطعی ۱۴۰۴Q4" : "همه قطعی"]);
    }
    const sr = tadil.setup_row;
    if (sr) {
      td += sr.deltaDefinitive;
      tp += sr.delta;
      d.push(["تجهیز", "تجهیز و برچیدن (شاخص رشته)", moneyCell(sr.amount),
              moneyCell(sr.deltaDefinitive), moneyCell(sr.delta - sr.delta),
              moneyCell(sr.delta),
              sr.delta !== sr.deltaDefinitive ? "علی‌الحساب = ضریب موقت × قطعی ۱۴۰۴Q4" : "همه قطعی"]);
    }
    const nrw = tadil.new_work_row;
    if (nrw) {
      td += nrw.deltaDefinitive;
      tp += nrw.delta;
      d.push(["کار جدید", `کار جدید (${nrw.method ?? ""}) - بندهای ۳-۱..۳-۵`,
              moneyCell(nrw.amount), moneyCell(nrw.deltaDefinitive),
              moneyCell(nrw.delta - nrw.deltaDefinitive), moneyCell(nrw.delta),
              "همان منطقِ تجهیز (شاخص رشته)"]);
    }
    // ── فاز E-6: ردیف مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) ──
    const kd = tadil.k_diff ?? 0;
    if (tadil.completed_within_term && Math.abs(kd) >= 0.01) {
      td += kd;
      d.push(["تبصرهٔ ۲", "مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ بند ۱-۸)",
              "", moneyCell(kd), "", moneyCell(kd),
              "همزمان با صورت‌وضعیت قطعی پرداخت می‌شود (بند ۸-۴)"]);
    }
    d.push([]);
    d.push(["جمع", "", "", moneyCell(td), moneyCell(tp - td), moneyCell(tp),
            "علی‌الحساب = جمع منهای بخش قطعی"]);
    d.push([]);
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(d, [10, 30, 22, 22, 22, 22, 30]), "بخش قطعی و علی‌الحساب");
  }

  // ═════════ برگه ۱۰: رجیستری مقادیر منتظر تأیید (فاز B) ═════════
  // هر مقدار غیررسمی + منبع + صفحهٔ PDF + وضعیت + اقدام.
  // این شیت همیشه ساخته می‌شود (مانند app.py) — حتی بدون موتورها،
  // چون شاخص‌های استخراج‌شده نیازمند تأیید هستند.
  {
    const p: Cell[][] = [...headerBlock(meta)];
    p.push(["المان", "مقدار", "منبع (بخشنامه)", "صفحهٔ PDF", "وضعیت", "اقدام"]);
    const seen = new Set<string>();
    for (const eng of [adj?.tadil, adj?.baravord]) {
      for (const it of eng?.pending ?? []) {
        const key = `${it.item}|${it.value}`;
        if (seen.has(key)) continue;
        seen.add(key);
        p.push([it.item, it.value !== null ? numCell(it.value, 4) : "—",
                it.source, it.page, it.status, it.action]);
      }
    }
    // شاخص فصول ابنیه (پیوست ۳، صفحه‌های ۶–۷) — هر فصل در هر دوره
    p.push(["شاخص فصول ابنیه — استخراج‌شده از بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳، پیوست ۳ (صفحه‌های ۶–۷)", "", "", "", "", ""]);
    const chapRows: any[] = (INDEX_BULLETINS as any)["chapters_abnieh"] ?? [];
    for (const r of chapRows) {
      for (const [pk, fk] of [["base", "base_esfand_1403"], ["q1", "q1_1404"], ["q2", "q2_1404"], ["q3", "q3_1404"], ["q4", "q4_1404"]] as [string, string][]) {
        const v = r[fk];
        if (typeof v === "number") {
          p.push([`فصل ${faDigits(String(r["chapter"]))} — شاخص ${periodLabel(pk)}`, numCell(v, 1),
                  `بخشنامه ۱۴۰۵/۱۵۵۲۳۳ — پیوست ۳، فصل ${faDigits(String(r["chapter"]))}`,
                  `صفحهٔ ${r["page"]} PDF`, "استخراج‌شده — نیازمند تأیید",
                  "مقدار را با جدول پیوست ۳ تطبیق دهید"]);
        }
      }
    }
    p.push([]);
    p.push(["شاخص‌های قطعی رشتهٔ ابنیه — استخراج‌شده از بخشنامه ۱۴۰۵/۱۵۵۲۳۳، پیوست ۳", "", "", "", "", ""]);
    const ibMeta = (INDEX_BULLETINS as any)["meta"] ?? {};
    if (ibMeta["status"]) {
      p.push(["وضعیت کلی جدول شاخص", ibMeta["status"], ibMeta["bulletin"], "", "", ""]);
    }
    for (const k of ["base", "q1", "q2", "q3", "q4"]) {
      const [v, pg] = indexValue(k);
      if (v === null) continue;
      p.push([`شاخص دورهٔ ${periodLabel(k)}`, numCell(v, 1),
              "بخشنامه ۱۴۰۵/۱۵۵۲۳۳ — پیوست ۳، ردیف ۱ (ابنیه)",
              `صفحهٔ ${pg} PDF`, "استخراج‌شده — نیازمند تأیید",
              "مقدار را با جدول پیوست ۳ بخشنامه تطبیق دهید"]);
    }
    p.push([]);
    p.push(["یادداشت", "فصل ۱۵ (سقف‌های از پیش ساخته) در جدول شاخص فصول ابنیه موجود نیست؛ با صفحهٔ ۶ PDF تطبیق دهید.", "", "", "اطلاع", ""]);
    // ═════════ فاز E-6 Part C گام ۱۲ (حرف g): تصمیمات منتظر تأیید ═════════
    // تک‌منبعِ حقیقت: PENDING_INTERPRETATIONS (همان که پنلِ «وضعیت ورودی‌ها»
    // و §۱۸-۳ ACCEPTANCE.md می‌خوانند). فاز E-8 §۱: شناسهٔ پایدار D-xx.
    p.push(["تصمیماتِ باز — منتظر تأیید کاربر", "", "", "", "", ""]);
    p.push(["شناسه", "موضوع", "تفسیرِ پیاده‌سازی‌شده", "گزینهٔ دیگر", "اثر عددی", ""]);
    for (const it of PENDING_INTERPRETATIONS) {
      p.push([it.id, it.subject, it.implemented,
              it.alternative, it.effect, ""]);
    }
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(p, [34, 20, 28, 22, 28, 34]), "مقادیر منتظر تأیید");
  }

  // ═════════ برگهٔ ۱۲: رجیستری مرکزی هشدارها (ایراد ۱۰) ═════════
  // هم‌سان با app.py:ExcelExporter.export برگهٔ «هشدارها».
  {
    const w: Cell[][] = [...headerBlock(meta)];
    const st = result.status ?? { complete: false, errors: 0, warningsN: 0, info: 0 };
    w.push([
      "وضعیت کلی",
      st.complete ? "کامل" : "ناقص",
      `خطا: ${faDigits(st.errors)} — هشدار: ${faDigits(st.warningsN)} — اطلاع: ${faDigits(st.info)}`,
      "", "", "",
    ]);
    w.push([]);
    w.push(["سطح", "دسته", "المان/ردیف", "شرح", "اقدام پیشنهادی", "بند مرجع"]);
    for (const x of result.warnings ?? []) {
      w.push([x.level, x.category, x.item, x.message, x.action, x.ref]);
    }
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(w, [10, 22, 18, 60, 40, 34]), "هشدارها");
  }

  // ── برگهٔ ۱۰: قیمت‌های دستی (فاز C) ──
  // ساختارِ ماشین‌خوانا: هر بخش با یک سطر عنوانِ یکتا شروع می‌شود و سپس
  // سطر سرستون و داده‌ها. parseManualEntriesXlsx همین شیت را می‌خواند
  // (ورود از Excel بین پروژه‌ها — §۱۵-۴). هم‌سان با app.py.
  {
    const priceSheet: Cell[][] = [
      ...headerBlock(meta),
      [MPX_VERSION_LABEL, MANUAL_ENTRIES_VERSION, "تاریخ خروجی", jalaliNowStr(),
        "کاربر", settings.priceUser ?? "", "", "", "", "", "", ""],
      [],
      [MPX_SECTION_PRICES, "", "", "", "", "", "", "", "", "", "", ""],
      ["شناسهٔ ردیف", "کد فهرست‌بها", "قیمت دستی", "قیمت فهرست", "اختلاف ٪",
        "منبع", "شماره سند", "تاریخ سند", "وضعیت", "فصل",
        "کاربر / تاریخ ورود", "توضیح"],
    ];
    const byLineId = new Map(result.lines.map((l) => [l.id, l]));
    for (const [key, rec] of Object.entries(settings.manualPrices ?? {}).sort(([a], [b]) =>
      a < b ? -1 : a > b ? 1 : 0)) {
      const line = byLineId.get(key);
      const ap = line ? (line.appPrice ?? line.price) : null;
      const code = line ? line.code : (rec.chapter ?? "");
      const dp = ap ? ((rec.price - ap) / ap) * 100 : null;
      priceSheet.push([
        key, code, round0(rec.price), ap ? round0(ap) : "—",
        dp == null ? "—" : `${dp >= 0 ? "+" : ""}${dp.toFixed(1)}`,
        rec.source ?? "", rec.docNo ?? "", rec.docDate ?? "",
        rec.status || "دستی",
        rec.chapter || (line?.chapter ?? ""),
        `${rec.user ?? ""} — ${rec.at ?? ""}`.trim().replace(/^—|—$/g, "").trim(),
        rec.note ?? "",
      ]);
    }
    priceSheet.push([]);
    priceSheet.push([MPX_SECTION_CODES, "", "", "", "", "", "", "", "", "", "", ""]);
    priceSheet.push(["شناسهٔ ردیف", "کد جایگزین", "دلیل", "کاربر", "تاریخ ورود",
      "", "", "", "", "", "", ""]);
    for (const [key, rec] of Object.entries(settings.manualCodes ?? {}).sort(([a], [b]) =>
      a < b ? -1 : a > b ? 1 : 0)) {
      if (typeof rec === "string") continue;
      priceSheet.push([key, rec.code ?? "", rec.reason ?? "", rec.user ?? "",
        rec.at ?? "", "", "", "", "", "", "", ""]);
    }
    priceSheet.push([]);
    priceSheet.push([MPX_SECTION_EXCLUDED, "", "", "", "", "", "", "", "", "", "", ""]);
    priceSheet.push(["شناسهٔ ردیف", "دلیل", "کاربر", "تاریخ ورود",
      "", "", "", "", "", "", "", ""]);
    for (const e of settings.excluded ?? []) {
      if (typeof e === "string") continue;
      priceSheet.push([e.id, e.reason ?? "", e.user ?? "", e.at ?? "",
        "", "", "", "", "", "", "", ""]);
    }
    priceSheet.push([]);
    priceSheet.push([MPX_SECTION_STARRED, "", "", "", "", "", "", "", "", "", "", ""]);
    priceSheet.push(["کد", "شرح", "واحد", "مقدار", "قیمت واحد", "فصل",
      "منبع", "شماره سند", "تاریخ سند", "کاربر / تاریخ ورود", "توضیح", ""]);
    for (const sr of settings.starredRows ?? []) {
      priceSheet.push([
        sr.code, sr.desc, sr.unit, sr.qty, round0(sr.price), sr.chapter,
        sr.source, sr.docNo, sr.docDate,
        `${sr.user ?? ""} — ${sr.at ?? ""}`.trim().replace(/^—|—$/g, "").trim(),
        sr.note ?? "", "",
      ]);
    }
    XLSX.utils.book_append_sheet(
      wb,
      sheetFromAoA(priceSheet, [26, 14, 14, 14, 14, 16, 12, 12, 12, 12, 16, 30]),
      MPX_SHEET,
    );
  }

  // ── برگهٔ ۱۱: سابقهٔ ویرایش (Audit trail — §۱۵-۴ بند ۴) ──
  {
    const auditSheet: Cell[][] = [
      ...headerBlock(meta),
      ["زمان", "کاربر", "ردیف", "فیلد", "مقدار قبلی", "مقدار جدید", "منبع", "نوع"],
    ];
    for (const a of settings.priceAudit ?? []) {
      auditSheet.push([
        a.at ?? "", a.user ?? "", a.item ?? "", a.field ?? "",
        a.old ?? "", a.new ?? "", a.source ?? "",
        AUDIT_KIND_LABELS[a.kind ?? "price"] ?? "قیمت/کد",
      ] as Cell[]);
    }
    XLSX.utils.book_append_sheet(
      wb,
      sheetFromAoA(auditSheet, [24, 18, 20, 18, 20, 20, 18, 14]),
      MPX_AUDIT_SHEET,
    );
  }

  // ═════════ برگه‌های جدید فاز D (۵ شیت) ═════════
  // برگه‌ها در پایان (پیش از writeFile) به ترتیب رسمی SHEET_ORDER مرتب
  // می‌شوند؛ لذا ترتیبِ ساخته‌شدن در اینجا مهم نیست.
  // دسترسی‌ها defensive هستند تا خروجی با نتیجهٔ ناقص (تست‌های حداقلی)
  // هم کارساز بماند.
  const st = result.status ?? {
    complete: false, errors: 0, warningsN: 0, info: 0,
    floorsStatus: "—", regionalStatus: "—",
  };
  const pss = ((result as any).priceStatusSummary ?? {}) as Record<string, number>;
  const cf = (result as any).coefs ?? {};
  const fl = cf.floors ?? {};
  const rg = cf.regional ?? {};
  const ix = (result as any).index ?? null;

  // ── برگه: مشخصات پیمان ──
  {
    const sh: Cell[][] = [
      ...headerBlock(meta),
      ["", "بخش ۱ — مشخصات پروژه و قرارداد", "", ""],
      ["", "نام پروژه", meta.projectName || "—", ""],
      ["", "کارفرما", meta.employer || "—", ""],
      ["", "پیمانکار", meta.contractor || "—", ""],
      ["", "مشاور / ناظر", meta.consultant || "—", ""],
      ["", "محل اجرا", meta.location || "—", ""],
      ["", "شماره پیمان (قرارداد)", meta.contractNo || "—", ""],
      ["", "تاریخ پیمان (شمسی)", meta.contractDate || "—", ""],
      [],
      ["", "بخش ۲ — مشخصات صورت‌وضعیت", "", ""],
      ["", "شماره صورت‌وضعیت", meta.reportNo || "—", ""],
      ["", "نوع صورت‌وضعیت", meta.reportType || "—", ""],
      ["", "شروع دورهٔ صورت‌وضعیت", meta.periodStart || "—", ""],
      ["", "پایان دورهٔ صورت‌وضعیت", meta.periodEnd || "—", ""],
      [],
      ["", "بخش ۳ — مبنای قیمت‌گذاری و ضرایب قراردادی", "", ""],
      ["", "فهرست‌بهای مبنای قیمت‌گذاری", "فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه سال ۱۴۰۴", ""],
      ["", "واحد پول", "ریال", ""],
      ["", "ضریب بالاسری", `${faFloat(settings.overheadCoef ?? 1.0, 4)} — تنظیم کاربر`, ""],
      ["", "ضریب منطقه‌ای", `${faFloat(rg.value ?? 1.0, 4)} — ${st.regionalStatus ?? "—"}`, ""],
      ["", "ضریب طبقات", `${faFloat(fl.value ?? 1.0, 4)} — ${st.floorsStatus ?? "—"}`, ""],
      ["", "تجهیز و برچیدن کارگاه", `${faFloat(settings.siteSetupAmount ?? 0.0, 0)} ریال — مبلغ مستقیم`, ""],
      ["", "کسورات بیمه", `${faDigits(settings.insurancePct ?? 0)}٪ — فقط در خالص پرداختی`, ""],
      ["", "کسورات مالیات", `${faDigits(settings.taxPct ?? 0)}٪ — فقط در خالص پرداختی`, ""],
      ["", "کسورات حسن انجام کار", `${faDigits(settings.goodJobPct ?? 0)}٪ — فقط در خالص پرداختی`, ""],
      ["", "پیش‌پرداخت", `${faFloat(settings.advancePayment ?? 0.0, 0)} ریال — فقط در خالص پرداختی`, ""],
      [],
      ["", "بخش ۴ — اعتبارسنجی تاریخ‌ها (ایراد ۱۲)", "", ""],
    ];
    const derrs = validateMeta(meta);
    if (derrs.length) {
      for (const e of derrs) {
        sh.push(["", e.item ?? "—", e.message ?? "", "خطا"]);
      }
    } else {
      sh.push(["", "ترتیب تاریخ‌ها", "معتبر است", "تاریخ پیمان ≤ شروع دوره ≤ پایان دوره"]);
    }
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(sh, [8, 32, 26, 46]), "مشخصات پیمان");
  }

  // ── برگه: ضرایب ──
  {
    const coefRows: [string, string, string, string][] = [
      ["ضریب طبقات (P)", faFloat(fl.value ?? 1.0, 4), st.floorsStatus ?? "—",
       `پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — ${fl.formula ?? "فرمول P"}`],
      ["ضریب منطقه‌ای", faFloat(rg.value ?? 1.0, 4), st.regionalStatus ?? "—",
       rg.source ?? "تنظیم دستی کاربر"],
      ["ضریب بالاسری", faFloat(settings.overheadCoef ?? 1.0, 4), "تنظیم کاربر",
       "دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸ — پیش‌فرض عمرانی + مناقصه: ۱٫۳ (ترک تشریفات ۱٫۲ / غیرعمرانی ۱٫۴ / ۱٫۳)"],
      ["تجهیز و برچیدن کارگاه (ریال)", faFloat(settings.siteSetupAmount ?? 0.0, 0),
       "تنظیم کاربر",
       "مبلغ مستقیم — سقف ۴٪ صرفاً هشدار (دستورالعمل کاربرد بند ۲-۸)"],
    ];
    const sh: Cell[][] = [
      ...headerBlock(meta),
      ["شماره", "ضریب", "مقدار", "وضعیت", "منبع / بند مرجع"],
    ];
    coefRows.forEach(([nm, vl, stt, src], i) => {
      sh.push([faDigits(i + 1), nm, vl, stt, src]);
    });
    if (ix) {
      const fs = ix.chapters.map((c: any) => c.factor).filter((f: any) => f != null) as number[];
      const ftxt = fs.length ? `${faFloat(Math.min(...fs), 4)} تا ${faFloat(Math.max(...fs), 4)}` : "—";
      sh.push([faDigits(coefRows.length + 1), "شاخص تعدیل فهرست‌بها", ftxt,
               `فعال${ix.provisional ? " — شامل موقت" : ""}`,
               `کلیات بند ۲۲ — دورهٔ مبنا: ${ix.basePeriod ?? "—"} → هدف: ${ix.targetPeriod ?? "—"} (جزئیات در شیت «شاخص‌ها»)`]);
    } else {
      sh.push([faDigits(coefRows.length + 1), "شاخص تعدیل فهرست‌بها", "۱٫۰۰۰۰",
               "غیرفعال",
               "دورهٔ هدف = دورهٔ مبنا (اسفند ۱۴۰۳) — همهٔ ضرایب ۱ (کلیات بند ۲۲)"]);
    }
    sh.push(
      [],
      ["", "کسورات قانونی (بر ناخالص اثر ندارند — فقط در «خالص پرداختی» محاسبه می‌شوند)", "", "", ""],
      ["", "بیمه", `${faDigits(settings.insurancePct ?? 0)}٪`, "نمایشی",
       "قاعدهٔ طلایی ۵: کسورات جزو «ناخالص پرداختی» نیستند"],
      ["", "مالیات", `${faDigits(settings.taxPct ?? 0)}٪`, "نمایشی",
       "قاعدهٔ طلایی ۵: کسورات جزو «ناخالص پرداختی» نیستند"],
      ["", "حسن انجام کار", `${faDigits(settings.goodJobPct ?? 0)}٪`, "نمایشی",
       "قاعدهٔ طلایی ۵: کسورات جزو «ناخالص پرداختی» نیستند"],
      ["", "پیش‌پرداخت", `${faFloat(settings.advancePayment ?? 0.0, 0)} ریال`, "نمایشی",
       "قاعدهٔ طلایی ۵: کسورات جزو «ناخالص پرداختی» نیستند"],
    );
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(sh, [8, 30, 20, 20, 48]), "ضرایب");
  }

  // ── برگه: شاخص‌ها ──
  {
    const ib = INDEX_BULLETINS as any;
    const ibMeta = ib.meta ?? {};
    const sh: Cell[][] = [
      ...headerBlock(meta),
      ["", "بخش ۱ — شاخص‌های رسمی رشتهٔ ابنیه (پیوست ۳ بخشنامه ۱۴۰۵/۱۵۵۲۳۳)", "", "", "", "", ""],
    ];
    if (ibMeta.status) {
      sh.push(["", "وضعیت استخراج", ibMeta.status as string, "", "", "", ""]);
    }
    sh.push(["ردیف", "دوره", "شاخص رشتهٔ ابنیه", "منبع", "صفحه", "وضعیت", "یادداشت"]);
    const disc = (ib.disciplines ?? []).find((d: any) => d.name === "ابنیه");
    if (disc) {
      const periods: [string, any][] = [
        ["اسفند ۱۴۰۳ (مبنا)", disc.base_esfand_1403],
        ["سه‌ماهه اول ۱۴۰۴", disc.q1_1404],
        ["سه‌ماهه دوم ۱۴۰۴", disc.q2_1404],
        ["سه‌ماهه سوم ۱۴۰۴", disc.q3_1404],
        ["سه‌ماهه چهارم ۱۴۰۴", disc.q4_1404],
      ];
      for (const [p, k] of periods) {
        sh.push([faDigits(disc.row ?? 1), p, numCell(Number(k), 2),
                 ibMeta.bulletin ?? "—", faDigits(disc.page ?? 4),
                 "استخراج‌شده — نیازمند تأیید", `ستون «${p}»، ردیف ۱ صفحهٔ ۴`]);
      }
    }
    sh.push(
      [],
      ["", "بخش ۲ — شاخص فصول ابنیه (صفحهٔ ۶–۷ پیوست ۳)", "", "", "", "", ""],
      ["فصل", "نام فصل", "مبنا (اسفند ۱۴۰۳)", "سه‌ماهه اول", "سه‌ماهه دوم", "سه‌ماهه سوم", "سه‌ماهه چهارم"],
    );
    for (const ch of ib.chapters_abnieh ?? []) {
      sh.push([ch.chapter ? faDigits(ch.chapter) : "—", ch.name ?? "—",
               numCell(Number(ch.base_esfand_1403), 2), numCell(Number(ch.q1_1404), 2),
               numCell(Number(ch.q2_1404), 2), numCell(Number(ch.q3_1404), 2),
               numCell(Number(ch.q4_1404), 2)]);
    }
    sh.push([]);
    if (ix) {
      sh.push(
        ["", "بخش ۳ — ضریب تعدیل محاسبه‌شده برای دورهٔ هدف", "", "", "", "", ""],
        ["فصل", "ضریب تعدیل", "شاخص دورهٔ هدف", "نوع شاخص", "وضعیت", "منبع", ""],
      );
      for (const ch of ix.chapters) {
        sh.push([faDigits(ch.chapter ?? "—"),
                 ch.factor == null ? "—" : faFloat(ch.factor, 4),
                 ch.level == null ? "—" : numCell(ch.level, 2),
                 ch.kind ?? "—", ch.kind === "موقت" ? "موقت" : "قطعی",
                 ch.source ?? "—", ""]);
      }
      sh.push(["", "یادداشت",
               `دورهٔ مبنا: ${ix.basePeriod ?? "—"} — دورهٔ هدف: ${ix.targetPeriod ?? "—"}${ix.provisional ? " — شامل شاخص موقت است" : " — تمام شاخص‌ها قطعی"}`,
               "", "", "", ""]);
    } else {
      sh.push(["", "یادداشت",
               "دورهٔ هدف برابر دورهٔ مبنا (اسفند ۱۴۰۳) است — ضریب همهٔ فصل‌ها ۱ و شاخص تعدیل غیرفعال است (کلیات بند ۲۲). برای فعال‌سازی، دورهٔ هدف را در تنظیمات انتخاب کنید.",
               "", "", "", ""]);
    }
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(sh, [8, 24, 18, 18, 18, 18, 40]), "شاخص‌ها");
  }

  // ── برگه: منابع و بخشنامه‌ها ──
  {
    const ib = INDEX_BULLETINS as any;
    const sh: Cell[][] = [
      ...headerBlock(meta),
      ["شناسه", "نوع", "عنوان / موضوع", "شماره / مرجع", "تاریخ", "وضعیت", "محل استفاده در برنامه"],
    ];
    for (const [sid, typ, ttl, ref, dt, sts, use] of SOURCES) {
      sh.push([sid, typ, ttl, ref, dt, sts, use]);
    }
    sh.push(
      [],
      ["", "بخش ۲ — ارجاع ردیف‌های قیمت به فهرست‌بهای ۱۴۰۴", "", "", "", "", ""],
      ["کد", "ارجاع", "", "", "", "", ""],
    );
    for (const code of Object.keys(PRICE_REFS).sort()) {
      sh.push([code, PRICE_REFS[code], "", "", "", "", ""]);
    }
    sh.push(
      [],
      ["", "بخش ۳ — بندهای پیوست ۳ بخشنامه ۱۴۰۵/۱۵۵۲۳۳", "", "", "", "", ""],
      ["بند", "متن بند", "", "", "", "صفحه", ""],
    );
    for (const rl of ib.rules ?? []) {
      sh.push([rl.clause ?? "—", rl.text ?? "", "", "", "", faDigits(rl.page ?? 1), ""]);
    }
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(sh, [8, 14, 32, 30, 14, 26, 34]), "منابع و بخشنامه‌ها");
  }

  // ── برگه: خلاصه و وضعیت (صفحهٔ اول) ──
  {
    const sh: Cell[][] = [
      ...headerBlock(meta),
      ["", "بخش ۱ — وضعیت گزارش", "", ""],
      ["", "وضعیت کلی", st.complete ? "کامل" : "ناقص",
       `خطا: ${faDigits(st.errors ?? 0)} — هشدار: ${faDigits(st.warningsN ?? 0)} — اطلاع: ${faDigits(st.info ?? 0)} (جزئیات در شیت «هشدارها»)`],
      ["", "نوع خروجی", meta.reportType ?? "—",
       "اگر «پیش‌نویس» است، حداقل یک ردیف «نیازمند ورود» قیمت دارد (شیت «قیمت‌های دستی»)"],
      ["", "مبنای قیمت‌گذاری", "فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴",
       "سازمان برنامه و بودجه — واحد پول: ریال"],
      ["", "تعداد ردیف‌های متره",
       `${faDigits(result.lines?.length ?? 0)} ردیف`,
       "جزئیات کمیت و قیمت هر ردیف در شیت «متره ریز»"],
      [],
      ["", "بخش ۲ — شمارش وضعیت قیمت‌ها", "", ""],
      ["", "وضعیت قیمت", "تعداد ردیف", "شرح"],
    ];
    for (const k of MANUAL_STATUSES) {
      sh.push(["", k, faDigits(pss[k] ?? 0), PRICE_STATUS_DESC[k] ?? ""]);
    }
    const npe = result.needsPriceEntry ?? 0;
    if (npe) {
      sh.push(["", "پیام", `${faDigits(npe)} ردیف نیازمند ورود قیمت`,
               "خروجی تا تأیید این ردیف‌ها «پیش‌نویس» است"]);
    }
    sh.push(
      [],
      ["", "بخش ۳ — وضعیت ضرایب", "", ""],
      ["", "ضریب", "مقدار / وضعیت", "منبع و بند مرجع"],
      ["", "ضریب طبقات (P)",
       `${faFloat(fl.value ?? 1.0, 4)} — ${st.floorsStatus ?? "—"}`,
       "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — فرمول P (محاسبهٔ کامل در شیت «ضریب طبقات»)"],
      ["", "ضریب منطقه‌ای",
       `${faFloat(rg.value ?? 1.0, 4)} — ${st.regionalStatus ?? "—"}`,
       rg.source ?? "تنظیم دستی کاربر"],
      ["", "ضریب بالاسری", faFloat(settings.overheadCoef ?? 1.0, 4),
       "تنظیم کاربر — پیش‌فرض ۱٫۳ (عمرانی + مناقصه) — دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸"],
      ["", "تجهیز و برچیدن کارگاه", faFloat(settings.siteSetupAmount ?? 0.0, 0),
       "مبلغ مستقیم (ریال) — سقف ۴٪ صرفاً هشدار است"],
    );
    if (ix) {
      sh.push(["", "شاخص تعدیل فهرست‌بها", `فعال — ${ix.targetPeriod ?? "—"}`,
               `کلیات بند ۲۲ — ${ix.provisional ? "شامل شاخص موقت است" : "تمام شاخص‌ها قطعی"} (جزئیات در شیت «شاخص‌ها»)`]);
    } else {
      sh.push(["", "شاخص تعدیل فهرست‌بها", "غیرفعال",
               "دورهٔ هدف = دورهٔ مبنا (اسفند ۱۴۰۳) — همهٔ ضرایب ۱ (کلیات بند ۲۲)"]);
    }
    sh.push(
      [],
      ["", "بخش ۴ — خلاصهٔ مالی", "", ""],
      ["", "شرح", "مبلغ (ریال)", "یادداشت"],
      ["", "جمع ردیف‌ها (به قیمت فهرست‌بها)", moneyCell(result.baseTotal ?? 0), ""],
      ["", "ناخالص پرداختی (با ضرایب + تجهیز)", moneyCell(result.grossPayable ?? 0), ""],
      ["", "جمع نهایی صورت‌وضعیت", moneyCell(result.grandTotal ?? 0), ""],
      ["", "خالص پرداختی (پس از کسورات قانونی)", moneyCell(result.netPayable ?? 0), ""],
      ["", "تفصیل کامل زنجیرهٔ مالی در شیت «خلاصهٔ مالی و برآورد»", "",
       "مبلغ به حروف نیز در همان شیت"],
      [],
      ["", "بخش ۵ — فهرست برگه‌ها", "", ""],
      ["شماره", "نام برگه", "شرح کوتاه", "وضعیت"],
    );
    const adj0 = (result as any).adjustment ?? {};
    const hasTadil = !!(adj0.tadil);
    const hasBaravord = !!(adj0.baravord);
    // حضور برگه‌ها قطعی است (۱۶ برگهٔ پایه همیشه + ۳ برگهٔ موتور):
    // مستقل از ترتیبِ ساخته‌شدن، مانند app.py.
    const enginePresent: Record<string, boolean> = {
      "تعدیل پیمان": hasTadil,
      "برآورد به‌هنگام": hasBaravord,
      "بخش قطعی و علی‌الحساب": hasTadil,
    };
    const present = new Set(SHEET_ORDER.filter((n) => enginePresent[n] ?? true));
    for (let i = 0; i < SHEET_INDEX.length; i++) {
      const [nm, ds] = SHEET_INDEX[i];
      sh.push([faDigits(i + 1), nm, ds, present.has(nm) ? "فعال" : "موتور خاموش"]);
    }
    XLSX.utils.book_append_sheet(wb, sheetFromAoA(sh, [8, 42, 22, 46]), "خلاصه و وضعیت");
  }

  // ═════════ مرتب‌سازی برگه‌ها به ترتیب رسمی (فاز D) ═════════
  const sheetRank = new Map(SHEET_ORDER.map((n, i) => [n, i]));
  wb.SheetNames.sort(
    (a, b) => (sheetRank.get(a) ?? SHEET_ORDER.length) - (sheetRank.get(b) ?? SHEET_ORDER.length),
  );

  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  XLSX.writeFile(wb, `SooratVaziat_${sanitizeName(meta.projectName || "Project")}_Shomare_${meta.reportNo || "0"}_${stamp}.xlsx`);
}

function sanitizeName(s: string): string {
  return s.replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 50);
}
function round0(n: number): number {
  return Math.round(n);
}
function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
function unitFa(u: string): string {
  return { m3: "مترمکعب", m2: "مترمربع", kg: "کیلوگرم", m: "مترطول", count: "عدد" }[u] ?? u;
}
function matchLabel(m: string): string {
  return {
    "rule-exact": "قانون + کد دقیق",
    "rule-fuzzy": "قانون فازی",
    fuzzy: "فازی",
    manual: "دستی",
    "direct-code": "کد مستقیم",
  }[m] ?? m;
}
