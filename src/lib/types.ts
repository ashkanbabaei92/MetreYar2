// ─────────────────────────────────────────────────────────────
// انواع دادهٔ اصلی سامانهٔ «متره‌یار هوشمند»
// ─────────────────────────────────────────────────────────────

/** ردیف فهرست‌بهای واحد پایه */
export interface FehrestRow {
  code: string; // کد ۶ رقمی ردیف مثل 060101
  chapter: string; // شمارهٔ فصل مثل "06"
  desc: string; // شرح ردیف
  unit: string; // واحد (مترمربع، کیلوگرم و...)
  price: number; // بهای واحد (ریال)
  estimated?: boolean; // قیمت تخمینی پیش‌فرض است (تا جایگزینی با فایل رسمی)
}

/** فصل‌های فهرست‌بها */
export interface FehrestChapter {
  no: string;
  title: string;
}

/**
 * نوع جدول خروجی Revit که به‌صورت خودکار تشخیص داده می‌شود.
 */
export type TableKind =
  | "lean_concrete" // بتن مگر
  | "structural_concrete" // بتن سازه‌ای
  | "formwork_foundation" // قالب‌بندی پی
  | "formwork_super" // قالب‌بندی سازه
  | "joist_floor" // سقف تیرچه‌بلوک
  | "joist_materials" // بتن پاشنه و یونولیت
  | "rebar_detailed" // لیستوفر آماتور تفصیلی
  | "rebar_joist" // آرماتور تیرچه
  | "rebar_connection" // آرماتور اتصال تیرچه
  | "mapping" // خروجی Mapping داینامو
  | "unknown";

/** جدول خوانده‌شده از خروجی Schedule رویت */
export interface RevitTable {
  id: string;
  fileName: string;
  title: string; // عنوان تشخیصی جدول
  headers: string[];
  rows: TableRow[];
  grandTotal?: Record<string, number>; // مقادیر Grand total رسمی رویت
  kind: TableKind;
  kindConfidence: number; // اطمینان تشخیص نوع جدول
  colMap: Partial<Record<SemanticCol, number>>;
  warnings: string[];
}

export type SemanticCol =
  | "mark"
  | "familyType"
  | "category"
  | "hostCategory"
  | "hostMark"
  | "material"
  | "level"
  | "count"
  | "length"
  | "width"
  | "diameter"
  | "barType"
  | "shape"
  | "spacing"
  | "volume"
  | "area"
  | "weight";

export interface TableRow {
  cells: string[];
  values: Partial<Record<SemanticCol, number>>;
  texts: Partial<Record<SemanticCol, string>>;
  isSubtotal: boolean; // ردیف جمع‌جزئی داخلی Revit (از محاسبات کنار می‌ماند)
}

/** رکورد کمیت استخراج‌شده از جداول (ورودی موتور متره) */
export interface QuantityRecord {
  tableId: string;
  fileName: string;
  tableTitle: string;
  kind: TableKind;
  ref: string; // Mark یا Family یا Category
  group: string; // گروه سازه‌ای تشخیصی
  material: string;
  /** مقاومت فشاری استخراج‌شده از نام متریال Revit (ایراد ۱) — یا null */
  strengthMpa?: number | null;
  /** تراز/طبقهٔ Revit (ستون Level) — مبنای جدول ضریب طبقات (ایراد ۳) */
  level?: string;
  qty: number; // مقدار عددی (به واحد استاندارد SI)
  unit: "m3" | "m2" | "kg" | "m" | "count";
  detail: string;
  fromGrandTotal?: boolean;
}

/** نحوهٔ تطبیق ردیف با فهرست‌بها */
export type MatchMethod = "rule-exact" | "rule-fuzzy" | "fuzzy" | "manual" | "direct-code" | "manual-starred";

// ═══════ پنل قیمت دستی (فاز C — §۱۵-۴): مدل داده‌ای ═══════

/** رکورد قیمت دستی یک ردیف — هر عدد ردیخی‌پذیر (قاعدهٔ طلایی ۲) */
export interface ManualPriceRecord {
  price: number;
  source: string; // بخشنامه / استعلام / فاکتور / توافق / ویرایش قدیمی
  docNo: string;
  docDate: string; // شمسی
  note: string;
  status: string; // قطعی / دستی / موقت / پیش‌فرض اپ / نیازمند تأیید
  chapter: string;
  user: string;
  at: string; // زمان ورود (شمسی + ساعت)
}

/** رکورد کد جایگزین فهرست‌بها */
export interface ManualCodeRecord {
  code: string;
  reason: string;
  user: string;
  at: string;
}

/** رکورد ردیف مستثنی‌شده */
export interface ExcludedRecord {
  id: string;
  reason: string;
  user: string;
  at: string;
}

/** ردیف غیرفهرستی ستاره‌دار (ورود کامل دستی) */
export interface StarredRow {
  code: string;
  desc: string;
  unit: string;
  qty: number;
  price: number;
  chapter: string; // فصل برای شاخص تعدیل
  source: string;
  docNo: string;
  docDate: string;
  note: string;
  user: string;
  at: string;
}

