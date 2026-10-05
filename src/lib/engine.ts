// ─────────────────────────────────────────────────────────────
// موتور متره: تجمیع کمیت‌ها، تطبیق با فهرست‌بها،
// اعمال پرت و ضرایب، تولید خلاصه‌متره، لیستوفر و گزارش کیفیت
// ─────────────────────────────────────────────────────────────
import {
  CONCRETE_STRENGTH_CODES,
  JOIST_BLOCK_STRENGTH_SURCHARGE,
  JOIST_BLOCK_THICKNESS_CODES,
  LEAN_CEMENT_CODES,
  SLAB_FORMWORK_CODES,
} from "./types";
import type {
  BoqLine,
  CoefsReport,
  FehrestRow,
  IndexReport,
  MatchMethod,
  MappingData,
  ProjectResult,
  ProjectSettings,
  ProjectStatus,
  QualityReport,
  QuantityRecord,
  RebarLine,
  RevitTable,
  Warning,
  ManualPriceRecord,
  ExcludedRecord,
} from "./types";
import { MANUAL_STATUSES } from "./types";
import type { AuditKind } from "./types";
import { IndexTable } from "./indices";
import { computeFloorsCoef, computeRegionalCoef, leanFootprint, faFloat } from "./floors";
import { jalaliNowStr } from "./farsi";
import { runAdjustment, haulTargetChapter, isHaulUnit } from "./adjustment";
import { byCode, searchFehrest } from "./matching";
import { toQuantityRecords, structuralGroup, rebarListGroup, rebarListMark } from "./revitParser";
import { chapterTitle } from "../data/fehrest";
import { normalizeText, rebarUnitWeight, faDigits } from "./normalize";
// جداول پیکربندی مشترک پایتون/TypeScript (یک منبع واحد)
import REBAR_DENSITY_CFG from "../../config/rebar_density_thresholds.json";

export function defaultSettings(): ProjectSettings {
  return {
    joistSpacing: 0.55, // فاصلهٔ محور تا محور تیرچه (متر)
    haulDistanceKm: 50, // مسافت حمل مصالح (km) — بازهٔ ۳۰–۷۵ → ردیف ۲۸۰۱۰۱
    surchargeRebarDensity: false, // اضافه‌بهای ۰۸۰۳۱۱ (سختی ارتعاش بتن) — اختیاری
    surchargeReinforcedConcrete: false, // اضافه‌بهای ۰۸۰۳۱۰ (بتن مسلح، per-element) — اختیاری
    surchargeThinConcrete: false, // اضافه‌بهای ۰۸۰۳۰۴ (کف‌سازی ≤ ۱۵cm روی زمین) — اختیاری
    // ── فرض‌های فنی: کد و بهای ردیف بتن/سقف از این مقادیر ساخته می‌شود ──
    concreteStrengthMpa: {
      foundation: 20, // پی
      columnBeam: 30, // ستون و تیر
      slab: 25, // سقف
      stair: 20, // پله
    },
    leanCementKg: 150, // بتن مگر: ۱۰۰ → ۰۸۰۱۰۱، ۱۵۰ → ۰۸۰۱۰۲
    joistBlockThicknessCm: 25, // سقف تیرچه‌بلوک: ۲۵ → ۱۰۰۳۰۵، ۳۰ → ۱۰۰۳۰۶
    joistBlockConcreteMpa: 25, // مقاومت بتن سقف تیرچه‌بلوک: ۲۰ → بدون اضافه‌بها، ۲۵ → ۱۰۰۷۰۱، ۳۰ → ۱۰۰۷۰۲
    joistBlockTopThicknessCm: 5, // ضخامت بتن روی بلوک طبق مشخصات (cm) — مازاد بر ۵ cm جداگانه
    slabFormworkHeightM: 3.5, // ارتفاع طبقه برای قالب‌بندی دال/تاوه (ایراد ۲): ۳٫۵ → ۰۶۰۴۰۱
    rebarManualWeight: {}, // وزن دستی میلگرد هر گروه (ایراد ۱۴): خالی → وزن مدل Revit
    // ── زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸) ──
    // ترتیب: جمع ردیف‌ها × طبقات × بالاسری × منطقه‌ای + تجهیز و برچیدن.
    // هیچ ضریب «پرت مصالح» وجود ندارد (کلیات بند ۳ و ۱۴ و فصل ۸ بند ۴:
    // افت تراکم و اتلاف حمل/تخلیه در بهای واحد ردیف‌ها لحاظ شده است).
    overheadCoef: 1.3, // عمرانی + مناقصه (پروژهٔ ابنیه) — سایر حالت‌ها در UI
    // ضریب منطقه‌ای (ایراد ۴): null → جستجو در جدول بخشنامه ۹۴/۶۹۴۱۶.
    // پروژهٔ مرجع: گلستان/گرگان/بخش مرکزی/ابنیه = ۱٫۰۴ (ردیف ۲۰).
    regionalCoef: null,
    regionalSelection: { province: "گلستان", city: "گرگان", district: "مرکزی", discipline: "ابنیه" },
    // ضریب طبقات (ایراد ۳): floors_auto=True → فرمول پیوست ۲ از مساحت طبقات.
    floorsCoef: 1.0, floorsAuto: true, floorsData: {},
    // مخرج فرمول پیوست ۲: «100×S» (متن رسمی دریافت‌شده) یا «S» (مغایر متن).
    floorsDivisor: "100×S",
    // فصول مستثنی از ضریب طبقات (پیوست ۲ بند ۱-۳: فقط کار ساختمان)؛
    // فصل ۲۸ (حمل و نقل) + فصل ۳۰ به بالا (محوطه‌سازی) مشمول نیستند.
    floorsExcludedChapters: ["28"],
    // ترازهای بام/مرجع که از فرمول ضریب طبقات مستثنی‌اند (طبقه نیستند).
    floorsRoofLevels: ["Story6"],
    siteSetupAmount: 0, // مبلغ تجهیز و برچیدن کارگاه (ریال) — ورودی کاربر
    // ── کسورات قانونی: فقط برای خروجی جداگانهٔ «خالص پرداختی» ──
    insurancePct: 7.8,
    taxPct: 5,
    goodJobPct: 10,
    advancePayment: 0,
    // ── شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) ──
    // null یا «» → دورهٔ مبنا (بدون تعدیل). دورهٔ هدف از indices/abnieh.json.
    indexTargetPeriod: null,
    // ── نمایش ──
    currency: "rial",
    rounding: true,
    manualCodes: {},
    priceOverrides: {},
    manualPrices: {},
    excluded: [],
    starredRows: [],
    priceAudit: [],
    priceUser: "",
    priceDiffWarnPct: 30,
    priceProjectFile: "",
    // ── فاز E-۵: پروفایل پروژه ──
    fehrestYear: "۱۴۰۴", // سال فهرست‌بهای انتخابیِ این پروژه
    fehrestDbYear: "۱۴۰۴", // سال فهرستِ بارگذاری‌شده
    // ═══ فاز B: دو موتور مجزای تعدیل (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند) ═══
    tadilEnabled: false, // موتور ۱: تعدیل پیمان (فصل به فصل)
    baravordEnabled: false, // موتور ۲: برآورد به‌هنگام
    proposalDate: "", // تاریخ تسلیم پیشنهاد → Io (الزامی برای موتور تعدیل)
    proposalDeadline: "", // مهلت تسلیم پیشنهاد → Io (۱۴۴۳۷۴: تابستان ۱۴۰۵)
    proposalCoef: 1.0, // ضریب پیشنهادی پیمانکار — دستی، نیازمند تأیید
    // مبنای A: «با ضرایب» = قیمت پیمان؛ ۱۰۱/۱۷۳۰۷۳ تصویری است ⇒ حدس زده
    // نمی‌شود. پیش‌فرض «با ضرایب» (درخواست کاربر).
    aBasis: "با ضرایب",
    chapterIndexManual: {}, // شاخص دستی هر فصل (دستی مقدم بر پیوست ۳)
    disciplineIndexManual: {}, // شاخص دستی رشته (بند ۴)
    // شاخص موقت ۱۴۰۵Q1 = این ضریب × آخرین قطعی. منبع: ۱۴۴۳۷۳ (تصویری)
    // ⇒ پیش‌فرض خالی و موتورها در صورت نیاز می‌ایستند.
    provisionalCoef1405q1: null,
    // فاز E-6: k از completedWithinTerm مشتق می‌شود (بند ۱-۸ و تبصرهٔ ۲).
    tadilCoef: 0.95, // فقط سازگاری پروفایل‌های قدیمی — k اکنون مشتق می‌شود
    completedWithinTerm: null,
    coefRounding2080: true,
    // فاز E-6 Part C: ورودی‌های قرارداد (بخشنامهٔ ۲۰۸۰)
    baseIndexMethod: "proposal_period", // بند ۱-۶-۱ دوم (رفتار فعلی)
    finalOfferDate: "", // ترک تشریفات: پیشنهاد نهایی کتبی (۱-۶-۱ دوم)
    contractDurationMonths: null, // بند ۲-۵
    contractExtensions: [], // بندهای ۲-۵-۱..۲-۵-۳
    contractStatus: "فعال", // بندهای ۶ و ۷
    faultDeductionOnNegative: false, // بند ۷ — تفسیر (ACCEPTANCE §۱۸-۳)
    contractInitialAmount: null, // مبلغ اولیه (۲-۱/۲-۲ و سقف ۱۰٪)
    indexMethod: "گروهی", // بند ۲-۲ (پروژهٔ مرجع)
    newItemMethod: "فهرست پیمان", // گام ۵: بندهای ۳-۱..۳-۵
    newItemAmount: 0, // مبلغ کار جدید (ریال)
    newItemAmountAttached: 0, // فقط ۳-۴: بخشِ ۳-۱
    newItemBasePeriod: "", // کلید سه‌ماههٔ شاخصِ مبنا (مثل 1404Q2)
    lastProvisionalDate: "", // بند ۲-۶
    provisionalDiffMethod: "average", // تبصرهٔ ۱ بند ۲-۶
    contractDate: "", // فاز E-6 Part C: تاریخ شروع پیمان (از meta همگام)
    tadilIoPeriod: "base",
    tadilItPeriod: "q4",
    tadilAdvanceMode: "کل مبلغ کارکرد",
    tadilDelayMode: "مشمول کل دوره",
    tadilDelayDate: "",
    tadilAllowNegative: true,
    tadilApproved: false, // تا تأیید، خروجی «پیش‌نویس» است
    baravordIoPeriod: "base",
    baravordItPeriod: "q4",
    baravordApproved: false,
    workPeriodStart: "",
    workPeriodEnd: "",
  };
}

// ─────────────────────────────────────────────────────────────
// طرح‌های قاعده‌محور: هر طرح می‌گوید کدام رکوردها با کدام ردیف
// فهرست‌بها قیمت می‌شوند. «query» شرح استاندارد ردیف است که در
// فهرست‌بهای آپلودی جست‌وجوی فازی می‌شود.
// ─────────────────────────────────────────────────────────────
interface Plan {
  id: string;
  targetCode: string; // کد پیش‌فرض در صورت نبودن فهرست آپلودی
  fallbackDesc: string;
  fallbackUnit: string;
  fallbackPrice: number;
  query: string; // متن مرجع جست‌وجوی فازی
  collect: (ctx: Ctx) => { qty: number; sources: QuantityRecord[]; note?: string };
}

interface Ctx {
  records: QuantityRecord[];
  tables: RevitTable[];
  settings: ProjectSettings;
  /** مرجع المان‌های سقف تیرچه‌بلوک (از جدول Joist Floor Schedule) */
  joistRefs: Set<string>;
}

/**
 * مجموعهٔ مرجع المان‌های سقف تیرچه‌بلوک (از جدول Joist Floor Schedule).
 *
 * این المان‌ها طبق بند ۳ الزامات عمومی فصل دهم، شامل شمع‌بندی، داربست،
 * قالب‌بندی و بتن‌ریزی هستند و نباید ردیف بتن/قالب جداگانه تولید کنند.
 * مرجعِ «تیرچه رویی» (مثل JSL-TOP01) جزو این مجموعه نیست — یک دال مستقل
 * است و بتن آن جداگانه حساب می‌شود. منطبق با app.py:TechnicalOfficeEngine._joist_floor_refs.
 */
export function joistFloorRefs(tables: RevitTable[]): Set<string> {
  const refs = new Set<string>();
  for (const t of tables) {
    if (t.kind !== "joist_floor") continue;
    for (const r of t.rows) {
      if (r.isSubtotal) continue;
      const mk = (r.texts.mark ?? "").trim();
      if (mk && mk !== "—") refs.add(mk);
    }
  }
  return refs;
}

/**
 * مرجع المان‌های «رویهٔ روی سقف تیرچه‌بلوک» (روشناژ JSL-TOP*).
 *
 * طبق بند ۹ الزامات عمومی فصل دهم، بتن تا ۵ cm روی بلوک داخل نرخ ۱۰۰۳۰۵
 * است؛ حجم رویه که معادل همان ۵ cm باشد (۰٫۰۵ × مساحت ۱۰۰۳۰۵) از ردیف بتن
 * جداگانه کسر می‌شود و فقط مازاد بر آن در ۰۸۰۱۰۶ می‌ماند.
 * منططبق با app.py:TechnicalOfficeEngine._joist_topping_refs.
 */
export function joistToppingRefs(tables: RevitTable[]): Set<string> {
  const refs = new Set<string>();
  for (const t of tables) {
    if (t.kind !== "structural_concrete") continue;
    for (const r of t.rows) {
      if (r.isSubtotal) continue;
      const mk = (r.texts.mark ?? "").trim();
      if (mk && mk.toUpperCase().startsWith("JSL-TOP")) refs.add(mk);
    }
  }
  return refs;
}

