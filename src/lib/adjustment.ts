// ─────────────────────────────────────────────────────────────
// موتورهای تعدیل فاز B (مرحلهٔ ۱۳ — نسخهٔ ۴)
//
// دو موتور کاملاً مجزا که هرگز ادغام نمی‌شوند (قاعدهٔ طلایی ۵):
//   ۱) تعدیل پیمان      : ΔP = k × Σ_c (It_c/Io_c − 1) × A_c   (شاخص هر فصل)
//   ۲) برآورد به‌هنگام   : A_new = Σ_c A_c × It_c/Io_c
// هر دو موتور می‌توانند همزمان فعال شوند (دو شیت و دو کارت مجزا) ولی
// هرگز روی زنجیرهٔ مالی اصلی اثر نمی‌گذارند.
//
// شاخص‌ها از config/index_bulletins.json (بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳، پیوست ۳،
// صفحه‌های ۶–۷) خوانده می‌شوند. تجهیز/برچیدن و ردیف‌های بدون شاخص فصل با
// شاخص رشته‌ای تعدیل می‌شوند (بند ۴). Io از تاریخ تسلیم پیشنهاد (بند ۱-۲).
// k از بخشنامهٔ ۲۰۸۰ (بند ۱-۸ و تبصرهٔ ۲) مشتق می‌شود (فاز E-۶)؛
// تا تأیید کاربر خروجی «پیش‌نویس» است.
//
// منطبق با app.py:_tadil_engine/_baravord_engine — خروجی‌ها باید
// bit-identical باشند.
// ─────────────────────────────────────────────────────────────
import INDEX_BULLETINS from "../../config/index_bulletins.json";
import CPI_MONTHLY_RAW from "../../config/cpi_monthly.json";
import PROVISIONAL_M_RAW from "../../config/provisional_m.json";
import { faDigits } from "./normalize";
import { chapterTitle } from "../data/fehrest";
import type { ProjectMeta } from "./types";
import type {
  AdjChapterRow,
  AdjChainRow,
  AdjPending,
  AdjSetupRow,
  AdjustmentCtx,
  AdjustmentResult,
  BaravordResult,
  ContractExtension,
  DelayInfo,
  DelayNote,
  ProjectSettings,
  TadilResult,
  Warning,
} from "./types";

/** delay_info خالی — برای مسیرهای توقفِ زودهنگامِ موتور */
const EMPTY_DELAY_INFO: DelayInfo = {
  contract_end: null,
  term_end: null,
  term_quarters: [],
  override: {},
};

// ── جداول دوره‌های شاخص (پیوست ۳) ──

const PERIOD_FIELDS: Record<string, string> = {
  base: "base_esfand_1403",
  q1: "q1_1404",
  q2: "q2_1404",
  q3: "q3_1404",
  q4: "q4_1404",
};

// معادل سه‌ماهه‌ای هر کلید دوره («base» همان سه‌ماههٔ چهارم ۱۴۰۳ است)
const PERIOD_QUARTERS: Record<string, string> = {
  base: "1403Q4",
  q1: "1404Q1",
  q2: "1404Q2",
  q3: "1404Q3",
  q4: "1404Q4",
};

const QUARTER_PERIOD: Record<string, string> = Object.fromEntries(
  Object.entries(PERIOD_QUARTERS).map(([k, v]) => [v, k]),
);

type Bulletins = Record<string, any>;
const CFG = INDEX_BULLETINS as Bulletins;

/** شاخص یک فصل (کد دو رقمی) در یک دوره (پیوست ۳، صفحه‌های ۶–۷).
 * کدهای فصل هم به‌صورت عددی (۶) و هم رشتهٔ صفرپرشده («06») کار می‌کنند.
 * خروجی: (مقدار, صفحه). اگر فصل استخراج نشده باشد (null, null). */
export function chapterIndex(
  chapter: string | number,
  periodKey: string,
): [number, string | number | null] | [null, null] {
  const code = String(chapter).trim().padStart(2, "0");
  const rows = ((CFG["chapters_abnieh"] as any[]) ?? []).filter(
    (r) => String(r["chapter"]).trim().padStart(2, "0") === code,
  );
  if (rows.length === 0) return [null, null];
  const field = PERIOD_FIELDS[periodKey ?? ""];
  if (!field) return [null, null];
  const v = rows[0][field];
  return typeof v === "number" ? [v, rows[0]["page"] ?? null] : [null, null];
}

/** شاخص یک فصل با کلید سه‌ماهه (قطعی‌های پیوست ۳). */
export function chapterIndexQ(
  chapter: string | number,
  quarter: string,
): [number, string | number | null] | [null, null] {
  const pk = QUARTER_PERIOD[quarter ?? ""];
  if (!pk) return [null, null];
  return chapterIndex(chapter, pk);
}

/** شاخص رشتهٔ انتخابی در یک دوره (پیوست ۳، ردیف ۱). → (مقدار, صفحه). */
export function indexValue(
  periodKey: string,
  discipline = "ابنیه",
): [number, string | number | null] | [null, null] {
  const rows = ((CFG["disciplines"] as any[]) ?? []).filter(
    (d) => d["name"] === discipline,
  );
  if (rows.length === 0) return [null, null];
  const field = PERIOD_FIELDS[periodKey ?? ""];
  if (!field) return [null, null];
  const v = rows[0][field];
  return typeof v === "number" ? [v, rows[0]["page"] ?? null] : [null, null];
}

const QUARTER_LABELS: Record<string, string> = {
  "1403Q4": "سه‌ماههٔ چهارم ۱۴۰۳ (اسفند ۱۴۰۳ — مبنا)",
  "1404Q1": "سه‌ماههٔ اول ۱۴۰۴",
  "1404Q2": "سه‌ماههٔ دوم ۱۴۰۴",
  "1404Q3": "سه‌ماههٔ سوم ۱۴۰۴",
  "1404Q4": "سه‌ماههٔ چهارم ۱۴۰۴",
  "1405Q1": "سه‌ماههٔ اول ۱۴۰۵ (موقت)",
  "1405Q2": "سه‌ماههٔ دوم ۱۴۰۵ (موقت)",
  "1405Q3": "سه‌ماههٔ سوم ۱۴۰۵ (موقت)",
  "1405Q4": "سه‌ماههٔ چهارم ۱۴۰۵ (موقت)",
};

/** برچسب فارسی یک سه‌ماهه از کلید آن (مثل ۱۴۰۴Q2). */
export function quarterLabel(key: string | null | undefined): string {
  return QUARTER_LABELS[String(key ?? "")] ?? String(key ?? "—");
}

/** برچسب دورهٔ مبنا (Io): ماهانه (۱۴۴۳۷۴) یا سه‌ماهه‌ای (پیوست ۳). */
export function ioLabel(
  engineOut: { io_month?: string | null; io_q?: string | null } | null,
): string {
  const m = engineOut?.io_month;
  if (m) {
    const found = monthlyPeriods().find((p) => p.key === m);
    return `${found ? found.label : m} (ماهانه — بخشنامهٔ ۱۴۴۳۷۴)`;
  }
  return quarterLabel(engineOut?.io_q);
}

/** سه‌ماهه‌های سال ۱۴۰۵ به بعد — شاخص قطعی ندارند (بند ۳، ۱۴۴۳۷۳).
 * بندهای ۲ و ۳: کارکرد ۱۴۰۵Q1 و بعدتر بدون شاخص قطعی با
 * «ضریب موقت × آخرین شاخص قطعی (۱۴۰۴Q4)» — علی‌الحساب. */
export function quarterIsProvisional(quarter: string | null | undefined): boolean {
  const y = Number(String(quarter ?? "").split("Q")[0]);
  return Number.isFinite(y) && y >= 1405;
}

const PERIOD_LABELS: Record<string, string> = {
  base: "اسفند ۱۴۰۳ (مبنا)",
  q1: "سه‌ماههٔ اول ۱۴۰۴",
  q2: "سه‌ماههٔ دوم ۱۴۰۴",
  q3: "سه‌ماههٔ سوم ۱۴۰۴",
  q4: "سه‌ماههٔ چهارم ۱۴۰۴",
};

/** برچسب فارسی یک دورهٔ شاخص از کلید آن (base/q1/.../q4). */
export function periodLabel(key: string | null | undefined): string {
  return PERIOD_LABELS[String(key ?? "")] ?? String(key ?? "—");
}

// ── کمکّی‌های تاریخ شمسی و تقسیم کارکرد بین سه‌ماهه‌ها ──

/** تجزیهٔ تاریخ شمسی → [سال، ماه، روز] یا null. */
export function parseJalali(text: string | null | undefined): [number, number, number] | null {
  if (text == null) return null;
  const m = /^(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})$/.exec(
    String(text).trim().replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))),
  );
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!(1300 <= y && y <= 1500 && 1 <= mo && mo <= 12 && 1 <= d && d <= 31)) return null;
  return [y, mo, d];
}

/** سال کبیسهٔ شمسی (قاعدهٔ استاندارد ۲۸۲۰-ساله). */
export function jalaliLeap(y: number): boolean {
  return (((y - 474) % 2820) * 682) % 2816 < 682;
}

// ── کمکّی‌های تاریخ شمسی و تقسیم کارکرد بین سه‌ماهه‌ها ──

import { jalaliToGregorian } from "./farsi";

/** تبدیل تاریخ شمسی به میلادی — از farsi.ts (جستجوی دودویی روی g2j —
 * ایراد ۱۳). دوباره صادر شده تا یک نقطهٔ ورود واحد برای مصرف‌کنندگانِ
 * این ماژول باشد. */
export { jalaliToGregorian };

/** تاریخ شمسی (متن) → ISO میلادی «YYYY-MM-DD» یا null (ایراد ۱۳).
 * ستون مخفی میلادی در Excel از این تابع ساخته می‌شود. */
export function jalaliToISO(text: string | null | undefined): string | null {
  const p = parseJalali(text);
  if (!p) return null;
  const g = jalaliToGregorian(...p);
  if (!g) return null;
  return `${String(g[0]).padStart(4, "0")}-${String(g[1]).padStart(2, "0")}-${String(g[2]).padStart(2, "0")}`;
}

/** شمارهٔ روز از یک مبدأ ثابت — فقط برای مقایسهٔ بازه‌ها. */
export function absDay(y: number, mo: number, d: number): number {
  const dim = [
    31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, jalaliLeap(y) ? 30 : 29,
  ];
  const doy = dim.slice(0, mo - 1).reduce((a, b) => a + b, 0) + d;
  let leaps = 0;
  for (let yy = 1300; yy < y; yy++) if (jalaliLeap(yy)) leaps++;
  return y * 365 + leaps + doy;
}

/** کلید سه‌ماههٔ یک تاریخ شمسی (مثل «۱۴۰۴Q2») یا null. */
export function dateQuarter(dateText: string): string | null {
  const p = parseJalali(dateText);
  if (!p) return null;
  return `${p[0]}Q${Math.floor((p[1] - 1) / 3) + 1}`;
}

/** اعتبارسنجی تاریخ‌های پروژه (ایراد ۱۲).
 *
 * سه تاریخ متمایز و هرگز ادغام‌نشدنی:
 *   - «تاریخ شروع پیمان»            ← contractDate
 *   - «تاریخ شروع دورهٔ صورت‌وضعیت»  ← periodStart
 *   - «تاریخ پایان دورهٔ صورت‌وضعیت» ← periodEnd
 *
 * قاعده: شروع پیمان ≤ شروع دوره ≤ پایان دوره. تاریخ‌های خالی در این
 * بررسی شرکت نمی‌کنند (تنها تاریخ‌های پرشده بررسی می‌شوند). خروجی: لیست
 * هشدارهای مرکزی (level === "خطا") — اگر خالی نباشد، محاسبه/خروجی باید
 * متوقف شود (قاعدهٔ ایراد ۱۲). */
export function validateMeta(meta: ProjectMeta | null | undefined): Warning[] {
  const errs: Warning[] = [];
  if (!meta) return errs;
  const fields: [string, string][] = [
    ["تاریخ شروع پیمان", (meta.contractDate || "").trim()],
    ["تاریخ شروع دورهٔ صورت‌وضعیت", (meta.periodStart || "").trim()],
    ["تاریخ پایان دورهٔ صورت‌وضعیت", (meta.periodEnd || "").trim()],
  ];
  // ۱) هر تاریخ پرشده باید شمسیِ معتبر باشد (ارقام فارسی/لاتین)
  for (const [label, v] of fields) {
    if (v && !parseJalali(v)) {
      errs.push({
        level: "خطا",
        category: "تاریخ‌ها",
        item: label,
        message: `${label} = «${v}» یک تاریخ شمسی معتبر نیست (قالب موردنظر: ۱۴۰۵/۰۷/۰۸).`,
        action: "تاریخ را به‌صورت شمسی (سال/ماه/روز) اصلاح کنید.",
        ref: "ایراد ۱۲ — اعتبارسنجی تاریخ‌ها",
      });
    }
  }
  // ۲) ترتیب: شروع پیمان ≤ شروع دوره ≤ پایان دوره
  const day = (label: string): number | null => {
    const v = fields.find((f) => f[0] === label)![1];
    const p = parseJalali(v);
    return p ? absDay(...p) : null;
  };
  const dStart = day("تاریخ شروع پیمان");
  const dPStart = day("تاریخ شروع دورهٔ صورت‌وضعیت");
  const dPEnd = day("تاریخ پایان دورهٔ صورت‌وضعیت");
  if (dStart != null && dPStart != null && dStart > dPStart) {
    errs.push({
      level: "خطا",
      category: "تاریخ‌ها",
      item: "ترتیب تاریخ‌ها",
      message: "تاریخ شروع پیمان پس از تاریخ شروع دورهٔ صورت‌وضعیت است (شروع پیمان باید ≤ شروع دوره باشد).",
      action: "تاریخ شروع پیمان یا تاریخ شروع دوره را اصلاح کنید.",
      ref: "ایراد ۱۲ — شروع پیمان ≤ شروع دوره ≤ پایان دوره",
    });
  }
  if (dPStart != null && dPEnd != null && dPStart > dPEnd) {
    errs.push({
      level: "خطا",
      category: "تاریخ‌ها",
      item: "ترتیب تاریخ‌ها",
      message: "تاریخ شروع دورهٔ صورت‌وضعیت پس از تاریخ پایان دوره است (شروع دوره باید ≤ پایان دوره باشد).",
      action: "تاریخ شروع یا پایان دورهٔ صورت‌وضعیت را اصلاح کنید.",
      ref: "ایراد ۱۲ — شروع پیمان ≤ شروع دوره ≤ پایان دوره",
    });
  }
  if (dStart != null && dPEnd != null && dStart > dPEnd) {
    errs.push({
      level: "خطا",
      category: "تاریخ‌ها",
      item: "ترتیب تاریخ‌ها",
      message: "تاریخ شروع پیمان پس از تاریخ پایان دورهٔ صورت‌وضعیت است.",
      action: "تاریخ شروع پیمان یا تاریخ پایان دوره را اصلاح کنید.",
      ref: "ایراد ۱۲ — شروع پیمان ≤ شروع دوره ≤ پایان دوره",
    });
  }
  return errs;
}

/** تقسیم دورهٔ انجام کار بین سه‌ماهه‌ها بر اساس روزها.
 * اگر delayText داده شود، کارکردِ قبل از آن تاریخ (دورهٔ تأخیر) مستثنی
 * می‌شود. خروجی: [[کلید سه‌ماهه, کسر]...] یا []. */
export function workSplit(
  startText: string,
  endText: string,
  delayText?: string | null,
): [string, number][] {
  const a = parseJalali(startText);
  const b = parseJalali(endText);
  if (!a || !b) return [];
  let d0 = absDay(...a);
  const d1 = absDay(...b);
  if (delayText) {
    const dd = parseJalali(delayText);
    if (dd) d0 = Math.max(d0, absDay(...dd));
  }
  if (d1 < d0) return [];
  const total = d1 - d0 + 1;
  const out: [string, number][] = [];
  for (let cy = a[0]; cy <= b[0]; cy++) {
    const yearDays = jalaliLeap(cy) ? 366 : 365;
    const y0 = absDay(cy, 1, 1);
    // مرزهای سه‌ماهه‌ها در روزهای سال شمسی:
    // Q1 = ۱–۹۳ ، Q2 = ۹۴–۱۸۶ ، Q3 = ۱۸۷–۲۷۶ ، Q4 = ۲۷۷–۳۶۵/۳۶۶
    for (const [qs, qe, ql] of [
      [1, 93, 1],
      [94, 186, 2],
      [187, 276, 3],
      [277, yearDays, 4],
    ] as [number, number, number][]) {
      const qsA = y0 + qs - 1;
      const qeA = y0 + qe - 1;
      const ov = Math.min(qeA, d1) - Math.max(qsA, d0) + 1;
      if (ov > 0) out.push([`${cy}Q${ql}`, ov / total]);
    }
  }
  return out;
}


