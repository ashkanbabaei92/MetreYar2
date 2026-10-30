// ─────────────────────────────────────────────────────────────
// ابزارهای فارسی کاملاً دست‌نویس (بدون هیچ کتابخانهٔ خارجی):
// ۱) تبدیل تاریخ میلادی به شمسی و اعتبارسنجی رشتهٔ تاريخ شمسی
// ۲) تبدیل عدد به حروف فارسی (برای مبالغ صورت‌وضعیت)
// ۳) قالب‌بندی پول ریال/تومان با گزینهٔ رند کردن
// ─────────────────────────────────────────────────────────────

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const EN_DIGITS = "0123456789";
const INVISIBLE_CHARS_RE = /[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]/g;

export const fa = (s: string | number): string =>
  String(s).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);

/** نرمال‌سازی رشتهٔ عددی/تاریخی: تبدیل ارقام فارسی و عربی به انگلیسی، حذف کاراکترهای نامرئی و ممیز فارسی */
export function normalizeDigits(input: string | number | null | undefined): string {
  if (input == null) return "";
  let s = String(input);
  let out = "";
  for (const ch of s) {
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
  return out.replace(INVISIBLE_CHARS_RE, "").replace(/\u066b/g, ".").trim();
}

/** سال کبیسهٔ شمسی (قاعدهٔ استاندارد ۲۸۲۰-ساله) */
export function isJalaliLeap(y: number): boolean {
  return (((y - 474) % 2820) * 682) % 2816 < 682;
}

// ── الگوریتم تبدیل میلادی به جلالی ──
export function g2j(gy: number, gm: number, gd: number): [number, number, number] {
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let gy2 = gm > 2 ? gy + 1 : gy;
  let days =
    355666 + 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) + gd + g_d_m[gm - 1];
  let jy = -1595 + 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return [jy, jm, jd];
}

/** تبدیل تاریخ شمسی به میلادی (معکوسِ g2j — ایراد ۱۳).
 *
 * پیاده‌سازی: جستجوی دودویی روی همان تابع میلادی→شمسیِ موجود. این روش
 * به هیچ فرضی دربارهٔ قواعد کبیسه یا مبدأِ شمارش روزها نیاز ندارد و
 * همواره با g2j دقیقاً سازگار است. ورودی نامعتبر (مثل اسفند ۳۰ در
 * سال غیرکبیسه) → null. */
export function jalaliToGregorian(
  jy: number,
  jm: number,
  jd: number,
): [number, number, number] | null {
  if (!(1300 <= jy && jy <= 1500 && jm >= 1 && jm <= 12 && jd >= 1)) return null;
  const target: [number, number, number] = [jy, jm, jd];
  // سال جلالی ≈ میلادی − ۶۲۱/۶۲۲؛ بازهٔ جستجو سه سال میلادی است.
  let lo = Date.UTC(jy + 620, 0, 1);
  let hi = Date.UTC(jy + 623, 11, 31);
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    const d = new Date(mid);
    const got = g2j(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
    const c = cmpJalali(got, target);
    if (c === 0) return [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()];
    if (c < 0) lo = mid + 1;
    else hi = mid - 1;
  }
  return null;
}

/** مقایسهٔ ترتیبی دو تاریخ شمسی (الگوریتم جستجوی دودویی بالا). */
function cmpJalali(a: [number, number, number], b: [number, number, number]): number {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return 0;
}

/** تاريخ شمسی امروز به فرمت «۱۴۰۴/۰۷/۲۵» */
export function todayJalali(): string {
  const now = new Date();
  const [jy, jm, jd] = g2j(now.getFullYear(), now.getMonth() + 1, now.getDate());
  const p = (n: number) => String(n).padStart(2, "0");
  return fa(`${jy}/${p(jm)}/${p(jd)}`);
}

/** تاریخ و ساعت لحظهٔ به وقت تهران، به‌صورت متن شمسی (سابقهٔ ویرایش و
 *  فایل کناری — قاعدهٔ طلایی ۲: تمام تاریخ‌ها شمسی). */
export function jalaliNowStr(): string {
  const now = new Date();
  const tzMs = now.getTimezoneOffset() * 60000 + 12600000; // +03:30
  const local = new Date(now.getTime() + tzMs);
  const [jy, jm, jd] = g2j(local.getUTCFullYear(), local.getUTCMonth() + 1, local.getUTCDate());
  const p = (n: number) => String(n).padStart(2, "0");
  return fa(
    `${jy}/${p(jm)}/${p(jd)} ${p(local.getUTCHours())}:${p(local.getUTCMinutes())}`,
  );
}

