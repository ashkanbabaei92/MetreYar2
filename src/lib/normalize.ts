// ─────────────────────────────────────────────────────────────
// موتور نرمال‌سازی متن فارسی/عربی و تجزیهٔ اعداد واحد‌دار
// معادل کلاس TextNormalizer نسخهٔ پایتونی — نسخهٔ کامل وب
// ─────────────────────────────────────────────────────────────

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const EN_DIGITS = "0123456789";

/** نگاشت نویسه‌های عربی/فارسیِ متنوع به فرم استاندارد فارسی */
const CHAR_MAP: Record<string, string> = {
  "ك": "ک",
  "ى": "ی",
  "ة": "ه",
  "ئ": "ی",
  "إ": "ا",
  "أ": "ا",
  "ٱ": "ا",
  "ء": "",
  "ٔ": "",
  "ي": "ی",  // ی عربی (تنها شکل ی در Windows-1256)
  "‌": " ",
};

/** تبدیل ارقام فارسی/عربی به انگلیسی */
export function toEnDigits(input: string): string {
  let out = "";
  for (const ch of input) {
    let i = FA_DIGITS.indexOf(ch);
    if (i >= 0) {
      out += EN_DIGITS[i];
      continue;
    }
    i = AR_DIGITS.indexOf(ch);
    if (i >= 0) {
      out += EN_DIGITS[i];
      continue;
    }
    out += ch;
  }
  return out;
}