/**
 * کل مرجع المان‌های سیستم سقف تیرچه‌بلوک: تیرچه‌ها + رویهٔ JSL-TOP*.
 *
 * مبنای کسر حجم JSL از پایهٔ اضافه‌بهای فصل ۸ (بند ۳-۵: ردیف‌های
 * ۰۸۰۳۰۱/۰۸۰۳۰۲/۰۸۰۳۰۴/۰۸۰۳۱۰/۰۸۰۳۱۱ به سقف تیرچه‌بلوک تعلق نمی‌گیرد).
 * منططبق با app.py:TechnicalOfficeEngine._joist_system_refs.
 */
export function joistSystemRefs(tables: RevitTable[]): Set<string> {
  return new Set<string>([...joistFloorRefs(tables), ...joistToppingRefs(tables)]);
}

/**
 * سقف تیرچه‌بلوک: بتن و قالب المان‌های تیرچه داخل نرخ ۱۰۰۳۰۵ است و نباید در
 * ردیف‌های بتن (۰۸۰۱۰۵..۰۸۰۱۰۷) یا قالب (فصل ۰۶) دوبار شمرده شود. فقط
 * رکوردهای structural_concrete/formwork_super مستثنی می‌شوند؛ بتن پاشنه
 * (joist_materials) سر جای خودش باقی می‌ماند.
 */
function notJoistElement(r: QuantityRecord, joistRefs: Set<string>): boolean {
  return !(joistRefs.has(r.ref) && (r.kind === "structural_concrete" || r.kind === "formwork_super"));
}

/**
 * جمع جبران‌شدهٔ Neumaier — تطبیق دقیق با `sum()` در Python ۳.۱۲.
 *
 * CPython ۳.۱۲ به‌ازای ورودی‌های float از الگوریتم Neumaier برای کاهش
 * خطای انباشتهٔ گردسازی استفاده می‌کند. `reduce` سادهٔ JS همین کار را
 * ترتیبی انجام می‌دهد و در مبالغ بزرگ (مثلاً جمع ۱۱۲ کمیت) در مرز
 * گرد کردنِ سطرها اختلافی در حد چند ULP ایجاد می‌کند که می‌تواند یک
 * رقم صحیح را تغییر دهد. هر دو زبان باید روی یک الگوریتم توافق کنند
 * تا خروجی‌ها bit-identical بمانند.
 */
export function neumaier(values: number[]): number {
  let total = 0;
  let comp = 0;
  for (const x of values) {
    const t = total + x;
    if (Math.abs(total) >= Math.abs(x)) comp += (total - t) + x;
    else comp += (x - t) + total;
    total = t;
  }
  return total + comp;
}

/**
 * تراکم میلگرد (kg/m³) = وزن آرماتور ÷ حجم بتن سازه‌ای.
 *
 * مبنای شرط ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴ (آستانهٔ ۱۸۰ kg/m³).
 */
export function rebarDensity(rebarKg: number, concreteM3: number): number {
  return concreteM3 > 0 ? rebarKg / concreteM3 : 0;
}

/**
 * آستانهٔ تراکم میلگرد در شرط ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴:
 * «...در صورتی که میلگرد به کار رفته بیش از ۱۸۰ کیلوگرم در مترمکعب بتن باشد».
 */
export const REBAR_DENSITY_THRESHOLD = 180;

/**
 * آستانهٔ ضخامت در شرط ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴:
 * «هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد» (بر حسب متر).
 */
export const THIN_CONCRETE_THRESHOLD_M = 0.15;

/**
 * حجم بتن با ضخامت ≤ ۱۵ سانتی‌متر (m³، خالص) — استخراج‌شده از داده‌ها.
 *
 * مبنای شرط ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴ (فصل ۸ بند ۳-۳): «اضافه‌بها به
 * ردیف‌های بتن‌ریزی، هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد».
 * این اضافه‌بها مختص «دال روی زمین» (بتن‌ریزی کف روی خاک) است و سقف‌های
 * معلق شامل نمی‌شوند. ضخامت فقط از داده‌های خود پروژه استخراج می‌شود:
 *
 * فقط ردیفی که در **جدول خودش** هم ستون «حجم» و هم ستون «مساحت» دارد
 * (مثل جداول بتن‌مگر و بتن‌ریزی پی) ارزیابی می‌شود → ضخامت = حجم ÷ مساحت.
 * ردیف‌های فاقد مساحتِ هم‌جدولی (دال‌های سقف، پله، تیر، ستون) هرگز ارزیابی
 * نمی‌شوند؛ جفت‌سازی با مساحت قالب‌بندی مجاز نیست چون کناره‌ها/پاها را شامل
 * می‌شود و دیگر نشانگر دال روی زمین نیست. منططبق با app.py:thin_concrete_net.
 */
export function thinConcreteNet(tables: RevitTable[]): number {
  let thin = 0;
  for (const t of tables) {
    if (t.kind !== "lean_concrete" && t.kind !== "structural_concrete") continue;
    for (const r of t.rows) {
      if (r.isSubtotal) continue;
      const v = r.values.volume ?? 0;
      const a = r.values.area ?? 0;
      if (v > 0 && a > 0 && v / a <= THIN_CONCRETE_THRESHOLD_M) thin += v;
    }
  }
  return thin;
}

const sum = (rs: QuantityRecord[], pred?: (r: QuantityRecord) => boolean) =>
  neumaier(rs.filter(pred ?? (() => true)).map((r) => r.qty));

const pick = (rs: QuantityRecord[], pred: (r: QuantityRecord) => boolean) => rs.filter(pred);

const isConcrete = (r: QuantityRecord) => r.kind === "structural_concrete";

/** کلید نرم‌الشدهٔ مرجع المان برای تطبیق بین Scheduleها؛ خالی/«—» نامعتبر است */
function foundationRefKey(ref: string | undefined): string | null {
  const r = (ref ?? "").trim();
  if (!r || r === "—") return null;
  return normalizeText(r);
}

/**
 * قرارداد تقدم منابع حجم بتن پی (فقط دامنهٔ foundation concrete):
 * جدول اختصاصی پی > جدول تجمیعی بتن > مقادیر استنتاجی از قالب‌بندی پی (per-ref fallback).
 * • رکوردهایی که ref آن‌ها در جدول بتن مگر آمده (kind === "lean_concrete") حذف می‌شوند.
 * • dedup فقط per-ref و در همین دامنه انجام می‌شود، نه سراسری روی کل پروژه.
 */
export function foundationCandidates(
  records: QuantityRecord[],
  tables: RevitTable[],
): { direct: QuantityRecord[]; derived: QuantityRecord[] } {
  const leanRefs = new Set<string>();
  for (const r of records) {
    if (r.kind !== "lean_concrete" || r.unit !== "m3") continue;
    const k = foundationRefKey(r.ref);
    if (k) leanRefs.add(k);
  }

  const cand = new Map<string, Map<string, QuantityRecord[]>>();
  const tableRows = new Map<string, number>();
  const tablePi = new Map<string, number>();
  for (const r of records) {
    if (r.kind !== "structural_concrete" || r.unit !== "m3") continue;
    const tkey = r.fileName;
    tableRows.set(tkey, (tableRows.get(tkey) ?? 0) + 1);
    if (r.group !== "پی") continue;
    tablePi.set(tkey, (tablePi.get(tkey) ?? 0) + 1);
    const k = foundationRefKey(r.ref);
    if (!k || leanRefs.has(k)) continue;
    const byTable = cand.get(k) ?? new Map<string, QuantityRecord[]>();
    const rows = byTable.get(tkey) ?? [];
    rows.push(r);
    byTable.set(tkey, rows);
    cand.set(k, byTable);
  }

  // جدول اختصاصی پی: تمام رکوردهای بتنی آن از گروه «پی» هستند
  const dedicated = new Set<string>();
  for (const [tkey, n] of tablePi) if (n === (tableRows.get(tkey) ?? 0)) dedicated.add(tkey);

  const rank = (tkey: string): [number, number, string] => [
    dedicated.has(tkey) ? 0 : 1,
    (tableRows.get(tkey) ?? 0) - (tablePi.get(tkey) ?? 0),
    tkey,
  ];

  const direct: QuantityRecord[] = [];
  const seen = new Set<string>();
  for (const [k, byTable] of cand) {
    const chosen = [...byTable.keys()].sort((a, b) => {
      const ra = rank(a);
      const rb = rank(b);
      return ra[0] - rb[0] || ra[1] - rb[1] || ra[2].localeCompare(rb[2]);
    })[0];
    direct.push(...(byTable.get(chosen) ?? []));
    seen.add(k);
  }

  const derived: QuantityRecord[] = [];
  for (const t of tables) {
    if (t.kind !== "formwork_foundation") continue;
    for (const row of t.rows) {
      if (row.isSubtotal) continue;
      const fam = row.texts.familyType ?? "";
      const m = fam.match(/(\d{3,4})\s*[x×]\s*(\d{3,4})/i);
      const lenM = row.values.length ?? 0;
      if (!m || !lenM) continue;
      const k = foundationRefKey(row.texts.mark);
      if (k && seen.has(k)) continue; // این المان از منبع مستقیم معتبر تأمین شده است
      derived.push({
        tableId: t.id,
        fileName: t.fileName,
        tableTitle: t.title,
        kind: t.kind,
        ref: row.texts.mark || fam,
        group: "پی",
        material: "CONCRETE",
        qty: lenM * (parseFloat(m[1]) / 1000) * (parseFloat(m[2]) / 1000),
        unit: "m3",
        detail: `حجم استنتاجی پی ${row.texts.mark ?? ""} (طول × ${m[1]}×${m[2]})`,
      });
    }
  }
  return { direct, derived };
}