/** فاز E-6 — تاریخ شمسی + N ماه (با تطبیقِ طولِ ماه).
 * خروجی: رشتهٔ تاریخ با ارقام لاتین (مصرفِ داخلی) یا null.
 * منبع: بخشنامهٔ ۲۰۸۰، بند ۲-۵ (محاسبهٔ پایان مدت پیمان). */
export function addMonthsJalali(
  dateText: string,
  months: number | null | undefined,
): string | null {
  const p = parseJalali(dateText);
  if (!p || !months) return null;
  const [y, mo, d] = p;
  const total = y * 12 + (mo - 1) + Math.floor(months);
  const ny = Math.floor(total / 12);
  const nm = (total % 12) + 1;
  const dim = [
    31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30,
    jalaliLeap(ny) ? 30 : 29,
  ];
  const dd = Math.min(d, dim[nm - 1]);
  return `${ny}/${String(nm).padStart(2, "0")}/${String(dd).padStart(2, "0")}`;
}

/** فاز E-6 Part C گام ۳ — طبقه‌بندی تأخیرها (بندهای ۲-۵-۱..۲-۵-۳).
 *
 * مدت پیمان = مدت اولیه + تمدیدها. کارکردِ پس از مدت بر اساس نوع تأخیر
 * شاخص‌گذاری می‌شود:
 *   مجاز       (۲-۵-۱): شاخص همان دورهٔ انجام کار (بدون بازنویسی).
 *   غیرمجاز    (۲-۵-۲): میانگین شاخص‌های سه‌ماهه‌های داخل مدت پیمان.
 *   تعیین‌نشده (۲-۵-۳): علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمهٔ مدت
 *                        (یا تمدیدِ پوشش‌دهنده).
 *
 * تفسیر granularity: هر سه‌ماهه اتمیک است — سه‌ماهه‌ای که روز شروعش
 * کوچک‌تر از تاریخ خاتمهٔ مدت است، درونِ مدت محسوب می‌شود. */
export function delayClassification(
  contractStart: string,
  durationMonths: number | null | undefined,
  extensions: ContractExtension[] | null | undefined,
  split: [string, number][],
  w: Warning[],
): DelayInfo {
  const res: DelayInfo = {
    contract_end: null,
    term_end: null,
    term_quarters: [],
    override: {},
  };
  const p0 = parseJalali(contractStart);
  if (!p0 || !durationMonths) return res;
  const cEnd = addMonthsJalali(contractStart, durationMonths)!;
  res.contract_end = cEnd;
  const cEndDay = absDay(...parseJalali(cEnd)!);
  let tEndDay = cEndDay;
  let tEndText: string = cEnd;
  const ranges: [number, number, string, string][] = [];
  for (const ext of extensions ?? []) {
    const eDate = (ext.date ?? "").trim();
    const eMonths = ext.months ?? 0;
    const p = parseJalali(eDate);
    if (!p || !eMonths) {
      if (eDate || eMonths) {
        w.push({
          level: "خطا",
          category: "تأخیر پیمان",
          item: "contract_extensions",
          message:
            "یک تمدید با تاریخ یا مدتِ نامعتبر نادیده گرفته شد — نیازمند اصلاح.",
          action: "تاریخ شمسیِ معتبر و مدتِ غیرصفر وارد کنید.",
          ref: "بخشنامهٔ ۲۰۸۰، بند ۲-۵-۳",
        });
      }
      continue;
    }
    const eEnd = addMonthsJalali(eDate, eMonths)!;
    const eEndDay = absDay(...parseJalali(eEnd)!);
    ranges.push([absDay(...p), eEndDay, ext.kind ?? "تعیین‌نشده", eEnd]);
    if (eEndDay > tEndDay) {
      tEndDay = eEndDay;
      tEndText = eEnd;
    }
  }
  res.term_end = tEndText;
  // سه‌ماهه‌های داخل مدت — مبنای میانگینِ ۲-۵-۲
  res.term_quarters = workSplit(contractStart, tEndText).map(([q]) => q);
  // طبقه‌بندی سه‌ماهه‌های پس از مدت
  let warnedNa = false;
  for (const [q] of split) {
    const y = Number(q.slice(0, 4));
    const qi = Number(q.slice(-1));
    const qsDay = absDay(y, (qi - 1) * 3 + 1, 1);
    if (qsDay < cEndDay) continue; // درونِ مدت
    let kind: string | null = null;
    let basis: string | null = null;
    for (const [s, e, k, et] of ranges) {
      if (s <= qsDay && qsDay <= e) {
        kind = k;
        if (k === "تعیین‌نشده") basis = dateQuarter(et);
        break;
      }
    }
    if (kind === null) {
      // پس از مدت، ولی تمدیدی آن را پوشش نمی‌دهد ⇒ علی‌الحساب
      kind = "تعیین‌نشده";
      basis = dateQuarter(tEndText);
      w.push({
        level: "هشدار",
        category: "تأخیر پیمان",
        item: "delay_uncovered",
        message: `کارکردِ دورهٔ «${q}» پس از پایان مدت پیمان است ولی تمدیدی آن را پوشش نمی‌دهد؛ تعدیلِ آن علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمه محاسبه شد.`,
        action: "مدت و نوع تأخیرِ این دوره را در لیست تمدیدها ثبت کنید (پس از تعیینِ دستگاه باید دوباره محاسبه شود).",
        ref: "بخشنامهٔ ۲۰۸۰، بند ۲-۵-۳",
      });
    } else if (kind === "تعیین‌نشده" && !warnedNa) {
      warnedNa = true;
      w.push({
        level: "اطلاع",
        category: "تأخیر پیمان",
        item: "delay_undefined",
        message: "نوع تأخیرِ برخی تمدیدها «تعیین‌نشده» است؛ تعدیل کارکردهای پس از مدت، علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمهٔ تمدید محاسبه می‌شود (۲-۵-۳).",
        action: "پس از تعیینِ نوع تأخیر توسط دستگاه، مقدار را اصلاح و دوباره محاسبه کنید.",
        ref: "بخشنامهٔ ۲۰۸۰، بند ۲-۵-۳",
      });
    }
    if (kind === "مجاز") continue; // ۲-۵-۱: شاخص همان دورهٔ انجام کار
    res.override[q] = { rule: kind, basis_q: basis };
  }
  return res;
}

/** شاخص یک فصل در یک سه‌ماهه؛ ۱۴۰۵Q1 با «ضریب موقت × قطعی ۱۴۰۴Q4».
 * خروجی: (مقدار, وضعیت). وضعیت: «قطعی» / «موقت» / «ناموجود». */
export function quarterIndex(
  chapter: string,
  quarter: string,
  provisionalCoef: number | null,
): [number | null, string] {
  const [v] = chapterIndexQ(chapter, quarter);
  if (v !== null) return [v, "قطعی"];
  if (quarterIsProvisional(quarter) && provisionalCoef) {
    const [v2] = chapterIndex(chapter, "q4");
    if (v2 !== null) return [v2 * provisionalCoef, "موقت"];
  }
  return [null, "ناموجود"];
}

/** شاخص رشته در یک سه‌ماهه (تجهیز و ردیف‌های بدون شاخص فصل — بند ۴). */
export function quarterDiscipline(
  quarter: string,
  provisionalCoef: number | null,
  discipline = "ابنیه",
): [number | null, string] {
  const pk = QUARTER_PERIOD[quarter ?? ""];
  if (pk) {
    const [v] = indexValue(pk, discipline);
    if (v !== null) return [v, "قطعی"];
    return [null, "ناموجود"];
  }
  if (quarterIsProvisional(quarter) && provisionalCoef) {
    const [v] = indexValue("q4", discipline);
    if (v !== null) return [v * provisionalCoef, "موقت"];
  }
  return [null, "ناموجود"];
}

// ── شاخص‌های ماهانهٔ ۱۴۰۵ (بخشنامهٔ ۱۴۴۳۷۴) ──

/** بخشِ شاخص‌های ماهانهٔ config/index_bulletins.json. */
function monthlyCfg(): Record<string, any> {
  return (CFG["monthly"] ?? {}) as Record<string, any>;
}

/** دوره‌های ماهانهٔ موجود در config. */
export function monthlyPeriods(): { key: string; label: string }[] {
  return Object.entries(monthlyCfg()["periods"] ?? {}).map(([key, label]) => ({
    key,
    label: String(label),
  }));
}

/** آیا شاخص ماهانه وارد شده؟ (هرگز حدس زده نمی‌شود). */
export function monthlyHasData(monthKey: string): boolean {
  const m = monthlyCfg();
  const ch = (m["chapters_abnieh"] as any[]) ?? [];
  const di = (m["disciplines"] as any[]) ?? [];
  if (ch.length === 0 && di.length === 0) return false;
  return (
    ch.some((r) => typeof r[monthKey] === "number") ||
    di.some((r) => typeof r[monthKey] === "number")
  );
}

/** شاخص یک فصل در یک ماه (۱۴۴۳۷۴). → (مقدار, صفحه). */
export function monthlyChapterIndex(
  chapter: string | number,
  monthKey: string,
): [number, string | number | null] | [null, null] {
  const code = String(chapter).trim().padStart(2, "0");
  const rows = ((monthlyCfg()["chapters_abnieh"] as any[]) ?? []).filter(
    (r) => String(r["chapter"]).trim().padStart(2, "0") === code,
  );
  if (rows.length === 0) return [null, null];
  const v = rows[0][monthKey];
  return typeof v === "number" ? [v, rows[0]["page"] ?? null] : [null, null];
}

/** شاخص رشته در یک ماه (۱۴۴۳۷۴). → (مقدار, صفحه). */
export function monthlyDiscipline(
  monthKey: string,
  discipline = "ابنیه",
): [number, string | number | null] | [null, null] {
  const rows = ((monthlyCfg()["disciplines"] as any[]) ?? []).filter(
    (d) => d["name"] === discipline,
  );
  if (rows.length === 0) return [null, null];
  const v = rows[0][monthKey];
  return typeof v === "number" ? [v, rows[0]["page"] ?? null] : [null, null];
}

/** بخشنامهٔ ۱۴۴۳۷۴: مهلت تسلیم در تابستان ۱۴۰۵ ⇒ Io = خرداد ۱۴۰۵.
 * تابستان ۱۴۰۵ = تیر/مرداد/شهریور (ماه‌های ۴–۶)؛ در غیر این صورت null. */
export function ioMonthFor(dateText: string | null | undefined): string | null {
  const p = parseJalali(dateText);
  if (!p) return null;
  const [y, mo] = p;
  return y === 1405 && mo >= 4 && mo <= 6 ? "khordad_1405" : null;
}

// ── ضریب موقت ۱۴۰۵Q1: محاسبهٔ خودکار از CPI + m (بخشنامهٔ ۱۴۴۳۷۳) ──

const CPI_MONTHLY = CPI_MONTHLY_RAW as unknown as {
  months: Record<string, Record<string, number>>;
};
const PROVISIONAL_M = PROVISIONAL_M_RAW as unknown as {
  meta: {
    numerator_month?: { year: string | number; month: string | number; label?: string };
    denominator_months?: Array<{ year: string | number; month: string | number; label?: string }>;
  };
  m_by_discipline: Record<string, number>;
  exceptions?: Array<{
    disciplines: string[];
    chapter: string | number;
    apply?: boolean;
    note?: string;
  }>;
};

export interface ProvisionalTrace {
  discipline: string;
  m: number;
  numerator_label: string;
  numerator: number;
  denominator_labels: string[];
  denominator_values: number[];
  denominator_mean: number;
  coef: number;
  source: string;
}

/** ضریب موقت سه‌ماههٔ اول ۱۴۰۵ — محاسبهٔ خودکار از CPI و m.
 *
 * فرمول (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳، پیوست ص۱):
 *     coef = 1 + m × (CPI[اردیبهشت ۱۴۰۵] / mean(CPI[دی، بهمن، اسفند ۱۴۰۴]) − 1)
 *
 * CPI از config/cpi_monthly.json (مرکز آمار ایران) و m از
 * config/provisional_m.json. اگر شاخص ماهانهٔ موردنیاز موجود نباشد،
 * null برمی‌گرداند تا موتور متوقف شود (قاعدهٔ طلایی: حدس زده نمی‌شود).
 *
 * خروجی: [coef, status, trace] — status: «محاسبه‌شده»/«ناموجود»/«استثنا». */
export function provisionalCoef1405q1(
  discipline = "ابنیه",
  chapter: string | null = null,
): [number | null, string, Record<string, unknown>] {
  const meta = PROVISIONAL_M.meta ?? {};
  // استثنا (مثلاً «به جز فصل ۱۵» برای راه و راهداری)
  if (chapter !== null) {
    for (const exc of PROVISIONAL_M.exceptions ?? []) {
      if (
        String(chapter) === String(exc.chapter) &&
        (exc.disciplines ?? []).includes(discipline) &&
        exc.apply === false
      ) {
        return [null, "استثنا", { reason: exc.note ?? "" }];
      }
    }
  }
  const m = PROVISIONAL_M.m_by_discipline?.[discipline];
  if (m === undefined || m === null) {
    return [
      null,
      "ناموجود",
      { reason: `ضریب m برای رشتهٔ ${discipline} در provisional_m.json نیست` },
    ];
  }
  const cpi = CPI_MONTHLY.months ?? {};
  const num = (meta.numerator_month ?? {}) as {
    year: string | number;
    month: string | number;
    label?: string;
  };
  const den = (meta.denominator_months ?? []) as Array<{
    year: string | number;
    month: string | number;
    label?: string;
  }>;
  let nV = NaN;
  let dVs: number[] = [];
  try {
    nV = Number(cpi[String(num.year)]?.[String(num.month)]);
    dVs = den.map((d) => Number(cpi[String(d.year)]?.[String(d.month)]));
    if (!Number.isFinite(nV) || dVs.some((v) => !Number.isFinite(v))) {
      throw new Error("missing CPI");
    }
  } catch {
    return [
      null,
      "ناموجود",
      { reason: "شاخص ماهانهٔ موردنیاز در config/cpi_monthly.json نیست" },
    ];
  }
  const meanD = dVs.reduce((a, b) => a + b, 0) / dVs.length;
  const coef = 1 + m * (nV / meanD - 1);
  const trace: ProvisionalTrace = {
    discipline,
    m,
    numerator_label: num.label ?? "",
    numerator: nV,
    denominator_labels: den.map((d) => d.label ?? ""),
    denominator_values: dVs,
    denominator_mean: meanD,
    coef,
    source: "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱ + مرکز آمار ایران",
  };
  return [coef, "محاسبه‌شده", trace as unknown as Record<string, unknown>];
}

/** گرد کردن به ndigits رقم اعشار (ریال). */
export function roundTo(value: number, ndigits = 0): number {
  const f = 10 ** ndigits;
  return Math.round((value + (value >= 0 ? 1 : -1) * Number.EPSILON) * f) / f;
}

/** تفکیک گردشدهٔ یک جمع به دو بخش، با این تضمین که
 * «بخش اول + بخش دوم ≡ گردشدهٔ کل» برقرار باشد. باقیماندهٔ
 * گردسازی به بخش دوم (علی‌الحساب) داده می‌شود.
 * → [کل گردشده, بخش اول گردشده, بخش دوم گردشده]. */
export function splitRounded(
  total: number,
  first: number,
  ndigits = 0,
): [number, number, number] {
  const r = roundTo(total, ndigits);
  const a = roundTo(first, ndigits);
  return [r, a, r - a];
}

// ── رجیستری «مقادیر منتظر تأیید» ──

function adjPending(
  item: string,
  value: number | null,
  source: string,
  page: string,
  status: string,
  action = "",
): AdjPending {
  return { item, value, source, page, status, action };
}

/** خواندن یک شاخص دستی (دستی مقدم بر جدول بخشنامه). */
function adjManualGet(
  manual: Record<string, any> | null | undefined,
  key: string,
): number | null {
  if (!manual || typeof manual !== "object") return null;
  const v = manual[key];
  return typeof v === "number" && v ? v : null;
}

/** ── فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستی (فیلدِ اجباریِ src). ──
 * متنِ منبع را برمی‌گرداند یا null اگر مشخص نشده. */
function manualSrc(
  manual: Record<string, any> | null | undefined,
): string | null {
  if (!manual || typeof manual !== "object") return null;
  const src = manual["src"];
  return typeof src === "string" && src.trim() ? src.trim() : null;
}