/** نوع رویداد در سابقهٔ ویرایش (ستون «نوع» در شیت سابقهٔ ویرایش) */
export type AuditKind = "price" | "setting" | "meta";
export const AUDIT_KIND_LABELS: Record<AuditKind, string> = {
  price: "قیمت/کد",
  setting: "تنظیمات",
  meta: "مشخصات",
};
export const AUDIT_KIND_CODES: Record<string, AuditKind> = Object.fromEntries(
  Object.entries(AUDIT_KIND_LABELS).map(([k, v]) => [v, k as AuditKind]),
);

/** یک رویداد در سابقهٔ ویرایش */
export interface AuditEntry {
  at: string;
  user: string;
  item: string;
  field: string;
  old: unknown;
  new: unknown;
  source: string;
  kind: AuditKind;
}

export const MANUAL_SOURCES = [
  "بخشنامه", "استعلام", "فاکتور", "توافق", "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)",
] as const;

export const MANUAL_STATUSES = [
  "قطعی", "دستی", "موقت", "پیش‌فرض اپ", "نیازمند ورود",
] as const;

/** ردیف خروجی متره (خلاصه‌متره / صورت‌وضعیت) */
export interface BoqLine {
  id: string;
  rowNo: number;
  chapter: string;
  chapterTitle: string;
  code: string;
  desc: string;
  unit: string;
  qty: number; // مقدار خالص (مرحلهٔ ۱۱: هیچ ضریب پرتی وجود ندارد)
  price: number; // بهای واحد
  total: number; // بهای کل = qty × price
  matchMethod: MatchMethod;
  confidence: number; // ۰ تا ۱
  sources: QuantityRecord[];
  estimatedPrice: boolean;
  needsReview: boolean;
  note?: string;
  candidates: { code: string; desc: string; price: number; score: number }[];
  /** لایهٔ شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) — قبل از ضرایب زنجیرهٔ مالی */
  indexFactor: number; // ضریب فصلِ این ردیف (۱ در دورهٔ مبنا)
  totalIndexed: number; // مبلغ تعدیل‌شده = total × indexFactor
  /** مقاومت فشاری مؤثر این ردیف (ایراد ۱) — یا null برای ردیف‌های غیربتنی */
  strengthMpa?: number | null;
  /** منشأ مقاومت: «material» (نام متریال Revit) یا «setting» (ورودی دستی) */
  strengthOrigin?: "material" | "setting" | null;
  // ── پنل قیمت دستی (فاز C — §۱۵-۴) ──
  /** قیمت فهرست‌بها پیش از بازنویسی دستی (برای نمایش دوگانه و اختلاف ٪) */
  appPrice?: number | null;
  basePrice?: number | null;
  /** درصد اختلاف قیمت دستی با قیمت فهرست */
  diffPct?: number | null;
  /** سطح قیمت: دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی */
  priceStatus?: string;
  manual?: ManualPriceRecord | StarredRow | null;
  starred?: boolean;
}

/** رجیستری مرکزی هشدارها (ایراد ۱۰) — هر هشدار ساختار یکسان دارد */
export interface Warning {
  level: "خطا" | "هشدار" | "اطلاع";
  category: string;
  item: string;
  message: string;
  action: string;
  ref: string;
}

/** یادداشتِ طبقه‌بندی تأخیر برای یک سه‌ماههٔ کارکرد (فاز E-6 Part C گام ۳) */
export interface DelayNote {
  q: string;
  rule: string; // «غیرمجاز» / «تعیین‌نشده»
  note: string;
}

/** بازنویسیِ شاخصِ یک سه‌ماههٔ پس از مدت (بندهای ۲-۵-۲/۲-۵-۳) */
export interface DelayOverride {
  rule: string;
  basis_q: string | null;
}

/** اطلاعاتِ مدت پیمان و طبقه‌بندی تأخیرها (بند ۲-۵) */
export interface DelayInfo {
  contract_end: string | null;
  term_end: string | null;
  term_quarters: string[];
  override: Record<string, DelayOverride>;
}

/** ورودی دستی یک تراز در floorsData: عدد مساحت (قدیمی) یا رکورد */
export type FloorManualEntry = {
  area?: number | null;
  /** انتخاب دستیِ «طبقه بودن» تراز (درخواست کاربر — بند ۱) */
  isFloor?: boolean | null;
};

/** ردیف جدول طبقات (ضریب طبقات — ایراد ۳) */
export interface FloorRow {
  name: string;
  kind: "above" | "ground" | "below_base" | "roof" | "none";
  /** نوع پیش‌فرض تراز قبل از انتخاب دستیِ «طبقه بودن» (بند ۱) */
  autoKind: "above" | "ground" | "below_base" | "none";
  index: number;
  areaModel: number | null;
  areaManual: number | null;
  area: number | null;
}

/** گزارش ضریب طبقات (ایراد ۳ — پیوست ۲) */
export interface FloorsCoef {
  value: number | null;
  status: string; // محاسبه‌شده / دستی / ناقص
  source: string | null;
  rows: FloorRow[];
  calc: { divisor: string; num: number; den: number; pAlt: number; altLabel: string } | null;
  eligibleTotal: number;
  excludedTotal: number;
  excludedChapters: string[];
  eligibleLines: { code: string; desc: string; chapter: string; total: number }[];
  footprint: {
    volume: number;
    thickness: number;
    area: number;
    assumedThickness: boolean;
    status: string;
  } | null;
  floorsAmount: number;
  formula: string | null;
  clause: string | null;
}

