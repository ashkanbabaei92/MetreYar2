// ─────────────────────────────────────────────────────────────
// ضریب طبقات (ایراد ۳ — پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴)
// و ضریب منطقه‌ای (ایراد ۴ — بخشنامه ۹۴/۶۹۴۱۶)
// معادل `_floors_coef` و `_regional_coef` نسخهٔ پایتونی
// ─────────────────────────────────────────────────────────────
import REGIONAL_TABLE from "../../config/regional_coefficients.json";
import FLOORS_SPEC from "../../config/floors_coefficients.json";
import { faDigits, normalizeText } from "./normalize";
import type {
  FloorRow,
  FloorsCoef,
  ProjectSettings,
  QuantityRecord,
  RegionalCoef,
  Warning,
} from "./types";

/** قالب‌بندی عدد اعشاری با جداکنندهٔ هزارگان و ارقام فارسی */
export function faFloat(value: number, ndigits = 1): string {
  return faDigits(Number(value).toLocaleString("en-US", { minimumFractionDigits: ndigits, maximumFractionDigits: ndigits }));
}

type LevelKind = "above" | "ground" | "below_base" | "none";

/** طبقه‌بندی تراز Revit: زیرهمکف / همکف / بالاتر (شماره).
 *
 * طبق پیوست ۲: همکف = B0 (ضریب ۰)، اولین طبقه بالاتر = F1 (ضریب ۱)،
 * اولین طبقه پایین‌تر از زیرهمکف = B1 (ضریب ۱). */
export function levelKind(name: string): [LevelKind, number] | null {
  const n = normalizeText(name);
  const m = n.match(/story\s*(\d+)/);
  if (m) {
    const i = parseInt(m[1], 10);
    return i > 1 ? ["above", i - 1] : ["ground", 0];
  }
  // تراز بالای فونداسیون (Foundation Top) طبقه نیست — پی است، نه زیرهمکف.
  // طبق تعریف پیوست ۲ فقط «طبقات» در Σ می‌آیند. قابل تغییر با
  // floorsData[name]["isFloor"] (درخواست کاربر — بند ۱).
  if (/foundation|footing/i.test(n)) return ["none", 0];
  if (/base/i.test(n) || n.includes("زیر")) return ["below_base", 1];
  return null;
}

/** رَدپای ساختمان از بتن مگر: حجم ÷ ضخامت (توصیه برای همکف/زیرهمکف). */
export function leanFootprint(records: QuantityRecord[]) {
  let vol = 0;
  let thick: number | null = null;
  let found = false;
  for (const r of records) {
    if (r.kind !== "lean_concrete") continue;
    vol += r.qty ?? 0;
    const fam = normalizeText(r.detail || r.ref || "");
    const mm = fam.match(/(\d{2,3})\s*(mm|م\.?م|مم)/i);
    if (mm) {
      thick = parseInt(mm[1], 10) / 1000;
      found = true;
    }
  }
  if (vol <= 0) return null;
  if (!found || !thick) thick = 0.1; // پیش‌فرض اپ: بتن مگر ۱۰ cm
  return {
    volume: vol,
    thickness: thick,
    area: vol / thick,
    assumedThickness: !found,
    status: "تخمینی (دستی)",
  };
}