/** هشدارِ «منبعِ شاخص دستی وارد نشده» (با dedup روی کد). پیام‌ها باید
 * دقیقاً با app.py (Python) یکسان باشند. */
function warnManualSrcRequired(
  warns: Warning[],
  code: string,
  kind: "chapter" | "discipline",
): void {
  if (
    !warns.some(
      (x) =>
        x.item === "manual_index_source_required" &&
        (x as any)._code === code,
    )
  ) {
    const isChapter = kind === "chapter";
    warns.push({
      level: "خطا",
      category: "موتور تعدیل",
      item: "manual_index_source_required",
      message: isChapter
        ? `شاخص دستی برای فصل ${code} وارد شده ولی منبعِ آن (src) مشخص نشده است؛ منبع را وارد کنید (مثلاً «نامهٔ کارفرما» یا «پیوست ۳، صفحهٔ ۸۲»).`
        : `شاخص دستی برای رشتهٔ ${code} وارد شده ولی منبعِ آن (src) مشخص نشده است؛ منبع را وارد کنید.`,
      action: isChapter
        ? "فیلدِ src شاخص دستیِ این فصل را پر کنید."
        : "فیلدِ src شاخص دستیِ رشته را پر کنید.",
      ref: "بخشنامهٔ ۲۰۸۰ — گام ۸",
    } as Warning & { _code: string });
  }
}

// ── زنجیرهٔ محاسبهٔ مبلغ پایهٔ A — نمایش شفاف قدم‌به‌قدم ──

export function adjBaseChain(
  s: ProjectSettings,
  ctx: AdjustmentCtx,
  applyAdvance = false,
  pending?: AdjPending[],
): { A: number; chain: AdjChainRow[]; applied: number } {
  const baseTotal = Number(ctx.base_total ?? 0);
  const fi = ctx.floors_info ?? { value: 1, status: "—", eligible_total: 0, excluded_total: 0 };
  const eligible = Number(fi.eligible_total ?? 0);
  const excludedAmt = baseTotal - eligible;
  const pf = Number(fi.value ?? 1);
  const floorsAmt = Number(ctx.floors_amount ?? 0);
  const rows: AdjChainRow[] = [
    ["جمع کل ردیف‌های فهرست‌بها", baseTotal, "مجموع مبالغ اندیس‌شدهٔ همهٔ ردیف‌ها"],
    [
      "ردیف‌های مستثنی از ضریب طبقات",
      excludedAmt,
      "فصل ۲۸ (حمل‌ونقل) و فصول ≥۳۰ — ضریب طبقات اعمال نمی‌شود",
    ],
    [
      "ردیف‌های مشمول ضریب طبقات",
      eligible,
      `ضریب P = ${faFloat(pf, 4)} — وضعیت: ${fi.status ?? "—"}`,
    ],
    [
      "مبلغ کارکرد پایه (A۰ = مشمول × P + مستثنی)",
      floorsAmt,
      "پایهٔ تعدیل؛ شامل سربار و ضریب منطقه‌ای نیست",
    ],
  ];
  // ── ضرایب قیمت پیمان: بالاسری × منطقه‌ای × ضریب پیشنهادی پیمانکار ──
  const oh = Number(ctx.overhead_coef ?? 1);
  const reg = Number(ctx.regional_coef ?? 1);
  const prop = Number(s.proposalCoef ?? 1);
  const priceMult = oh * reg * prop;
  const basis = s.aBasis ?? "با ضرایب";
  const withCoefs = basis === "با ضرایب";
  let A = floorsAmt;
  let applied = 1;
  if (withCoefs && priceMult !== 1) {
    applied = applied * priceMult;
    let a = A * oh;
    rows.push(["× ضریب بالاسری", a, `ضریب ${faFloat(oh, 4)} — قیمت پیمان`]);
    a = a * reg;
    rows.push(["× ضریب منطقه‌ای", a, `ضریب ${faFloat(reg, 4)}`]);
    A = a * prop;
    rows.push([
      "× ضریب پیشنهادی پیمانکار",
      A,
      `دستی — ضریب ${faFloat(prop, 4)} — نیازمند تأیید`,
    ]);
  }
  if (pending && withCoefs) {
    pending.push(
      adjPending(
        "ضریب پیشنهادی پیمانکار",
        prop,
        "دستی — پروندهٔ قرارداد / مدیریت پیمان",
        "—",
        "دستی — نیازمند تأیید",
        "ضریب پیشنهادی پیمانکار را از پروندهٔ قرارداد وارد کنید.",
      ),
    );
  }
  if (applyAdvance && s.tadilAdvanceMode === "کسر پیش‌پرداخت") {
    const adv = Number(ctx.advance_payment ?? 0);
    if (adv > 0) {
      A = A - adv;
      rows.push([
        "− کسر پیش‌پرداخت",
        A,
        "مبلغ کارکرد پس از کسر پیش‌پرداخت (تنظیم موتور)",
      ]);
    }
  }
  return { A, chain: rows, applied };
}

const TADIL_FORMULA = "ΔP = k × Σ_c (It_c/Io_c − 1) × A_c";
const BARAVORD_FORMULA = "A_new = Σ_c A_c × It_c/Io_c";

function pageLabel(p: string | number | null): string {
  return p !== null && p !== undefined && p !== "" ? `صفحهٔ ${faDigits(p)}` : "—";
}

// ── موتور ۱ — تعدیل پیمان ──

// ── فاز E-6: ضریب قانونی k و گردکردن آن (بخشنامهٔ ۲۰۸۰) ──
// منبع: docs/sources/2080.pdf (اسکن ۷ صفحه‌ای). شماره و تاریخ روی خود
// سند درج شده‌اند (صفحهٔ ۴): بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ مورخ ۱۳۷۰/۰۶/۲۳،
// صادرکننده: سازمان برنامه و بودجه (معاون رئیس‌جمهور و رئیس سازمان:
// مسعود روغنی زنجانی). کامل‌ترین متن بندها در docs/sources/2080_summary.md.
export const TADIL_K_2080 = 0.95; // بند ۱-۸ — ضریب پایه
export const TADIL_K_COMPLETED = 1.0; // تبصرهٔ ۲ بند ۱-۸ — اتمام کار در مدت پیمان
export const TADIL_K_SOURCE =
  "بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳) — سازمان برنامه و " +
  "بودجه، دستورالعمل تعدیل واحدهای پایهٔ پیمان — بند ۱-۸";
export const TADIL_K_SOURCE_COMPLETED = TADIL_K_SOURCE + " + تبصرهٔ ۲";

// ─ـ فاز E-6 Part C گام ۱۲ (حرف g): تصمیماتِ باز «منتظر تأیید کاربر» ─ـ
// فاز E-8 §۱: شناسهٔ ثابت و پایدار D-01..D-20 (هرگز عوض نمی‌شود).
// D-01..D-18 = تفسیرهای ابهامِ بخشنامهٔ ۲۰۸۰ (ACCEPTANCE §۱۸-۳).
// D-19/D-20 = دو تصمیمِ وابسته به داده (خارج از تفسیرِ ۲۰۸۰).
// تک‌منبعِ حقیقت برای پنلِ «وضعیت ورودی‌ها» (React) و شیتِ Excel
// «مقادیر منتظر تأیید». این فهرست باید با §۱۸-۳ ACCEPTANCE.md و
// PENDING_INTERPRETATIONS در app.py یکی باشد.
export interface PendingInterpretation {
  id: string;
  subject: string;
  implemented: string;
  alternative: string;
  effect: string;
}
export const PENDING_INTERPRETATIONS: PendingInterpretation[] = [
  {
    id: "D-01",
    subject: "ضریب k ورودی کاربر نیست (بند ۱-۸)",
    implemented:
      "k از وضعیت اتمام کار مشتق می‌شود: ۰٫۹۵ (بند ۱-۸) یا ۱ (تبصرهٔ ۲).",
    alternative: "ورودیِ دستیِ k مثلِ نسخه‌های قدیم.",
    effect:
      "k=۱ به‌جای ۰٫۹۵ ⇒ ΔP از ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲ به ۱۰٬۴۸۹٬۵۹۴٬۳۶۹٫۰۷ یعنی +۵۰۵٬۳۱۶٬۹۶۰٫۸۶ ریال (=`k_diff` بند ۸-۴).",
  },
  {
    id: "D-02",
    subject: "گرانولاریتیِ گردکردن (بند ۸-۲)",
    implemented: "ضریبِ هر فصل در هر سه‌ماهه به‌صورتِ مجزا گرد می‌شود.",
    alternative: "گردکردنِ ضریبِ کلِ فصل.",
    effect: "تفاوتِ جزئی در فصل‌هایی با کارکردِ ناتمام.",
  },
  {
    id: "D-03",
    subject: "تفسیر گردکردن (الف)",
    implemented:
      "ضریب با ۳ رقم اعشار با ROUND_HALF_UP؛ اگر رقمِ سوم ≥ ۵ بود رقمِ دوم بالا می‌رود وگرنه رقمِ سوم برداشته می‌شود.",
    alternative: "گردکردنِ مستقیم به ۲ رقم (تفسیر ب).",
    effect: "تفاوتِ حداکثر ۰٫۰۰۵ در هر ضریب.",
  },
  {
    id: "D-04",
    subject: "ضرایب منفی",
    implemented:
      "بخشنامه ساکت است؛ ضرایبِ منفی مجازند و ΔP می‌تواند منفی شود.",
    alternative: "صفر کردنِ ضرایبِ منفی.",
    effect: "در صورتِ کاهشِ شاخص، ΔP منفی نشان داده می‌شود.",
  },
  {
    id: "D-05",
    subject: "پیاده‌سازی بدون خطای شناور",
    implemented:
      "پایتون از Decimal روی کوتاه‌ترین نمایشِ float استفاده می‌کند.",
    alternative: "استفاده از round() سرّی.",
    effect: "تفاوت در مرزهایِ گردکردن (مثل ۰٫۰۰۵).",
  },
  {
    id: "D-06",
    subject: "رفتار UI",
    implemented:
      "فیلد عددی k حذف شد و به‌جای آن selectbox برای وضعیت اتمام کار است.",
    alternative: "نگه‌داشتنِ فیلد عددی.",
    effect: "فقط تجربهٔ کاربری؛ اعداد تغییر نمی‌کنند.",
  },
  {
    id: "D-07",
    subject: "مبنای کسرِ ۵٪ (بند ۷)",
    implemented: "کسر = ۵٪ از کلِ ΔP (مستقل از قطعی/علی‌الحساب).",
    alternative: "۵٪ فقط از بخشِ قطعی.",
    effect: "در سناریوی ترکیبی، کسر از کلِ ΔP بیشتر می‌شود.",
  },
  {
    id: "D-08",
    subject: "کسر در تعدیلِ منفی (بند ۷)",
    implemented:
      "اگر ΔP < ۰، کسر اعمال نمی‌شود (هیچ کسری از عددِ منفی کسر نمی‌شود).",
    alternative: "اعمالِ کسر در همهٔ حالات (ΔPِ منفی‌تر).",
    effect: "در صورتِ کاهشِ شاخص، کسر صفر می‌شود.",
  },
  {
    id: "D-09",
    subject: "گرانولاریتیِ بند ۲-۶",
    implemented:
      "هر سه‌ماهه‌ای که روز شروعش > آخرین موقت است میانگینِ ۲-۶ را می‌گیرد.",
    alternative: "تقسیمِ وزنیِ سه‌ماههٔ مرزی به نسبتِ روزها.",
    effect: "فقط در پروژه‌هایی با lpd نمایش داده می‌شود.",
  },
  {
    id: "D-10",
    subject: "کارِ پوشش‌شده با تمدیدِ مجاز در بند ۲-۶",
    implemented:
      "«مدت پیمان» = مدت اولیه + تمدیدها؛ کارِ قبل از term_end درونِ مدت محسوب می‌شود و میانگینِ ۲-۶ را می‌گیرد.",
    alternative: "شاخصِ همان دوره طبق ۲-۵-۱ (تأخیر مجاز).",
    effect: "فقط در پروژه‌هایی با تمدیدِ مجاز + lpd.",
  },
  {
    id: "D-11",
    subject: "آستانهٔ ۳۰۰ میلیون ریال (بندهای ۲-۱/۲-۲)",
    implemented:
      "مقدار از config (bulletin_2080.threshold_rail) خوانده می‌شود.",
    alternative: "ثابتِ هاردکدشده.",
    effect: "با مقدارِ فعلی: هیچ.",
  },
  {
    id: "D-12",
    subject: "مرزِ آستانه (۲-۱/۲-۲)",
    implemented: "آستانه و بیشتر ⇒ گروهی (amount >= threshold).",
    alternative: "دقیقاً برابر ⇒ رشته‌ای.",
    effect: "فقط در پیمانِ دقیقاً ۳۰۰٬۰۰۰٬۰۰۰ ریالی.",
  },
  {
    id: "D-13",
    subject: "گرانولاریتیِ مسیر رشته‌ای (۲-۱)",
    implemented:
      "در مسیر رشته‌ای همهٔ فصول و تجهیز از شاخصِ رشته استفاده می‌کنند.",
    alternative: "فقط فصولی که شاخصِ گروهی ندارند.",
    effect:
      "پروژهٔ مرجع ابنیه و مسیرِ پیش‌فرض گروهی است؛ اعداد ثابت می‌مانند.",
  },
  {
    id: "D-14",
    subject: "کار جدید بعد از تبدیل مثلِ تجهیز تعدیل می‌شود (۳-۱..۳-۵)",
    implemented:
      "بعد از تبدیل، مبلغِ کار جدید مثلِ تجهیز (بند ۴) با شاخصِ رشته و شاخه‌های تأخیر تعدیل می‌شود.",
    alternative: "فقط جبرانِ ۳-۵ بدونِ تعدیلِ مجدد.",
    effect: "ΔP در پروژهٔ مرجع به‌جای ۰ به ۳۰۹٬۸۳۰٬۰۹۷٫۰۹ ریال می‌رسد.",
  },
  {
    id: "D-15",
    subject: "دورهٔ شاخصِ مبنا در ۳-۲/۳-۳ ناموجود",
    implemented:
      "اگر new_item_base_period خالی یا ناموجود باشد، ردیف ساخته نمی‌شود و هشدارِ خطا داده می‌شود.",
    alternative: "استفاده از آخرین سه‌ماههٔ موجود یا توقفِ موتور.",
    effect: "کار جدید کاملاً نادیده گرفته می‌شود (ΔP ثابت).",
  },
  {
    id: "D-16",
    subject: "روشِ نامعتبرِ کار جدید به ۳-۱ برمی‌گردد",
    implemented:
      "اگر new_item_method مجاز نباشد، موتور به «فهرست پیمان» برمی‌گردد.",
    alternative: "خطا و توقف.",
    effect: "با فرضِ ۳-۱ ادامه می‌یابد (conv = ۱).",
  },
  {
    id: "D-17",
    subject: "گردنشدنِ ضریبِ تبدیلِ ۳-۵ قبل از ضرب در مبلغ",
    implemented:
      "conv با دقتِ کامل float محاسبه و در مبلغ ضرب می‌شود؛ گردکردنِ ۸-۲ فقط روی ضرایبِ k×(It/Io−1) اعمال می‌شود.",
    alternative: "گردکردنِ conv به n رقم قبل از ضرب.",
    effect: "تفاوت زیرریالی (conv = ۰٫۸۸۳۶۶۴۶۲۳۳۰۸۷۸۹).",
  },
  {
    id: "D-18",
    subject: "مبنای «مبلغ برآورد» در سقفِ ۱۰٪ نامه-۶ (گام ۷)",
    implemented:
      "مبلغ برآورد بر اساس قیمت‌های پایه = base_total (بدون ضرایب)، نه grand_total.",
    alternative: "grand_total (شاملِ ضرایب).",
    effect:
      "سقفِ ۲۵٬۵۴۰٬۲۱۹٬۴۷۰٫۷۱ به‌جای ۳۴٬۵۳۰٬۳۷۶٬۷۲۴٫۴۰ — تفاوت ۸٬۹۹۰٬۱۵۷٬۲۵۳٫۶۹ ریال.",
  },
  // ── دو تصمیمِ بازِ خارج از تفسیرِ بخشنامه (وابسته به داده) ──
  {
    id: "D-19",
    subject: "شاخص کلیِ مستقل برای تجهیز/مصالح (بندهای ۱-۲/۲-۳)",
    implemented:
      "در مسیرِ رشته‌ای، شاخصِ رشتهٔ خودِ پروژه خوانده می‌شود؛ شاخصِ کلیِ مستقل هنوز در config وجود ندارد.",
    alternative: "استفاده از شاخصِ کلیِ مستقلِ مرکز آمار (داده نیاز است).",
    effect:
      "اگر شاخصِ مستقل برابرِ شاخصِ رشته باشد اثر صفر؛ در غیر این صورت تفاوت روی هزینهٔ تجهیزِ کارگاه (ایراد I-09).",
  },
  {
    id: "D-20",
    subject: "مصالحِ پای‌کار (بند ۲-۴)",
    implemented:
      "هیچ شاخصِ اختصاصی برای مصالحِ پای‌کار پیاده نشده؛ از شاخصِ رشته استفاده می‌شود.",
    alternative: "شاخصِ اختصاصیِ مصالحِ پای‌کار (کرایهٔ حمل از پایِ کارگاه).",
    effect:
      "در پروژهٔ مرجع site_setup_amount = ۰ است ⇒ اثر صفر؛ در پروژه‌هایی با تجهیزِ بالا تفاوت می‌کند.",
  },
];