/** گزارش ضریب منطقه‌ای (ایراد ۴ — بخشنامه ۹۴/۶۹۴۱۶) */
export interface RegionalCoef {
  value: number | null;
  status: string; // استخراج‌شده / دستی / ناقص
  source: string | null;
}

/** ضرایب زنجیرهٔ مالی با وضعیت و منبع */
export interface CoefsReport {
  floors: FloorsCoef;
  regional: RegionalCoef;
}

/** وضعیت کلی پروژه: ناقص اگر هشدار سطح خطا یا ضریب ناقص وجود دارد */
export interface ProjectStatus {
  complete: boolean;
  errors: number;
  warningsN: number;
  info: number;
  floorsStatus: string;
  regionalStatus: string;
}

/** ردیف لیستوفر آرماتور */
export interface RebarLine {
  mark: string;
  group: string; // پی / تیر / ستون / پله / دال / دیوار / سقف تیرچه / نامشخص
  evidence?: string; // گروه میزبان آرماتور (مبنای تشخیص بتن مسلح در ۰۸۰۳۱۰)
  hostMark?: string; // مارک خام میزبان (ستون «Host Mark») — مبنای per-element در ۰۸۰۳۱۰
  barType: string; // Φ14 ...
  diameter: number;
  steelGrade: string; // A-I / AIII ...
  shape: string;
  count: number;
  totalLength: number; // متر، مجموع
  weight: number; // کیلوگرم
  priceCode: string;
  source: string;
  // ستون‌های لیستوفر (ایراد ۱۱):
  level: string; // طبقه — ستون «Level» جدول Revit (خالی مجاز است؛ ساخته نمی‌شود)
  perBarLength: number; // طول هر شاخه (m) = totalLength / count
  unitWeight: number; // وزن واحد (kg/m) = weight / totalLength
}

/** ساختار نتیجهٔ کامل پردازش پروژه */
export interface ProjectResult {
  lines: BoqLine[];
  rebar: RebarLine[];
  chapterSums: { chapter: string; title: string; total: number }[];
  /** زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸ — مرحلهٔ ۱۱):
   *  جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای
   *  + تجهیز و برچیدن = مبلغ ناخالص نهایی. کسورات قانونی جزو ناخالص
   *  نیستند و فقط در خروجی جداگانهٔ «خالص پرداختی» محاسبه می‌شوند. */
  baseTotal: number; // جمع مبالغ تعدیل‌شدهٔ ردیف‌های فهرست‌بها
  floorsAmount: number; // پس از ضریب طبقات
  overheadAmount: number; // پس از ضریب بالاسری
  regionalAmount: number; // پس از ضریب منطقه‌ای
  siteSetup: number; // تجهیز و برچیدن کارگاه (مبلغ ورودی کاربر)
  grossPayable: number; // مبلغ ناخالص نهایی = regionalAmount + siteSetup
  grandTotal: number; // برابر grossPayable (کسورات بر آن اثر ندارند)
  /** خالص پرداختی — خروجی جداگانه با برچسب روشن، بر ناخالص اثر ندارد */
  insurance: number; // کسر: بیمه
  tax: number; // کسر: مالیات
  goodJob: number; // کسر: حسن انجام کار
  advancePayment: number; // کسر: پیش‌پرداخت
  totalDeductions: number; // مجموع کسورات
  netPayable: number; // ناخالص نهایی − مجموع کسورات
  /** گزارش شاخص تعدیل فهرست‌بها (دوره، نوع و منبع هر فصل) — null در دورهٔ مبنا */
  index: IndexReport | null;
  /** ضرایب زنجیرهٔ مالی با وضعیت و منبع (ایراد ۳ و ۴) */
  coefs: CoefsReport;
  /** رجیستری مرکزی هشدارها (ایراد ۱۰) — خطا / هشدار / اطلاع */
  warnings: Warning[];
  warningsByLevel: Record<string, number>;
  /** وضعیت کلی پروژه: complete = بدون خطا و بدون ضریب ناقص */
  status: ProjectStatus;
  quality: QualityReport;
  records: QuantityRecord[];
  /** موتورهای مستقل تعدیل فاز B — هرگز روی زنجیرهٔ مالی اثر ندارند */
  adjustment: AdjustmentResult | null;
  // ── پنل قیمت دستی (فاز C — §۱۵-۴) ──
  priceStatusSummary: Record<string, number>;
  needsPriceEntry: number;
  starredTotal: number;
  starredPct: number;
}

export interface QualityReport {
  tablesParsed: number;
  tablesUnknown: number;
  rowsRead: number;
  linesMatched: number;
  linesExact: number;
  linesFuzzy: number;
  linesEstimatedPrice: number;
  linesNeedReview: number;
  warnings: string[];
}

/** نگاشت فرض‌های فنی پروژه به کدهای فهرست‌بهای ۱۴۰۴ — تنها یک‌جا تعریف می‌شود.
 *  مقدار انتخابی کاربر از رابط کاربری (defaultSettings) خوانده می‌شود و
 *  buildPlans() کد/شرح/بهای ردیف را از همین جداول می‌سازد. */