/** طرح‌های تولید ردیف‌های متره‌ای */
export function buildPlans(settings: ProjectSettings): Plan[] {
  // کد، شرح و بهی ردیف‌های بتن و سقف تیرچه‌بلوک از فرض‌های فنی
  // پروژه (مقاومت فشاری به تفکیک گروه سازه‌ای، عیار سیمان بتن مگر،
  // ضخامت سقف) و جداول نگاشتِ ماژول ساخته می‌شوند — هیچ کد فهرست‌بهایی ثابت نیست.
  const strength = settings.concreteStrengthMpa;
  const leanKg = settings.leanCementKg ?? 150;
  const [leanCode, leanPrice] = LEAN_CEMENT_CODES[leanKg] ?? LEAN_CEMENT_CODES[150];
  const joistCm = settings.joistBlockThicknessCm ?? 25;
  const [joistCode, joistPrice] = JOIST_BLOCK_THICKNESS_CODES[joistCm] ?? JOIST_BLOCK_THICKNESS_CODES[25];
  // ارتفاع طبقه برای انتخاب ردیف قالب‌بندی دال (تاوه) — ایراد ۲
  const slabH = settings.slabFormworkHeightM ?? 3.5;
  const slabEntry =
    SLAB_FORMWORK_CODES.find(([t]) => slabH <= t) ??
    SLAB_FORMWORK_CODES[SLAB_FORMWORK_CODES.length - 1];

  // مقاومت فشاری مشخصهٔ یک گروه → کد، شرح و بهای ردیف فهرست‌بها
  const conc = (k: keyof typeof strength, d: number) => {
    const v = strength[k] ?? d;
    const [code, price] = CONCRETE_STRENGTH_CODES[v] ?? CONCRETE_STRENGTH_CODES[d];
    return {
      targetCode: code,
      query: `تهیه و اجرای بتن مقاومت فشاری مشخصه ${faDigits(v)} مگاپاسکال`,
      fallbackDesc: `تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته با مقاومت فشاری مشخصه ${faDigits(v)} مگاپاسکال`,
      fallbackPrice: price,
    };
  };

  return [
    // ── فصل ۰۸: بتن درجا ──
    // کد ردیف بتن مگر از عیار سیمان، و کد بتن المان‌ها از مقاومت فشاری
    // مشخصهٔ همان گروه (پی/ستون-تیر/سقف/پله) انتخاب می‌شود. جداول
    // نگاشت در سطح ماژول هستند (CONCRETE_STRENGTH_CODES و ...).
    {
      id: "lean",
      targetCode: leanCode,
      query: `تهیه و اجرای بتن با ${faDigits(leanKg)} کیلوگرم سیمان`,
      fallbackDesc: `تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته، با ${faDigits(leanKg)} کیلوگرم سیمان در مترمکعب بتن`,
      fallbackUnit: "مترمکعب",
      fallbackPrice: leanPrice,
      collect: ({ records }) => {
        const src = pick(records, (r) => r.kind === "lean_concrete" && r.unit === "m3");
        return { qty: sum(src), sources: src };
      },
    },
    {
      id: "conc-foundation",
      ...conc("foundation", 20),
      fallbackUnit: "مترمکعب",
      collect: ({ records, tables, joistRefs }) => {
        // قرارداد تقدم منابع: هر المان پی فقط از یک منبع (اختصاصی > تجمیعی > استنتاجی)
        const { direct, derived } = foundationCandidates(records, tables);
        const src = [...direct, ...derived].filter((r) => notJoistElement(r, joistRefs));
        return {
          qty: sum(src),
          sources: src,
          note:
            derived.length > 0 && direct.length === 0
              ? "حجم پی‌ها به‌صورت استنتاجی از ابعاد جدول قالب‌بندی پی محاسبه شد."
              : undefined,
        };
      },
    },
    {
      id: "conc-col-beam",
      ...conc("columnBeam", 30),
      fallbackUnit: "مترمکعب",
      collect: ({ records, joistRefs }) => {
        const isColBeam = (r: QuantityRecord) =>
          notJoistElement(r, joistRefs) &&
          isConcrete(r) &&
          (r.group === "ستون" || r.group === "تیر" || /COLUMN|BEAM|FRAMING/i.test(r.detail));
        const src = pick(records, isColBeam);
        return { qty: sum(src), sources: src };
      },
    },
    {
      id: "conc-slab",
      ...conc("slab", 25),
      fallbackUnit: "مترمکعب",
      collect: ({ records, joistRefs, tables, settings }) => {
        const floor = pick(
          records,
          (r) => notJoistElement(r, joistRefs) && isConcrete(r) && r.group === "سقف",
        );
        // ── بقایای سقف تیرچه‌بلوک (مرحلهٔ ۱۱) ──
        // بند ۳ فصل دهم: نرخ ۱۰۰۳۰۵ شامل تمام مصالح سقف به‌جز میلگرد است
        // → بتن پاشنهٔ تیرچه (joist_materials) دیگر به ۰۸۰۱۰۶ اضافه نمی‌شود.
        // بند ۹ فصل دهم: بتن تا ۵ cm روی بلوک داخل نرخ ۱۰۰۳۰۵ است →
        // معادل ۰٫۰۵ × مساحت ۱۰۰۳۰۵ از حجم رویهٔ JSL-TOP* کسر می‌شود و
        // فقط مازاد بر آن در این ردیف می‌ماند.
        const toppingRefs = joistToppingRefs(tables);
        const plain = floor.filter((r) => !toppingRefs.has(r.ref));
        const topping = floor.filter((r) => toppingRefs.has(r.ref));
        const toppingVol = neumaier(topping.map((r) => r.qty));
        const src: QuantityRecord[] = [...plain];
        let note: string | undefined;
        if (toppingVol > 0) {
          const jbLen = sum(records.filter((r) => r.kind === "joist_floor" && r.unit === "m"));
          const jbArea = jbLen * (settings.joistSpacing ?? 0.55);
          const allowance = 0.05 * jbArea;
          const deduct = Math.min(toppingVol, allowance);
          const share = toppingVol > 0 ? deduct / toppingVol : 0;
          for (const r of topping) {
            const adj: QuantityRecord = { ...r, qty: r.qty * (1 - share) };
            src.push(adj);
          }
          note =
            `شامل ${topping.length} المان رویهٔ سقف تیرچه‌بلوک ` +
            `(${toppingVol.toFixed(3)} m³) پس از کسر سهم داخل نرخ ۱۰۰۳۰۵ ` +
            `(${deduct.toFixed(3)} m³ = ۰٫۰۵ × ${jbArea.toFixed(3)} m² — بند ۹ فصل دهم)`;
        }
        return { qty: sum(src), sources: src, note };
      },
    },
    {
      id: "conc-stair",
      ...conc("stair", 20),
      fallbackUnit: "مترمکعب",
      collect: ({ records, joistRefs }) => {
        // در جداول Revit، بتن پله هم در Category اصلی و هم در Runs تکرار می‌شود؛ فقط Category اصلی
        const src = pick(
          records,
          (r) =>
            notJoistElement(r, joistRefs) &&
            isConcrete(r) &&
            r.group === "پله" &&
            !/^Stairs: Runs/i.test(r.ref) &&
            !/^Stairs: Runs/i.test(r.detail),
        );
        return { qty: sum(src), sources: src };
      },
    },
    // ── فصل ۰۶: قالب‌بندی ──
    {
      id: "form-foundation",
      targetCode: "060101",
      query: "قالب بندی با قالب فلزی پی ها و شناژهای پی",
      fallbackDesc: "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در پی\u200cها و شناژهای پی",
      fallbackUnit: "مترمربع",
      fallbackPrice: 1150000,
      collect: ({ records }) => {
        const src = pick(records, (r) => r.kind === "formwork_foundation" && r.unit === "m2");
        return { qty: sum(src), sources: src };
      },
    },
    {
      id: "form-column",
      targetCode: "060301",
      query: "قالب بندی با قالب فلزی ستون ها با مقطع چهارضلعی",
      fallbackDesc: "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در ستون\u200cها و شناژهای قائم با مقطع چهارضلعی",
      fallbackUnit: "مترمربع",
      fallbackPrice: 1750000,
      collect: ({ records, joistRefs }) => {
        const src = pick(
          records,
          (r) =>
            notJoistElement(r, joistRefs) &&
            r.kind === "formwork_super" && r.unit === "m2" && (r.group === "ستون" || /COLUMN/i.test(r.ref + r.detail) || /COLUMN/i.test(r.material)),
        );
        return { qty: sum(src), sources: src };
      },
    },
    {
      id: "form-beam",
      targetCode: "060501",
      query: "قالب بندی با قالب فلزی تیرها و شناژهای افقی",
      fallbackDesc: "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در تیرها و شناژهای افقی",
      fallbackUnit: "مترمربع",
      fallbackPrice: 1580000,
      collect: ({ records, joistRefs }) => {
        const src = pick(
          records,
          (r) =>
            notJoistElement(r, joistRefs) &&
            r.kind === "formwork_super" && r.unit === "m2" && (r.group === "تیر" || /FRAMING|BEAM/i.test(r.ref + r.detail)),
        );
        return { qty: sum(src), sources: src };
      },
    },
    {
      id: "form-stair",
      targetCode: "060701",
      query: "قالب بندی با قالب فلزی پله ها و رمپ ها",
      fallbackDesc: "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در پله\u200cها و رمپ\u200cها",
      fallbackUnit: "مترمربع",
      fallbackPrice: 1500000,
      collect: ({ records, joistRefs }) => {
        const src = pick(
          records,
          (r) =>
            notJoistElement(r, joistRefs) &&
            r.kind === "formwork_super" && r.unit === "m2" && (r.group === "پله" || /STAIR|RUNS/i.test(r.ref + r.detail)),
        );
        return { qty: sum(src), sources: src };
      },
    },
    // قالب‌بندی دال/تاوه مستقل (ایراد ۲): ردیف ۰۶۰۴۰۱..۰۶۰۴۰۴ بر اساس
    // ارتفاع طبقه — همانند سایر ردیف‌های فصل ۰۶. دال‌های رویهٔ سقف
    // تیرچه‌بلوک (JSL-TOP*) مشمول نرخ ۱۰۰۳۰۵ هستند و اینجا نمی‌آیند.
    {
      id: "form-slab",
      targetCode: slabEntry[1],
      query: "قالب بندی با قالب فلزی در تاوه ها دال ها",
      fallbackDesc: "تهیه وسایل و قالب\u200cبندی با استفاده از قالب فلزی در تاوه\u200cها (دال\u200cها)",
      fallbackUnit: "مترمربع",
      fallbackPrice: slabEntry[2],
      collect: ({ records, joistRefs, tables }) => {
        const toppingRefs = joistToppingRefs(tables);
        const src = pick(
          records,
          (r) =>
            notJoistElement(r, joistRefs) &&
            r.kind === "formwork_super" &&
            r.unit === "m2" &&
            r.group === "سقف" &&
            !toppingRefs.has(r.ref) &&
            !/JSL/i.test(r.ref),
        );
        return { qty: sum(src), sources: src };
      },
    },
    // ── فصل ۱۰: سقف تیرچه‌بلوک — کد از ضخامت انتخاب می‌شود ──
    {
      id: "joist-block",
      targetCode: joistCode,
      query: `اجرای سقف تیرچه و بلوک به ضخامت ${faDigits(joistCm)} سانتی متر`,
      fallbackDesc: `اجرای سقف تیرچه و بلوک به ضخامت ${faDigits(joistCm)} سانتی\u200cمتر با تیرچه پاشنه بتنی و بلوک پلی\u200cاستایرن منبسط\u200cشده، شامل تهیه تمام مصالح به استثنای میلگرد و تهیه تجهیزات لازم به طور کامل`,
      fallbackUnit: "مترمربع",
      fallbackPrice: joistPrice,
      collect: ({ records, settings }) => {
        const joists = pick(records, (r) => r.kind === "joist_floor" && r.unit === "m");
        const totalLen = sum(joists);
        const area = totalLen * settings.joistSpacing;
        // سطحمسقف از حیطهٔ یونولیت هم قابل استخراج است و در ریزمتره نمایش داده می‌شود
        return {
          qty: area,
          sources: joists,
          note: `مساحت = مجموع طول تیرچه‌ها (${totalLen.toFixed(1)} متر) × فاصلهٔ محور ${settings.joistSpacing} متر`,
        };
      },
    },
  ];
}

/** سینی‌بندی آرماتور بر اساس گرید فولاد و قطر */
function rebarBucket(diameter: number, grade: string): "070101" | "070201" | "070202" | "070203" {
  // قطر همواره بر حسب میلی‌متر تفسیر می‌شود. مقدار ستون «Bar Diameter» پس از
  // toSI بر حسب متر است (مثلاً 0.018)؛ چون قطر آرماتور همواره ≥ ۱ mm است،
  // هر مقدار کوچک‌تر از ۱ متر به میلی‌متر نرمال می‌شود تا آستانه‌های ۱۰/۱۸ mm
  // معنا بدهند. مسیر regex fallback از قبل mm است.
  let d = diameter || 0;
  if (d > 0 && d < 1) d *= 1000; // متر → میلی‌متر
  const g = normalizeText(grade).toUpperCase();
  const isPlain = /A.?I[^II]|2400|SMOOTH|SADEH/.test(g) && !/4000/.test(g);
  if (isPlain) return "070101";
  if (d <= 10) return "070201";
  if (d <= 18) return "070202";
  return "070203";
}

const REBAR_BUCKET_DESC: Record<string, { query: string; desc: string; price: number }> = {
  "070101": { query: "تهیه بریدن خم کردن کارگذاشتن میلگرد ساده", desc: "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد ساده از نوع AI با سیم‌پیچی لازم", price: 505000 },
  "070201": { query: "تهیه بریدن خم کردن کارگذاشتن میلگرد آجدار قطر تا ۱۰", desc: "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار AIII به قطر تا ۱۰ میلی‌متر با سیم‌پیچی لازم", price: 522000 },
  "070202": { query: "تهیه بریدن خم کردن کارگذاشتن میلگرد آجدار قطر ۱۲ تا ۱۸", desc: "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار AIII به قطر ۱۲ تا ۱۸ میلی‌متر با سیم‌پیچی لازم", price: 510000 },
  "070203": { query: "تهیه بریدن خم کردن کارگذاشتن میلگرد آجدار قطر ۲۰ به بالا", desc: "تهیه، بریدن، خم‌کردن و کارگذاشتن میلگرد آجدار AIII به قطر ۲۰ میلی‌متر و بیشتر با سیم‌پیچی لازم", price: 498000 },
};