// ── فاز E-6 Part C گام ۶ (حرف b): مسیر شاخص — بندهای ۲-۱/۲-۲ ──
// پیمانِ با مبلغ اولیهٔ کمتر از آستانه با شاخص رشته‌ای (۲-۱) و آستانه و
// بیشتر با شاخص‌های گروهی (۲-۲) تعدیل می‌شود. منبعِ آستانه:
// config/index_bulletins.json → bulletin_2080.threshold_rail (ارقامِ سال
// ۱۳۷۰ بندهای ۲-۱/۲-۲). اگر کلید نبود، مقدارِ ۳۰۰٬۰۰۰٬۰۰۰ فرض می‌شود و
// موتور هشدار می‌دهد (حدسِ بدونِ هشدار ممنوع است).
const _B2080_CFG = (CFG["bulletin_2080"] ?? {}) as Record<string, any>;
export const CHAIN_THRESHOLD_MISSING =
  typeof _B2080_CFG["threshold_rail"] !== "number" ||
  !(_B2080_CFG["threshold_rail"] > 0);
export const CHAIN_THRESHOLD_RIALS = CHAIN_THRESHOLD_MISSING
  ? 300_000_000
  : Number(_B2080_CFG["threshold_rail"]);

// ── فاز E-6 Part C گام ۷ (حرف c): سقفِ قیمت قابل قبول — نامه-۶ ──
// «در کارهایی که شاخص مبنایشان طبق ۱-۶-۱ یکم است، سقف قیمت قابل قبول
//  حداکثر ۱۰٪ بالاتر از مبلغ برآورد بر اساس قیمت‌های پایه است.»
// منبع: config/index_bulletins.json → bulletin_2080.ceiling_over_estimate_pct.
// اگر کلید نبود، مقدارِ ۱۰ فرض می‌شود و موتور هشدار می‌دهد.
export const CEILING_MISSING =
  typeof _B2080_CFG["ceiling_over_estimate_pct"] !== "number" ||
  !(_B2080_CFG["ceiling_over_estimate_pct"] > 0);
export const CEILING_OVER_ESTIMATE_PCT = CEILING_MISSING
  ? 10
  : Number(_B2080_CFG["ceiling_over_estimate_pct"]);

// ─ـ فاز E-6 Part C گام ۸ (حرف e): آستانهٔ اختلافِ شاخص دستی با config ──
// اگر شاخص دستی بیش از این کسر با شاخصِ config اختلاف داشته باشد، موتور
// هشدار می‌دهد (حدسِ خاموش ممنوع). ۰٫۲۰ = ۲۰٪.
export const MANUAL_INDEX_DEVIATION_MISSING =
  typeof _B2080_CFG["manual_index_deviation_pct"] !== "number" ||
  !(_B2080_CFG["manual_index_deviation_pct"] > 0);
export const MANUAL_INDEX_DEVIATION_PCT = MANUAL_INDEX_DEVIATION_MISSING
  ? 0.20
  : Number(_B2080_CFG["manual_index_deviation_pct"]);

/** ضریب قانونی k بر اساس وضعیت اتمام کار (فاز E-6 — بند ۱-۸ و تبصرهٔ ۲).
 * خروجی: [k, برچسب وضعیت, منبع] */
export function tadilK(s: ProjectSettings): [number, string, string] {
  const cwt = s.completedWithinTerm;
  if (cwt === true) {
    return [
      TADIL_K_COMPLETED,
      "قطعی — کار در مدت پیمان تمام شد (تبصرهٔ ۲ بند ۱-۸)",
      TADIL_K_SOURCE_COMPLETED,
    ];
  }
  if (cwt === false) {
    return [
      TADIL_K_2080,
      "قطعی — کار در مدت پیمان تمام نشد (بند ۱-۸)",
      TADIL_K_SOURCE,
    ];
  }
  return [
    TADIL_K_2080,
    "علی‌الحساب — تکلیف اتمام کار در مدت پیمان نامشخص است (بند ۱-۸)",
    TADIL_K_SOURCE,
  ];
}

/** گردکردن ضریب تعدیل طبق بند ۸-۲ بخشنامهٔ ۲۰۸۰.
 *
 * ضریب اول با ۳ رقم اعشار حساب می‌شود؛ اگر رقم سوم >= ۵ باشد رقم دوم
 * یکی بالا می‌رود وگرنه رقم سوم حذف می‌شود (ضریب نهایی با ۲ رقم اعشار).
 * معادل app.py:round_coef_2080 (Decimal) — بدون خطای شناور، روی
 * کوتاه‌ترین نمایش دهدهی عدد. ضرایب منفی روی قدر مطلق عمل می‌کنند. */
export function roundCoef2080(x: number): number;
export function roundCoef2080(x: number | null | undefined): number | null;
export function roundCoef2080(x: number | null | undefined): number | null {
  if (x === null || x === undefined) return null;
  const neg = x < 0;
  const a = neg ? -x : x;
  let str = a.toString();
  if (str.includes("e")) str = a.toFixed(12); // هرگز برای ضرایب واقعی رخ نمی‌دهد
  const dot = str.indexOf(".");
  const ip = dot < 0 ? str : str.slice(0, dot);
  const fpRaw = dot < 0 ? "" : str.slice(dot + 1);
  const fp = fpRaw.padEnd(4, "0");
  // ۱) ۳ رقم اعشار با نیم‌به‌بالا (رقم چهارم و بعد از آن تصمیم می‌گیرند)
  let r3 = parseInt(ip + fp.slice(0, 3), 10); // مقدار × ۱۰۰۰
  if (parseInt(fp.slice(3, 4), 10) >= 5) r3 += 1;
  // ۲) رقم سوم اعشار تصمیم می‌گیرد: >= ۵ => رقم دوم بالا می‌رود
  const third = ((r3 % 10) + 10) % 10;
  const scaled = third >= 5 ? Math.ceil(r3 / 10) : Math.floor(r3 / 10);
  const r2 = scaled / 100;
  return neg ? -r2 : r2;
}

/** فاز E-6 Part C گام ۶ — مسیر شاخص: «گروهی» (۲-۲) یا «رشته‌ای» (۲-۱).
 * «خودکار» از رویِ مبلغ اولیهٔ پیمان در برابرِ آستانهٔ config حل می‌شود.
 * خروجی: [method, source]. هشدارها با dedup روی item ساطع می‌شوند تا
 * با اجرای هر دو موتور تکرار نشوند (هر دو warns را به‌اشتراک می‌گذارند). */
export function chainMethod(
  s: ProjectSettings,
  warns: Warning[],
): ["گروهی" | "رشته‌ای", string] {
  const rawMethod = (s.indexMethod ?? "گروهی").trim();
  const im: "گروهی" | "رشته‌ای" | "خودکار" =
    rawMethod === "رشته‌ای" || rawMethod === "خودکار" ? rawMethod : "گروهی";
  if (im !== "خودکار") return [im, "دستی"];
  // هشدارِ آستانهٔ ۱۳۷۰ فقط در حالتِ خودکار (دستگاه خودش حل می‌کند)
  if (!warns.some((x) => x.item === "index_method_threshold_1370")) {
    let msg =
      `آستانهٔ ${faDigits(CHAIN_THRESHOLD_RIALS.toLocaleString("en-US"))} ریال برای مسیر رشته‌ای/گروهی از ارقامِ سال ۱۳۷۰ بندهای ۲-۱/۲-۲ است؛ اگر در بخشنامه‌های بعدی تصحیح شده، مقدارِ config/index_bulletins.json → bulletin_2080.threshold_rail را به‌روز کنید.`;
    if (CHAIN_THRESHOLD_MISSING) {
      msg +=
        " نکته: کلیدِ bulletin_2080.threshold_rail در config نیست — مقدارِ ۳۰۰٬۰۰۰٬۰۰۰ فرض شد.";
    }
    warns.push({
      level: "اطلاع",
      category: "موتور تعدیل",
      item: "index_method_threshold_1370",
      message: msg,
      action: "آستانه و مبلغ اولیهٔ پیمان را بررسی کنید.",
      ref: "بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲",
    });
  }
  const raw = s.contractInitialAmount;
  const amt =
    typeof raw === "number" && !Number.isNaN(raw) && raw >= 0 ? raw : null;
  if (amt !== null) {
    if (amt < CHAIN_THRESHOLD_RIALS) {
      return ["رشته‌ای", "خودکار: مبلغ اولیه < آستانه (بند ۲-۱)"];
    }
    return ["گروهی", "خودکار: مبلغ اولیه ≥ آستانه (بند ۲-۲)"];
  }
  if (!warns.some((x) => x.item === "index_method_no_amount")) {
    warns.push({
      level: "هشدار",
      category: "موتور تعدیل",
      item: "index_method_no_amount",
      message:
        "مسیر شاخص «خودکار» است ولی مبلغ اولیهٔ پیمان وارد نشده؛ مسیر گروهی (۲-۲) فرض می‌شود.",
      action:
        "مبلغ اولیهٔ پیمان را در بخش «ورودی‌های قرارداد» وارد کنید.",
      ref: "بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲",
    });
  }
  return ["گروهی", "خودکار: مبلغ اولیه وارد نشده — مسیر گروهی (۲-۲)"];
}

/** ردیفِ مبلغی که با شاخصِ رشته تعدیل می‌شود (فاز E-6 Part C).
 *
 * تجهیز/برچیدن (بند ۴) و کارهای جدید (بندهای ۳-۱..۳-۵) هر دو از
 * این منطق استفاده می‌کنند: نسبتِ It/Io برای هر سه‌ماهه با
 * شاخه‌های تأخیر (۲-۵-۲/۲-۵-۳/۲-۶) و گردکردنِ بند ۸-۲.
 */
function disciplineAmountRow(
  amount: number,
  dIo: number,
  split: [string, number][],
  delay: DelayInfo,
  prov: number | null,
  disc: string,
  dItM: number | null,
  doRound: boolean,
  k: number,
  missing: [string, string, string][],
  label: string,
  status: string,
  src: string,
  span26: string[] = [],
  ov26: Set<string> = new Set(),
): { row: AdjSetupRow; dp: number; dpDef: number; dp095: number } {
  let dp = 0;
  let dpDef = 0;
  let dp095 = 0;
  let dItW = 0;
  const coefRows: [string, number, number][] = [];
  const dn: DelayNote[] = [];
  for (const [q, f] of split) {
    const ov = delay.override[q] ?? null;
    let dItV: number | null;
    let dSt: string;
    let dBaseSt: string;
    if (ov && ov.rule === "غیرمجاز") {
      // ۲-۵-۲: میانگین شاخص رشتهٔ داخل مدت پیمان
      const vals: number[] = [];
      const sts: string[] = [];
      for (const tq of delay.term_quarters) {
        let tv: number | null;
        let ts: string;
        if (dItM !== null) {
          tv = dItM;
          ts = "دستی";
        } else {
          const [dv, ds] = quarterDiscipline(tq, prov, disc);
          tv = dv;
          ts = ds;
        }
        if (tv === null) continue;
        vals.push(tv);
        sts.push(ts);
      }
      if (vals.length === 0) {
        missing.push([label, "It", `${q} (میانگین مدت)`]);
        continue;
      }
      dItV = vals.reduce((a, b) => a + b, 0) / vals.length;
      dBaseSt = sts.includes("موقت")
        ? "موقت"
        : sts.includes("دستی")
          ? "دستی"
          : "قطعی";
      dSt = `${dBaseSt} (میانگین مدت — ۲-۵-۲)`;
      dn.push({ q, rule: "غیرمجاز",
        note: "میانگین شاخص‌های داخل مدت (۲-۵-۲)" });
    } else if (ov26.has(q)) {
      // بند ۲-۶: میانگین شاخصِ رشتهٔ شروع تا آخرین موقت
      const vals: number[] = [];
      const sts: string[] = [];
      for (const tq of span26) {
        let tv: number | null;
        let ts: string;
        if (dItM !== null) {
          tv = dItM;
          ts = "دستی";
        } else {
          const [dv, ds] = quarterDiscipline(tq, prov, disc);
          tv = dv;
          ts = ds;
        }
        if (tv === null) continue;
        vals.push(tv);
        sts.push(ts);
      }
      if (vals.length === 0) {
        missing.push([label, "It", `${q} (میانگین ۲-۶)`]);
        continue;
      }
      dItV = vals.reduce((a, b) => a + b, 0) / vals.length;
      dBaseSt = sts.includes("موقت")
        ? "موقت"
        : sts.includes("دستی")
          ? "دستی"
          : "قطعی";
      dSt = `${dBaseSt} (میانگینِ تا آخرین موقت — ۲-۶)`;
      dn.push({ q, rule: "۲-۶",
        note: "میانگین شاخص‌های شروع تا آخرین موقت (۲-۶)" });
    } else if (ov) {
      // ۲-۵-۳: علی‌الحساب با شاخص دورهٔ خاتمه
      const bq = ov.basis_q!;
      if (dItM !== null) {
        dItV = dItM;
        dSt = "دستی";
      } else {
        const [dv, ds] = quarterDiscipline(bq, prov, disc);
        dItV = dv;
        dSt = ds;
      }
      if (dItV === null) {
        missing.push([label, "It", bq]);
        continue;
      }
      dBaseSt = dSt;
      dSt = `${dSt} (علی‌الحساب — ۲-۵-۳)`;
      dn.push({ q, rule: "تعیین‌نشده",
        note: "علی‌الحساب با شاخص دورهٔ خاتمه (۲-۵-۳)" });
    } else {
      if (dItM !== null) {
        dItV = dItM;
        dSt = "دستی";
      } else {
        const [dv, ds] = quarterDiscipline(q, prov, disc);
        dItV = dv;
        dSt = ds;
      }
      if (dItV === null) {
        missing.push([label, "It", q]);
        continue;
      }
      dBaseSt = dSt;
    }
    const ratio = dItV / dIo;
    // بند ۸-۲: گردکردن ضریب
    const raw = k * (ratio - 1);
    const used = doRound ? roundCoef2080(raw) : raw;
    dp += used * amount * f;
    if (dBaseSt === "قطعی" && !(ov && ov.rule === "تعیین‌نشده")) {
      dpDef += used * amount * f;
    }
    // مبنای تبصرهٔ ۲
    const raw9 = TADIL_K_2080 * (ratio - 1);
    const used9 = doRound ? roundCoef2080(raw9) : raw9;
    dp095 += used9 * amount * f;
    coefRows.push([q, raw, used]);
    dItW += dItV * f;
  }
  const row: AdjSetupRow = {
    amount,
    io: dIo,
    it: dItW,
    ratio: dIo ? dItW / dIo : null,
    value: dp,
    delta: dp,
    deltaDefinitive: dpDef,
    delta_k095: dp095,
    coef_rows: coefRows,
    delay_notes: dn,
    status,
    src,
  };
  return { row, dp, dpDef, dp095 };
}