// مقاومت فشاری مشخصهٔ بتن (MPa) → [کد فهرست‌بها، بهای پیش‌فرض ریال]
export const CONCRETE_STRENGTH_CODES: Record<number, [string, number]> = {
  12: ["080103", 17996000],
  16: ["080104", 18904000],
  20: ["080105", 19535000],
  25: ["080106", 20162000],
  30: ["080107", 20924000],
  35: ["080108", 21422000],
  40: ["080109", 22200000],
};
// عیار سیمان بتن مگر (kg/m³) → [کد، بهای پیش‌فرض]
export const LEAN_CEMENT_CODES: Record<number, [string, number]> = {
  100: ["080101", 16039000],
  150: ["080102", 17152000],
};
// ضخامت سقف تیرچه‌بلوک (cm) → [کد، بهای پیش‌فرض]
export const JOIST_BLOCK_THICKNESS_CODES: Record<number, [string, number]> = {
  25: ["100305", 8391000],
  30: ["100306", 9101000],
};
// اضافه‌بهای مقاومت بتن سقف تیرچه‌بلوک (MPa) → [کد، بهای پیش‌فرض] یا null
// بند ۸ الزامات عمومی فصل دهم فهرست‌بهای ۱۴۰۴: بتن سقف ۲۰ MPa فرض شده؛
// بیش از ۲۰ تا ۲۵ MPa → ۱۰۰۷۰۱، بیش از ۲۵ تا ۳۰ MPa → ۱۰۰۷۰۲.
// قالب‌بندی دال مستقل (تاوه) بر اساس ارتفاع طبقه (متر) → [کد، بهای پیش‌فرض]
// فصل ۰۶ ردیف ۰۶۰۴۰۱..۰۶۰۴۰۴: نرخ بر اساس ارتفاع تا ۳/۵، ۵/۵، ۷/۵ و بالاتر.
export const SLAB_FORMWORK_CODES: [number, string, number][] = [
  [3.5, "060401", 4107000],
  [5.5, "060402", 4607000],
  [7.5, "060403", 5287000],
  [Infinity, "060404", 6091000],
];
export const JOIST_BLOCK_STRENGTH_SURCHARGE: Record<number, [string, number] | null> = {
  20: null,
  25: ["100701", 59500],
  30: ["100702", 76500],
};

/** تنظیمات مالی و محاسباتی پروژه توسط کاربر */
/** تمدید مدت پیمان (بخشنامهٔ ۲۰۸۰، بند ۲-۵) */
export interface ContractExtension {
  date: string; // تاریخ تمدید (شمسی)
  months: number; // مدت تمدید به ماه
  kind: "مجاز" | "غیرمجاز" | "تعیین‌نشده"; // بندهای ۲-۵-۱..۲-۵-۳
  docNo: string; // شماره سند تمدید
}

