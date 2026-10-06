// ─────────────────────────────────────────────────────────────
// فاز E-۵ — ثبت تغییرات ورودی‌های پروژه در سابقهٔ ویرایش
// (آینهٔ کمک‌توابعِ _audit_sig/_audit_snap/_audit_diff_apply در app.py)
//
// هر تغییرِ تنظیمات یا مشخصاتِ پیمان در رجیستریِ سابقهٔ ویرایش ثبت
// می‌شود. کلیدهای ورودیِ دستیِ قیمت (که رویداد اختصاصیِ خود را دارند) و
// خودِ priceAudit (که خود سابقه است) از این تفاضل مستثنی‌اند.
// ─────────────────────────────────────────────────────────────
import type { AuditEntry, AuditKind } from "./types";

export const SETTING_LABELS: Record<string, string> = {
  joistSpacing: "فاصلهٔ محور تیرچه",
  haulDistanceKm: "مسافت حمل مصالح",
  concreteStrengthMpa: "مقاومت بتن‌ها",
  leanCementKg: "بتن مگر",
  joistBlockThicknessCm: "ضخامت تیرچه‌بلوک",
  joistBlockConcreteMpa: "مقاومت بتن سقف",
  joistBlockTopThicknessCm: "ضخامت بتن روی بلوک",
  slabFormworkHeightM: "ارتفاع طبقه برای قالب‌بندی",
  surchargeRebarDensity: "اضافه‌بهای چگالی میلگرد",
  surchargeReinforcedConcrete: "اضافه‌بهای بتن مسلح",
  surchargeThinConcrete: "اضافه‌بهای بتن کف‌سازی",
  overheadCoef: "ضریب بالاسری",
  regionalCoef: "ضریب منطقه‌ای",
  regionalSelection: "انتخاب منطقه",
  rebarManualWeight: "وزن دستی میلگرد",
  floorsCoef: "ضریب طبقات",
  floorsAuto: "محاسبهٔ خودکار ضریب طبقات",
  floorsData: "مساحت طبقات",
  floorsDivisor: "مخرج فرمول ضریب طبقات",
  floorsExcludedChapters: "فصول مستثنی از ضریب طبقات",
  floorsRoofLevels: "ترازهای بام",
  siteSetupAmount: "تجهیز و برچیدن کارگاه",
  insurancePct: "بیمه",
  taxPct: "مالیات",
  goodJobPct: "حسن انجام کار",
  advancePayment: "پیش‌پرداخت",
  indexTargetPeriod: "دورهٔ هدف شاخص",
  currency: "واحد پول نمایش",
  rounding: "رند کردن مبالغ",
  priceUser: "نام کاربر واردکنندهٔ قیمت‌ها",
  priceDiffWarnPct: "آستانهٔ هشدار اختلاف قیمت",
  fehrestYear: "سال فهرست‌بهای پروژه",
  fehrestDbYear: "سال فهرست بارگذاری‌شده",
  tadilEnabled: "فعال بودن موتور تعدیل",
  baravordEnabled: "فعال بودن موتور برآورد",
  proposalDate: "تاریخ تسلیم پیشنهاد",
  proposalDeadline: "مهلت تسلیم پیشنهاد",
  proposalCoef: "ضریب پیشنهادی پیمانکار",
  aBasis: "مبنای مبلغ پایه",
  chapterIndexManual: "شاخص دستی فصول",
  disciplineIndexManual: "شاخص دستی رشته",
  provisionalCoef1405q1: "ضریب موقت ۱۴۰۵Q1",
  tadilCoef: "ضریب k تعدیل",
  completedWithinTerm: "وضعیت اتمام کار در مدت پیمان (الزامی — تبصرهٔ ۲)",
  coefRounding2080: "گردکردن ضریب تعدیل (بند ۸-۲)",
  negativeCoefRounding: "جهت گردکردن ضرایب منفی (D-04 — بخشنامه ساکت است)",
  baseIndexMethod: "روش شاخص مبنا (بند ۱-۶)",
  finalOfferDate: "تاریخ پیشنهاد نهایی (ترک تشریفات)",
  contractDurationMonths: "مدت اولیهٔ پیمان (ماه — بند ۲-۵)",
  contractExtensions: "تمدیدهای مدت پیمان (بند ۲-۵)",
  contractStatus: "وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷)",
  faultDeductionOnNegative: "کسر ۵٪ در فسخ با قصور، حتی با تعدیل منفی",
  contractInitialAmount: "مبلغ اولیهٔ پیمان (ریال)",
  indexMethod: "مسیر شاخص تعدیل (بندهای ۲-۱/۲-۲)",
  lastProvisionalDate: "تاریخ آخرین صورت‌وضعیت موقت (بند ۲-۶)",
  provisionalDiffMethod: "روش شاخصِ مابه‌التفاوتِ آخرین موقت و قطعی (بند ۲-۶)",
  tadilIoPeriod: "دورهٔ Io تعدیل",
  tadilItPeriod: "دورهٔ It تعدیل",
  tadilAdvanceMode: "حالت پیش‌پرداخت تعدیل",
  tadilDelayMode: "حالت تأخیر تعدیل",
  tadilDelayDate: "تاریخ تحویل قرارداد",
  tadilAllowNegative: "اجازهٔ تعدیل منفی",
  tadilApproved: "تأیید موتور تعدیل",
  baravordIoPeriod: "دورهٔ Io برآورد",
  baravordItPeriod: "دورهٔ It برآورد",
  baravordApproved: "تأیید موتور برآورد",
  workPeriodStart: "شروع دورهٔ انجام کار",
  workPeriodEnd: "پایان دورهٔ انجام کار",
  demoMode: "حالتِ نمایشی (واترمارکِ «نسخهٔ نمایشی»)",
};