/** اعتبارسنجی رشتهٔ تاريخ شمسی ورودی کاربر: ۱۴۰۴/۰۱/۱۵ */
export function isValidJalaliDate(input: string): boolean {
  if (!input) return false;
  const en = normalizeDigits(input);
  const m = en.match(/^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$/);
  if (!m) return false;
  const y = parseInt(m[1], 10);
  const mo = parseInt(m[2], 10);
  const d = parseInt(m[3], 10);
  if (y < 1300 || y > 1500 || mo < 1 || mo > 12 || d < 1) return false;
  const dim = mo <= 6 ? 31 : mo <= 11 ? 30 : isJalaliLeap(y) ? 30 : 29;
  return d <= dim;
}

/** نرمال‌سازی قالب تاريخ شمسی به yyyy/mm/dd با ارقام فارسی */
export function normalizeJalaliDate(input: string): string {
  const en = normalizeDigits(input);
  const m = en.match(/^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$/);
  if (!m) return fa(input.trim());
  const p = (n: string) => n.padStart(2, "0");
  return fa(`${m[1]}/${p(m[2])}/${p(m[3])}`);
}

// ─────────────────────────────────────────────────────────────
// تبدیل عدد به حروف فارسی (پشتیبانی تا تريليون)
// ─────────────────────────────────────────────────────────────
const ONES = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"];
const TEENS = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"];
const TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"];
const HUNDREDS = ["", "یکصد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"];
const SCALES = ["", " هزار", " میلیون", " میلیارد", " بیلیون", " بیلیارد", " تریلیون"];

function threeDigit(n: number): string {
  const parts: string[] = [];
  const h = Math.floor(n / 100);
  const r = n % 100;
  if (h) parts.push(HUNDREDS[h]);
  if (r >= 10 && r < 20) parts.push(TEENS[r - 10]);
  else {
    const t = Math.floor(r / 10);
    const o = r % 10;
    if (t) parts.push(TENS[t]);
    if (o) parts.push(ONES[o]);
  }
  return parts.join(" و ");
}

/** تبدیل عدد صحیح مثبت به حروف فارسی */
export function numberToPersianWords(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "";
  n = Math.floor(Math.abs(n));
  if (n === 0) return "صفر";
  const groups: string[] = [];
  let scale = 0;
  while (n > 0 && scale < SCALES.length) {
    const g = n % 1000;
    if (g > 0) groups.unshift(threeDigit(g) + SCALES[scale]);
    n = Math.floor(n / 1000);
    scale++;
  }
  if (n > 0) groups.unshift(threeDigit(Math.floor(n % 1000)) + " " + SCALES[SCALES.length - 1]);
  return groups.join(" و ").replace(/\s+/g, " ").trim();
}

/** مبلغ ریال به حروف فارسی: «دو میلیارد و ... ریال» */
export function moneyToWords(rial: number): string {
  const rialRounded = Math.round(rial);
  if (rialRounded === 0) return "صفر ریال";
  return `${numberToPersianWords(rialRounded)} ریال`;
}

// ─────────────────────────────────────────────────────────────
// قالب‌بندی پول با واحد انتخابی کاربر
// ─────────────────────────────────────────────────────────────
export interface MoneyFormatOpts {
  currency?: "rial" | "toman";
  rounding?: boolean; // رند به ۱۰۰۰ ریال
  withUnit?: boolean;
}

export function fmtMoneyVal(rial: number, opts: MoneyFormatOpts = {}): string {
  // پیش‌فرضِ rounding = true — همگام با fmt_money در app.py (هر دو موتور
  // ریال محاسبه می‌شوند؛ این فقط تابعِ نمایش است و هرگز روی اعداد اثر
  // ندارد). آزمون: T114.
  const { currency = "rial", rounding = true, withUnit = true } = opts;
  let v = rounding ? Math.round(rial / 1000) * 1000 : Math.round(rial);
  let out: string;
  if (currency === "toman") {
    // همگام با fmt_money در app.py: تومان همیشه ۱ رقم اعشار (مثلاً ۱۰۰٫۰).
    out = (v / 10).toLocaleString("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  } else {
    out = v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }
  return fa(out) + (withUnit ? ` ${currency === "toman" ? "تومان" : "ریال"}` : "");
}

export function moneyUnitName(currency: "rial" | "toman"): string {
  return currency === "toman" ? "تومان" : "ریال";
}

/** نام مقیاس‌های رایج صورت‌وضعیت برای نمایش در جداول */
export const DEDUCTION_DEFAULTS = {
  insurancePct: 7.8,
  taxPct: 5,
  goodJobPct: 10,
};