/** جدول طبقات: نام | نوع | مساحت مدل | مساحت دستی | مساحت مؤثر | ضریب. */
export function floorsTable(records: QuantityRecord[], settings: ProjectSettings): FloorRow[] {
  // مساحت کف طبقه = قالب زیرین دال/رویه (جلوگیری از دوباره‌شماری:
  // المان‌های تیرچه خودشان در این دسته نیستند)
  const modelAreas: Record<string, number> = {};
  for (const r of records) {
    if (r.kind !== "formwork_super" || r.group !== "سقف") continue;
    const lv = (r.level ?? "").trim();
    if (!lv) continue;
    modelAreas[lv] = (modelAreas[lv] ?? 0) + r.qty;
  }
  const manual = settings.floorsData ?? {};
  const rows: FloorRow[] = [];
  const seen = new Set<string>();
  for (const r of records) {
    const lv = (r.level ?? "").trim();
    if (!lv || seen.has(lv)) continue;
    seen.add(lv);
    const kind = levelKind(lv);
    if (!kind) continue;
    const mv = modelAreas[lv] ?? null;
    // floorsData[lv]: عدد مساحت (قدیمی) یا رکورد {area, isFloor} — انتخاب
    // دستیِ طبقه بودن تراز (درخواست کاربر — بند ۱).
    const manualEntry = manual[lv];
    const entry = manualEntry && typeof manualEntry === "object" ? manualEntry : null;
    const uvRaw = entry ? entry.area : manualEntry;
    const floorFlag = entry ? entry.isFloor ?? null : null;
    const uv = uvRaw !== undefined && uvRaw !== null ? Number(uvRaw) : null;
    let kind0: FloorRow["kind"] = kind[0];
    let idx = kind[1];
    if (floorFlag === true && kind0 === "none") {
      kind0 = "below_base"; // کاربر این تراز را طبقه می‌داند (زیرهمکف)
      idx = 1;
    } else if (floorFlag === false && kind0 !== "none") {
      kind0 = "none"; // کاربر این تراز را غیرطبقه‌ای کرد
      idx = 0;
    }
    rows.push({
      name: lv,
      kind: kind0,
      autoKind: kind[0],
      index: idx,
      areaModel: mv,
      areaManual: uv,
      area: uv !== null ? uv : mv,
    });
  }
  // ترازهای بام/مرجع (تنظیم floors_roof_levels) از فرمول مستثنی می‌شوند
  const roof = new Set(settings.floorsRoofLevels ?? []);
  for (const r of rows) {
    if (roof.has(r.name)) {
      r.kind = "roof";
      r.index = 0;
    }
  }
  // شماره‌گذاری طبقات: بالاتر از همکف ۱..n، زیرهمکف ۱..m (بام مستثنی)
  const below = rows
    .filter((r) => r.kind === "below_base")
    .sort((a, b) => a.name.localeCompare(b.name));
  below.forEach((r, i) => (r.index = i + 1));
  const above = rows
    .filter((r) => r.kind === "above")
    .sort((a, b) => a.name.localeCompare(b.name));
  above.forEach((r, i) => (r.index = i + 1));
  rows.sort((a, b) => {
    // ترتیب رسمی: زیرهمکف، همکف، بالاتر، بام (همانند خروجی Python)
    const key = (k: FloorRow["kind"]) => [
      k === "roof" ? 1 : 0,
      k === "above" ? 1 : 0,
      k === "ground" ? 1 : 0,
    ];
    const ka = key(a.kind), kb = key(b.kind);
    for (let i = 0; i < 3; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
    return a.index - b.index;
  });
  return rows;
}

const FLOORS_FALLBACK = {
  meta: { status: "پیش‌فرض اپ" },
  formula: "P = ( sum(i*Fi) + sum(j*Bj) ) / S",
  apply_to: "تمام اقلام کار ساختمان",
};

/**
 * ضریب طبقات بر اساس فرمول رسمی پیوست ۲.
 *
 * P = 1 + [ Σ(i×Fi) + Σ(j×Bj) ] ÷ S    (مخرج از تنظیم floors_divisor)
 * همکف (B0) در صورت S می‌آید ولی در صورت سهمی ندارد (ضریب ۰).
 */
export function computeFloorsCoef(
  records: QuantityRecord[],
  settings: ProjectSettings,
  warns: Warning[],
): FloorsCoef {
  const rows = floorsTable(records, settings);
  const manual = settings.floorsCoef;
  if (settings.floorsAuto === false && manual !== undefined && manual !== null) {
    return blankFloors(rows, { value: Number(manual), status: "دستی", source: "ورود کاربر" });
  }
  const divisorMode = settings.floorsDivisor ?? "100×S";
  const missing = rows
    .filter((r) => (r.kind === "above" || r.kind === "below_base") && (r.area === null || r.area === undefined))
    .map((r) => r.name);
  if (missing.length && rows.length) {
    warns.push({
      level: "خطا",
      category: "ضریب طبقات",
      item: missing.join("، "),
      message:
        `مساحت این طبقات در مدل Revit موجود نیست (${missing.length} طبقه: ${missing.join(", ")}). ` +
        "در این مدل فقط طبقه‌ای که المان سقف (دست Floors) دارد مساحت خودکار می‌گیرد — بقیه را از نقشه‌های مصوب دستی " +
        "وارد کنید (تنظیمات → floors_data). رَدپای ساختمان از بتن مگر در شیت «ضریب طبقات» به‌عنوان راهنما نمایش داده می‌شود.",
      action: "مساحت هر طبقه را از نقشه‌های مصوب وارد کنید.",
      ref: "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — بندهای ۱-۱ و ۱-۳",
    });
    return blankFloors(rows, { value: 1.0, status: "ناقص", source: null });
  }
  const num = rows
    .filter((r) => r.kind === "above" || r.kind === "below_base")
    .reduce((a, r) => a + r.index * (r.area ?? 0), 0);
  const den = rows.filter((r) => r.kind !== "roof" && r.kind !== "none").reduce((a, r) => a + (r.area ?? 0), 0);
  if (den <= 0) {
    warns.push({
      level: "هشدار",
      category: "ضریب طبقات",
      item: "—",
      message: "هیچ مساحت طبقه‌ای در دسترس نیست — ضریب طبقات ۱.",
      action: "مساحت طبقات را از نقشه‌های مصوب وارد کنید.",
      ref: "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴",
    });
    return blankFloors(rows, { value: 1.0, status: "ناقص", source: null });
  }
  const div = den * (divisorMode === "100×S" ? 100.0 : 1.0);
  const p = 1.0 + (div > 0 ? num / div : 0.0);
  const pAlt = divisorMode !== "100×S" ? 1.0 + num / (den * 100.0) : 1.0 + num / den;
  const warnDev = divisorMode === "S";
  const src =
    `محاسبه از فرمول پیوست ۲: P = 1 + [Σ(i×Fi) + Σ(j×Bj)] ÷ ${divisorMode} = ` +
    `1 + (${faFloat(num, 2)} ÷ ${faFloat(den, 2)}) = ${faFloat(p, 6)} — نیازمند تأیید کاربر`;
  const roofRows = rows.filter((r) => r.kind === "roof");
  if (roofRows.length) {
    warns.push({
      level: "اطلاع",
      category: "ضریب طبقات",
      item: roofRows.map((r) => r.name).join("، "),
      message:
        "این ترازها به‌عنوان بام/مرجع (غیرطبقه) در تنظیمات floorsRoofLevels مشخص شده‌اند و از صورت و مخرج " +
        "فرمول ضریب طبقات مستثنی شده‌اند. طبق تعاریف پیوست ۲ فقط «طبقات» (بالای همکف، همکف، و زیرهمکف) در S وارد می‌شوند.",
      action: "در صورت اشتباه بودن، در تنظیمات تغییر دهید.",
      ref: "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — تعاریف F/B/S",
    });
  }
  const nonFloorRows = rows.filter((r) => r.kind === "none");
  if (nonFloorRows.length) {
    warns.push({
      level: "اطلاع",
      category: "ضریب طبقات",
      item: nonFloorRows.map((r) => r.name).join("، "),
      message:
        "این ترازها غیرطبقه‌ای هستند (مثلاً تراز بالای فونداسیون — پی است، نه زیرهمکف) و در Σ ضریب طبقات وارد نمی‌شوند. " +
        "طبق تعاریف پیوست ۲ فقط «طبقات» در صورت و مخرج می‌آیند.",
      action: "اگر یکی از این ترازها در پروژهٔ شما طبقهٔ واقعی است، در تنظیمات → floors_data آن را به‌عنوان طبقه علامت بزنید.",
      ref: "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — تعریف طبقه (بند ۱)",
    });
  }
  if (warnDev) {
    warns.push({
      level: "هشدار",
      category: "ضریب طبقات",
      item: "مخرج فرمول",
      message:
        "مخرج کسر در متن رسمی پیوست ۲ «۱۰۰ × S» است ولی گزینهٔ «S» انتخاب شده که با متن رسمی بخشنامه مغایرت دارد. " +
        "مقدار P با هر دو مخرج در شیت «ضریب طبقات» نمایش داده می‌شود.",
      action: "مخرج رسمی «۱۰۰ × S» را تأیید کنید (تنظیمات → floorsDivisor).",
      ref: "پیوست ۲ فهرست‌بهای ابنیه ۱۴۰۴ — متن رسمی دریافت‌شده از کاربر",
    });
  }
  return {
    value: p,
    status: "محاسبه‌شده",
    source: src,
    rows,
    calc: { divisor: divisorMode, num, den, pAlt, altLabel: divisorMode === "S" ? "100×S" : "S" },
    eligibleTotal: 0,
    excludedTotal: 0,
    excludedChapters: [],
    eligibleLines: [],
    footprint: null,
    floorsAmount: 0,
    formula: floorsFormula(),
    clause: floorsClause(),
  };
}

function floorsFormula(): string | null {
  const v = (FLOORS_SPEC as Record<string, unknown>).formula;
  return typeof v === "string" ? v : FLOORS_FALLBACK.formula;
}

function floorsClause(): string | null {
  const v = (FLOORS_SPEC as Record<string, unknown>).apply_to;
  return typeof v === "string" ? v : FLOORS_FALLBACK.apply_to;
}

function blankFloors(
  rows: FloorRow[],
  out: { value: number | null; status: string; source: string | null },
): FloorsCoef {
  return {
    ...out,
    rows,
    calc: null,
    eligibleTotal: 0,
    excludedTotal: 0,
    excludedChapters: [],
    eligibleLines: [],
    footprint: null,
    floorsAmount: 0,
    formula: floorsFormula(),
    clause: floorsClause(),
  };
}

interface RegionalEntry {
  row: number;
  city: string;
  district: string;
  high_altitude: boolean;
  coefs: Record<string, number>;
}

/**
 * ضریب منطقه‌ای از جدول S5؛ اولویت: ورودی دستی > جدول استخراج‌شده.
 *
 * خروجی: (ضریب, وضعیت, منبع). اگر نه جدول و نه دستی → ناقص.
 */
export function computeRegionalCoef(settings: ProjectSettings, warns: Warning[]): RegionalCoef {
  const sel = settings.regionalSelection ?? {};
  const manual = settings.regionalCoef;
  if (manual !== undefined && manual !== null) {
    return { value: Number(manual), status: "دستی", source: "ورود کاربر" };
  }
  const prov = sel.province;
  const city = sel.city;
  const disc = sel.discipline ?? "ابنیه";
  const dist = sel.district;
  const table = REGIONAL_TABLE as { provinces?: Record<string, RegionalEntry[]>; meta?: Record<string, unknown> };
  const entries = table.provinces?.[prov ?? ""] ?? [];
  if (!entries.length) {
    warns.push({
      level: "خطا",
      category: "ضریب منطقه‌ای",
      item: prov ?? "—",
      message: `استان «${prov ?? "انتخاب‌نشده"}» در جدول ضرایب منطقه‌ای (config/regional_coefficients.json) یافت نشد.`,
      action: "استان/شهرستان را انتخاب یا ضریب را دستی وارد کنید.",
      ref: "بخشنامه ۹۴/۶۹۴۱۶ (S5)",
    });
    return { value: null, status: "ناقص", source: null };
  }
  const cands = entries.filter(
    (e) => e.city === city && (dist === undefined || dist === null || dist === "" || e.district === dist),
  );
  if (!cands.length) {
    warns.push({
      level: "خطا",
      category: "ضریب منطقه‌ای",
      item: `${prov}/${city}`,
      message:
        `شهرستان «${city ?? "—"}» در استان «${prov ?? "—"}» یافت نشد. ` +
        `بخش‌های موجود: ${[...new Set(entries.map((e) => e.district))].sort().join("، ")}`,
      action: "بخش صحیح را انتخاب یا ضریب را دستی وارد کنید.",
      ref: "بخشنامه ۹۴/۶۹۴۱۶ (S5)",
    });
    return { value: null, status: "ناقص", source: null };
  }
  const e = cands[0];
  const v = e.coefs[disc];
  if (v === undefined) {
    warns.push({
      level: "خطا",
      category: "ضریب منطقه‌ای",
      item: `${prov}/${city}/${e.district}/${disc}`,
      message: `ضریب رشتهٔ «${disc}» برای این شهرستان یافت نشد.`,
      action: "رشته را تغییر دهید یا ضریب را دستی وارد کنید.",
      ref: "بخشنامه ۹۴/۶۹۴۱۶ (S5)",
    });
    return { value: null, status: "ناقص", source: null };
  }
  const meta = table.meta ?? {};
  const page = meta.page as number | undefined;
  const src =
    `استخراج‌شده از بخشنامه ۹۴/۶۹۴۱۶${page ? `، صفحهٔ ${faDigits(page)} PDF` : ""}، ` +
    `ردیف ${faDigits(e.row)} (${prov}/${city}/${e.district})${e.high_altitude ? "، حوزهٔ بالای ۵۰۰ متر" : ""} — نیازمند تأیید کاربر`;
  return { value: v, status: "استخراج‌شده", source: src };
}