export function tadilEngine(
  s: ProjectSettings,
  ctx: AdjustmentCtx,
  warns: Warning[],
): TadilResult {
  const pending: AdjPending[] = [];
  // ── فاز E-6 Part C گام ۶ (حرف b): مسیر شاخص (بندهای ۲-۱/۲-۲) ──
  const [chainMethodResolved, chainMethodSource] = chainMethod(s, warns);
  const disc = (s.regionalSelection?.discipline ?? "ابنیه").trim() || "ابنیه";
  // ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) ──
  let newWorkRow: AdjSetupRow | null = null;
  let newBaseAmt = 0;
  const newMethod0 = (s.newItemMethod ?? "فهرست پیمان").trim()
    || "فهرست پیمان";
  const newMethod = ["فهرست پیمان", "فهرست پایه", "قیمت روز",
    "ترکیب"].includes(newMethod0)
    ? newMethod0
    : "فهرست پیمان";
  const newAmt = Number(s.newItemAmount ?? 0);
  const newAmtAtt = Number(s.newItemAmountAttached ?? 0);
  let newAmtA: number;
  let newAmtB: number;
  if (newMethod === "فهرست پیمان") {
    newAmtA = newAmt;
    newAmtB = 0;
  } else if (newMethod === "ترکیب") {
    newAmtA = newAmtAtt;
    newAmtB = newAmt;
  } else {
    newAmtA = 0;
    newAmtB = newAmt;
  }

  // ── ضریب قانونی k (فاز E-6 — بخشنامهٔ ۲۰۸۰، بند ۱-۸ و تبصرهٔ ۲) ──
  const [k, kStatus, kSource] = tadilK(s);
  const cwt = s.completedWithinTerm === true;
  const doRound = !!s.coefRounding2080;
  pending.push(
    adjPending(
      "ضریب قانونی تعدیل (k)",
      k,
      kSource,
      "بند ۱-۸" + (cwt ? " + تبصرهٔ ۲" : ""),
      kStatus,
      "اگر کار در مدت پیمان (با احتساب تمدیدهای ناشی از تغییر مقادیر) تمام و تحویل موقت شده، completedWithinTerm را روی «بله» تنظیم کنید تا k = ۱ شود (تبصرهٔ ۲ بند ۱-۸). مابه‌التفاوت طبق بند ۸-۴ همزمان با صورت‌وضعیت قطعی پرداخت می‌شود.",
    ),
  );

  // ── مبلغ پایه A و زنجیرهٔ شفاف آن ──
  const { A, chain, applied } = adjBaseChain(s, ctx, true, pending);
  const setup = Number(ctx.site_setup ?? 0);
  // مبالغ فصل‌ها در همان ضریبِ A ضرب می‌شوند تا Σ A_c = A برقرار شود.
  const chap: Record<string, number> = {};
  for (const [c, v] of Object.entries(ctx.chapter_amounts ?? {})) {
    chap[String(c)] = Number(v) * applied;
  }

  // ── دورهٔ مبنا (Io) — بخشنامهٔ ۲۰۸۰، بندهای ۱-۶-۱ و ۱-۶-۲ ──
  let ioQ: string | null = PERIOD_QUARTERS[s.tadilIoPeriod ?? "base"] ?? null;
  const prop = s.proposalDate ?? "";
  const dead = s.proposalDeadline ?? "";
  const offer = s.finalOfferDate ?? "";
  const bim = s.baseIndexMethod ?? "proposal_period";
  let ioDate = "";
  let err: string | null = null;
  if (bim === "fehrest_period") {
    // بند ۱-۶-۱ یکم: شاخص مبنا = دورهٔ سه‌ماهه‌ای که فهرست‌بهای پیمان بر
    // اساس قیمت‌های آن تهیه شده. فقط از config با منبع؛ اگر نبود، موتور
    // می‌ایستد و «نیازمند ورود» می‌دهد (قاعدهٔ طلایی).
    const fy = String(s.fehrestYear ?? "");
    const fbp = (CFG["fehrest_base_periods"] ?? {})[fy];
    if (typeof fbp === "string" && fbp in QUARTER_PERIOD) {
      ioQ = fbp;
    } else {
      err = `دورهٔ قیمت پایهٔ فهرست‌بهای سال ${fy} در config/index_bulletins.json (fehrest_base_periods) وارد نشده است. روش اول بند ۱-۶-۱ نیازمند این دوره است.`;
    }
  } else {
    // بند ۱-۶-۱ دوم و ۱-۶-۲: ملاکِ Io در ترک تشریفاتِ مناقصه، تاریخ تسلیم
    // کتبیِ پیشنهاد نهایی است؛ در غیر آن، مهلت تسلیم پیشنهاد، و اگر نبود
    // خود تاریخ تسلیم پیشنهاد (بخشنامهٔ ۱۴۴۳۷۴).
    ioDate = offer || dead || prop;
    // در موتور تعدیل پیمان یکی از این تاریخ‌ها الزامی است (Io = سه‌ماههٔ
    // آن). خالی یا نامعتبر ⇒ خطا و توقف موتور.
    if (!ioDate) {
      err = "تاریخ تسلیم پیشنهاد (یا مهلت تسلیم، یا پیشنهاد نهایی) خالی است.";
    } else {
      const pq = dateQuarter(ioDate);
      if (pq) {
        ioQ = pq;
      } else {
        err = `تاریخ تسلیم پیشنهاد نامعتبر است: «${ioDate}».`;
      }
    }
  }
  // ── هشدار: Io بعد از It (بند ۱-۷: شاخص دورهٔ انجام کار باید بعد از
  // دورهٔ مبنا باشد). مقایسهٔ کلیدهای سه‌ماهه (ترتیب الفبایی برای فرمت
  // YYYYQn درست است). ──
  // ─ـ فاز E-6 Part C گام ۷ (حرف c): سقفِ قیمت قابل قبول — نامه-۶ ─ـ
  // «در کارهایی که شاخص مبنایشان طبق ۱-۶-۱ یکم است، سقف قیمت قابل
  //  قبول حداکثر ۱۰٪ بالاتر از مبلغ برآورد بر اساس قیمت‌های پایه است
  //  و انعقاد قرارداد بیش از آن مجاز نیست.»
  // مبلغِ برآورد بر اساس قیمت‌های پایه = ctx.base_total (تفسیر ۱۸:
  // base_total، نه grand_total — §۱۸-۳). فقط وقتی روش ۱-۶-۱ یکم
  // (fehrest_period) انتخاب شده باشد بررسی می‌شود.
  if (bim === "fehrest_period") {
    const bt = Number(ctx.base_total ?? 0);
    const ciaRaw = s.contractInitialAmount;
    const cia =
      typeof ciaRaw === "number" && Number.isFinite(ciaRaw) ? ciaRaw : null;
    if (cia !== null && bt > 0
        && cia > bt * (1 + CEILING_OVER_ESTIMATE_PCT / 100)) {
      if (!warns.some((x) => x.item === "contract_price_ceiling_110")) {
        const ceiling = bt * (1 + CEILING_OVER_ESTIMATE_PCT / 100);
        let ceilMsg =
          `قیمت قرارداد (${faFloat(cia, 0)}) بیشتر از سقفِ مجاز ` +
          `(${faFloat(ceiling, 0)} = مبلغ برآورد بر اساس قیمت‌های پایه ` +
          `${faFloat(bt, 0)} + ${faFloat(CEILING_OVER_ESTIMATE_PCT, 0)}%) ` +
          "است؛ انعقادِ قرارداد بیش از این سقف طبق نامه-۶ مجاز نیست.";
        if (CEILING_MISSING) {
          ceilMsg +=
            " نکته: کلیدِ bulletin_2080.ceiling_over_estimate_pct در config نیست — مقدارِ ۱۰ فرض شد.";
        }
        warns.push({
          level: "هشدار",
          category: "موتور تعدیل",
          item: "contract_price_ceiling_110",
          message: ceilMsg,
          action:
            "قیمت قرارداد را با مبلغ برآورد بر اساس قیمت‌های پایه تطبیق دهید یا دلیل انحراف را مستند کنید.",
          ref: "نامه-۶",
        });
      }
    }
  }

  const itQKey = PERIOD_QUARTERS[s.tadilItPeriod ?? "q4"] ?? null;
  if (!err && ioQ && itQKey && ioQ > itQKey) {
    warns.push({
      level: "هشدار",
      category: "موتور تعدیل",
      item: "io_after_it",
      message: `دورهٔ مبنا (Io = ${ioQ}) بعد از دورهٔ انجام کار (It = ${itQKey}) است. شاخص مبنا باید دوره‌ای قبل از شروع کار باشد (بند ۱-۷).`,
      action: "روش شاخص مبنا یا تاریخ تسلیم پیشنهاد را بررسی کنید.",
      ref: "فاز E-6 — بند ۱-۷ بخشنامهٔ ۲۰۸۰",
    });
  }
  // ── بخشنامهٔ ۱۴۴۳۷۴: اگر مهلت تسلیم در تابستان ۱۴۰۵ باشد، Io
  // شاخصِ ماهانهٔ خرداد ۱۴۰۵ است (نه سه‌ماهه‌ای). تا شاخص ماهانه وارد
  // نشده، موتور با خطا متوقف می‌شود. ──
  const ioMonth = ioMonthFor(ioDate);
  if (!err && ioMonth && !monthlyHasData(ioMonth)) {
    warns.push({
      level: "خطا",
      category: "موتور تعدیل",
      item: "monthly_index_1405",
      message:
        "مهلت تسلیم پیشنهاد در تابستان ۱۴۰۵ است؛ طبق بخشنامهٔ ۱۴۴۳۷۴ Io باید شاخص ماهانهٔ خرداد ۱۴۰۵ (آحادبها) باشد، ولی این شاخص هنوز در config/index_bulletins.json وارد نشده است. موتور تعدیل پیمان متوقف شد.",
      action:
        "شاخص‌های ماهانهٔ خرداد ۱۴۰۵ را در بخش monthly فایل config/index_bulletins.json وارد کنید (هرگز حدس زده نمی‌شود).",
      ref: "فاز E — بخشنامهٔ ۱۴۴۳۷۴",
    });
    return {
      mode: "تعدیل پیمان",
      formula: TADIL_FORMULA,
      error: "شاخص ماهانهٔ خرداد ۱۴۰۵ وارد نشده — موتور تعدیل پیمان متوقف شد.",
      coef: k,
      k_diff: 0,
      coef_rounding: !!s.coefRounding2080,
      completed_within_term: s.completedWithinTerm === true,
      contract_status: s.contractStatus ?? "فعال",
      deduction_fault: 0,
      io_q: ioQ,
      io_month: ioMonth,
      delay_info: EMPTY_DELAY_INFO,
      index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
      split: [],
      base_amount: 0,
      work_base: A,
      chain,
      setup_amount: 0,
      setup_row: null,
      new_work_row: null,
      chapters: [],
      delta_p: 0,
      delta_p_definitive: 0,
      delta_p_provisional: 0,
      result_amount: 0,
      advance_mode: s.tadilAdvanceMode ?? "کل مبلغ کارکرد",
      delay_mode: s.tadilDelayMode ?? "مشمول کل دوره",
      params: {
        allow_negative: !!s.tadilAllowNegative,
        advance_payment: Number(ctx.advance_payment ?? 0),
        proposal_date: prop,
        provisional_coef: null,
      },
      incomplete: true,
      missing: [],
      draft: true,
      pending,
      source: "فاز E — ۱۴۴۳۷۴ (توقف: شاخص ماهانهٔ خرداد ۱۴۰۵)",
    };
  }
  if (err) {
    warns.push({
      level: "خطا",
      category: "موتور تعدیل",
      item: "proposal_date",
      message:
        err + " موتور تعدیل پیمان متوقف شد؛ بدون این تاریخ دورهٔ مبنا (Io) مشخص نیست.",
      action: "تاریخ تسلیم پیشنهاد (شمسی) را در سایدبار وارد کنید (مثل ۱۴۰۴/۰۲/۱۵).",
      ref: "فاز B — پیوست ۳، بند ۱-۲",
    });
    return {
      mode: "تعدیل پیمان",
      formula: TADIL_FORMULA,
      error: err + " موتور تعدیل پیمان متوقف شد.",
      coef: k,
      k_diff: 0,
      coef_rounding: !!s.coefRounding2080,
      completed_within_term: s.completedWithinTerm === true,
      contract_status: s.contractStatus ?? "فعال",
      deduction_fault: 0,
      io_q: null,
      io_month: null,
      delay_info: EMPTY_DELAY_INFO,
      index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
      split: [],
      base_amount: 0,
      work_base: A,
      chain,
      setup_amount: 0,
      setup_row: null,
      new_work_row: null,
      chapters: [],
      delta_p: 0,
      delta_p_definitive: 0,
      delta_p_provisional: 0,
      result_amount: 0,
      advance_mode: s.tadilAdvanceMode ?? "کل مبلغ کارکرد",
      delay_mode: s.tadilDelayMode ?? "مشمول کل دوره",
      params: {
        allow_negative: !!s.tadilAllowNegative,
        advance_payment: Number(ctx.advance_payment ?? 0),
        proposal_date: prop,
        provisional_coef: null,
      },
      incomplete: true,
      missing: [],
      draft: true,
      pending,
      source: "فاز B — پیوست ۳، بند ۱-۲ (توقف: تاریخ تسلیم الزامی)",
    };
  }

  // ── شاخص موقت ۱۴۰۵Q1: ضریب دستی کاربر معیار است؛ در غیر این صورت
  // از CPI + m محاسبه می‌شود (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱). ──
  const provMan = adjManualGet({ v: s.provisionalCoef1405q1 }, "v");
  const [provAuto, , provTr] = provisionalCoef1405q1("ابنیه");
  const prov = provMan ?? provAuto;
  if (provMan) {
    pending.push(
      adjPending(
        "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵",
        provMan,
        "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ (PDF تصویری — متن استخراج نشد)",
        "—",
        "دستی — نیازمند تأیید",
        "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴)",
      ),
    );
  } else if (prov !== null) {
    pending.push(
      adjPending(
        "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵",
        prov,
        "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱ + مرکز آمار ایران",
        "فرمول: ۱ + m × (CPI[اردیبهشت ۱۴۰۵] ÷ میانگین CPI[دی، بهمن، اسفند ۱۴۰۴] − ۱)",
        `موقت — محاسبه‌شده از CPI (m=${faDigits(provTr.m as number)}` + ")",
        "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴). " +
          `m=${faDigits(provTr.m as number)}، میانگین زمستان ۱۴۰۴=${faDigits(
            Number((provTr.denominator_mean as number).toFixed(4)),
          )}، اردیبهشت ۱۴۰۵=${faDigits(provTr.numerator as number)}.`,
      ),
    );
  }

  // ── تقسیم کارکرد بین سه‌ماهه‌ها ──
  const delayMode = s.tadilDelayMode ?? "مشمول کل دوره";
  const delayDate = s.tadilDelayDate ?? "";
  const wstart = s.workPeriodStart ?? "";
  const wend = s.workPeriodEnd ?? "";
  let split = workSplit(
    wstart,
    wend,
    delayMode === "مستثنی کردن دورهٔ تأخیر" ? delayDate : null,
  );
  if (split.length === 0) {
    split = [[PERIOD_QUARTERS[s.tadilItPeriod ?? "q4"] ?? "1404Q4", 1]];
  }
  // ── فاز E-6 Part C گام ۳: طبقه‌بندی تأخیرها (بندهای ۲-۵-۱..۲-۵-۳) ──
  // مدت پیمان = مدت اولیه + تمدیدها. کارکردِ پس از مدت بر اساس نوع تأخیر
  // شاخص‌گذاری می‌شود (۲-۵-۱ مجاز / ۲-۵-۲ غیرمجاز / ۲-۵-۳ تعیین‌نشده).
  // بدونِ مدتِ پیمان هیچ بازنویسی‌ای صورت نمی‌گیرد (اعداد مرجع تغییر
  // نمی‌کنند).
  const delay = delayClassification(
    s.contractDate ?? "",
    s.contractDurationMonths,
    s.contractExtensions,
    split,
    warns,
  );

  // ── فاز E-6 Part C گام ۹ (حرف a): بند ۲-۶ — مابه‌التفاوتِ آخرین
  // صورت‌وضعیتِ موقت و قطعی. کارکردِ پس از آخرین موقتِ درونِ مدت با
  // میانگینِ شاخص‌های سه‌ماهه‌هایِ بینِ شروعِ پیمان و آخرین موقت
  // شاخص‌گذاری می‌شود (متنِ اصلیِ بند). تبصرهٔ ۲: تأخیر غیرمجاز → ۲-۵-۲
  // که اولویت بالاتر دارد (delayClassification). تبصرهٔ ۱: با فلگِ
  // provisionalDiffMethod = "own_period" هر سه‌ماهه شاخصِ خودش را
  // می‌گیرد. بدونِ lastProvisionalDate هیچ کاری نمی‌کند (اعداد مرجع
  // تغییر نمی‌کنند).
  const span26: string[] = [];
  const ov26 = new Set<string>();
  const lpd26 = (s.lastProvisionalDate ?? "").trim();
  if (lpd26 && (s.provisionalDiffMethod ?? "average") === "average") {
    const pLpd = parseJalali(lpd26);
    const pC0 = parseJalali(s.contractDate ?? "");
    if (!pC0) {
      warns.push({
        level: "هشدار",
        category: "موتور تعدیل",
        item: "last_provisional_date",
        message:
          "تاریخ آخرین صورت‌وضعیت موقت وارد شده ولی تاریخ شروع پیمان مشخص نیست؛ میانگینِ بند ۲-۶ قابل محاسبه نیست.",
        action: "تاریخ شروع پیمان را در بخش «ورودی‌های قرارداد» وارد کنید.",
        ref: "بخشنامهٔ ۲۰۸۰، بند ۲-۶",
      });
    } else if (!pLpd) {
      warns.push({
        level: "هشدار",
        category: "موتور تعدیل",
        item: "last_provisional_date",
        message:
          "تاریخ آخرین صورت‌وضعیت موقت نامعتبر است — میانگینِ بند ۲-۶ نادیده گرفته شد.",
        action: "تاریخ را به‌صورتِ شمسیِ معتبر (مثل ۱۴۰۴/۰۶/۳۱) وارد کنید.",
        ref: "بخشنامهٔ ۲۰۸۰، بند ۲-۶",
      });
    } else {
      const lpdDay = absDay(...pLpd);
      const c0Day = absDay(...pC0);
      if (lpdDay < c0Day) {
        warns.push({
          level: "هشدار",
          category: "موتور تعدیل",
          item: "last_provisional_date",
          message:
            "تاریخ آخرین صورت‌وضعیت موقت قبل از شروع پیمان است — میانگینِ بند ۲-۶ نادیده گرفته شد.",
          action: "تاریخ آخرین موقت را اصلاح کنید.",
          ref: "بخشنامهٔ ۲۰۸۰، بند ۲-۶",
        });
      } else {
        for (const [q26] of workSplit(s.contractDate ?? "", lpd26)) {
          span26.push(q26);
        }
        let tEndDay: number | null = null;
        if (delay.term_end) {
          const pTe = parseJalali(delay.term_end);
          if (pTe) tEndDay = absDay(...pTe);
        }
        for (const [q] of split) {
          const y = Number(q.slice(0, 4));
          const qi = Number(q.slice(-1));
          const qsDay = absDay(y, (qi - 1) * 3 + 1, 1);
          if (qsDay <= lpdDay) continue; // متعلق به دورهٔ موقت
          if (tEndDay !== null && qsDay >= tEndDay) continue; // پس از مدتِ پیمان (۲-۵-۳)
          if (delay.override[q]) continue; // تأخیرِ مشخص‌شده (۲-۵-۲/۲-۵-۳)
          ov26.add(q);
        }
      }
    }
  }

  const man = s.chapterIndexManual ?? {};
  const dman = s.disciplineIndexManual ?? {};
  const dIoM = adjManualGet(dman, "io");
  const dItM = adjManualGet(dman, "it");
  // ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستیِ رشته ─ـ
  const dSrc = manualSrc(dman);
  if ((dIoM !== null || dItM !== null) && !dSrc) {
    warnManualSrcRequired(warns, disc, "discipline");
  }
  const dSrcLabel = dSrc ? ` (${dSrc})` : "";
  // شاخص رشته برای Io (تجهیز و فصل‌های بدون شاخص)
  let dIo: number | null;
  let dIoPage: string | number | null;
  if (dIoM !== null) {
    dIo = dIoM;
    dIoPage = `دستی${dSrcLabel}`;
  } else if (ioMonth) {
    const [v, pg] = monthlyDiscipline(ioMonth, disc);
    dIo = v;
    dIoPage = pg;
  } else {
    const [v, pg] = indexValue(QUARTER_PERIOD[ioQ ?? ""] ?? "base", disc);
    dIo = v;
    dIoPage = pg;
  }

  // ── شاخص موقت ۱۴۰۵Q1: ضریب از CPI + m محاسبه می‌شود (بخشنامهٔ
  // ۱۴۴۳۷۳ پیوست ص۱)؛ اگر شاخص ماهانهٔ موردنیاز موجود نباشد، موتور با
  // خطا متوقف می‌شود (قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود).
  // استثنا: اگر شاخص دستی It برای همهٔ فصل‌ها (و تجهیز) وارد شده
  // باشد، ضریب موقت لازم نیست.
  const active = Object.entries(chap).filter(([, v]) => Math.abs(v) >= 0.01).map(([c]) => c);
  const allManualIt =
    active.length > 0 &&
    active.every((c) => {
      const m = man[c];
      return !!m && adjManualGet(m, "it") !== null;
    });
  const setupManualOk = setup <= 0 || dItM !== null;
  if (split.some(([q]) => quarterIsProvisional(q)) && !prov && !(allManualIt && setupManualOk)) {
    warns.push({
      level: "خطا",
      category: "موتور تعدیل",
      item: "provisional_coef_1405q1",
      message:
        "دورهٔ کارکرد به سه‌ماههٔ اول ۱۴۰۵ می‌رسد ولی ضریب موقت قابل محاسبه نیست — شاخص ماهانهٔ CPI در config/cpi_monthly.json ناقص است یا m رشته تعریف نشده؛ موتور تعدیل پیمان متوقف شد.",
      action:
        "شاخص‌های ماهانهٔ CPI را در config/cpi_monthly.json تکمیل کنید (یا ضریب دستی را در سایدبار وارد کنید یا شاخص دستی It همهٔ فصل‌ها را پر کنید).",
      ref: "فاز E — بخشنامهٔ ۱۴۴۳۷۳ پیوست ص۱ (CPI)",
    });
    return {
      mode: "تعدیل پیمان",
      formula: TADIL_FORMULA,
      error: "ضریب موقت ۱۴۰۵Q1 قابل محاسبه نیست (CPI ناقص) — موتور تعدیل پیمان متوقف شد.",
      coef: k,
      k_diff: 0,
      coef_rounding: !!s.coefRounding2080,
      completed_within_term: s.completedWithinTerm === true,
      contract_status: s.contractStatus ?? "فعال",
      deduction_fault: 0,
      io_q: ioQ,
      io_month: ioMonth,
      split,
      delay_info: EMPTY_DELAY_INFO,
      index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
      base_amount: 0,
      work_base: A,
      chain,
      setup_amount: 0,
      setup_row: null,
      new_work_row: null,
      chapters: [],
      delta_p: 0,
      delta_p_definitive: 0,
      delta_p_provisional: 0,
      result_amount: 0,
      advance_mode: s.tadilAdvanceMode ?? "کل مبلغ کارکرد",
      delay_mode: delayMode,
      params: {
        allow_negative: !!s.tadilAllowNegative,
        advance_payment: Number(ctx.advance_payment ?? 0),
        proposal_date: prop,
        provisional_coef: null,
      },
      incomplete: true,
      missing: [],
      draft: true,
      pending,
      source: "فاز E — ۱۴۴۳۷۳ پیوست ص۱ (توقف: CPI موقت ناموجود)",
    };
  }

  // ── حلقهٔ فصل‌ها ──
  const rows: AdjChapterRow[] = [];
  const missing: [string, string, string][] = [];
  let dpTotal = 0;
  let dpDefTotal = 0;
  let dpTotal095 = 0;
  const sortedChap = Object.entries(chap).sort((a, b) => b[1] - a[1]);
  for (const [code, amt] of sortedChap) {
    if (Math.abs(amt) < 0.01) continue;
    const m = man[code] ?? {};
    const mIo = adjManualGet(m, "io");
    const mIt = adjManualGet(m, "it");
    // ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستی اجباری است ─ـ
    const mSrc = manualSrc(m);
    if ((mIo !== null || mIt !== null) && !mSrc) {
      warnManualSrcRequired(warns, code, "chapter");
    }
    const mSrcLabel = mSrc ? ` (${mSrc})` : "";
    let ioV0: number | null;
    let ioPage: string | number | null;
    if (chainMethodResolved === "رشته‌ای") {
      // بند ۲-۱: مسیر رشته‌ای — شاخصِ رشتهٔ پروژه (نه شاخصِ فصل)
      if (ioMonth) {
        const [v, pg] = monthlyDiscipline(ioMonth, disc);
        ioV0 = v;
        ioPage = pg;
      } else {
        const [v, pg] = indexValue(
          QUARTER_PERIOD[ioQ ?? ""] ?? "base",
          disc,
        );
        ioV0 = v;
        ioPage = pg;
      }
    } else {
      [ioV0, ioPage] = ioMonth
        ? monthlyChapterIndex(code, ioMonth)
        : chapterIndexQ(code, ioQ!);
    }
    let ioV: number | null = ioV0;
    const useDisc =
      chainMethodResolved === "رشته‌ای" || (ioV === null && mIo === null);
    // ─ـ فاز E-6 Part C گام ۸ (حرف e): هشدارِ اختلافِ شاخص دستی ──
    if (mIo !== null && ioV !== null) {
      const dev = ioV !== 0 ? Math.abs(mIo - ioV) / ioV : 0;
      if (
        dev > MANUAL_INDEX_DEVIATION_PCT &&
        !warns.some(
          (x) =>
            x.item === "manual_index_deviation_20" &&
            (x as any)._code === code,
        )
      ) {
        warns.push({
          level: "هشدار",
          category: "موتور تعدیل",
          item: "manual_index_deviation_20",
          _code: code,
          message: `شاخص دستیِ Io فصل ${code} (${faFloat(mIo, 2)}) بیش از ${faFloat(MANUAL_INDEX_DEVIATION_PCT * 100, 0)}٪ با شاخصِ config (${faFloat(ioV, 2)}) اختلاف دارد — منبع را تأیید کنید.`,
          action: "منبعِ شاخص دستی را مستند کنید یا شاخص config را به‌روز کنید.",
          ref: "بخشنامهٔ ۲۰۸۰ — گام ۸",
        } as Warning & { _code: string });
      }
    }
    let src: string;
    if (mIo !== null) {
      ioV = mIo;
      src = `دستی${mSrcLabel}`;
    } else if (useDisc) {
      if (dIo === null) {
        missing.push([code, "Io", ioQ!]);
        continue;
      }
      ioV = dIo;
      if (chainMethodResolved === "رشته‌ای") {
        src = "شاخص رشته (مسیر ۲-۱)";
      } else {
        src = "شاخص رشته (بدون شاخص فصل — بند ۴)";
        pending.push(
          adjPending(
            `شاخص فصل ${code} — Io`,
            dIo,
            "پیوست ۳، ردیف ۱ (شاخص رشته)",
            pageLabel(dIoPage),
            "فصل استخراج نشده — جایگزین با شاخص رشته، نیازمند تأیید",
            `شاخص اختصاصی فصل ${code} را از جدول پیوست ۳ وارد کنید.`,
          ),
        );
      }
    } else {
      src = pageLabel(ioPage);
      src = src !== "—" ? `پیوست ۳، ${src}` : "جدول";
    }
    let dpC = 0;
    let dpCDef = 0;
    let dpC095 = 0;
    let itW = 0;
    let stLast = "قطعی";
    const qRows: [string, number, string][] = [];
    const coefRows: [string, number, number][] = [];
    const dn: DelayNote[] = [];
    for (const [q, f] of split) {
      const ov = delay.override[q] ?? null;
      let itV: number | null;
      let itSt: string;
      let baseSt: string;
      let dnRow: DelayNote | null = null;
      if (ov && ov.rule === "غیرمجاز") {
        // ۲-۵-۲: میانگین شاخص‌های سه‌ماهه‌های داخل مدت پیمان
        const vals: number[] = [];
        const sts: string[] = [];
        for (const tq of delay.term_quarters) {
          let tv: number | null;
          let ts: string;
          if (mIt !== null) {
            tv = mIt;
            ts = "دستی";
          } else if (useDisc) {
            const [dv, ds] = quarterDiscipline(tq, prov, disc);
            tv = dv;
            ts = ds;
          } else {
            const [cv, cs] = quarterIndex(code, tq, prov);
            tv = cv;
            ts = cs;
          }
          if (tv === null) continue;
          vals.push(tv);
          sts.push(ts);
        }
        if (vals.length === 0) {
          missing.push([code, "It", `${q} (میانگین مدت)`]);
          continue;
        }
        itV = vals.reduce((a, b) => a + b, 0) / vals.length;
        baseSt = sts.includes("موقت")
          ? "موقت"
          : sts.includes("دستی")
            ? "دستی"
            : "قطعی";
        itSt = `${baseSt} (میانگین مدت — ۲-۵-۲)`;
        dnRow = { q, rule: "غیرمجاز", note: "میانگین شاخص‌های داخل مدت (۲-۵-۲)" };
      } else if (ov26.has(q)) {
        // بند ۲-۶: میانگین شاخص‌های شروع تا آخرین موقت
        const vals: number[] = [];
        const sts: string[] = [];
        for (const tq of span26) {
          let tv: number | null;
          let ts: string;
          if (mIt !== null) {
            tv = mIt;
            ts = "دستی";
          } else if (useDisc) {
            const [dv, ds] = quarterDiscipline(tq, prov, disc);
            tv = dv;
            ts = ds;
          } else {
            const [cv, cs] = quarterIndex(code, tq, prov);
            tv = cv;
            ts = cs;
          }
          if (tv === null) continue;
          vals.push(tv);
          sts.push(ts);
        }
        if (vals.length === 0) {
          missing.push([code, "It", `${q} (میانگین ۲-۶)`]);
          continue;
        }
        itV = vals.reduce((a, b) => a + b, 0) / vals.length;
        baseSt = sts.includes("موقت")
          ? "موقت"
          : sts.includes("دستی")
            ? "دستی"
            : "قطعی";
        itSt = `${baseSt} (میانگینِ تا آخرین موقت — ۲-۶)`;
        dnRow = {
          q,
          rule: "۲-۶",
          note: "میانگین شاخص‌های شروع تا آخرین موقت (۲-۶)",
        };
      } else if (ov) {
        // ۲-۵-۳: علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمه
        if (mIt !== null) {
          itV = mIt;
          itSt = "دستی";
        } else if (useDisc) {
          const [dv, ds] = quarterDiscipline(ov.basis_q!, prov, disc);
          itV = dv;
          itSt = ds;
        } else {
          const [cv, cs] = quarterIndex(code, ov.basis_q!, prov);
          itV = cv;
          itSt = cs;
        }
        if (itV === null) {
          missing.push([code, "It", ov.basis_q!]);
          continue;
        }
        baseSt = itSt;
        itSt = `${itSt} (علی‌الحساب — ۲-۵-۳)`;
        dnRow = { q, rule: "تعیین‌نشده", note: "علی‌الحساب با شاخص دورهٔ خاتمه (۲-۵-۳)" };
      } else {
        // ۲-۵-۱ (مجاز) یا درونِ مدت: شاخص همان سه‌ماهه
        if (mIt !== null) {
          itV = mIt;
          itSt = "دستی";
        } else if (useDisc) {
          const [dv, ds] = quarterDiscipline(q, prov, disc);
          itV = dv;
          itSt = ds;
        } else {
          const [cv, cs] = quarterIndex(code, q, prov);
          itV = cv;
          itSt = cs;
        }
        if (itV === null) {
          missing.push([code, "It", q]);
          continue;
        }
        baseSt = itSt;
      }
      qRows.push([q, itV, itSt]);
      const ratio = itV / ioV!;
      // بند ۸-۲: ضریب با ۳ رقم اعشار حساب، سپس به ۲ رقم گرد می‌شود
      const raw = k * (ratio - 1);
      const used = doRound ? roundCoef2080(raw) : raw;
      dpC += used * amt * f;
      // قطعی: شاخص قطعی باشد و علی‌الحساب (۲-۵-۳) نباشد
      if (baseSt === "قطعی" && !(ov && ov.rule === "تعیین‌نشده")) {
        dpCDef += used * amt * f;
      }
      // مبنای تبصرهٔ ۲: همان محاسبه با k = ۰٫۹۵
      const raw9 = TADIL_K_2080 * (ratio - 1);
      const used9 = doRound ? roundCoef2080(raw9) : raw9;
      dpC095 += used9 * amt * f;
      coefRows.push([q, raw, used]);
      itW += itV * f;
      stLast = itSt;
      if (dnRow) dn.push(dnRow);
    }
    dpTotal += dpC;
    dpDefTotal += dpCDef;
    dpTotal095 += dpC095;
    rows.push({
      chapter: code,
      title: chapterTitle(code),
      amount: amt,
      io: ioV!,
      it: itW,
      ratio: ioV ? itW / ioV : null,
      value: dpC,
      delta: dpC,
      deltaDefinitive: dpCDef,
      status: stLast,
      src,
      quarters: qRows,
      coef_rows: coefRows,
      delay_notes: dn,
      delta_k095: dpC095,
    });
  }

  // ── تجهیز و برچیدن کارگاه (شاخص رشته‌ای — بند ۴) ──
  // منطقِ مشترکِ ردیف‌های شاخصِ رشته (تجهیز + کار جدیدِ گام ۵) در
  // `disciplineAmountRow` است تا هر دو ردیف یکسان طی شوند.
  let setupRow: AdjSetupRow | null = null;
  let dpSetup = 0;
  let dpSetupDef = 0;
  let dpSetup095 = 0;
  if (setup > 0 && dIo !== null) {
    const sr = disciplineAmountRow(
      setup,
      dIo,
      split,
      delay,
      prov,
      disc,
      dItM,
      doRound,
      k,
      missing,
      "تجهیز",
      "رشته‌ای (بند ۴)",
      `پیوست ۳، ردیف ۱${dIoPage ? ` — ${pageLabel(dIoPage)}` : ""}`,
      span26,
      ov26,
    );
    setupRow = sr.row;
    dpSetup = sr.dp;
    dpSetupDef = sr.dpDef;
    dpSetup095 = sr.dp095;
  }

  // ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) ──
  // ۳-۱: قیمت از فهرستِ ضمیمهٔ پیمان ⇒ شاخص مبنا = شاخص مبنای پیمان.
  // ۳-۲/۳-۳: فهرستِ پایه / قیمت روز ⇒ شاخص مبنا = دورهٔ آن قیمت‌ها.
  // ۳-۴: ترکیب — هر بخش طبق روشِ همان بخش (دو مبلغِ جداگانه).
  // ۳-۵: قیمتِ کار جدید بر ۰٫۹۵ تقسیم، سپس × (Io پیمان ÷ Io کار
  // جدید) تا به مبنای پیمان برسد، بعد مثلِ تجهیز با نسبتِ It/Io
  // پیمان تعدیل می‌شود.
  let dpNew = 0;
  let dpNewDef = 0;
  let dpNew095 = 0;
  newWorkRow = null;
  newBaseAmt = 0;
  if ((newAmtA > 0 || newAmtB > 0) && dIo !== null) {
    let ioNew: number | null = dIo;
    let conv = 1;
    if (newAmtB > 0) {
      const bp = (s.newItemBasePeriod ?? "").trim();
      ioNew = bp ? quarterDiscipline(bp, prov, disc)[0] : null;
        if (!warns.some((x) => x.item === "new_item_base_period_missing"))
          warns.push({
            level: "خطا",
            category: "موتور تعدیل",
            item: "new_item_base_period_missing",
            message:
              `روش قیمتِ کار جدید ${newMethod} است ولی دورهٔ شاخص` +
              " مبنا وارد نشده یا شاخصش ناموجود است؛ ردیفِ کار" +
              " جدید محاسبه نشد.",
            action:
              "دورهٔ سه‌ماههٔ مبنای کار جدید را در بخش «ورودی‌های قرارداد» وارد کنید.",
            ref: "بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳",
          });
      if (ioNew !== null) {
        conv = (dIo / ioNew) / 0.95;
        if (!warns.some((x) => x.item === "new_item_095_conversion"))
          warns.push({
            level: "اطلاع",
            category: "موتور تعدیل",
            item: "new_item_095_conversion",
            message:
              "کار جدید: قیمت بر ۰٫۹۵ تقسیم و در ضریب " +
              `${conv.toFixed(6)} (Io پیمان ÷ Io کار جدید) ضرب شد` +
              " (بند ۳-۵).",
            action: "در صورت نیاز، روش یا دورهٔ مبنا را اصلاح کنید.",
            ref: "بخشنامهٔ ۲۰۸۰، بند ۳-۵",
          });
      }
    }
    newBaseAmt = newAmtA + newAmtB * conv;
    if (newBaseAmt > 0 && (newAmtB === 0 || ioNew !== null)) {
      const nr = disciplineAmountRow(
        newBaseAmt,
        dIo,
        split,
        delay,
        prov,
        disc,
        dItM,
        doRound,
        k,
        missing,
        "کار جدید",
        `کار جدید (${newMethod})`,
        "بخشنامهٔ ۲۰۸۰، بندهای ۳-۱..۳-۵",
        span26,
        ov26,
      );
      newWorkRow = nr.row;
      dpNew = nr.dp;
      dpNewDef = nr.dpDef;
      dpNew095 = nr.dp095;
      newWorkRow.method = newMethod;
      newWorkRow.amount_own = newAmtA;
      newWorkRow.amount_new = newAmtB;
      newWorkRow.io_new = ioNew;
      newWorkRow.conv = conv;
    }
  }

  const incomplete = missing.length > 0;
  if (incomplete) {
    warns.push({
      level: "خطا",
      category: "موتور تعدیل",
      item: "تعدیل پیمان",
      message:
        "شاخص برخی فصل‌ها ناموجود است: " +
        missing.map(([c, w, q]) => `${c} (${w} ${q})`).join("، "),
      action: "شاخص دستی آن فصل را در chapterIndexManual وارد کنید یا شاخص رشته را ثبت کنید.",
      ref: "فاز B — پیوست ۳",
    });
  }

  // ── جمع و شرط‌ها ──
  let deltaP = dpTotal + dpSetup + dpNew;
  let deltaPDef = dpDefTotal + dpSetupDef + dpNewDef;
  // ── تبصرهٔ ۲ بند ۱-۸ + بند ۸-۴: مابه‌التفاوت k = ۰٫۹۵ → k = ۱ ──
  const kDiff = deltaP - (dpTotal095 + dpSetup095 + dpNew095);
  if (cwt && Math.abs(kDiff) >= 0.005) deltaPDef += kDiff;
  const allowNeg = !!s.tadilAllowNegative;
  if (deltaP < 0 && !allowNeg) {
    warns.push({
      level: "هشدار",
      category: "موتور تعدیل",
      item: "تعدیل پیمان",
      message: "تعدیل منفی محاسبه شد ولی مجاز نیست؛ صفر اعمال شد.",
      action: "در صورت مجاز بودن، tadilAllowNegative را فعال کنید.",
      ref: "فاز B — قاعدهٔ کاربر",
    });
    deltaP = 0;
  }

  const newBaseAmtT = newWorkRow ? newWorkRow.amount : 0;
  const aTotal = A + setup + newBaseAmtT;
  // ── فاز E-6 Part C گام ۴: وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷) ──
  // بند ۶: خاتمه بدون قصور ⇒ طبق همین دستورالعمل، بدون تغییر.
  // بند ۷: فسخ به علت قصور پیمانکار ⇒ ۵٪ از مبلغ تعدیل کسر می‌شود.
  // کسر فقط روی «مبلغ نهایی» اعمال می‌شود؛ خودِ ΔP و تفکیک قطعی/
  // علی‌الحساب دست‌نخورده می‌مانند (قطعی + علی‌الحساب ≡ ΔP).
  const cStatus = (s.contractStatus ?? "فعال").trim();
  let deductionFault = 0;
  if (cStatus === "فسخ با قصور") {
    if (deltaP < 0 && !s.faultDeductionOnNegative) {
      warns.push({
        level: "هشدار",
        category: "موتور تعدیل",
        item: "تعدیل پیمان",
        message: "مبلغ تعدیل منفی است؛ کسر ۵٪ (بند ۷) اعمال نشد. در صورت نیاز، گزینهٔ «کسر در تعدیل منفی» را فعال کنید.",
        action: "این تفسیر در ACCEPTANCE.md §۱۸-۳ ثبت شده است.",
        ref: "بخشنامهٔ ۲۰۸۰، بند ۷",
      });
    } else {
      deductionFault = -0.05 * deltaP;
      warns.push({
        level: "هشدار",
        category: "موتور تعدیل",
        item: "تعدیل پیمان",
        message: "وضعیت خاتمهٔ پیمان «فسخ با قصور» است؛ ۵٪ از مبلغ تعدیل کسر می‌شود.",
        action: "اگر این اشتباه است، وضعیت خاتمه را در بخش «ورودی‌های قرارداد» اصلاح کنید.",
        ref: "بخشنامهٔ ۲۰۸۰، بند ۷",
      });
    }
  }
  const resultAmount = aTotal + deltaP + deductionFault;
  const approved = !!s.tadilApproved;
  if (!approved) {
    warns.push({
      level: "اطلاع",
      category: "موتور تعدیل",
      item: "تعدیل پیمان",
      message: "خروجی موتور تعدیل «پیش‌نویس» است تا مقادیر منبع تصویری تأیید شوند.",
      action: "پس از بررسی «مقادیر منتظر تأیید»، دکمهٔ تأیید را بزنید.",
      ref: "فاز B — قاعدهٔ کاربر",
    });
  }
  return {
    mode: "تعدیل پیمان",
    formula: TADIL_FORMULA,
    coef: k,
    k_diff: cwt ? kDiff : 0,
    coef_rounding: doRound,
    completed_within_term: cwt,
    contract_status: cStatus,
    deduction_fault: deductionFault,
    io_q: ioQ,
    io_month: ioMonth,
    split,
    delay_info: delay,
    index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
    base_amount: aTotal,
    work_base: A,
    chain,
    setup_amount: setup,
    setup_row: setupRow,
    new_work_row: newWorkRow,
    chapters: rows,
    delta_p: deltaP,
    delta_p_definitive: deltaPDef,
    delta_p_provisional: deltaP - deltaPDef,
    result_amount: resultAmount,
    advance_mode: s.tadilAdvanceMode ?? "کل مبلغ کارکرد",
    delay_mode: delayMode,
    params: {
      allow_negative: allowNeg,
      advance_payment: Number(ctx.advance_payment ?? 0),
      proposal_date: prop,
      provisional_coef: prov,
    },
    incomplete,
    missing,
    draft: !approved,
    pending,
    source:
      "تعدیل فصل به فصل با شاخص‌های پیوست ۳ بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳ (استخراج‌شده، نیازمند تأیید)؛ ضریب k از بخشنامهٔ ۲۰۸۰ مشتق می‌شود (بند ۱-۸ و تبصرهٔ ۲ — فاز E-۶)",
  };
}