/** استخراج لیستوفر آرماتور از جداول ریزمترهٔ میلگرد */
export function extractRebar(tables: RevitTable[], mapping?: MappingData): {
  lines: RebarLine[];
  bucketKg: Record<string, number>;
  bucketSources: Record<string, QuantityRecord[]>;
  warnings: string[];
} {
  const lines: RebarLine[] = [];
  const bucketKg: Record<string, number> = {};
  const bucketSources: Record<string, QuantityRecord[]> = {};
  const warnings: string[] = [];
  // مارک‌های آرماتور پوشش‌داده‌شده توسط Revit Schedule ها — برای جلوگیری از
  // دوباره‌شماری میلگردهای Mapping v1 که زیرمجموعهٔ همان Schedule ها هستند.
  const revitMarks = new Set<string>();

  // شمارش ردیف‌های فاقد مارک / گروه برای هشدار یکباره به ازای هر جدول
  // (ایراد ۱۱) — از پر شدن رجیستری با هشدارهای تکراری جلوگیری می‌کند.
  const noMark: Record<string, number> = {};
  const unknownGrp: Record<string, number> = {};

  for (const t of tables) {
    if (!["rebar_detailed", "rebar_joist", "rebar_connection"].includes(t.kind)) continue;
    // ستون خام «Schedule Mark» در جداول rebar_detailed داخل colMap نیست
    // (الگوی ^mark$ فقط هدرهای دقیق «Mark» را می‌گیرد)؛ برای dedup از
    // سلول خام خوانده می‌شود تا ساختار جدول تغییر نکند.
    const smIdx = t.headers.findIndex((h) => h.trim().toLowerCase() === "schedule mark");

    let rowsSum = 0;
    for (const row of t.rows) {
      if (row.isSubtotal) continue;
      const weight = row.values.weight ?? 0;
      if (weight <= 0) continue;

      const mark = row.texts.mark || row.texts.familyType || "—";
      let rMark = (row.texts.mark ?? "").trim();
      if (!rMark && smIdx >= 0) rMark = (row.cells[smIdx] ?? "").trim();
      if (rMark) revitMarks.add(normalizeText(rMark));
      const barType = row.texts.barType || row.texts.material || "";
      let diameter = row.values.diameter ?? 0;
      if (!diameter) {
        const dm = (barType + " " + mark).match(/[φΦ⌀]\s?(\d{1,2})/);
        if (dm) diameter = parseFloat(dm[1]);
      }
      const grade = row.texts.material || barType;
      const bucket = rebarBucket(diameter || 12, grade);
      const count = row.values.count ?? 0;
      const length = row.values.length ?? 0;
      // ستون‌های لیستوفر (ایراد ۱۱): مارک و گروه از میزبان، طبقه، طول هر
      // شاخص و وزن واحد. گروه هرگز «سایر» و مارک هرگز «—» نیست.
      const hostCat = (row.texts.hostCategory ?? "").trim();
      const [grp2, grpUnknown] = rebarListGroup(
        hostCat,
        rMark + " " + (row.texts.familyType ?? ""),
        t.kind,
      );
      const dispMark = rebarListMark(rMark, row.texts.familyType);
      if (dispMark === "بدون مارک") noMark[t.title] = (noMark[t.title] || 0) + 1;
      if (grpUnknown) unknownGrp[t.title] = (unknownGrp[t.title] || 0) + 1;

      lines.push({
        mark: dispMark,
        group: grp2,
        // گروه میزبان: ستون «Host Category» مبنای تشخیص بتن مسلح در ردیف
        // اختیاری ۰۸۰۳۱۰ است. در نبود آن (مثلاً جداول آرماتور تیرچه) از
        // گروه استخراج‌شدهٔ مارک استفاده می‌شود. گروه «سایر» (= نامعلوم)
        // به‌عنوان مدرک میزبان به‌شمار نمی‌آید.
        evidence: (() => {
          const grp = structuralGroup(mark + " " + (row.texts.familyType ?? ""), t.kind);
          if (hostCat && hostCat.toLowerCase() !== "<varies>")
            return structuralGroup(hostCat, t.kind);
          return grp !== "سایر" ? grp : "";
        })(),
        // مارک خام میزبان (ستون «Host Mark») — مبنای تراکم per-element در
        // ردیف اختیاری ۰۸۰۳۱۰ (بند ۳-۶ فصل ۸). مقدار «<varies>» نامعلوم است.
        hostMark: (() => {
          const hm = (row.texts.hostMark ?? "").trim();
          return hm && hm.toLowerCase() !== "<varies>" ? hm : "";
        })(),
        barType: barType.replace(/\[|\]/g, ""),
        diameter,
        steelGrade: /2400/.test(grade) ? "AI" : /4000/.test(grade) ? "AIII" : "—",
        shape: row.texts.shape || "",
        count: count || 1,
        totalLength: length,
        weight,
        priceCode: bucket,
        source: t.title,
        // ستون‌های لیستوفر (ایراد ۱۱):
        level: (row.texts.level ?? "").trim(),
        perBarLength: count ? length / count : 0,
        unitWeight: length ? weight / length : 0,
      });

      bucketKg[bucket] = (bucketKg[bucket] || 0) + weight;
      (bucketSources[bucket] ??= []).push({
        tableId: t.id,
        fileName: t.fileName,
        tableTitle: t.title,
        kind: t.kind,
        ref: mark,
        group: structuralGroup(mark, t.kind),
        material: grade,
        qty: weight,
        unit: "kg",
        detail: `${barType} × ${count || "—"} شاخه`,
      });
      rowsSum += weight;
    }

    // تطبیق با Grand total رسمی رویت (جلوگیری از نشت وزن)
    const gtW = t.grandTotal?.weight;
    if (gtW && rowsSum > 0 && gtW > rowsSum * 1.02) {
      const diff = gtW - rowsSum;
      const dominant =
        Object.entries(bucketKg).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "070202";
      bucketKg[dominant] = (bucketKg[dominant] || 0) + diff;
      (bucketSources[dominant] ??= []).push({
        tableId: t.id,
        fileName: t.fileName,
        tableTitle: t.title,
        kind: t.kind,
        ref: "سایر شاخه‌ها",
        group: "متفرقه",
        material: "—",
        qty: diff,
        unit: "kg",
        detail: `تراز با Grand total رسمی جدول (${gtW.toFixed(1)} kg) — ردیف‌های خارج از نمونهٔ خوانده‌شده`,
        fromGrandTotal: true,
      });
      warnings.push(
        `جدول «${t.title}»: اختلاف ${diff.toFixed(1)} کیلوگرم بین جمع ردیف‌ها و Grand total رسمی، بر اساس گروه غالب تخصیص یافت.`,
      );
    }
  }

  // هشدارهای لیستوفر (ایراد ۱۱): مارک ناموجود + گروه نامشخص — یکی به
  // ازای هر جدول (نه به ازای هر ردیف، تا رجیستری پر نشود).
  // منطبق با app.py:_extract_rebar: این هشدارها **پیش از** غنی‌سازی Mapping
  // v1/v2 صادر می‌شوند تا ردیف‌های Mapping (که ستون Host Category ندارند)
  // هشدار تکراری تولید نکنند.
  for (const [t, n] of Object.entries(noMark)) {
    warnings.push(
      `جدول «${t}»: ${faDigits(n)} ردیف آرماتور فاقد مارک هستند و به‌عنوان «بدون مارک» ثبت شدند — پارامتر Revit «Rebar Number/Mark» در مدل تکمیل شود (ایراد ۱۱).`,
    );
  }
  for (const [t, n] of Object.entries(unknownGrp)) {
    warnings.push(
      `جدول «${t}»: ${faDigits(n)} ردیف آرماتور گروه سازه‌ای مشخصی ندارند (Host Category ناموجود) و به‌عنوان «نامشخص» ثبت شدند — ستون «Host Category» در مدل Revit تکمیل شود (ایراد ۱۱).`,
    );
  }

  // غنی‌سازی لیستوفر از Mapping v1 (با قطر/گرید/طول دقیق). Revit Schedule
  // مرجع است: میلگردی که قبلاً در Schedule پوشش داده شده، دوباره از Mapping
  // اضافه نمی‌شود (جلوگیری از دوباره‌شماری آرماتورهای مشترک بین خروجی Revit
  // و داینامو) — منطبق با app.py:_extract_rebar.
  const v1Rows = mapping?.rows?.filter((r) => r.source_format === "v1") ?? [];
  for (const row of v1Rows) {
    const d = row.diameter_mm ?? 0;
    const lengthM = row.length_m ?? 0;
    if (d <= 0 || lengthM <= 0) continue;
    // Revit precedence: مارک تکراری skip می‌شود
    const markV1 = normalizeText((row.mark ?? "").trim());
    if (markV1 && revitMarks.has(markV1)) continue;
    const grade = row.steel_type ?? "";
    const bucket = rebarBucket(d, grade);
    const weight = lengthM * rebarUnitWeight(d);
    const grp = structuralGroup(`${row.mark ?? ""} ${row.host_family ?? ""}`, "mapping");
    // ستون‌های لیستوفر (ایراد ۱۱): گروه از Host Category، مارک هرگز «—»
    // (در فرمت Mapping ستون Host Category وجود ندارد — مانند app.py "")
    const _mk = (row.mark ?? "") || (row.host_mark ?? "");
    const [grp2, grpUnknown] = rebarListGroup("", `${_mk} ${row.host_family ?? ""}`, "mapping");
    const dispMark = rebarListMark(row.mark, row.host_mark);
    if (dispMark === "بدون مارک") noMark["Mapping v1"] = (noMark["Mapping v1"] || 0) + 1;
    if (grpUnknown) unknownGrp["Mapping v1"] = (unknownGrp["Mapping v1"] || 0) + 1;
    lines.push({
      mark: dispMark,
      group: grp2,
      evidence: grp !== "سایر" ? grp : "",
      barType: `Φ${Math.round(d)}`,
      diameter: d,
      steelGrade: /2400/.test(grade) ? "AI" : /4000/.test(grade) ? "AIII" : "—",
      shape: row.rebar_detail ?? "",
      count: 1,
      totalLength: lengthM,
      weight,
      priceCode: bucket,
      source: "Mapping v1",
      level: (row.level ?? "").trim(),
      perBarLength: lengthM,
      unitWeight: lengthM ? weight / lengthM : 0,
    });
    bucketKg[bucket] = (bucketKg[bucket] || 0) + weight;
    (bucketSources[bucket] ??= []).push({
      tableId: "mapping",
      fileName: "Mapping v1",
      tableTitle: String(row.element_id ?? ""),
      kind: "mapping",
      ref: row.mark || row.host_mark || "—",
      group: structuralGroup(row.mark ?? "", "mapping"),
      material: grade,
      qty: weight,
      unit: "kg",
      detail: `Φ${Math.round(d)} × طول ${lengthM.toFixed(2)} متر`,
    });
  }

  // ردیف‌های آرماتور مستقیم از v2 (وزن اعلام‌شدهٔ المان)
  const v2Rows = mapping?.rows?.filter((r) => r.source_format === "v2") ?? [];
  for (const row of v2Rows) {
    const w = row.rebar_weight_kg ?? 0;
    if (w <= 0) continue;
    const mark = row.mark || row.family || "";
    const grp = structuralGroup(`${row.category ?? ""} ${row.family ?? ""}`, "mapping");
    // ستون‌های لیستوفر (ایراد ۱۱): گروه از Host Category، مارک هرگز «—»
    // (در فرمت Mapping ستون Host Category وجود ندارد — مانند app.py "")
    const [grp3, grpUnknown3] = rebarListGroup("", `${row.category ?? ""} ${row.family ?? ""}`, "mapping");
    const dispMark3 = rebarListMark(row.mark, row.family);
    if (dispMark3 === "بدون مارک") noMark["Mapping v2"] = (noMark["Mapping v2"] || 0) + 1;
    if (grpUnknown3) unknownGrp["Mapping v2"] = (unknownGrp["Mapping v2"] || 0) + 1;
    lines.push({
      mark: dispMark3,
      group: grp3,
      evidence: grp !== "سایر" ? grp : "",
      barType: "—",
      diameter: 0,
      steelGrade: "—",
      shape: "",
      count: 1,
      totalLength: 0,
      weight: w,
      priceCode: "070202",
      source: "Mapping v2",
      level: (row.level ?? "").trim(),
      perBarLength: 0,
      unitWeight: 0,
    });
    bucketKg["070202"] = (bucketKg["070202"] || 0) + w;
    (bucketSources["070202"] ??= []).push({
      tableId: "mapping",
      fileName: "Mapping v2",
      tableTitle: String(row.element_id ?? ""),
      kind: "mapping",
      ref: mark,
      group: structuralGroup(row.category ?? "", "mapping"),
      material: "",
      qty: w,
      unit: "kg",
      detail: "وزن میلگرد المان (Mapping v2)",
    });
  }

  return { lines, bucketKg, bucketSources, warnings };
}

// ════════════════════════════════════════════════════════════════
// پنل قیمت دستی (فاز C — §۱۵-۴): مدل داده‌ای، مهاجرت و کمک‌توابع
// ════════════════════════════════════════════════════════════════

/** رکورد قیمت/کد دستی با تمام فیلدهای ردیخی‌پذیر (قاعدهٔ طلایی ۲) */
export function manualRecord(
  price: number,
  source = "بخشنامه",
  docNo = "",
  docDate = "",
  note = "",
  status = "دستی",
  chapter = "",
  user = "",
  at = "",
): ManualPriceRecord {
  return { price, source, docNo, docDate, note, status, chapter, user, at };
}

/** ثبت یک رویداد در سابقهٔ ویرایش (§۱۵-۴ بند ۴ — Audit trail) */
export function appendAudit(
  s: ProjectSettings,
  item: string,
  field: string,
  old: unknown,
  next: unknown,
  source = "",
  kind: AuditKind = "price",
): void {
  s.priceAudit.push({
    at: jalaliNowStr(),
    user: s.priceUser ?? "",
    item: String(item),
    field: String(field),
    old,
    new: next,
    source: source ?? "",
    kind,
  });
}

// نرمال‌سازی سال فارسی برای مقایسه (ارقام فارسی → لاتین، حذف فاصله/ZWNJ)
function normFaYear(v: unknown): string {
  return String(v ?? "")
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d).toString())
    .replace(/[\u200c ]/g, "")
    .trim();
}

/**
 * مهاجرت ورودی‌های دستی قدیمی به ساختار ریکاردی فاز C (یک‌بار، Idempotent).
 *
 * - priceOverrides قدیمی (عددی) → manualPrices با منبع «ویرایش قدیمی» و
 *   وضعیت «نیازمند تأیید» (درخواست کاربر: برچسب زده شود ولی ارقام عوض نشوند).
 * - manualCodes قدیمی (رشته) → رکورد با دلیل «ویرایش قدیمی».
 * - excluded قدیمی (رشته) → رکورد بدون دلیل.
 */
export function migrateManualEntries(s: ProjectSettings): ProjectSettings {
  if ((s as { _manualMigrated?: boolean })._manualMigrated) return s;
  (s as { _manualMigrated?: boolean })._manualMigrated = true;
  s.manualPrices = s.manualPrices ?? {};
  s.manualCodes = s.manualCodes ?? {};
  s.excluded = s.excluded ?? [];
  s.starredRows = s.starredRows ?? [];
  s.priceAudit = s.priceAudit ?? [];

  const legacy = s.priceOverrides ?? {};
  for (const [key, val] of Object.entries(legacy)) {
    if (key in s.manualPrices) continue;
    s.manualPrices[key] = manualRecord(
      typeof val === "number" ? val : 0,
      "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)",
      "", "", "قیمت دستیِ واردشده قبل از پنل قیمت دستی فاز C",
      "نیازمند تأیید",
    );
  }
  for (const [key, val] of Object.entries(s.manualCodes)) {
    if (typeof val === "string" && val) {
      s.manualCodes[key] = {
        code: val, reason: "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)", user: "", at: "",
      };
    }
  }
  s.excluded = s.excluded.map((e) =>
    typeof e === "string"
      ? { id: e, reason: "", user: "", at: "" }
      : (e as ExcludedRecord),
  );
  return s;
}

/** مجموعهٔ شناسه‌های مستثنی‌شده (پشتیبانی ساختار قدیمی رشته‌ای) */
export function excludedIds(s: ProjectSettings): Set<string> {
  return new Set((s.excluded ?? []).map((e) => (typeof e === "string" ? e : e.id)));
}

/** کد فهرست‌بهای جایگزینِ دستی برای یک طرح (رشته یا رکورد) */
export function manualCodeOf(s: ProjectSettings, planId: string): string {
  const v = (s.manualCodes ?? {})[planId];
  if (!v) return "";
  return typeof v === "string" ? v : v.code ?? "";
}

/** قیمت دستی یک طرح یا null اگر ورودی دستی وجود ندارد.
 *  پس از مهاجرت فقط manualPrices مرجع است؛ قبل از آن ساختار قدیمی
 *  priceOverrides برای سازگاری با فراخوانی‌های مستقیم (قرارداد T14) خوانده
 *  می‌شود. */