export interface ProjectSettings {
  joistSpacing: number; // فاصلهٔ محور تا محور تیرچه (متر) برای محاسبهٔ مساحت سقف
  haulDistanceKm: number; // مسافت حمل مصالح (km) — بازهٔ ۳۰–۷۵ → ردیف ۲۸۰۱۰۱
  surchargeRebarDensity: boolean; // اضافه‌بهای ۰۸۰۳۱۱ (سختی ارتعاش بتن) — اختیاری
  surchargeReinforcedConcrete: boolean; // اضافه‌بهای ۰۸۰۳۱۰ (بتن مسلح، per-element) — اختیاری
  surchargeThinConcrete: boolean; // اضافه‌بهای ۰۸۰۳۰۴ (کف‌سازی ≤ ۱۵cm روی زمین) — اختیاری
  /** فرض‌های فنی: کد و بهای ردیف بتن/سقف از این مقادیر ساخته می‌شود */
  concreteStrengthMpa: {
    foundation: number; // پی
    columnBeam: number; // ستون و تیر
    slab: number; // سقف
    stair: number; // پله
  };
  leanCementKg: number; // عیار سیمان بتن مگر: ۱۰۰ → ۰۸۰۱۰۱، ۱۵۰ → ۰۸۰۱۰۲
  joistBlockThicknessCm: number; // ضخامت سقف تیرچه‌بلوک: ۲۵ → ۱۰۰۳۰۵، ۳۰ → ۱۰۰۳۰۶
  joistBlockConcreteMpa: number; // مقاومت بتن سقف تیرچه‌بلوک: ۲۰ → بدون اضافه‌بها، ۲۵ → ۱۰۰۷۰۱، ۳۰ → ۱۰۰۷۰۲
  joistBlockTopThicknessCm: number; // ضخامت بتن روی بلوک طبق مشخصات (cm) — مازاد بر ۵ cm جداگانه
  /** ارتفاع طبقه برای انتخاب ردیف قالب‌بندی دال/تاوه (ایراد ۲ — فصل ۰۶) */
  slabFormworkHeightM: number; // پیش‌فرض ۳٫۵ → ۰۶۰۴۰۱
  /** وزن دستی میلگرد هر گروه سازه‌ای (kg) — ایراد ۱۴: خالی → از مدل */
  rebarManualWeight: Record<string, number>;
  /** ضرایب زنجیرهٔ مالی — ترتیب: جمع ردیف‌ها × طبقات × بالاسری × منطقه‌ای + تجهیز */
  overheadCoef: number; // ضریب بالاسری (پیش‌فرض‌های OVERHEAD_PRESETS در UI)
  /** ضریب منطقه‌ای (ایراد ۴): عدد دستی، یا null → جستجو در جدول بخشنامه ۹۴/۶۹۴۱۶ */
  regionalCoef: number | null;
  regionalSelection: {
    province: string;
    city: string;
    district: string;
    discipline: string;
  };
  /** ضریب طبقات (ایراد ۳): floorsAuto=true → فرمول پیوست ۲؛ false → floorsCoef دستی */
  floorsCoef: number; // ورودی دستی (فقط وقتی floorsAuto=false)
  floorsAuto: boolean; // محاسبه از فرمول پیوست ۲
  floorsData: Record<string, number | FloorManualEntry>; // مساحت دستی هر تراز (+ انتخاب طبقه بودن)
  floorsDivisor: "100×S" | "S"; // مخرج فرمول پیوست ۲ (متن رسمی: ۱۰۰×S)
  floorsExcludedChapters: string[]; // فصول مستثنی از ضریب طبقات (پیوست ۲ بند ۱-۳)
  floorsRoofLevels: string[]; // ترازهای بام/مرجع (غیرطبقه)
  siteSetupAmount: number; // مبلغ تجهیز و برچیدن کارگاه (ریال) — ورودی کاربر
  /** کسورات قانونی (درصد) — فقط برای خروجی جداگانهٔ «خالص پرداختی» */
  insurancePct: number; // بیمه
  taxPct: number; // مالیات
  goodJobPct: number; // حسن انجام کار
  advancePayment: number; // پیش‌پرداخت (ریال)
  /** شاخص تعدیل فهرست‌بها (کلیات بند ۲۲): دورهٔ هدف یا null/"" → دورهٔ مبنا */
  indexTargetPeriod: string | null;
  /** نمایش */
  currency: "rial" | "toman"; // واحد پول نمایش
  rounding: boolean; // رند کردن مبالغ به ۱۰۰۰ ریال
  manualCodes: Record<string, string | ManualCodeRecord>; // بازنویسی دستی کد هر ردیف
  priceOverrides: Record<string, number>; // ساختار قدیمی (قبل از مرحلهٔ ۱۳)
  manualPrices: Record<string, ManualPriceRecord>; // پنل قیمت دستی (فاز C)
  excluded: (string | ExcludedRecord)[]; // ردیف‌های مستثنی‌شده از محاسبات
  starredRows: StarredRow[]; // ردیف‌های غیرفهرستی ستاره‌دار (ورود کامل دستی)
  priceAudit: AuditEntry[]; // سابقهٔ ویرایش (Audit trail)
  // ── فاز E-۵: پروفایل پروژه ──
  fehrestYear: string; // سال فهرست‌بهای انتخابیِ این پروژه
  fehrestDbYear: string; // سال فهرستِ بارگذاری‌شده
  priceUser: string; // نام کاربر واردکنندهٔ قیمت‌ها
  priceDiffWarnPct: number; // آستانهٔ هشدار اختلاف قیمت (درصد)
  priceProjectFile: string; // مسیر فایل پروژه (برای فایل کناری قیمت‌ها)
  _manualMigrated?: boolean; // پرچم داخلی مهاجرت یک‌باره
  // ═══ فاز B: دو موتور مجزای تعدیل (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند) ═══
  /** موتور ۱: تعدیل پیمان (فصل به فصل) */
  tadilEnabled: boolean;
  /** موتور ۲: برآورد به‌هنگام */
  baravordEnabled: boolean;
  /** تاریخ تسلیم پیشنهاد پیمانکار (شمسی) → Io = سه‌ماههٔ آن (پیوست ۳، بند ۱-۲) */
  proposalDate: string;
  /** مهلت تسلیم پیشنهاد (شمسی) — در ترک تشریفات خالی است؛ در تابستان ۱۴۰۵
   *  Io = شاخص ماهانهٔ خرداد ۱۴۰۵ (بخشنامهٔ ۱۴۴۳۷۴) */
  proposalDeadline: string;
  /** ضریب پیشنهادی پیمانکار — دستی، در A₀ ضرب می‌شود (مبلغ کارکرد به قیمت پیمان) */
  proposalCoef: number;
  /** مبنای مبلغ پایهٔ A: «با ضرایب» = قیمت پیمان، «بدون ضرایب» = قیمت فهرست‌بها */
  aBasis: "با ضرایب" | "بدون ضرایب";
  /** شاخص دستی هر فصل: {"06": {io, it, src}} — دستی مقدم بر جدول پیوست ۳.
   * src (منبع) از گام ۸ اجباری است اگر io یا it وارد شده باشد. */
  chapterIndexManual: Record<string, { io?: number; it?: number; src?: string }>;
  /** شاخص دستی رشته (تجهیز/برچیدن و ردیف‌های بدون شاخص فصل — بند ۴) */
  disciplineIndexManual: { io?: number; it?: number; src?: string };
  /** شاخص موقت ۱۴۰۵Q1 = این ضریب × آخرین شاخص قطعی (۱۴۰۴Q4) — تصویری ⇒ دستی */
  provisionalCoef1405q1: number | null;
  // ── موتور ۱ — تعدیل پیمان: ΔP = k × Σ_c (It_c/Io_c − 1) × A_c ──
  /** k = ۰٫۹۵ از بخشنامه ۲۰۸۰ (تصویری) ⇒ پیش‌فرض اپ، نیازمند تأیید */
  tadilCoef: number;
  completedWithinTerm: boolean | null; // فاز E-6: اتمام کار در مدت پیمان (تبصرهٔ ۲ بند ۱-۸)
  coefRounding2080: boolean; // فاز E-6: گردکردن ضریب به ۲ رقم اعشار (بند ۸-۲)
  // ── فاز E-6 Part C: ورودی‌های قرارداد (بخشنامهٔ ۲۰۸۰) ──
  /** روش شاخص مبنا (بندهای ۱-۶-۱/۱-۶-۲): proposal_period | fehrest_period | no_base_list */
  baseIndexMethod: "proposal_period" | "fehrest_period" | "no_base_list";
  /** تاریخ تسلیم کتبیِ پیشنهادِ نهایی در ترک تشریفات (بندهای ۱-۶-۱ دوم/۱-۶-۲) */
  finalOfferDate: string;
  /** مدت اولیهٔ پیمان به ماه (بند ۲-۵) — null = نامشخص */
  contractDurationMonths: number | null;
  /** تمدیدهای مدت پیمان: [{date, months, kind, doc_no}] — kind: مجاز/غیرمجاز/تعیین‌نشده */
  contractExtensions: ContractExtension[];
  /** وضعیت خاتمه: فعال | خاتمه بدون قصور | فسخ با قصور (بندهای ۶ و ۷) */
  contractStatus: "فعال" | "خاتمه بدون قصور" | "فسخ با قصور";
  /** کسر ۵٪ در فسخ با قصور، حتی با تعدیل منفی (بند ۷ — تفسیر) */
  faultDeductionOnNegative: boolean;
  /** مبلغ اولیهٔ پیمان (ریال) — ملاک مسیر ۲-۱/۲-۲ و سقف ۱۰٪ (نامه بند ۶) */
  contractInitialAmount: number | null;
  // فاز E-6 Part C گام ۵ (بندهای ۳-۱..۳-۵): کارهای جدید
  newItemMethod?: string;          // «فهرست پیمان» (پیش‌فرض) /
                                    // «فهرست پایه» / «قیمت روز» / «ترکیب»
  newItemAmount?: number;          // مبلغ کار جدید (ریال)
  newItemAmountAttached?: number;  // فقط ۳-۴: بخشِ ۳-۱
  newItemBasePeriod?: string;      // کلید سه‌ماهه (مثل 1404Q2)
  /** مسیر شاخص: گروهی (پیش‌فرض) | رشته‌ای | خودکار (از روی مبلغ اولیه) */
  indexMethod: "گروهی" | "رشته‌ای" | "خودکار";
  /** تاریخ آخرین صورت‌وضعیت موقت (بند ۲-۶) */
  lastProvisionalDate: string;
  /** تبصرهٔ ۱ بند ۲-۶: «average» = میانگین شاخص‌ها (متنِ بند) |
   * «own_period» = شاخصِ هر سه‌ماهه. */
  provisionalDiffMethod: "average" | "own_period";
  /** تاریخ شروع پیمان (شمسی) — ملاک محاسبهٔ پایان مدت (بند ۲-۵).
   * در UI از meta.contractDate همگام می‌شود (دقیقاً مثل پایتون). */
  contractDate: string;
  tadilIoPeriod: string; // کلید دورهٔ مبنا (base/q1..q4)
  tadilItPeriod: string; // کلید دورهٔ هدف
  tadilAdvanceMode: "کل مبلغ کارکرد" | "کسر پیش‌پرداخت";
  tadilDelayMode: "مشمول کل دوره" | "مستثنی کردن دورهٔ تأخیر";
  tadilDelayDate: string; // تاریخ تحویل قرارداد (حالت تأخیر)
  tadilAllowNegative: boolean; // اجازهٔ تعدیل منفی
  tadilApproved: boolean; // تا تأیید، خروجی «پیش‌نویس» است
  // ── موتور ۲ — برآورد به‌هنگام: A_new = Σ_c A_c × It_c/Io_c (بدون k) ──
  baravordIoPeriod: string;
  baravordItPeriod: string;
  baravordApproved: boolean;
  /** دورهٔ انجام کار (شمسی) — تقسیم کارکرد بین سه‌ماهه‌ها */
  workPeriodStart: string;
  workPeriodEnd: string;
}