// ── موتور ۲ — برآورد به‌هنگام ──

export function baravordEngine(
  s: ProjectSettings,
  ctx: AdjustmentCtx,
  warns: Warning[],
): BaravordResult {
  const pending: AdjPending[] = [];
  // ── فاز E-6 Part C گام ۶: مسیر شاخص (بندهای ۲-۱/۲-۲) — مثلِ موتور ۱ ──
  const [chainMethodResolved, chainMethodSource] = chainMethod(s, warns);
  const disc = (s.regionalSelection?.discipline ?? "ابنیه").trim() || "ابنیه";
  // ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) ──
  let newWorkRow: AdjSetupRow | null = null;
  let newBaseAmt = 0;
  const newMethod0 = (s.newItemMethod ?? "فهرست پیمان").trim()
    || "فهرست پیمان";
  const newMethod = ["فهرست پیمان", "فهرست پایه", "قیمت روز",
    "ترکیب"].includes(newMethod0)
    ? newMethod0
    : "فهرست پیمان";
  const newAmt = Number(s.newItemAmount ?? 0);
  const newAmtAtt = Number(s.newItemAmountAttached ?? 0);
  let newAmtA: number;
  let newAmtB: number;
  if (newMethod === "فهرست پیمان") {
    newAmtA = newAmt;
    newAmtB = 0;
  } else if (newMethod === "ترکیب") {
    newAmtA = newAmtAtt;
    newAmtB = newAmt;
  } else {
    newAmtA = 0;
    newAmtB = newAmt;
  }
  const { A, chain, applied } = adjBaseChain(s, ctx, false, pending);
  const setup = Number(ctx.site_setup ?? 0);
  // مبالغ فصل‌ها در همان ضریبِ A ضرب می‌شوند تا Σ A_c = A برقرار شود.
  const chap: Record<string, number> = {};
  for (const [c, v] of Object.entries(ctx.chapter_amounts ?? {})) {
    chap[String(c)] = Number(v) * applied;
  }
  const ioQ = PERIOD_QUARTERS[s.baravordIoPeriod ?? "base"] ?? null;
  // ── بخشنامهٔ ۱۴۴۳۷۴: مهلت تسلیم در تابستان ۱۴۰۵ ⇒ Io ماهانه ──
  const ioDateB = (s.proposalDeadline ?? "").trim() || (s.proposalDate ?? "").trim();
  const ioMonth = ioDateB ? ioMonthFor(ioDateB) : null;
  if (ioMonth && !monthlyHasData(ioMonth)) {
    warns.push({
      level: "خطا",
      category: "موتور برآورد",
      item: "monthly_index_1405",
      message:
        "مهلت تسلیم پیشنهاد در تابستان ۱۴۰۵ است؛ طبق بخشنامهٔ ۱۴۴۳۷۴ Io باید شاخص ماهانهٔ خرداد ۱۴۰۵ (آحادبها) باشد، ولی این شاخص هنوز در config/index_bulletins.json وارد نشده است. موتور برآورد به‌هنگام متوقف شد.",
      action:
        "شاخص‌های ماهانهٔ خرداد ۱۴۰۵ را در بخش monthly فایل config/index_bulletins.json وارد کنید (هرگز حدس زده نمی‌شود).",
      ref: "فاز E — بخشنامهٔ ۱۴۴۳۷۴",
    });
    return {
      mode: "برآورد به‌هنگام",
      formula: BARAVORD_FORMULA,
      error: "شاخص ماهانهٔ خرداد ۱۴۰۵ وارد نشده — موتور برآورد به‌هنگام متوقف شد.",
      io_q: ioQ,
      io_month: ioMonth,
      it_q: null,
      index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
      base_amount: A + setup,
      work_base: A,
      chain,
      setup_amount: setup,
      setup_row: null,
      new_work_row: null,
      chapters: [],
      result_amount: 0,
      grand_updated: 0,
      grand_current: Number(ctx.grand_total ?? 0),
      applied_mult: applied,
      incomplete: true,
      missing: [],
      draft: true,
      pending,
      source: "فاز E — ۱۴۴۳۷۴ (توقف: شاخص ماهانهٔ خرداد ۱۴۰۵)",
    };
  }
  const itRaw = s.baravordItPeriod ?? "q4";
  // گزینهٔ «۱۴۰۵Q1 (موقت)» فقط برای It در سایدبار قابل انتخاب است.
  const itQ: string | null = quarterIsProvisional(itRaw)
    ? itRaw
    : PERIOD_QUARTERS[itRaw] ?? null;
  // ── شاخص موقت ۱۴۰۵Q1: ضریب دستی کاربر معیار است؛ در غیر این صورت
  // از CPI + m محاسبه می‌شود (بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱). ──
  const provMan = adjManualGet({ v: s.provisionalCoef1405q1 }, "v");
  const [provAuto, , provTr] = provisionalCoef1405q1("ابنیه");
  const prov = provMan ?? provAuto;
  if (provMan) {
    pending.push(
      adjPending(
        "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵",
        provMan,
        "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ (PDF تصویری — متن استخراج نشد)",
        "—",
        "دستی — نیازمند تأیید",
        "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴)",
      ),
    );
  } else if (prov !== null) {
    pending.push(
      adjPending(
        "ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵",
        prov,
        "بخشنامهٔ ۱۴۰۵/۱۴۴۳۷۳ پیوست ص۱ + مرکز آمار ایران",
        "فرمول: ۱ + m × (CPI[اردیبهشت ۱۴۰۵] ÷ میانگین CPI[دی، بهمن، اسفند ۱۴۰۴] − ۱)",
        `موقت — محاسبه‌شده از CPI (m=${faDigits(provTr.m as number)}` + ")",
        "موقت = این ضریب × آخرین شاخص قطعی (سه‌ماههٔ چهارم ۱۴۰۴). " +
          `m=${faDigits(provTr.m as number)}، میانگین زمستان ۱۴۰۴=${faDigits(
            Number((provTr.denominator_mean as number).toFixed(4)),
          )}، اردیبهشت ۱۴۰۵=${faDigits(provTr.numerator as number)}.`,
      ),
    );
  }
  const man = s.chapterIndexManual ?? {};
  const dman = s.disciplineIndexManual ?? {};
  const dIoM = adjManualGet(dman, "io");
  const dItM = adjManualGet(dman, "it");
  // ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستیِ رشته ─ـ
  const dSrc = manualSrc(dman);
  if ((dIoM !== null || dItM !== null) && !dSrc) {
    warnManualSrcRequired(warns, disc, "discipline");
  }
  const dSrcLabel = dSrc ? ` (${dSrc})` : "";
  let dIo: number | null;
  let dIoPage: string | number | null;
  if (dIoM !== null) {
    dIo = dIoM;
    dIoPage = `دستی${dSrcLabel}`;
  } else if (ioMonth) {
    const [v, pg] = monthlyDiscipline(ioMonth, disc);
    dIo = v;
    dIoPage = pg;
  } else {
    const [v, pg] = indexValue(QUARTER_PERIOD[ioQ ?? ""] ?? "base", disc);
    dIo = v;
    dIoPage = pg;
  }

  // ── شاخص موقت ۱۴۰۵Q1 برای It: ضریب از CPI + m محاسبه می‌شود؛ اگر
  // شاخص ماهانهٔ موردنیاز موجود نباشد، موتور متوقف می‌شود. ──
  const active = Object.entries(chap).filter(([, v]) => Math.abs(v) >= 0.01).map(([c]) => c);
  const allManualIt =
    active.length > 0 &&
    active.every((c) => {
      const m = man[c];
      return !!m && adjManualGet(m, "it") !== null;
    });
  const setupManualOk = setup <= 0 || dItM !== null;
  if (quarterIsProvisional(itQ) && !prov && !(allManualIt && setupManualOk)) {
    warns.push({
      level: "خطا",
      category: "موتور برآورد",
      item: "provisional_coef_1405q1",
      message:
        "دورهٔ هدف (It) سه‌ماههٔ اول ۱۴۰۵ (موقت) است ولی ضریب موقت قابل محاسبه نیست — شاخص ماهانهٔ CPI در config/cpi_monthly.json ناقص است یا m رشته تعریف نشده؛ موتور برآورد به‌هنگام متوقف شد.",
      action:
        "شاخص‌های ماهانهٔ CPI را در config/cpi_monthly.json تکمیل کنید (یا ضریب دستی را در سایدبار وارد کنید یا شاخص دستی It همهٔ فصل‌ها را پر کنید).",
      ref: "فاز E — بخشنامهٔ ۱۴۴۳۷۳ پیوست ص۱ (CPI)",
    });
    return {
      mode: "برآورد به‌هنگام",
      formula: BARAVORD_FORMULA,
      error: "ضریب موقت ۱۴۰۵Q1 قابل محاسبه نیست (CPI ناقص) — موتور برآورد به‌هنگام متوقف شد.",
      io_q: ioQ,
      io_month: ioMonth,
      it_q: itQ,
      index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
      base_amount: A + setup,
      work_base: A,
      chain,
      setup_amount: setup,
      setup_row: null,
      new_work_row: null,
      chapters: [],
      result_amount: 0,
      grand_updated: 0,
      grand_current: Number(ctx.grand_total ?? 0),
      applied_mult: applied,
      incomplete: true,
      missing: [],
      draft: true,
      pending,
      source: "فاز E — ۱۴۴۳۷۳ پیوست ص۱ (توقف: CPI موقت ناموجود)",
    };
  }

  const rows: AdjChapterRow[] = [];
  const missing: [string, string, string][] = [];
  let aNew = 0;
  let aNewChap = 0;
  const sortedChap = Object.entries(chap).sort((a, b) => b[1] - a[1]);
  for (const [code, amt] of sortedChap) {
    if (Math.abs(amt) < 0.01) continue;
    const m = man[code] ?? {};
    const mIo = adjManualGet(m, "io");
    const mIt = adjManualGet(m, "it");
    // ─ـ فاز E-6 Part C گام ۸ (حرف e): منبعِ شاخص دستی اجباری است ─ـ
    const mSrc = manualSrc(m);
    if ((mIo !== null || mIt !== null) && !mSrc) {
      warnManualSrcRequired(warns, code, "chapter");
    }
    const mSrcLabel = mSrc ? ` (${mSrc})` : "";
    let ioV0: number | null;
    let ioPage: string | number | null;
    if (chainMethodResolved === "رشته‌ای") {
      // بند ۲-۱: مسیر رشته‌ای — شاخصِ رشتهٔ پروژه (نه شاخصِ فصل)
      if (ioMonth) {
        const [v, pg] = monthlyDiscipline(ioMonth, disc);
        ioV0 = v;
        ioPage = pg;
      } else {
        const [v, pg] = indexValue(
          QUARTER_PERIOD[ioQ ?? ""] ?? "base",
          disc,
        );
        ioV0 = v;
        ioPage = pg;
      }
    } else {
      [ioV0, ioPage] = ioMonth
        ? monthlyChapterIndex(code, ioMonth)
        : chapterIndexQ(code, ioQ!);
    }
    let ioV: number | null = ioV0;
    const useDisc =
      chainMethodResolved === "رشته‌ای" || (ioV === null && mIo === null);
    // ─ـ فاز E-6 Part C گام ۸ (حرف e): هشدارِ اختلافِ شاخص دستی ──
    if (mIo !== null && ioV !== null) {
      const dev = ioV !== 0 ? Math.abs(mIo - ioV) / ioV : 0;
      if (
        dev > MANUAL_INDEX_DEVIATION_PCT &&
        !warns.some(
          (x) =>
            x.item === "manual_index_deviation_20" &&
            (x as any)._code === code,
        )
      ) {
        warns.push({
          level: "هشدار",
          category: "موتور تعدیل",
          item: "manual_index_deviation_20",
          _code: code,
          message: `شاخص دستیِ Io فصل ${code} (${faFloat(mIo, 2)}) بیش از ${faFloat(MANUAL_INDEX_DEVIATION_PCT * 100, 0)}٪ با شاخصِ config (${faFloat(ioV, 2)}) اختلاف دارد — منبع را تأیید کنید.`,
          action: "منبعِ شاخص دستی را مستند کنید یا شاخص config را به‌روز کنید.",
          ref: "بخشنامهٔ ۲۰۸۰ — گام ۸",
        } as Warning & { _code: string });
      }
    }
    let src: string;
    if (mIo !== null) {
      ioV = mIo;
      src = `دستی${mSrcLabel}`;
    } else if (useDisc) {
      if (dIo === null) {
        missing.push([code, "Io", ioQ!]);
        continue;
      }
      ioV = dIo;
      if (chainMethodResolved === "رشته‌ای") {
        src = "شاخص رشته (مسیر ۲-۱)";
      } else {
        src = "شاخص رشته (بدون شاخص فصل — بند ۴)";
        pending.push(
          adjPending(
            `شاخص فصل ${code} — Io`,
            dIo,
            "پیوست ۳، ردیف ۱ (شاخص رشته)",
            pageLabel(dIoPage),
            "فصل استخراج نشده — جایگزین با شاخص رشته، نیازمند تأیید",
            `شاخص اختصاصی فصل ${code} را از جدول پیوست ۳ وارد کنید.`,
          ),
        );
      }
    } else {
      src = pageLabel(ioPage);
      src = src !== "—" ? `پیوست ۳، ${src}` : "جدول";
    }
    let itV: number | null;
    let itSt: string;
    if (mIt !== null) {
      itV = mIt;
      itSt = "دستی";
    } else if (useDisc) {
      const [dv, ds] = quarterDiscipline(itQ!, prov, disc);
      itV = dv;
      itSt = ds;
    } else {
      const [cv, cs] = quarterIndex(code, itQ!, prov);
      itV = cv;
      itSt = cs;
    }
    if (itV === null) {
      missing.push([code, "It", itQ!]);
      continue;
    }
    const ratio = itV / ioV!;
    const newC = amt * ratio;
    aNew += newC;
    aNewChap += newC;
    rows.push({
      chapter: code,
      title: chapterTitle(code),
      amount: amt,
      io: ioV!,
      it: itV,
      ratio,
      value: newC,
      status: itSt,
      src,
    });
  }

  let setupRow: AdjSetupRow | null = null;
  if (setup > 0 && dIo !== null) {
    let dItV: number | null;
    let dSt: string;
    if (dItM !== null) {
      dItV = dItM;
      dSt = "دستی";
    } else {
      const [dv, ds] = quarterDiscipline(itQ!, prov, disc);
      dItV = dv;
      dSt = ds;
    }
    if (dItV === null) {
      missing.push(["تجهیز", "It", itQ!]);
    } else {
      const dRatio = dItV / dIo;
      setupRow = {
        amount: setup,
        io: dIo,
        it: dItV,
        ratio: dRatio,
        value: setup * dRatio,
        delta: 0,
        deltaDefinitive: 0,
        status: dSt,
        src: "پیوست ۳، ردیف ۱",
      };
      aNew += setupRow.value;
    }
  }

  // ── فاز E-6 Part C گام ۵: کارهای جدید (بندهای ۳-۱..۳-۵) —
  // مثلِ موتور ۱: تبدیلِ ۳-۵ روی مبلغ، سپس نسبتِ تک‌دورهٔ It/Io
  // پیمان (برآورد به‌هنگام تأخیر/۲-۶ ندارد). ──
  newWorkRow = null;
  newBaseAmt = 0;
  if ((newAmtA > 0 || newAmtB > 0) && dIo !== null) {
    let ioNewB: number | null = dIo;
    let convB = 1;
    if (newAmtB > 0) {
      const bp = (s.newItemBasePeriod ?? "").trim();
      ioNewB = bp ? quarterDiscipline(bp, prov, disc)[0] : null;
        if (!warns.some((x) => x.item === "new_item_base_period_missing"))
          warns.push({
            level: "خطا",
            category: "موتور برآورد",
            item: "new_item_base_period_missing",
            message:
              `روش قیمتِ کار جدید ${newMethod} است ولی دورهٔ شاخص` +
              " مبنا وارد نشده یا شاخصش ناموجود است؛ ردیفِ کار" +
              " جدید محاسبه نشد.",
            action:
              "دورهٔ سه‌ماههٔ مبنای کار جدید را در بخش «ورودی‌های قرارداد» وارد کنید.",
            ref: "بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳",
          });
      if (ioNewB !== null) {
        convB = (dIo / ioNewB) / 0.95;
      }
    }
    newBaseAmt = newAmtA + newAmtB * convB;
    if (newBaseAmt > 0 && (newAmtB === 0 || ioNewB !== null)) {
      let dItV: number | null;
      if (dItM !== null) {
        dItV = dItM;
      } else {
        const [dv] = quarterDiscipline(itQ!, prov, disc);
        dItV = dv;
      }
      if (dItV === null) {
        missing.push(["کار جدید", "It", itQ!]);
      } else {
        const nRatio = dItV / dIo;
        newWorkRow = {
          amount: newBaseAmt,
          io: dIo,
          it: dItV,
          ratio: nRatio,
          value: newBaseAmt * nRatio,
          delta: 0,
          deltaDefinitive: 0,
          status: `کار جدید (${newMethod})`,
          src: "بخشنامهٔ ۲۰۸۰، بندهای ۳-۱..۳-۵",
          method: newMethod,
          amount_own: newAmtA,
          amount_new: newAmtB,
          io_new: ioNewB,
          conv: convB,
        };
        aNew += newWorkRow.value;
      }
    }
  }

  // ── جمع کل به‌هنگام‌شده (قیمت پیمان) ──
  // اگر A_basis = «بدون ضرایب» باشد، ضرایبِ قیمت پس از It/Io اعمال می‌شوند.
  const oh = Number(ctx.overhead_coef ?? 1);
  const reg = Number(ctx.regional_coef ?? 1);
  const propC = Number(s.proposalCoef ?? 1);
  const residual = applied ? (oh * reg * propC) / applied : 1;
  const setupVal = setupRow ? setupRow.value : 0;
  const newVal = newWorkRow ? newWorkRow.value : 0;
  const grandUpdated = aNewChap * residual + setupVal + newVal;

  const incomplete = missing.length > 0;
  if (incomplete) {
    warns.push({
      level: "خطا",
      category: "موتور برآورد",
      item: "برآورد به‌هنگام",
      message:
        "شاخص برخی فصل‌ها ناموجود است: " +
        missing.map(([c, w, q]) => `${c} (${w} ${q})`).join("، "),
      action: "شاخص دستی آن فصل را در chapterIndexManual وارد کنید.",
      ref: "فاز B — پیوست ۳",
    });
  }
  const approved = !!s.baravordApproved;
  if (!approved) {
    warns.push({
      level: "اطلاع",
      category: "موتور برآورد",
      item: "برآورد به‌هنگام",
      message: "خروجی برآورد به‌هنگام «پیش‌نویس» است تا مقادیر استخراج‌شده تأیید شوند.",
      action: "پس از بررسی «مقادیر منتظر تأیید»، دکمهٔ تأیید را بزنید.",
      ref: "فاز B — قاعدهٔ کاربر",
    });
  }
  return {
    mode: "برآورد به‌هنگام",
    formula: BARAVORD_FORMULA,
    io_q: ioQ,
    io_month: ioMonth,
    it_q: itQ,
    index_method_resolved: { method: chainMethodResolved, source: chainMethodSource },
      base_amount: A + setup + newBaseAmt,
    work_base: A,
    chain,
    setup_amount: setup,
    setup_row: setupRow,
    new_work_row: newWorkRow,
    chapters: rows,
    result_amount: aNew,
    grand_updated: grandUpdated,
    grand_current: Number(ctx.grand_total ?? 0),
    applied_mult: applied,
    incomplete,
    missing,
    draft: !approved,
    pending,
    source:
      "به‌هنگام‌سازی فصل به فصل برآورد با شاخص‌های پیوست ۳ بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳ (استخراج‌شده، نیازمند تأیید)",
  };
}