export function manualPriceOf(s: ProjectSettings, planId: string): number | null {
  const rec = (s.manualPrices ?? {})[planId];
  if (rec && typeof rec.price === "number") return rec.price;
  if (!(s as { _manualMigrated?: boolean })._manualMigrated) {
    const legacy = s.priceOverrides?.[planId];
    if (typeof legacy === "number") return legacy;
  }
  return null;
}

/** وضعیت قیمت یک ردیف — اولویت: دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی */
export function priceStatusOf(line: {
  manual?: unknown;
  needsReview?: boolean;
  estimatedPrice?: boolean;
  matchMethod?: string;
  confidence?: number;
}): string {
  if (line.manual) return "دستی";
  if (line.needsReview) return "نیازمند ورود";
  if (line.estimatedPrice) return "موقت";
  if (line.matchMethod === "fuzzy" && (line.confidence ?? 0) < 0.5) return "پیش‌فرض اپ";
  return "قطعی";
}

/**
 * تطبیق یک طرح با فهرست‌بها: بازنویسی دستی کد → کد دقیق → فازی → پیش‌فرض.
 *
 * قیمت دستی در اینجا اعمال **نمی‌شود** — لایهٔ قیمت دستی (مرحلهٔ ۵.۵
 * computeProject) نقطهٔ واحد اعمال است تا قیمتِ پیشینِ برنامه (appPrice)
 * برای نمایش دوگانه و درصد اختلاف حفظ شود (§۱۵-۴ بند ۳).
 */
function matchPlan(
  plan: { id: string; targetCode: string; query: string; fallbackDesc: string; fallbackUnit: string; fallbackPrice: number },
  db: FehrestRow[],
  settings: ProjectSettings,
): {
  code: string;
  desc: string;
  unit: string;
  price: number;
  matchMethod: MatchMethod;
  confidence: number;
  estimatedPrice: boolean;
  needsReview: boolean;
  candidates: BoqLine["candidates"];
} {
  // ۱) انتخاب دستی کاربر مقدم است
  const manualCode = manualCodeOf(settings, plan.id);
  if (manualCode) {
    const row = byCode(db, manualCode);
    if (row) {
      return {
        code: row.code, desc: row.desc, unit: row.unit, price: row.price,
        matchMethod: "manual", confidence: 1, estimatedPrice: !!row.estimated, needsReview: false,
        candidates: [],
      };
    }
  }

  // ۲) کد هدف دقیق در پایگاه موجود است؟
  const exact = byCode(db, plan.targetCode);
  const candidates = searchFehrest(db, plan.query, { top: 5, minScore: 0.35 }).map((c) => ({
    code: c.row.code, desc: c.row.desc, price: c.row.price, score: c.score,
  }));

  if (exact) {
    return {
      code: exact.code, desc: exact.desc, unit: exact.unit,
      price: exact.price,
      matchMethod: "rule-exact",
      confidence: exact.estimated ? 0.85 : 0.99,
      estimatedPrice: !!exact.estimated,
      needsReview: !!exact.estimated,
      candidates,
    };
  }

  // ۳) جست‌وجوی فازی
  const best = candidates[0];
  if (best && best.score >= 0.55) {
    const row = byCode(db, best.code)!;
    return {
      code: row.code, desc: row.desc, unit: row.unit,
      price: row.price,
      matchMethod: "fuzzy",
      confidence: best.score,
      estimatedPrice: !!row.estimated,
      needsReview: best.score < 0.8,
      candidates,
    };
  }

  // ۴) بازگشت به پیش‌فرض داخلی (تخمینی)
  return {
    code: plan.targetCode,
    desc: plan.fallbackDesc,
    unit: plan.fallbackUnit,
    price: plan.fallbackPrice,
    matchMethod: "fuzzy",
    confidence: 0.4,
    estimatedPrice: true,
    needsReview: true,
    candidates,
  };
}

/** تبدیل عددی سخت‌گیرانه برای کمیت‌ها — معادل pandas.to_numeric(errors="coerce") */
function coerceNum(raw: unknown): number {
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : 0;
  if (typeof raw === "boolean") return raw ? 1 : 0;
  if (typeof raw === "string") {
    const t = raw.trim();
    if (!t) return 0;
    const v = Number(t);
    return Number.isFinite(v) ? v : 0;
  }
  return 0;
}

export function directCodedLines(
  mapping: MappingData,
  db: FehrestRow[],
  settings: ProjectSettings,
): BoqLine[] {
  const lines: BoqLine[] = [];
  if (!mapping || mapping.rows.length === 0) return lines;

  // کد کانونیکال (فقط حذف فاصله‌های اطراف) مبنای فیلتر، کلید گروه، جست‌وجو و شناسهٔ ردیف است
  const coded = mapping.rows
    .map((row) => ({ row, code: String(row.fehrest_code ?? "").trim() }))
    .filter((e) => /^\d{6}$/.test(e.code));
  if (coded.length === 0) return lines;

  const groups = new Map<string, typeof mapping.rows>();
  for (const e of coded) {
    const src = e.row.source_format ?? "v2";
    const key = `${e.code}|${src}`;
    let grp = groups.get(key);
    if (!grp) { grp = []; groups.set(key, grp); }
    grp.push(e.row);
  }

  for (const [key, grpRows] of groups) {
    const sep = key.indexOf("|");
    const code = key.slice(0, sep);
    const srcName = key.slice(sep + 1);

    let row = byCode(db, code);
    if (!row) {
      const candidates = searchFehrest(db, `ردیف ${code}`, { top: 1, minScore: 0.5 });
      const best = candidates[0]?.row;
      row = {
        code, chapter: code.slice(0, 2),
        desc: best?.desc ?? `ردیف ${code}`,
        unit: "مترمربع", price: 0, estimated: true,
      };
    }

    const unitNorm = row.unit.replace("‌", "");
    let qty: number;
    if (unitNorm.includes("مترمکعب")) {
      qty = grpRows.reduce((s, r) => s + coerceNum(r.volume_m3), 0);
    } else if (unitNorm.includes("کیلوگرم")) {
      qty = grpRows.reduce((s, r) => s + coerceNum(r.rebar_weight_kg), 0);
    } else if (unitNorm.includes("تن")) {
      qty = grpRows.reduce((s, r) => s + coerceNum(r.rebar_weight_kg), 0) / 1000;
    } else if (unitNorm.includes("مترطول")) {
      qty = grpRows.reduce((s, r) => s + coerceNum(r.length_m), 0);
    } else {
      qty = grpRows.reduce((s, r) => s + coerceNum(r.formwork_m2) + coerceNum(r.area_m2), 0);
    }

    if (qty <= 0) continue;

    // مرحلهٔ ۱۱ بخش ۱: هیچ ضریب پرتی وجود ندارد — qty تنها مقدار است.
    // لایهٔ قیمت دستی اینجا هم اعمال می‌شود تا فراخوانی مستقیم این تابع
    // (قرارداد T14) همان رفتار computeProject داشته باشد. قیمتِ پیش از
    // بازنویسی در basePrice برای نمایش اختلاف نگه داشته می‌شود.
    const mp = manualPriceOf(settings, `direct-${code}-${srcName}`);
    const price = mp ?? row.price;

    lines.push({
      id: `direct-${code}-${srcName}`,
      rowNo: 0,
      chapter: code.slice(0, 2),
      chapterTitle: chapterTitle(code.slice(0, 2)),
      code, desc: row.desc, unit: row.unit,
      qty,
      price, total: qty * price,
      basePrice: row.price,
      matchMethod: "direct-code",
      confidence: 1.0,
      sources: [],
      estimatedPrice: !!row.estimated,
      needsReview: qty <= 0 || row.price <= 0,
      note: `کد مستقیم از Mapping (${srcName}) — ${grpRows.length} المان`,
      candidates: [],
      indexFactor: 1.0,
      totalIndexed: qty * price,
    });
  }

  return lines;
}

// ─────────────────────────────────────────────────────────────
// تابع اصلی: پردازش کامل پروژه
// ─────────────────────────────────────────────────────────────
const CONCRETE_PLAN_IDS = ["conc-foundation", "conc-col-beam", "conc-slab", "conc-stair"];
const CONCRETE_GROUP: Record<string, keyof ProjectSettings["concreteStrengthMpa"]> = {
  "conc-foundation": "foundation",
  "conc-col-beam": "columnBeam",
  "conc-slab": "slab",
  "conc-stair": "stair",
};

/** مقاومت فشاری انتخابی کاربر برای گروه سازه‌ای (ورودی دستی). */
function settingMpa(settings: ProjectSettings, planId: string): number | null {
  const v = settings.concreteStrengthMpa?.[CONCRETE_GROUP[planId]];
  return typeof v === "number" ? v : null;
}

// ── هشدار چگالی میلگرد (ایراد ۱۴) ──
// وزن میلگرد هر گروه سازه‌ای ÷ حجم بتن همان گروه؛ خارج از محدودهٔ
// متعارف → خطا (میلگرد در مدل Revit کامل مدل نشده). اپ عدد را تغییر
// نمی‌دهد — فقط هشدار می‌دهد یا وزن دستی کاربر را می‌پذیرد.
export function rebarDensityWarnings(
  lines: BoqLine[],
  settings: ProjectSettings,
  warns: Warning[],
): { volumes: Record<string, number>; weights: Record<string, number> } {
  const th = ((REBAR_DENSITY_CFG as Record<string, unknown>).thresholds_kg_m3 ??
    {}) as Record<string, [number, number]>;
  const manual = settings.rebarManualWeight ?? {};
  // حجم بتن به تفکیک گروه (از ردیف‌های فصل ۰۸)
  const vol: Record<string, number> = {};
  for (const l of lines) {
    if (!l.code.startsWith("08") || l.unit !== "مترمکعب") continue;
    for (const r of l.sources ?? []) {
      const g = r.group;
      if (g) vol[g] = (vol[g] ?? 0) + r.qty;
    }
  }
  // وزن میلگرد به تفکیک گروه (از sources ردیف‌های آرماتور)
  const wt: Record<string, number> = {};
  for (const l of lines) {
    if (!l.code.startsWith("07")) continue;
    for (const r of l.sources ?? []) {
      const g = r.group;
      if (g) wt[g] = (wt[g] ?? 0) + r.qty;
    }
  }
  for (const [g, loHi] of Object.entries(th)) {
    if (!(g in vol) || (vol[g] ?? 0) <= 0.001) continue;
    const w = manual[g];
    if (w !== undefined) {
      warns.push({
        level: "اطلاع",
        category: "چگالی میلگرد",
        item: g,
        message: `وزن میلگرد گروه «${g}» به‌صورت دستی وارد شده (${faFloat(w)} کیلوگرم) — مقدار مدل کنار آن نمایش داده می‌شود.`,
        action: "—",
        ref: "ایراد ۱۴ — ورود کاربر",
      });
      continue;
    }
    if (!(g in wt)) continue;
    const d = wt[g] / vol[g];
    const [lo, hi] = loHi;
    if (d < lo || d > hi) {
      warns.push({
        level: "خطا",
        category: "چگالی میلگرد",
        item: g,
        message: `چگالی میلگرد ${g} = ${faFloat(d)} kg/m³؛ محدودهٔ متعارف ${faDigits(lo)} تا ${faDigits(hi)}. احتمالاً میلگرد در مدل Revit کامل مدل نشده. مقدار از مدل برداشته شده و تغییری داده نشد.`,
        action: "وزن یا چگالی دستی گروه را وارد کنید یا مدل را بازبینی کنید.",
        ref: "ایراد ۱۴ — کنترل کیفیت مدل",
      });
    }
  }
  return { volumes: vol, weights: wt };
}

// ── قالب بدون ردیف (ایراد ۲) — هر سطح قالب نگاشت‌نشده ──
// سطوح قالبی که در هیچ ردیف فصل ۰۶ قیمت‌گذاری نشدند: المان‌های تیرچه
// (JSL) داخل نرخ ۱۰۰۳۰۵ هستند (اطلاع)، بقیه هشدار نیاز به نگاشت دستی.
function unpricedFormworkWarnings(
  lines: BoqLine[],
  schedRecs: QuantityRecord[],
  warns: Warning[],
): void {
  const consumed = new Set<QuantityRecord>();
  for (const l of lines) {
    if (!l.code.startsWith("06")) continue;
    for (const r of l.sources ?? []) consumed.add(r);
  }
  for (const r of schedRecs) {
    if (r.kind !== "formwork_foundation" && r.kind !== "formwork_super") continue;
    if (r.unit !== "m2" || r.qty <= 0) continue;
    if (consumed.has(r)) continue;
    const ref = r.ref;
    if (/JSL/.test(ref)) {
      warns.push({
        level: "اطلاع",
        category: "قالب بدون ردیف",
        item: ref,
        message: `${faFloat(r.qty)} مترمربع قالب‌بندی این المان داخل نرخ ردیف ۱۰۰۳۰۵ (سقف تیرچه‌بلوک) است و در فصل ۰۶ قیمت‌گذاری نمی‌شود.`,
        action: "—",
        ref: "فصل ۱۰ فهرست‌بها — بند نرخ ۱۰۰۳۰۵",
      });
    } else {
      warns.push({
        level: "هشدار",
        category: "قالب بدون ردیف",
        item: ref,
        message: `${faFloat(r.qty)} مترمربع قالب‌بندی به هیچ ردیف فصل ۰۶ نگاشت نشد.`,
        action: "نگاشت دستی ردیف فصل ۰۶ را بررسی کنید.",
        ref: "فصل ۰۶ فهرست‌بها (ایراد ۲)",
      });
    }
  }
}