/**
 * پیش‌فرض‌های ضریب بالاسری طبق دستورالعمل کاربرد (بند ۲-۷):
 * نوع پروژه × نوع قرارداد. مقدار پیش‌فرض = عمرانی + مناقصه.
 */
export const OVERHEAD_PRESETS: [key: string, coef: number, label: string][] = [
  ["overhead_civil_tender", 1.3, "عمرانی — مناقصه"],
  ["overhead_civil_direct", 1.2, "عمرانی — ترک تشریفات"],
  ["overhead_noncivil_tender", 1.4, "غیرعمرانی — مناقصه"],
  ["overhead_noncivil_direct", 1.3, "غیرعمرانی — ترک تشریفات"],
];

// ── شاخص تعدیل فهرست‌بها (کلیات فهرست‌بهای ۱۴۰۴، بند ۲۲) ──

/** یک رکورد شاخص در indices/abnieh.json */
export interface IndexRecord {
  period: string; // دورهٔ شاخص (مثلاً «1403Q4»)
  chapter: string; // شمارهٔ فصل (دو رقم) و در صورت نیاز group
  value: number; // مقدار شاخص (رکورد موقت: ضریب نسبت به آخرین قطعی قبل از آن)
  kind: "قطعی" | "موقت";
  source: string; // شماره/تاریخ بخشنامه
}