/** اجرای موتورهای فاز B (هر دو می‌توانند همزمان فعال باشند).
 * هرگز روی زنجیرهٔ مالی اصلی اثر ندارد. */
export function runAdjustment(
  s: ProjectSettings,
  ctx: AdjustmentCtx,
  warns: Warning[],
): AdjustmentResult {
  const out: AdjustmentResult = { tadil: null, baravord: null };
  if (s.tadilEnabled) out.tadil = tadilEngine(s, ctx, warns);
  if (s.baravordEnabled) out.baravord = baravordEngine(s, ctx, warns);

  // ── فاز E — بند ۴: شاخص قطعی ۱۴۰۵ هنوز اعلام نشده ──
  const d1405 = CFG["definitive_1405"] ?? {};
  const d1405Has =
    !!((d1405 as any)["chapters_abnieh"] as any[])?.length ||
    !!((d1405 as any)["disciplines"] as any[])?.length;

  const anyProvisional = (e: TadilResult | BaravordResult | null): boolean => {
    if (!e) return false;
    return (e.chapters ?? []).some(
      (ch) =>
        ch.status === "موقت" ||
        (ch.quarters ?? []).some((qr) => qr[2] === "موقت"),
    );
  };

  if (!d1405Has && (anyProvisional(out.tadil) || anyProvisional(out.baravord))) {
    warns.push({
      level: "اطلاع",
      category: "شاخص‌های ۱۴۰۵",
      item: "definitive_1405",
      message:
        "کارکرد در سه‌ماهه‌های ۱۴۰۵ (یا بعدتر) با شاخص موقت محاسبه شده است (بند ۳ بخشنامهٔ ۱۴۴۳۷۳). شاخص‌های قطعی این دوره‌ها هنوز اعلام نشده‌اند؛ مبلغ این بخش علی‌الحساب است.",
      action:
        "پس از اعلام بخشنامهٔ قطعی، شاخص‌ها را در بخش definitive_1405 فایل config/index_bulletins.json وارد کنید.",
      ref: "فاز E — بند ۴ بخشنامهٔ ۱۴۴۳۷۳",
    });
  }

  // ── فاز E — بند ۵: جدول اختیاری دستورالعمل ۱۴۰۳/۷۴۴۳۱۷ ──
  const i744 = (CFG["instructions_744317"] ?? {}) as Record<string, any>;
  if (
    !((i744["chapters_abnieh"] as any[]) ?? []).length &&
    !((i744["disciplines"] as any[]) ?? []).length &&
    (out.tadil || out.baravord)
  ) {
    warns.push({
      level: "اطلاع",
      category: "شاخص‌های ۱۴۰۴",
      item: "instructions_744317",
      message:
        "جدول شاخص‌های دستورالعمل ۱۴۰۳/۷۴۴۳۱۷ (۱۴۰۳/۱۲/۲۹) وارد نشده است؛ شاخص‌های پیوست ۳ بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳ ملاک محاسبه‌ها هستند.",
      action:
        "در صورت در دسترس بودن، جدول را در بخش instructions_744317 فایل config/index_bulletins.json وارد کنید (برای دوره‌های مشترک، ماکزیمم دو شاخص ملاک است).",
      ref: "فاز E — بند ۵، دستورالعمل ۱۴۰۳/۷۴۴۳۱۷",
    });
  }

  return out;
}

/** قالب‌بندی عدد اعشاری با ارقام فارسی (معادل fa_float پایتون). */
function faFloat(value: number, ndigits = 1): string {
  return faDigits(
    Number(value).toLocaleString("en-US", {
      minimumFractionDigits: ndigits,
      maximumFractionDigits: ndigits,
    }),
  );
}