/** تبدیل ارقام لاتین به فارسی (برای نمایش) */
export function faDigits(input: string | number): string {
  return String(input).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

/**
 * نرمال‌سازی کامل متن برای مقایسه‌های فازی:
 * یکسان‌سازی حروف، حذف کشش/‌حرکت‌ها، نیم‌فاصله→فاصله، تبدیل ارقام، حذف نگارش اضافی
 */
export function normalizeText(input: string | null | undefined): string {
  if (!input) return "";
  let t = toEnDigits(String(input)).toLowerCase();

  // حذف اِعراب عربی
  t = t.replace(/[ً-ْٰ]/g, "");
  // حذف علائم جهت‌دهی
  t = t.replace(/[‎‏​‍]/g, " ");
  // یکسان‌سازی حروف
  for (const [from, to] of Object.entries(CHAR_MAP)) t = t.split(from).join(to);

  // علائم نگارشی → فاصله
  t = t.replace(/[-_/\\.,;:!?(){}[\]"'«»<>|*+×÷=~#$%^&\n\r\t]+/g, " ");
  // «های/هایی» چسبیده
  t = t.replace(/(ها|های)(?=\s|$)/g, " ");
  t = t.replace(/\s+/g, " ").trim();
  return t;
}

/**
 * تجزیهٔ رشته‌های عددی واحد‌دار رویت مانند:
 * "18.65 m³" ، "74,484.56 mm" ، "12001.91 kg" ، "1,234 m²"
 * خروجی: مقدار عددی + واحد؛ در صورت شکست null
 */
export interface ParsedValue {
  value: number;
  unit: string;
}
export function parseValueUnit(raw: string | null | undefined): ParsedValue | null {
  if (!raw) return null;
  let t = toEnDigits(String(raw)).trim();
  if (!t) return null;

  // جدا کردن واحد از عدد
  const m = t.match(/^([+-]?[\d\s,٬'’ .\u202f]+)\s*([^\d\s].*)?$/);
  if (!m) return null;

  let numPart = (m[1] || "").replace(/[\s \u202f]/g, "");
  // تشخیص جداکنندهٔ هزارگان در برابر ممیز اعشار
  const lastComma = numPart.lastIndexOf(",");
  const lastDot = numPart.lastIndexOf(".");
  if (lastComma > lastDot) {
    // ویرگول ممیز اعشار است (فرمت اروپایی)
    numPart = numPart.replace(/\./g, "").replace(",", ".");
  } else {
    // نقطه ممیز اعشار؛ ویرگول‌ها هزارگان‌اند
    numPart = numPart.replace(/,/g, "");
  }

  const value = parseFloat(numPart);
  if (!Number.isFinite(value)) return null;
  return { value, unit: (m[2] || "").trim().toLowerCase() };
}

/** تبدیل واحد به واحد استاندارد SI برای هر کمیت */
export function toSI(value: number, unit: string): { value: number; si: "m" | "m2" | "m3" | "kg" | "count" | null } {
  const u = unit.replace(/\s/g, "").toLowerCase();
  if (["mm", "میلیمتر"].includes(u)) return { value: value / 1000, si: "m" };
  if (["cm", "سانتیمتر", "سانتی‌متر"].includes(u)) return { value: value / 100, si: "m" };
  if (["m", "متر", "مترطول"].includes(u)) return { value, si: "m" };
  if (["mm2", "mm²"].includes(u)) return { value: value / 1e6, si: "m2" };
  if (["cm2", "cm²"].includes(u)) return { value: value / 1e4, si: "m2" };
  if (["m2", "m²", "مترمربع"].includes(u)) return { value, si: "m2" };
  if (["cm3", "cm³"].includes(u)) return { value: value / 1e6, si: "m3" };
  if (["m3", "m³", "مترمکعب"].includes(u)) return { value, si: "m3" };
  if (["g", "gr", "گرم"].includes(u)) return { value: value / 1000, si: "kg" };
  if (["kg", "کیلوگرم", "کیلو"].includes(u)) return { value, si: "kg" };
  if (["ton", "t", "تن"].includes(u)) return { value: value * 1000, si: "kg" };
  if (["", "-", "#"].includes(u)) return { value, si: "count" };
  if (u === "count" || u === "عدد") return { value, si: "count" };
  return { value, si: null };
}

/**
 * استخراج مقاومت فشاری مشخصهٔ بتن (MPa) از نام/متن متریال Revit (ایراد ۱).
 *
 * الگوهای پشتیبانی‌شده: C35، C 35، 35MPa، 35 MPa، f'c=35، fc35، fc 35،
 * 35 مگاپاسکال، ۳۵ مگاپاسکال. خروجی: عدد صحیح مگاپاسکال یا null.
 * تقدم رسمی: پارامتر صریح Revit > نام متریال > ورودی دستی (تنظیمات).
 */
export function parseConcreteStrength(text: string | null | undefined): number | null {
  if (!text) return null;
  const t = toEnDigits(String(text));
  // 35 MPa / 35MPa / 35 Mpa / 35 مگاپاسکال
  let m = t.match(/(?:^|[^A-Za-z0-9'])(\d{2,3})\s*(?:MPa|Mpa|mpa|مگاپاسکال)(?:\s|$|[^A-Za-z0-9])/);
  if (m) return parseInt(m[1], 10);
  // C35 / C 35 — اما نه ابعاد مقطع مثل «C 45×45» یا «C30/37»
  m = t.match(/(?:^|[^A-Za-z0-9])[Cc]\s*(\d{2,3})(?![\d/×*xX])/);
  if (m) return parseInt(m[1], 10);
  // f'c=35 / fc35 / fc 35 (جداکنندهٔ «=» اختیاری است)
  m = t.match(/f\s*'?\s*c\s*[=:]?\s*(\d{2,3})/i);
  if (m) return parseInt(m[1], 10);
  return null;
}

/** فرمت عدد با ارقام فارسی و جداکنندهٔ هزارگان */
export function fmtNum(n: number, maxDec = 2, minDec = 0): string {
  return faDigits(
    n.toLocaleString("en-US", {
      maximumFractionDigits: maxDec,
      minimumFractionDigits: minDec,
    }),
  );
}

/** فرمت مبلغ ریال به صورت خوانا */
export function fmtRial(n: number): string {
  return fmtNum(Math.round(n), 0);
}

/** نمایش فشردهٔ مبالغ بزرگ به میلیارد تومان */
export function fmtBillionToman(rial: number, dec = 1): string {
  return faDigits((rial / 1e10).toFixed(dec));
}

export function fmtKg(kg: number): string {
  return fmtNum(kg, kg >= 100 ? 0 : 1);
}

/** درصد اطمینان به متن فارسی */
export function confLabel(c: number): string {
  if (c >= 0.92) return "قطعی";
  if (c >= 0.78) return "بالا";
  if (c >= 0.62) return "متوسط";
  return "پایین";
}

/** وزن واحد میلگرد (کیلوگرم بر متر) بر اساس قطر — جدول اشتال */
export function rebarUnitWeight(diameterMm: number): number {
  const table: Record<number, number> = {
    6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888, 14: 1.208, 16: 1.578,
    18: 1.998, 20: 2.466, 22: 2.984, 25: 3.853, 28: 4.834, 30: 5.549,
    32: 6.313, 36: 7.99, 40: 9.864,
  };
  const d = Math.round(diameterMm);
  if (table[d] !== undefined) return table[d];
  // فرمول تقریبی وزن واحد میلگرد
  return (d * d) / 162;
}