/** ساختار فایل indices/abnieh.json */
export interface IndexTableData {
  base_period: string | null;
  periods: string[];
  indices: IndexRecord[];
}

/** گزارش شاخص یک فصل برای دورهٔ هدف */
export interface IndexChapterRow {
  chapter: string;
  factor: number | null;
  kind: "قطعی" | "موقت" | null;
  source: string | null;
  level: number | null;
}

/** گزارش کامل لایهٔ شاخص تعدیل */
export interface IndexReport {
  basePeriod: string | null;
  targetPeriod: string | null;
  provisional: boolean; // آیا دورهٔ هدف شامل شاخص موقت است
  chapters: IndexChapterRow[];
}

// ── موتورهای مستقل تعدیل فاز B (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند) ──

/** یک رکورد از رجیستری «مقادیر منتظر تأیید» (شیت جداگانه) */
export interface AdjPending {
  item: string;
  value: number | null;
  source: string;
  page: string;
  status: string;
  action: string;
}

/** یک قدم از زنجیرهٔ شفافِ محاسبهٔ A: [برچسب، مبلغ، توضیح] */
export interface AdjChainRow {
  0: string;
  1: number;
  2: string;
}

/** یک ردیف فصل در خروجی موتورها */
export interface AdjChapterRow {
  chapter: string;
  title: string;
  amount: number;
  io: number;
  it: number | null;
  ratio: number | null;
  value: number;
  delta?: number;
  deltaDefinitive?: number;
  status: string;
  src: string;
  quarters?: [string, number, string][];
  coef_rows?: [string, number, number][]; // فاز E-6: (سه‌ماهه, ضریب خام, ضریب گردشده)
  delay_notes?: DelayNote[]; // فاز E-6 Part C گام ۳: طبقه‌بندی تأخیر
  delta_k095?: number; // مبنای تبصرهٔ ۲
}

/** ردیف تجهیز و برچیدن کارگاه (شاخص رشته‌ای — بند ۴) */
export interface AdjSetupRow {
  amount: number;
  io: number;
  it: number;
  ratio: number | null;
  value: number;
  delta: number;
  deltaDefinitive: number;
  delta_k095?: number; // مبنای تبصرهٔ ۲
  coef_rows?: [string, number, number][];
  delay_notes?: DelayNote[]; // فاز E-6 Part C گام ۳
  status: string;
  src: string;
  // فاز E-6 Part C گام ۵: فقط ردیفِ کار جدید
  method?: string;        // روشِ کار جدید (۳-۱..۳-۴)
  amount_own?: number;    // بخشِ ۳-۱ (فهرست پیمان)
  amount_new?: number;    // بخشِ ۳-۲/۳-۳
  io_new?: number | null; // شاخص مبنای کار جدید
  conv?: number;          // ضریبِ تبدیلِ ۳-۵
}

/** ورودی موتورها — از نتیجهٔ زنجیرهٔ مالی اصلی ساخته می‌شود */
export interface AdjustmentCtx {
  chapter_amounts: Record<string, number>;
  /** فاز E-9 §۳.۳ — بند ۵: مبلغِ ردیف‌های «مترمکعب کیلومتر» که از فصل‌های
   * غیر از فصل حمل به فصل ۲۸ منتقل شده‌اند (۰ اگر چنین ردیفی نیست). */
  haul_moved_amount?: number;
  floors_amount: number;
  base_total: number;
  site_setup: number;
  advance_payment: number;
  overhead_coef: number;
  regional_coef: number;
  grand_total: number;
  floors_info: {
    value: number | null;
    status: string;
    eligible_total: number;
    excluded_total: number;
  };
}

/** خروجی موتور ۱ — تعدیل پیمان */
export interface TadilResult {
  mode: "تعدیل پیمان";
  formula: string;
  error?: string;
  coef: number;
  k_diff: number; // فاز E-6: مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ + بند ۸-۴)
  coef_rounding: boolean;
  completed_within_term: boolean;
  k_status: string; // فاز E-10 §۲: برچسبِ قطعی/علی‌الحسابِ k (بند ۱-۸)
  k_provisional: boolean; // فاز E-10 §۲: completed_within_term نامشخص ⇒ k=۰٫۹۵ علی‌الحساب
  work_period_missing: boolean; // فاز E-10 §۲: دورهٔ کارکرد خالی ⇒ قفلِ خروجیِ نهایی
  contract_status: string; // فاز E-6 Part C گام ۴ (بندهای ۶ و ۷)
  deduction_fault: number; // کسر ۵٪ در فسخ با قصور (بند ۷) — عددِ منفی
  io_q: string | null;
  io_month: string | null;
  split: [string, number][];
  delay_info: DelayInfo; // فاز E-6 Part C گام ۳
  index_method_resolved: {
    // فاز E-6 Part C گام ۶ (بندهای ۲-۱/۲-۲)
    method: "گروهی" | "رشته‌ای";
    source: string;
  };
  base_amount: number;
  work_base: number;
  chain: AdjChainRow[];
  setup_amount: number;
  setup_row: AdjSetupRow | null;
  new_work_row: AdjSetupRow | null;  // فاز E-6 Part C گام ۵ (بندهای ۳-۱..۳-۵)
  chapters: AdjChapterRow[];
  delta_p: number;
  delta_p_definitive: number;
  delta_p_provisional: number;
  result_amount: number;
  advance_mode: string;
  delay_mode: string;
  params: {
    allow_negative: boolean;
    advance_payment: number;
    proposal_date: string;
    provisional_coef: number | null;
  };
  incomplete: boolean;
  missing: [string, string, string][];
  draft: boolean;
  pending: AdjPending[];
  source: string;
}