export const META_LABELS: Record<string, string> = {
  projectName: "نام پروژه",
  employer: "کارفرما",
  contractor: "پیمانکار",
  consultant: "مشاور",
  contractNo: "شماره پیمان",
  contractDate: "تاریخ پیمان",
  location: "محل پروژه",
  reportNo: "شماره گزارش",
  reportType: "نوع گزارش",
  periodStart: "شروع دورهٔ گزارش",
  periodEnd: "پایان دورهٔ گزارش",
};

// کلیدهایی که رویداد اختصاصیِ خود را دارند یا خودِ سابقه‌اند.
const AUDIT_DIFF_EXCLUDE = new Set([
  "priceAudit",
  "manualPrices",
  "manualCodes",
  "excluded",
  "starredRows",
  "priceProjectFile",
]);

/** اثرِ پایدارِ یک مقدار برای مقایسهٔ تغییرات (شامل مقادیر تودرتو). */
export function auditSig(v: unknown): string {
  try {
    return JSON.stringify(v, (_k, x) => (typeof x === "bigint" ? String(x) : x)) ?? "undefined";
  } catch {
    return String(v);
  }
}

/** snapshotِ کلید→اثر، برای مقایسه با پس از تغییرات. */
export function auditSnap<T extends object>(obj: T): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (k.startsWith("_") || AUDIT_DIFF_EXCLUDE.has(k)) continue;
    out[k] = auditSig(v);
  }
  return out;
}

type AuditEntrySeed = Omit<AuditEntry, "at" | "user">;

/** تفاوتِ یک شیء (settings/meta) با snapshotِ قبل از تغییر. */
export function diffAuditEntries<T extends object>(
  before: Record<string, string>,
  after: T,
  kind: AuditKind,
  labels: Record<string, string>,
  scope: string,
): AuditEntrySeed[] {
  const out: AuditEntrySeed[] = [];
  for (const [k, v] of Object.entries(after)) {
    if (k.startsWith("_") || AUDIT_DIFF_EXCLUDE.has(k)) continue;
    if (!(k in before)) continue;
    const sig = auditSig(v);
    if (before[k] !== sig) {
      out.push({
        item: scope,
        field: labels[k] ?? k,
        old: before[k],
        new: sig,
        source: "تغییر از رابط کاربری",
        kind,
      });
    }
  }
  return out;
}