export function computeProject(
  tables: RevitTable[],
  db: FehrestRow[],
  settings: ProjectSettings,
  mapping?: MappingData,
  indexTable?: IndexTable,
): ProjectResult {
  // مهاجرت ورودی‌های دستی قدیمی به ساختار ریکاردی فاز C (یک‌بار، Idempotent)
  migrateManualEntries(settings);
  // رجیستری مرکزی هشدارها (ایراد ۱۰) — ساختار یافته: خطا / هشدار / اطلاع
  const warns: Warning[] = [];
  // هشدارهای متنی قدیمی (تجزیهٔ جداول / آرماتور) — در پایان به رجیستری می‌روند
  const legacyWarnings: string[] = [];
  // ── فاز E-۵: مغایرتِ سال فهرست‌بها (انتخاب پروژه vs فایل بارگذاری‌شده) ──
  const _fySel = normFaYear(settings.fehrestYear);
  const _fyDb = normFaYear(settings.fehrestDbYear);
  if (_fySel && _fyDb && _fySel !== _fyDb) {
    warns.push({
      level: "هشدار",
      category: "فهرست‌بها",
      item: "fehrest_year_mismatch",
      message: `سال فهرست‌بهای پروژه (${_fySel}) با سال فهرستِ بارگذاری‌شده `
        + `(${_fyDb}) متفاوت است.`,
      action: `یا سال پروژه را در سایدبار تصحیح کنید یا فهرست‌بهای سال `
        + `${_fySel} را در گام «فهرست‌بها» بارگذاری کنید.`,
      ref: "فاز E-۵ — پروفایل پروژه",
    });
  }
  const records = tables.flatMap((t) => toQuantityRecords(t));
  const joistRefs = joistFloorRefs(tables);
  const ctx: Ctx = { records, tables, settings, joistRefs };

  const directLines = mapping ? directCodedLines(mapping, db, settings) : [];
  const directCodes = new Set(directLines.map((l) => l.code));

  let lines: BoqLine[] = [...directLines];
  const plans = buildPlans(settings);

  // ── بتن مازاد بر ۵ cm روی بلوک (بند ۹ الزامات عمومی فصل دهم) ──
  // ضخامت سقف از زیر تیرچه تا ۵ cm بتن روی بلوک داخل نرخ ۱۰۰۳۰۵ است.
  // فقط بتن مازاد بر ۵ cm — بر اساس مشخصات فنی پروژه — به ردیف بتن
  // متناظر با مقاومت انتخابی افزوده می‌شود. اختلاف هندسی Revit
  // (مثلاً ۵٫۲ cm) مازاد محسوب نمی‌شود.
  const joistLen = sum(records.filter((r) => r.kind === "joist_floor" && r.unit === "m"));
  const joistAreaNet = joistLen * (settings.joistSpacing ?? 0.55);
  const topCm = settings.joistBlockTopThicknessCm ?? 5;
  const excessM3 = topCm > 5 ? ((topCm - 5) / 100) * joistAreaNet : 0;
  let excessPlanId: string | null = null;
  if (excessM3 > 0) {
    const jbMpa = settings.joistBlockConcreteMpa ?? 20;
    const jbCode = CONCRETE_STRENGTH_CODES[jbMpa]?.[0] ?? CONCRETE_STRENGTH_CODES[20][0];
    // ردیف بتن متناظر با مقاومت انتخابی؛ ترتیب ترجیح: سقف > ستون‌تیر > پله > پی
    for (const pid of ["conc-slab", "conc-col-beam", "conc-stair", "conc-foundation"]) {
      const p = plans.find((pl) => pl.id === pid);
      if (p && p.targetCode === jbCode) {
        excessPlanId = pid;
        break;
      }
    }
  }

  // نقشهٔ مقاومت بر اساس مرجع المان (ایراد ۱): جدولی که ستون متریال
  // ندارد (مثل جدول اختصاصی پی) می‌تواند مقاومت را از جدولی دیگر برای
  // همان مرجع تهیه کند.
  const refStrength = new Map<string, number>();
  for (const r of records) {
    if (r.strengthMpa) {
      const k = foundationRefKey(r.ref);
      if (k) refStrength.set(k, r.strengthMpa);
    }
  }

  for (const plan of plans) {
    // ── طرح‌های بتن: یک ردیف به ازای هر مقاومت مؤثر (ایراد ۱) ──
    // تقدم رسمی: پارامتر صریح Revit > نام متریال > ورودی دستی.
    if (CONCRETE_PLAN_IDS.includes(plan.id)) {
      const collected = plan.collect(ctx);
      const setMpa = settingMpa(settings, plan.id);
      const buckets = new Map<
        number,
        { qty: number; src: QuantityRecord[]; origin: "material" | "setting" | null; noteExtra: string | null }
      >();
      for (const r of collected.sources) {
        let mpa: number | null = r.strengthMpa ?? refStrength.get(foundationRefKey(r.ref) ?? "") ?? null;
        let origin: "material" | "setting" | null = mpa !== null ? "material" : null;
        if (mpa === null) {
          mpa = setMpa;
          origin = "setting";
        }
        if (mpa === null) continue;
        const b = buckets.get(mpa) ?? { qty: 0, src: [], origin: null, noteExtra: null };
        b.qty += r.qty;
        b.src.push(r);
        if (origin === "material") b.origin = "material";
        buckets.set(mpa, b);
      }
      // یادداشت طرح (مثلاً مستندسازی کسر رویهٔ سقف تیرچه‌بلوک) حفظ می‌شود
      if (collected.note) {
        for (const b of buckets.values()) if (!b.noteExtra) b.noteExtra = collected.note;
      }
      // بتن مازاد بر ۵ cm روی بلوک به سطل مقاومت سقف تیرچه‌بلوک افزوده می‌شود
      if (excessM3 > 0 && plan.id === excessPlanId) {
        const jbMpa = settings.joistBlockConcreteMpa ?? 20;
        const b = buckets.get(jbMpa) ?? { qty: 0, src: [], origin: "setting" as const, noteExtra: null };
        b.qty += excessM3;
        b.noteExtra = `شامل بتن مازاد بر ۵ cm روی بلوک (${excessM3.toFixed(3)} m³ — بند ۹ فصل دهم)`;
        buckets.set(jbMpa, b);
      }
      for (const [mpa, b] of buckets) {
        if (b.qty <= 0.0001) continue;
        const codePrice = CONCRETE_STRENGTH_CODES[mpa];
        if (!codePrice) {
          // مقاومت در جدول نگاشت نیست → ردیف پیش‌فرض انتخاب نمی‌شود
          warns.push({
            level: "خطا",
            category: "نگاشت مقاومت بتن",
            item: plan.id,
            message: `مقاومت فشاری ${faDigits(mpa)} مگاپاسکال برای گروه «${CONCRETE_GROUP[plan.id]}» در جدول نگاشت ردیف‌های فصل ۸ وجود ندارد. ${b.qty.toFixed(2)} مترمکعب بدون ردیف قیمت مانده است.`,
            action: "کد ردیف فصل ۸ به‌صورت دستی انتخاب شود (manualCodes).",
            ref: "فصل ۸ فهرست‌بهای ابنیه ۱۴۰۴",
          });
          continue;
        }
        const [code, price] = codePrice;
        const single = buckets.size === 1;
        const lineId = mpa === setMpa || single ? plan.id : `${plan.id}@${mpa}`;
        const subPlan = {
          ...plan,
          id: lineId,
          targetCode: code,
          fallbackPrice: price,
          query: `تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته با مقاومت فشاری مشخصه ${faDigits(mpa)} مگاپاسکال`,
          fallbackDesc: `تهیه و اجرای بتن با شن و ماسه شسته طبیعی یا شکسته با مقاومت فشاری مشخصه ${faDigits(mpa)} مگاپاسکال`,
        };
        const m = matchPlan(subPlan, db, settings);
        if (directCodes.has(m.code)) continue;
        const noteParts: string[] = [];
        if (b.origin === "material") {
          noteParts.push(`مقاومت فشاری ${faDigits(mpa)} مگاپاسکال از نام متریال Revit استخراج شد`);
          if (setMpa !== null && mpa !== setMpa) {
            warns.push({
              level: "اطلاع",
              category: "نگاشت مقاومت بتن",
              item: plan.id,
              message: `متریال Revit برای گروه «${CONCRETE_GROUP[plan.id]}» ${faDigits(mpa)} مگاپاسکال است ولی تنظیم کاربر ${faDigits(setMpa)} مگاپاسکال است. طبق تقدم رسمی، مقاومت متریال اعمال شد.`,
              action: "در صورت نیاز، تنظیم گروه را تغییر دهید.",
              ref: "ایراد ۱ — تقدم: پارامتر Revit > نام متریال > ورودی دستی",
            });
          }
        } else if (b.origin === "setting") {
          noteParts.push(`مقاومت فشاری ${faDigits(mpa)} مگاپاسکال از تنظیمات کاربر (متریال نامشخص)`);
        }
        if (b.noteExtra) noteParts.push(b.noteExtra);
        lines.push({
          id: lineId,
          rowNo: lines.length + 1,
          chapter: m.code.slice(0, 2),
          chapterTitle: chapterTitle(m.code.slice(0, 2)),
          code: m.code,
          desc: m.desc,
          unit: m.unit,
          qty: b.qty,
          price: m.price,
          total: b.qty * m.price,
          matchMethod: m.matchMethod,
          confidence: m.confidence,
          sources: b.src,
          estimatedPrice: m.estimatedPrice,
          needsReview: m.needsReview,
          note: noteParts.length ? noteParts.join(" — ") : undefined,
          candidates: m.candidates,
          strengthMpa: mpa,
          strengthOrigin: b.origin,
          indexFactor: 1.0,
          totalIndexed: b.qty * m.price,
        });
      }
      continue;
    }
    let { qty, sources, note } = plan.collect(ctx);
    if (plan.id === excessPlanId) {
      qty += excessM3;
      const extra = `شامل بتن مازاد بر ۵ cm روی بلوک (${excessM3.toFixed(3)} m³ — بند ۹ فصل دهم)`;
      note = note ? `${note} — ${extra}` : extra;
    }
    if (!qty || qty <= 0.0001) continue;
    const m = matchPlan(plan, db, settings);
    if (directCodes.has(m.code)) continue;
    // مرحلهٔ ۱۱ بخش ۱: هیچ ضریب پرتی وجود ندارد — total = qty × price.
    lines.push({
      id: plan.id,
      rowNo: lines.length + 1,
      chapter: m.code.slice(0, 2),
      chapterTitle: chapterTitle(m.code.slice(0, 2)),
      code: m.code,
      desc: m.desc,
      unit: m.unit,
      qty,
      price: m.price,
      total: qty * m.price,
      matchMethod: m.matchMethod,
      confidence: m.confidence,
      sources,
      estimatedPrice: m.estimatedPrice,
      needsReview: m.needsReview,
      note,
      candidates: m.candidates,
      indexFactor: 1.0,
      totalIndexed: qty * m.price,
    });
  }

  // ── آرماتور: لیستوفر + سینی‌بندی ──
  const rebarX = extractRebar(tables, mapping);
  legacyWarnings.push(...rebarX.warnings);

  for (const bucket of ["070101", "070201", "070202", "070203"] as const) {
    const kg = rebarX.bucketKg[bucket] ?? 0;
    if (kg <= 0.01 || directCodes.has(bucket)) continue;
    const meta = REBAR_BUCKET_DESC[bucket];
    const plan: {
      id: string; targetCode: string; query: string; fallbackDesc: string; fallbackUnit: string; fallbackPrice: number;
    } = {
      id: `rebar-${bucket}`,
      targetCode: bucket,
      query: meta.query,
      fallbackDesc: meta.desc,
      fallbackUnit: "کیلوگرم",
      fallbackPrice: meta.price,
    };
    const m = matchPlan(plan, db, settings);
    lines.push({
      id: `rebar-${bucket}`,
      rowNo: lines.length + 1,
      chapter: "07",
      chapterTitle: chapterTitle("07"),
      code: m.code,
      desc: m.desc,
      unit: m.unit,
      qty: kg,
      price: m.price,
      total: kg * m.price,
      matchMethod: m.matchMethod,
      confidence: m.confidence,
      sources: rebarX.bucketSources[bucket] ?? [],
      estimatedPrice: m.estimatedPrice,
      needsReview: m.needsReview,
      candidates: m.candidates,
      indexFactor: 1.0,
      totalIndexed: kg * m.price,
    });
  }

  // ── حمل میلگرد (فصل ۲۸) — پیشنهاد خودکار ──
  // ردیف ۲۸۰۱۰۱ فهرست‌بهای ۱۴۰۴: «هرگاه فاصله محل تهیه تا محل کارگاه،
  // بیش از ۳۰ کیلومتر و تا ۷۵ کیلومتر باشد، برای تمام طول مسیر پس از
  // کسر ۳۰ کیلومتر» → کمیت = وزن(تن) × (مسافت − ۳۰) بر حسب تن-کیلومتر.
  const totalRebarKg = neumaier(Object.values(rebarX.bucketKg));
  if (totalRebarKg > 0 && !directCodes.has("280101")) {
    const haulKm = settings.haulDistanceKm ?? 50;
    const plan = {
      id: "transport-rebar",
      targetCode: "280101",
      query: "حمل آهن آلات مصالح سنگی بیش از ۳۰ کیلومتر تا ۷۵ کیلومتر",
      fallbackDesc:
        "حمل سیمان پاکتی، مصالح سنگی، آهن‌آلات، آجر و بلوک، هرگاه فاصله محل تهیه تا محل کارگاه، بیش از ۳۰ کیلومتر و تا ۷۵ کیلومتر باشد، برای تمام طول مسیر پس از کسر ۳۰ کیلومتر",
      fallbackUnit: "تن-کیلومتر",
      fallbackPrice: 28400,
    };
    const m = matchPlan(plan, db, settings);
    const tons = totalRebarKg / 1000;
    const tonKm = tons * Math.max(haulKm - 30, 0);
    lines.push({
      id: "transport-rebar",
      rowNo: lines.length + 1,
      chapter: "28",
      chapterTitle: chapterTitle("28"),
      code: m.code,
      desc: m.desc,
      unit: m.unit,
      qty: tonKm,
      price: m.price,
      total: tonKm * m.price,
      matchMethod: m.matchMethod,
      confidence: m.confidence,
      sources: [],
      estimatedPrice: m.estimatedPrice,
      needsReview: true,
      note: `پیشنهاد خودکار — ${tons.toFixed(1)} تن × ${Math.max(haulKm - 30, 0)} کیلومتر (مسافت ${haulKm} کیلومتر، پس از کسر ۳۰). در صورت عدم نیاز، این ردیف را مستثنی کنید.`,
      candidates: m.candidates,
      indexFactor: 1.0,
      totalIndexed: tonKm * m.price,
    });
  }

  // ── اضافه‌بهای مقاومت بتن سقف تیرچه‌بلوک (۱۰۰۷۰۱ / ۱۰۰۷۰۲) ──
  // بندهای ۸ و ۹ الزامات عمومی فصل دهم فهرست‌بهای ۱۴۰۴: بتن سقف
  // تیرچه‌بلوک ۲۰ MPa فرض می‌شود؛ هرگاه مقاومت فشاری مشخصه بیش از ۲۰
  // و حداکثر ۲۵ MPa باشد → ۱۰۰۷۰۱ (۵۹٬۵۰۰ ریال/m²) و بیش از ۲۵ تا
  // ۳۰ MPa → ۱۰۰۷۰۲ (۷۶٬۵۰۰ ریال/m²) روی کل مساحت سقف. مقدار از
  // تنظیمات کاربر خوانده می‌شود (هیچ مقدار فرضی نیست) و کمیت برابر با
  // مساحت خالص ردیف ۱۰۰۳۰۵ است.
  {
    const jbMpa = settings.joistBlockConcreteMpa ?? 20;
    const jbSurcharge = JOIST_BLOCK_STRENGTH_SURCHARGE[jbMpa] ?? null;
    const jbLine = lines.find((l) => l.id === "joist-block") ?? null;
    if (jbSurcharge && jbLine && jbLine.qty > 0 && !directCodes.has(jbSurcharge[0])) {
      const [jbCode, jbPrice] = jbSurcharge;
      const plan = {
        id: "joist-strength-surcharge",
        targetCode: jbCode,
        query: "اضافه بها سقف تیرچه و بلوک مقاومت فشاری بتن",
        fallbackDesc:
          jbCode === "100701"
            ? "اضافه‌بها به ردیف‌های سقف تیرچه و بلوک، در صورتی که مقاومت فشاری مشخصه بتن سقف، بیش از ۲۰ مگاپاسکال و حداکثر ۲۵ مگاپاسکال باشد"
            : "اضافه‌بها به ردیف‌های سقف تیرچه و بلوک، در صورتی که مقاومت فشاری مشخصه بتن سقف، بیش از ۲۵ مگاپاسکال و حداکثر ۳۰ مگاپاسکال باشد",
        fallbackUnit: "مترمربع",
        fallbackPrice: jbPrice,
      };
      const m = matchPlan(plan, db, settings);
      const q = jbLine.qty;
      lines.push({
        id: "joist-strength-surcharge",
        rowNo: lines.length + 1,
        chapter: "10",
        chapterTitle: chapterTitle("10"),
        code: m.code,
        desc: m.desc,
        unit: m.unit,
        qty: q,
        price: m.price,
        total: q * m.price,
        matchMethod: m.matchMethod,
        confidence: m.confidence,
        sources: [],
        estimatedPrice: m.estimatedPrice,
        needsReview: false,
        note: `پیشنهاد خودکار — مقاومت بتن سقف تیرچه‌بلوک ${faDigits(jbMpa)} MPa (بند ۸ الزامات عمومی فصل دهم). در صورت عدم نیاز، این ردیف را مستثنی کنید.`,
        candidates: m.candidates,
        indexFactor: 1.0,
        totalIndexed: q * m.price,
      });
    }
  }

// ── اضافه‌بهای سختی ارتعاش بتن (۰۸۰۳۱۱) — پیشنهاد اختیاری ──
// ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴: «اضافه‌بها به ردیف‌های بتن‌ریزی برای سختی
// ارتعاش بتن، در صورتی که میلگرد به کار رفته بیش از ۱۸۰ کیلوگرم در
// مترمکعب بتن باشد». تراکم میلگرد = مجموع وزن آرماتور (kg) ÷ حجم
// بتن‌های سازه‌ای (m³، بدون بتن‌مگر). چون از ۱۸۰ بیشتر باشد، اضافه‌بها
// به ازای هر مترمکعب بتن سازه‌ای (مقدار خالص) محاسبه می‌شود. مبنای این
// ردیف حجم بتن‌های سازه‌ای به‌جز سیستم سقف تیرچه‌بلوک است (بند ۳-۵
// فصل ۸). قیمت و آستانه از فهرست‌بهای رسمی ۱۴۰۴ خوانده می‌شوند (در
// دادهٔ نمونه تراکم ≈ ۳۱ kg/m³ < ۱۸۰ → ردیفی افزوده نمی‌شود).
if (settings.surchargeRebarDensity) {
    // مبنای این ردیف حجم بتن‌های سازه‌ای به‌جز سیستم سقف تیرچه‌بلوک است
    // (بند ۳-۵ فصل ۸: به سقف تیرچه‌بلوک تعلق نمی‌گیرد).
    const joistSys = joistSystemRefs(tables);
    const concLines = lines.filter((l) => l.id.startsWith("conc-"));
    const structNet = neumaier(
      concLines.flatMap((l) => l.sources).filter((src) => !joistSys.has(src.ref)).map((src) => src.qty),
    );
    const density = structNet > 0 ? rebarDensity(totalRebarKg, structNet) : 0;
    if (structNet > 0 && density > REBAR_DENSITY_THRESHOLD && !directCodes.has("080311")) {
      const plan = {
        id: "surcharge-080311",
        targetCode: "080311",
        query: "اضافه بها سختی ارتعاش بتن میلگرد بیش از ۱۸۰ کیلوگرم مترمکعب",
        fallbackDesc: "اضافه‌بها به ردیف‌های بتن‌ریزی برای سختی ارتعاش بتن",
        fallbackUnit: "مترمکعب",
        fallbackPrice: 363500,
      };
      const m = matchPlan(plan, db, settings);
      lines.push({
        id: "surcharge-080311",
        rowNo: lines.length + 1,
        chapter: "08",
        chapterTitle: chapterTitle("08"),
        code: m.code,
        desc: m.desc,
        unit: m.unit,
        qty: structNet,
        price: m.price,
        total: structNet * m.price,
        matchMethod: m.matchMethod,
        confidence: m.confidence,
        sources: [],
        estimatedPrice: m.estimatedPrice,
        needsReview: false,
        note: `پیشنهاد خودکار — تراکم میلگرد ${density.toFixed(1)} kg/m³ > ۱۸۰ (آستانهٔ فهرست‌بهای ۱۴۰۴). در صورت عدم نیاز، این ردیف را مستثنی کنید.`,
        candidates: m.candidates,
        indexFactor: 1.0,
        totalIndexed: structNet * m.price,
      });
    }
  }

// ── اضافه‌بهای بتن مسلح (۰۸۰۳۱۰) — پیشنهاد اختیاری، per-element ──
// ردیف ۰۸۰۳۱۰ فهرست‌بهای ۱۴۰۴: «اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت
// مصرف بتن در بتن مسلح». مدرک «مسلح بودن» ستون «Host Mark» جدول
// آرماتور است: وزن آرماتور هر المان میزبان ÷ حجم همان المان. فقط
// المان‌هایی که تراکم خودشان > ۱۸۰ kg/m³ است حساب می‌شوند (نه میانگین
// پروژه — بند ۳-۶ فصل ۸). حجم JSL (تیرچه + رویه) از مبنای اضافه‌بها
// کسر می‌شود (بند ۳-۵: به سقف تیرچه‌بلوک تعلق نمی‌گیرد). بتن مگر (lean)
// هرگز مسلح نیست.
if (settings.surchargeReinforcedConcrete) {
    // تراکم میلگرد هر المان = وزن آرماتورِ میزبانِ همان مارک ÷ حجم همان
    // المان. فقط المان‌هایی که تراکم خودشان > ۱۸۰ kg/m³ است حساب می‌شوند
    // (نه میانگین پروژه — بند ۳-۶ فصل ۸). حجم سیستم سقف تیرچه‌بلوک
    // (تیرچه + رویهٔ JSL-TOP*) از مبنای اضافه‌بها کسر می‌شود (بند ۳-۵).
    const joistSys = joistSystemRefs(tables);
    const hostKg = new Map<string, number>();
    for (const rl of rebarX.lines) {
      if (!rl.hostMark) continue;
      hostKg.set(rl.hostMark, (hostKg.get(rl.hostMark) ?? 0) + rl.weight);
    }
    const qualifiers: string[] = [];
    let base = 0;
    for (const l of lines) {
      if (!l.id.startsWith("conc-")) continue; // بتن مگر مسلح نیست
      for (const src of l.sources) {
        const mk = (src.ref ?? "").trim();
        if (!mk || joistSys.has(mk)) continue; // حجم JSL کسر می‌شود
        const v = src.qty ?? 0;
        const kg = hostKg.get(mk) ?? 0;
        if (v > 0 && kg > 0 && kg / v > REBAR_DENSITY_THRESHOLD) {
          base += v;
          qualifiers.push(mk);
        }
      }
    }
    if (base > 0 && !directCodes.has("080310")) {
      const plan = {
        id: "surcharge-080310",
        targetCode: "080310",
        query: "اضافه بها ردیف های بتن ریزی در صورت مصرف بتن در بتن مسلح",
        fallbackDesc: "اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت مصرف بتن در بتن مسلح",
        fallbackUnit: "مترمکعب",
        fallbackPrice: 145500,
      };
      const m = matchPlan(plan, db, settings);
      lines.push({
        id: "surcharge-080310",
        rowNo: lines.length + 1,
        chapter: "08",
        chapterTitle: chapterTitle("08"),
        code: m.code,
        desc: m.desc,
        unit: m.unit,
        qty: base,
        price: m.price,
        total: base * m.price,
        matchMethod: m.matchMethod,
        confidence: m.confidence,
        sources: [],
        estimatedPrice: m.estimatedPrice,
        needsReview: false,
        note: `پیشنهاد خودکار — ${qualifiers.length} المان با تراکم میلگرد خودشان > ۱۸۰ kg/m³ (${[...new Set(qualifiers)].sort().join("، ")}). در صورت عدم نیاز، این ردیف را مستثنی کنید.`,
        candidates: m.candidates,
        indexFactor: 1.0,
        totalIndexed: base * m.price,
      });
    }
  }

// ── اضافه‌بهای ضخامت کم بتن (۰۸۰۳۰۴) — پیشنهاد اختیاری ──
// ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴: «اضافه‌بها به ردیف‌های بتن‌ریزی، هرگاه
// ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد» (فصل ۸ بند ۳-۳). این
// اضافه‌بها مختص کف‌سازی بتنی روی زمین است (دال روی زمین)؛ سقف‌های
// معلق ارزیابی نمی‌شوند. ضخامت فقط از داده‌های خود پروژه استخراج
// می‌شود: ردیفی که در جدول خودش هم «حجم» و هم «مساحت» دارد (مثل
// جداول بتن‌مگر و بتن‌ریزی پی) → ضخامت = حجم ÷ مساحت. تیر/ستون/پله
// ارزیابی نمی‌شوند (مساحت قالب‌بندی شامل کناره‌ها/پاهاست و حجم÷مساحت
// برابر ضخامت نیست). مقدار خالص است (بدون ضریب پرت — مرحلهٔ ۱۱ بخش ۱).
if (settings.surchargeThinConcrete) {
    const thinNet = thinConcreteNet(tables);
    if (thinNet > 0 && !directCodes.has("080304")) {
      const plan = {
        id: "surcharge-080304",
        targetCode: "080304",
        query: "اضافه بها ردیف های بتن ریزی هرگاه ضخامت بتن ۱۵ سانتی متر یا کمتر",
        fallbackDesc: "اضافه‌بها به ردیف‌های بتن‌ریزی، هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا کمتر باشد",
        fallbackUnit: "مترمکعب",
        fallbackPrice: 304000,
      };
      const m = matchPlan(plan, db, settings);
      lines.push({
        id: "surcharge-080304",
        rowNo: lines.length + 1,
        chapter: "08",
        chapterTitle: chapterTitle("08"),
        code: m.code,
        desc: m.desc,
        unit: m.unit,
        qty: thinNet,
        price: m.price,
        total: thinNet * m.price,
        matchMethod: m.matchMethod,
        confidence: m.confidence,
        sources: [],
        estimatedPrice: m.estimatedPrice,
        needsReview: false,
        note: `پیشنهاد خودکار — حجم بتن کف‌سازی روی زمین با ضخامت ≤ ۱۵ سانتی‌متر: ${thinNet.toFixed(2)} m³ (خالص). در صورت عدم نیاز، این ردیف را مستثنی کنید.`,
        candidates: m.candidates,
        indexFactor: 1.0,
        totalIndexed: thinNet * m.price,
      });
    }
  }

  // ── ردیف‌های ستاره‌دار (غیرفهرستی — فاز C): ورود کامل دستی با مقدار،
  // ├── قیمت و فصل؛ در صورت‌وضعیت و شاخص تعدیل می‌آیند (§۱۵-۴ بند ۲).
  for (const sr of settings.starredRows ?? []) {
    const sq = Number(sr.qty);
    const sp = Number(sr.price);
    if (!Number.isFinite(sq) || !Number.isFinite(sp) || sq <= 0 || sp <= 0) continue;
    const ch = String(sr.chapter ?? "").slice(0, 2) || "99";
    let sCode = String(sr.code ?? "").trim() || `starred-${ch}`;
    if (!sCode.endsWith("*")) sCode += "*";
    lines.push({
      id: `starred-${sCode}`,
      rowNo: 0,
      chapter: ch,
      chapterTitle: chapterTitle(ch),
      code: sCode,
      desc: String(sr.desc ?? "ردیف غیرفهرستی (ستاره‌دار)"),
      unit: String(sr.unit ?? "عدد"),
      qty: sq,
      price: sp,
      total: sq * sp,
      matchMethod: "manual-starred",
      confidence: 1.0,
      sources: [],
      estimatedPrice: false,
      needsReview: false,
      note: String(sr.note ?? "ورود دستی — فاقد ردیف متناظر در فهرست‌بها"),
      candidates: [],
      indexFactor: 1.0,
      totalIndexed: sq * sp,
      starred: true,
      manual: sr,
      appPrice: null,
      diffPct: null,
    });
  }

  // ── حذف ردیف‌های مستثنی‌شده توسط کاربر ──
  lines = lines.filter((l) => !excludedIds(settings).has(l.id));

  // ── مرتب‌سازی به ترتیب فصل و کد ──
  const order = ["08", "06", "07", "10", "28", "01", "02", "03", "04", "05", "09", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "29", "41", "99"];
  lines.sort((a, b) => {
    const ia = order.indexOf(a.chapter);
    const ib = order.indexOf(b.chapter);
    if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    return a.code.localeCompare(b.code);
  });
  lines.forEach((l, i) => (l.rowNo = i + 1));

  // ── ۵.۵) لایهٔ قیمت دستی (فاز C — §۱۵-۴) ──
  // اعمال اولویت: دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی روی هر
  // ردیف، با نگهداری قیمتِ پیشینِ برنامه و درصد اختلاف برای نمایش دوگانه
  // و هشدار بازبینی (>آستانهٔ تنظیمات).
  const warnPct = Number(settings.priceDiffWarnPct ?? 30);
  for (const l of lines) {
    let appPrice = l.basePrice ?? null;
    if (appPrice == null) appPrice = l.price;
    const rec = (settings.manualPrices ?? {})[l.id];
    if (rec && typeof rec.price === "number") {
      l.price = rec.price;
      l.total = l.qty * l.price;
      l.manual = rec;
      // رفتار قدیمی: قیمت دستی، ردیف را تأییدشده و غیرتخمینی می‌کند
      l.estimatedPrice = false;
      l.needsReview = false;
      if (appPrice) {
        l.diffPct = (l.price - appPrice) / appPrice * 100;
        if (Math.abs(l.diffPct) > warnPct) {
          warns.push({
            level: "هشدار",
            category: "قیمت دستی",
            item: l.code,
            message:
              `اختلاف قیمت دستی ردیف ${l.code} با قیمت فهرست‌بها ` +
              `${faFloat(Math.abs(l.diffPct), 1)}٪ است (بیش از آستانهٔ ` +
              `${faFloat(warnPct, 0)}٪).`,
            action: "منبع سند را بررسی و تأیید کنید.",
            ref: "§۱۵-۴ بند ۳ — پنل قیمت دستی",
          });
        }
      } else {
        l.diffPct = null;
      }
    } else {
      l.diffPct = null;
    }
    l.appPrice = rec ? appPrice : null;
    l.priceStatus = priceStatusOf(l);
  }

  // ── ۶) لایهٔ شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) ──
  // قبل از ضرایب زنجیرهٔ مالی و روی مبلغ ردیف (بر اساس دو رقم اول کد).
  // اگر دورهٔ هدف برابر دورهٔ مبنا باشد، ضریب همهٔ فصل‌ها ۱ است.
  const itable = indexTable ?? IndexTable.load();
  const indexTarget = settings.indexTargetPeriod || itable.basePeriod;
  let indexReport: IndexReport | null = null;
  if (indexTarget && itable.basePeriod && indexTarget !== itable.basePeriod) {
    for (const l of lines) {
      const f = itable.factor(l.code, indexTarget);
      l.indexFactor = f;
      l.totalIndexed = l.total * f;
    }
    indexReport = itable.report(indexTarget);
  } else {
    for (const l of lines) {
      l.indexFactor = 1.0;
      l.totalIndexed = l.total;
    }
  }

  // ── ۷) زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸) ──
  // جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای + تجهیز و
  // برچیدن کارگاه. کسورات قانونی (۲۲٫۸٪) جزو «ناخالص پرداختی» نیستند و
  // فقط در خروجی جداگانهٔ «خالص پرداختی» محاسبه می‌شوند.
  const baseTotal = neumaier(lines.map((l) => l.totalIndexed));
  // ضریب طبقات (ایراد ۳) و ضریب منطقه‌ای (ایراد ۴): محاسبهٔ شفاف با
  // ثبت منبع و وضعیت؛ در حالت ناقص، ضریب ۱ و برچسب «ناقص» داده می‌شود.
  const floorsX = computeFloorsCoef(records, settings, warns);
  const regionalX = computeRegionalCoef(settings, warns);
  // اعمال ضریب طبقات فقط روی ردیف‌های مشمول (پیوست ۲ بند ۱-۳):
  // کار ساختمان به‌استثنای محوطه‌سازی و حمل‌ونقل (فصل ۲۸).
  const excludedChapters = new Set<string>(settings.floorsExcludedChapters ?? ["28"]);
  for (const l of lines) {
    const ch = l.chapter;
    if (/^\d+$/.test(ch) && parseInt(ch, 10) >= 30) excludedChapters.add(ch);
  }
  const eligibleLines = lines.filter((l) => !excludedChapters.has(l.chapter));
  const eligibleTotal = neumaier(eligibleLines.map((l) => l.totalIndexed));
  const pf = floorsX.value ?? 1.0;
  const floorsAmount = eligibleTotal * pf + (baseTotal - eligibleTotal);
  const overheadAmount = floorsAmount * settings.overheadCoef;
  const regionalAmount = overheadAmount * (regionalX.value ?? 1.0);
  const siteSetup = settings.siteSetupAmount;
  const grossPayable = regionalAmount + siteSetup;
  const grandTotal = grossPayable;

  // خالص پرداختی (خروجی جداگانه، برچسب روشن — بر ناخالص اثر ندارد)
  const insurance = grossPayable * (settings.insurancePct / 100);
  const tax = grossPayable * (settings.taxPct / 100);
  const goodJob = grossPayable * (settings.goodJobPct / 100);
  const advancePayment = settings.advancePayment;
  const totalDeductions = insurance + tax + goodJob + advancePayment;
  const netPayable = grossPayable - totalDeductions;

  const chapterMap = new Map<string, number>();
  for (const l of lines) chapterMap.set(l.chapter, (chapterMap.get(l.chapter) ?? 0) + l.totalIndexed);
  const chapterSums = [...chapterMap.entries()]
    .map(([chapter, total]) => ({ chapter, title: chapterTitle(chapter), total }))
    .sort((a, b) => b.total - a.total);

  // ── رجیستری مرکزی هشدارها (ایراد ۱۰) ──
  // هر ردیف needs_review باید هشدار متناظر داشته باشد (قاعدهٔ کیفی)
  for (const l of lines) {
    if (l.needsReview) {
      const cand = l.candidates ?? [];
      warns.push({
        level: "هشدار",
        category: "تطبیق ردیف",
        item: l.code,
        message:
          `تطبیق ردیف ${l.code} با روش «${l.matchMethod}» (اطمینان ${faFloat(l.confidence, 2)}) نیاز به بازبینی دارد.` +
          (cand.length ? ` کدهای پیشنهادی: ${cand.slice(0, 3).map((c) => c.code).join(", ")}.` : ""),
        action: "کد ردیف را در فایل Mapping ثبت یا تأیید کنید.",
        ref: "ایراد ۱۰ — کنترل کیفیت تطبیق",
      });
    }
  }
  // چگالی میلگرد (ایراد ۱۴) و قالب بدون ردیف (ایراد ۲)
  rebarDensityWarnings(lines, settings, warns);
  unpricedFormworkWarnings(lines, records, warns);
  // هشدارهای متنی قدیمی (تجزیهٔ جداول / آرماتور) → ساختار مرکزی
  for (const w of [...new Set([...tables.flatMap((t) => t.warnings), ...legacyWarnings])]) {
    warns.push({
      level: "هشدار",
      category: "تجزیهٔ جداول/آرماتور",
      item: "—",
      message: w,
      action: "—",
      ref: "—",
    });
  }

  const quality: QualityReport = {
    tablesParsed: tables.length,
    tablesUnknown: tables.filter((t) => t.kind === "unknown").length,
    rowsRead: tables.reduce((a, t) => a + t.rows.length, 0),
    linesMatched: lines.length,
    linesExact: lines.filter((l) => l.matchMethod === "rule-exact" || l.matchMethod === "manual" || l.matchMethod === "direct-code").length,
    linesFuzzy: lines.filter((l) => l.matchMethod === "fuzzy").length,
    linesEstimatedPrice: lines.filter((l) => l.estimatedPrice).length,
    linesNeedReview: lines.filter((l) => l.needsReview).length,
    warnings: [...new Set([...tables.flatMap((t) => t.warnings), ...legacyWarnings])],
  };

  const warningsByLevel: Record<string, number> = {};
  for (const w of warns) warningsByLevel[w.level] = (warningsByLevel[w.level] ?? 0) + 1;

  // ── خلاصهٔ وضعیت قیمت‌ها (فاز C — §۱۵-۴ بندهای ۵ و ۶) ──
  const priceStatusSummary: Record<string, number> = {};
  for (const st of MANUAL_STATUSES) priceStatusSummary[st] = 0;
  for (const l of lines) {
    const key = l.priceStatus ?? "قطعی";
    priceStatusSummary[key] = (priceStatusSummary[key] ?? 0) + 1;
  }
  const needsPriceEntry = priceStatusSummary["نیازمند ورود"] ?? 0;
  const starredTotal = lines
    .filter((l) => l.starred)
    .reduce((s, l) => s + l.totalIndexed, 0);
  const starredPct = grandTotal ? (starredTotal / grandTotal) * 100 : 0;

  const coefs: CoefsReport = {
    floors: {
      ...floorsX,
      eligibleTotal,
      excludedTotal: baseTotal - eligibleTotal,
      excludedChapters: [...excludedChapters].sort(),
      eligibleLines: eligibleLines.map((l) => ({
        code: l.code,
        desc: l.desc,
        chapter: l.chapter,
        total: l.totalIndexed,
      })),
      footprint: leanFootprint(records),
      floorsAmount,
    },
    regional: regionalX,
  };

  const status: ProjectStatus = {
    complete:
      !warns.some((w) => w.level === "خطا") &&
      floorsX.status !== "ناقص" &&
      regionalX.status !== "ناقص",
    errors: warningsByLevel["خطا"] ?? 0,
    warningsN: warningsByLevel["هشدار"] ?? 0,
    info: warningsByLevel["اطلاع"] ?? 0,
    floorsStatus: floorsX.status,
    regionalStatus: regionalX.status,
  };

  // ۸) موتورهای فاز B: دو موتور مجزا («تعدیل پیمان» و «برآورد به‌هنگام»).
  // هر دو می‌توانند همزمان فعال باشند؛ ورودی، فرمول و خروجی هر کدام
  // جداست و روی زنجیرهٔ مالی بالا اثری ندارد (قاعدهٔ طلایی ۵).
  // فاز E-9 §۳.۳ — بند ۵ بخشنامهٔ ۱۵۵۲۳۳: مبلغِ ردیف‌های دارایِ واحدِ
  // «مترمکعب کیلومتر» در فصل‌های غیر از فصل حمل، به فصل ۲۸ منتقل می‌شود
  // تا با شاخص‌های فصل حمل تعدیل شوند.
  const haulCh = haulTargetChapter();
  let haulMoved = 0;
  const chapAmt: Record<string, number> = {};
  for (const l of lines) {
    let ch = l.chapter;
    if (ch !== haulCh && isHaulUnit(l.unit)) {
      ch = haulCh;
      haulMoved += l.totalIndexed ?? 0;
    }
    chapAmt[ch] = (chapAmt[ch] ?? 0) + (l.totalIndexed ?? 0);
  }
  const adjustment = runAdjustment(
    settings,
    {
      chapter_amounts: chapAmt,
      haul_moved_amount: haulMoved,
      floors_amount: floorsAmount,
      base_total: baseTotal,
      site_setup: siteSetup,
      floors_info: {
        value: floorsX.value,
        status: floorsX.status,
        eligible_total: eligibleTotal,
        excluded_total: baseTotal - eligibleTotal,
      },
      advance_payment: advancePayment,
      overhead_coef: settings.overheadCoef,
      regional_coef: regionalX.value ?? 1,
      grand_total: grandTotal,
    },
    warns,
  );

  return {
    lines,
    rebar: rebarX.lines,
    chapterSums,
    baseTotal,
    floorsAmount,
    overheadAmount,
    regionalAmount,
    siteSetup,
    grossPayable,
    grandTotal,
    // خالص پرداختی (خروجی جداگانه، بر ناخالص اثر ندارد)
    insurance,
    tax,
    goodJob,
    advancePayment,
    totalDeductions,
    netPayable,
    // گزارش شاخص تعدیل (دوره، نوع و منبع هر فصل) — null در دورهٔ مبنا
    index: indexReport,
    // ضرایب زنجیرهٔ مالی با وضعیت و منبع (ایراد ۳ و ۴)
    coefs,
    // رجیستری مرکزی هشدارها (ایراد ۱۰)
    warnings: warns,
    warningsByLevel,
    status,
    quality,
    records,
    // موتورهای مستقل تعدیل فاز B — هرگز روی زنجیرهٔ مالی اثر ندارند
    adjustment,
    // پنل قیمت دستی (فاز C): شمارش هر سطح، جمع ستاره‌دارها
    priceStatusSummary,
    needsPriceEntry,
    starredTotal,
    starredPct,
  };
}