/** خروجی موتور ۲ — برآورد به‌هنگام */
export interface BaravordResult {
  mode: "برآورد به‌هنگام";
  formula: string;
  error?: string;
  io_q: string | null;
  io_month: string | null;
  it_q: string | null;
  /** فاز E-8 §۳.۱ — برچسب موقت/قطعیِ دورهٔ It + ضریبِ موقت */
  it_status: string;
  prov: number | null;
  prov_manual: boolean;
  prov_trace: Record<string, unknown>;
  index_method_resolved: {
    // فاز E-6 Part C گام ۶ (بندهای ۲-۱/۲-۲)
    method: "گروهی" | "رشته‌ای";
    source: string;
  };
  base_amount: number;
  work_base: number;
  chain: AdjChainRow[];
  setup_amount: number;
  setup_row: AdjSetupRow | null;
  new_work_row: AdjSetupRow | null;  // فاز E-6 Part C گام ۵ (بندهای ۳-۱..۳-۵)
  chapters: AdjChapterRow[];
  result_amount: number;
  grand_updated: number;
  grand_current: number;
  applied_mult: number;
  incomplete: boolean;
  missing: [string, string, string][];
  draft: boolean;
  pending: AdjPending[];
  source: string;
}

/** {tadil, baravord} — هر دو می‌توانند همزمان فعال باشند */
export interface AdjustmentResult {
  tadil: TadilResult | null;
  baravord: BaravordResult | null;
}

/** مشخصات ثبتی پروژه و متا دیتای صورت‌وضعیت */
export interface ProjectMeta {
  projectName: string;
  employer: string; // کارفرما
  contractor: string; // پیمانکار
  consultant: string; // مشاور
  contractNo: string; // شماره قرارداد
  contractDate: string; // تاریخ شروع قرارداد (شمسی)
  location: string; // محل اجرا
  reportNo: string; // شماره صورت‌وضعیت
  reportType: string; // نوع صورت‌وضعیت (در خروجیِ پیش‌نویس پیشوند «پیش‌نویس — » می‌گیرد)
  periodStart: string; // تاریخ شروع دورهٔ صورت‌وضعیت (شمسی)
  periodEnd: string; // تاریخ پایان دورهٔ صورت‌وضعیت (شمسی)
  draftBanner?: string; // فاز E-10 §۲: واترمارکِ پیش‌نویسِ دورهٔ کارکرد روی همهٔ شیت‌ها
}

/** رکورد ذخیره‌شدهٔ یک صورت‌وضعیت در سوابق (برای محاسبهٔ تجمعی) */
export interface StatusReportRecord {
  id: string;
  createdAt: string; // ISO
  reportNo: string;
  reportType: "موقت" | "قطعی";
  periodStart: string;
  periodEnd: string;
  grossPayable: number; // ناخالص پس از ضرایب
  totalDeductions: number; // مجموع کسورات
  netPayable: number; // خالص قابل‌پرداخت (تجمعی این رکورد)
  currentWork: number; // کارکرد این دوره (با کسر سابقه)
}

export interface LoadedFile {
  id: string;
  name: string;
  size: number;
  text: string;
  table?: RevitTable;
  isFehrest?: boolean;
  mappingData?: MappingData;
}

/** گام‌های جریان کار سامانه */
export type Step = "home" | "fehrest" | "upload" | "settings" | "match" | "manual" | "reports" | "export";

// ─────────────────────────────────────────────────────────────
// Mapping داینامو — ستون‌های کانونیکال خروجی Mapping v1/v2
// ─────────────────────────────────────────────────────────────
export interface MappingRow {
  element_id: string;
  category: string;
  family: string;
  type: string;
  mark: string;
  level: string;
  phase: string;
  material: string;
  fehrest_code: string;
  note: string;
  volume_m3: number;
  area_m2: number;
  length_m: number;
  formwork_m2: number;
  rebar_weight_kg: number;
  rebar_detail: string;
  diameter_mm: number;
  steel_type: string;
  prefix: string;
  host_mark: string;
  host_family: string;
  position: string;
  source_format: "v1" | "v2";
}

export interface MappingData {
  rows: MappingRow[];
  format: "v1" | "v2" | "unknown";
  recordCount: number;
  warnings: string[];
  error?: string | null;
}


