// ─────────────────────────────────────────────────────────────
// پنل قیمت دستی (فاز C — §۱۵-۴): ماندگاری و جابه‌جایی ورودی‌های دستی
//
// - فایل کناری JSON با نسخه و تاریخ (درون‌ریزی/درون‌بری در مرورگر).
// - ورود از Excel: شیت «قیمت‌های دستی» که exportWorkbook می‌سازد.
//
// هم‌سان با app.py (manual_entries_payload / apply_manual_entries /
// parse_manual_entries_xlsx). نشانه‌های بخش و نام شیت‌ها در دو زبان
// یکسان هستند — تغییر ندهید.
// ─────────────────────────────────────────────────────────────
import * as XLSX from "xlsx";
import type {
  AuditEntry,
  ExcludedRecord,
  ManualCodeRecord,
  ManualPriceRecord,
  ProjectMeta,
  ProjectSettings,
  StarredRow,
} from "./types";
import { AUDIT_KIND_CODES, MANUAL_SOURCES } from "./types";
import { jalaliNowStr } from "./farsi";
import {
  appendAudit,
  defaultSettings,
  migrateManualEntries,
} from "./engine";

export const MANUAL_ENTRIES_VERSION = 1;
export const MANUAL_ENTRIES_FIELDS = [
  "manualPrices",
  "manualCodes",
  "excluded",
  "starredRows",
  "priceAudit",
] as const;

export const MPX_SHEET = "قیمت‌های دستی";
export const MPX_AUDIT_SHEET = "سابقهٔ ویرایش";
export const MPX_VERSION_LABEL = "نسخهٔ قالب";
export const MPX_SECTION_PRICES = "بخش: قیمت‌های دستی ردیف‌ها";
export const MPX_SECTION_CODES = "بخش: کدهای جایگزین فهرست‌بها";
export const MPX_SECTION_EXCLUDED = "بخش: ردیف‌های مستثنی‌شده";
export const MPX_SECTION_STARRED = "بخش: ردیف‌های ستاره‌دار (غیرفهرستی)";

export interface ManualEntriesPayload {
  version: number;
  app: string;
  savedAt: string;
  user: string;
  diffWarnPct: number;
  manualPrices: Record<string, ManualPriceRecord>;
  manualCodes: Record<string, ManualCodeRecord>;
  excluded: ExcludedRecord[];
  starredRows: StarredRow[];
  priceAudit: AuditEntry[];
}

/** تصویرِ کامل از ورودی‌های دستی برای ذخیره یا جابه‌جایی بین پروژه‌ها. */
export function manualEntriesPayload(s: ProjectSettings): ManualEntriesPayload {
  return {
    version: MANUAL_ENTRIES_VERSION,
    app: "MetreYar",
    savedAt: jalaliNowStr(),
    user: s.priceUser ?? "",
    diffWarnPct: s.priceDiffWarnPct ?? 30,
    manualPrices: s.manualPrices ?? {},
    manualCodes: (s.manualCodes ?? {}) as Record<string, ManualCodeRecord>,
    excluded: (s.excluded ?? []) as ExcludedRecord[],
    starredRows: s.starredRows ?? [],
    priceAudit: s.priceAudit ?? [],
  };
}

export type ManualEntriesWarn = string;

/**
 * بارگذاری ورودی‌های دستی از payload (فایل کناری یا Excel واردشده).
 * payload مرجع است (دقیقاً همان چیزی که ذخیره شده بود).
 */
export function applyManualEntries(
  s: ProjectSettings,
  payload: unknown,
): ManualEntriesWarn[] {
  const warns: ManualEntriesWarn[] = [];
  if (!payload || typeof payload !== "object") return ["فایل ورودی قیمت‌ها ساختار درستی ندارد."];
  const p = payload as Record<string, unknown>;
  if (p.version !== MANUAL_ENTRIES_VERSION) {
    warns.push(
      `نسخهٔ فایل قیمت‌ها (${String(p.version ?? "—")}) با نسخهٔ برنامه ` +
        `(${MANUAL_ENTRIES_VERSION}) متفاوت است — ممکن است بخشی از داده‌ها وارد نشوند.`,
    );
  }
  for (const k of MANUAL_ENTRIES_FIELDS) {
    const v = p[k] ?? p[SNAKE_ALIASES[k]]; // پذیرش فرمت sidecar پایتون (snake_case)
    if (v && typeof v === "object") {
      (s as unknown as Record<string, unknown>)[k] = v;
    }
  }
  const dwp = Number(p.diffWarnPct ?? p.diff_warn_pct);
  if (Number.isFinite(dwp) && dwp > 0) s.priceDiffWarnPct = dwp;
  delete (s as { _manualMigrated?: boolean })._manualMigrated;
  migrateManualEntries(s);
  return warns;
}

/**
 * خواندن شیت «قیمت‌های دستی» از یک فایل Excel → payload قابل اعمال.
 * ورودی: دادهٔ باینری xlsx. خروجی: payload یا null در صورت نبود شیت.
 */
export function parseManualEntriesXlsx(data: ArrayBuffer | Uint8Array): ManualEntriesPayload | null {
  const wb = XLSX.read(data, { type: "array" });
  if (!wb.SheetNames.includes(MPX_SHEET)) return null;

  const rows: unknown[][] = XLSX.utils.sheet_to_json(wb.Sheets[MPX_SHEET], {
    header: 1,
    blankrows: true,
    defval: "",
  });
  const norm = (r: unknown[]): string[] => r.map((c) => (c == null ? "" : String(c)));

  const payload: ManualEntriesPayload = {
    version: MANUAL_ENTRIES_VERSION,
    app: "MetreYar",
    savedAt: "",
    user: "",
    diffWarnPct: 30,
    manualPrices: {},
    manualCodes: {},
    excluded: [],
    starredRows: [],
    priceAudit: [],
  };

  // نسخهٔ قالب (ردیف نشانگر)
  for (const r of rows) {
    const cells = norm(r as unknown[]);
    if (cells[0].trim() === MPX_VERSION_LABEL) {
      const v = Number(cells[1]);
      if (Number.isFinite(v)) payload.version = v;
      break;
    }
  }

  type Section = {
    field: keyof Omit<ManualEntriesPayload, "version" | "app" | "savedAt" | "user" | "diffWarnPct">;
    kind: "dict" | "list";
    parse: (cells: string[]) => unknown;
  };
  const sections: Record<string, Section> = {
    [MPX_SECTION_PRICES]: {
      field: "manualPrices", kind: "dict", parse: priceRow,
    },
    [MPX_SECTION_CODES]: {
      field: "manualCodes", kind: "dict", parse: codeRow,
    },
    [MPX_SECTION_EXCLUDED]: {
      field: "excluded", kind: "list", parse: excludedRow,
    },
    [MPX_SECTION_STARRED]: {
      field: "starredRows", kind: "list", parse: starredRow,
    },
  };

  let i = 0;
  while (i < rows.length) {
    const first = norm(rows[i])[0].trim();
    if (first in sections) {
      const sec = sections[first];
      let j = i + 2; // ردیف بعدی = سرستون
      while (j < rows.length) {
        const cells = norm(rows[j]);
        if (cells[0].trim().startsWith("بخش:")) break;
        if (cells.some((c) => c.trim() !== "")) {
          const rec = sec.parse(cells);
          if (rec) {
            if (sec.kind === "dict") {
              const [key, val] = rec as [string, unknown];
              (payload[sec.field] as Record<string, unknown>)[key] = val;
            } else {
              (payload[sec.field] as unknown[]).push(rec);
            }
          }
        }
        j += 1;
      }
      i = j;
    } else {
      i += 1;
    }
  }

  // سابقهٔ ویرایش (شیت جدا)
  if (wb.SheetNames.includes(MPX_AUDIT_SHEET)) {
    const auditRows = XLSX.utils.sheet_to_json(wb.Sheets[MPX_AUDIT_SHEET], {
      header: 1, blankrows: true, defval: "",
    }) as unknown[][];
    const headerPrefixes = ["صورت وضعیت", "نام پروژه", "دورهٔ", "مبنای"];
    for (const r of auditRows) {
      const cells = norm(r);
      if (!cells[0] || cells[0].trim() === "زمان") continue;
      if (headerPrefixes.some((p) => cells[0].startsWith(p))) continue;
      payload.priceAudit.push({
        at: cells[0], user: cells[1], item: cells[2], field: cells[3],
        old: cells[4], new: cells[5], source: cells[6],
        kind: AUDIT_KIND_CODES[cells[7] ?? ""] ?? "price",
      });
    }
  }
  return payload;
}

// «کاربر — تاریخ ورود» یک ستون است؛ با اولین/آخرین « — » شکافته می‌شود.
function splitUserAt(raw: string): { user: string; at: string } {
  const parts = raw.split(" — ");
  return {
    user: (parts[0] ?? "").trim(),
    at: (parts[parts.length - 1] ?? "").trim(),
  };
}

function priceRow(cells: string[]): [string, ManualPriceRecord] | null {
  if (!cells[0]) return null;
  const price = Number(cells[2]);
  if (!Number.isFinite(price)) return null;
  const ua = splitUserAt(cells[10] ?? "");
  return [cells[0].trim(), {
    price,
    source: cells[5] || "بخشنامه",
    docNo: cells[6] ?? "",
    docDate: cells[7] ?? "",
    note: cells[11] ?? "",
    status: cells[8] || "دستی",
    chapter: cells[9] ?? "",
    user: ua.user,
    at: ua.at,
  }];
}

function codeRow(cells: string[]): [string, ManualCodeRecord] | null {
  if (!cells[0] || !cells[1]) return null;
  return [cells[0].trim(), {
    code: cells[1].trim(), reason: cells[2] ?? "",
    user: cells[3] ?? "", at: cells[4] ?? "",
  }];
}

function excludedRow(cells: string[]): ExcludedRecord | null {
  if (!cells[0]) return null;
  return {
    id: cells[0].trim(), reason: cells[1] ?? "",
    user: cells[2] ?? "", at: cells[3] ?? "",
  };
}

function starredRow(cells: string[]): StarredRow | null {
  const qty = Number(cells[3]);
  const price = Number(cells[4]);
  if (!Number.isFinite(qty) || !Number.isFinite(price)) return null;
  const ua = splitUserAt(cells[9] ?? "");
  return {
    code: (cells[0] ?? "").trim(),
    desc: cells[1] ?? "",
    unit: cells[2] || "عدد",
    qty, price,
    chapter: (cells[5] ?? "").slice(0, 2),
    source: cells[6] || "توافق",
    docNo: cells[7] ?? "",
    docDate: cells[8] ?? "",
    user: ua.user,
    at: ua.at,
    note: cells[10] ?? "",
  };
}

/** مسیر پیشنهادی فایل کناری برای یک فایل پروژه (همان پوشه، همان نام). */
export function manualSidecarPath(projectFile: string): string {
  if (!projectFile) return "";
  const dot = projectFile.lastIndexOf(".");
  const base = dot > 0 ? projectFile.slice(0, dot) : projectFile;
  return `${base}_manual_prices.json`;
}

/**
 * ذخیرهٔ ورودی‌های دستی به‌صورت فایل JSON مرورگر (با نسخه و تاریخ).
 * معادلِ save_manual_entries در app.py — در مرورگر به‌جای نوشتن کنار
 * فایل پروژه، یک دانلود تولید می‌کند.
 */
export function downloadManualEntries(s: ProjectSettings, projectName: string): string {
  const payload = manualEntriesPayload(s);
  const json = JSON.stringify(payload, null, 1);
  const blob = new Blob([json], { type: "application/json" });
  const stamp = jalaliNowStr().replace(/[/ :]/g, "-");
  const name = `ManualPrices_${sanitizeName(projectName || "Project")}_${stamp}.json`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  return name;
}

function sanitizeName(s: string): string {
  return s.replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 50);
}

/** منابع قابل انتخاب در پنل (هم‌سان با MANUAL_SOURCES در app.py). */
export const PRICE_SOURCES = MANUAL_SOURCES;

// کلیدهای فرمت sidecar پایتون (snake_case) — برای پذیرش فایل‌های ساخته‌شده
// توسط نسخهٔ Streamlit در مرورگر.
const SNAKE_ALIASES: Record<string, string> = {
  manualPrices: "manual_prices",
  manualCodes: "manual_codes",
  excluded: "excluded",
  starredRows: "starred_rows",
  priceAudit: "price_audit",
};

// ════════════════════════════════════════════════════════════════
// فاز E-۵ — پروفایل پروژه: همهٔ ورودی‌ها در یک فایل JSON مستقل
// ════════════════════════════════════════════════════════════════

export const PROFILE_KIND = "metreyar_project_profile";
export const PROFILE_VERSION = 1;

export interface ProjectProfile {
  kind: typeof PROFILE_KIND;
  version: number;
  exportedAt: string;
  meta: ProjectMeta;
  settings: ProjectSettings;
}

export function projectProfilePayload(
  s: ProjectSettings,
  meta: ProjectMeta,
): ProjectProfile {
  return {
    kind: PROFILE_KIND,
    version: PROFILE_VERSION,
    exportedAt: new Date().toISOString(),
    meta: { ...meta },
    settings: { ...s },
  };
}

/** دانلود پروفایل پروژه به‌عنوان JSON (معادل save_profile در app.py). */
export function downloadProjectProfile(
  s: ProjectSettings,
  meta: ProjectMeta,
  projectName: string,
): string {
  const payload = projectProfilePayload(s, meta);
  const json = JSON.stringify(payload, null, 1);
  const blob = new Blob([json], { type: "application/json" });
  const stamp = jalaliNowStr().replace(/[/ :]/g, "-");
  const name = `MetreYarProfile_${sanitizeName(projectName || "Project")}_${stamp}.json`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  return name;
}

/** تبدیلِ کلید snake_case (پایتون) به camelCase (TypeScript). */
function snakeToCamel(k: string): string {
  return k.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase());
}

/** پایهٔ مشخصاتِ پیمان برای پذیرشِ پروفایل (هم‌سان با defaultMeta). */
const PROFILE_META_BASE: ProjectMeta = {
  projectName: "", employer: "", contractor: "", consultant: "",
  contractNo: "", contractDate: "", location: "",
  reportNo: "۱", reportType: "موقت", periodStart: "", periodEnd: "",
};

/**
 * پذیرشِ کلیدهای ذخیره‌شده در پروفایل: camelCase یا snake_case.
 * فقط کلیدهای شناخته‌شده پذیرفته می‌شوند؛ بقیه در dropped گزارش می‌شوند
 * (قاعدهٔ طلایی ۳: هشدار به‌جای ساختِ داده).
 */
function adoptKeys<T extends object>(
  raw: unknown,
  base: T,
): { out: T; dropped: string[] } {
  const known = new Set(Object.keys(base));
  const out: Record<string, unknown> = {
    ...(base as Record<string, unknown>),
  };
  const dropped: string[] = [];
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (k.startsWith("_")) continue;
      if (known.has(k)) {
        out[k] = v;
      } else {
        const alt = snakeToCamel(k);
        if (alt !== k && known.has(alt)) out[alt] = v;
        else dropped.push(k);
      }
    }
  }
  return { out: out as T, dropped };
}

/**
 * خواندن پروفایل پروژه از متن JSON → { meta, settings, warns }.
 *
 * فایل‌های کناریِ قدیمیِ قیمت‌ها هم تشخیص داده می‌شوند: در آن صورت meta
 * برابر null است و فقط تنظیمات پر می‌شود. خطای تجزیه: settings === null.
 */
export function loadProjectProfileJson(text: string): {
  meta: ProjectMeta | null;
  settings: ProjectSettings | null;
  warns: string[];
} {
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch (ex) {
    return {
      meta: null,
      settings: null,
      warns: [`خواندن فایل پروفایل ناموفق بود: ${String(ex)}`],
    };
  }
  if (!payload || typeof payload !== "object") {
    return {
      meta: null,
      settings: null,
      warns: ["ساختار فایل پروفایل نامعتبر است."],
    };
  }
  const p = payload as Record<string, unknown>;
  const warns: string[] = [];
  if (p.kind === PROFILE_KIND) {
    if (p.version !== PROFILE_VERSION) {
      warns.push(
        `نسخهٔ پروفایل (${String(p.version)}) با نسخهٔ برنامه (${PROFILE_VERSION}) متفاوت است — ممکن است بخشی از داده‌ها وارد نشوند.`,
      );
    }
    const s = adoptKeys(p.settings, defaultSettings());
    const m = adoptKeys(p.meta, PROFILE_META_BASE);
    if (s.dropped.length || m.dropped.length) {
      warns.push(
        `برخی کلیدهای پروفایل ناشناخته بودند و نادیده گرفته شدند: ${[...s.dropped, ...m.dropped].slice(0, 10).join("، ")}`,
      );
    }
    delete (s.out as { _manualMigrated?: boolean })._manualMigrated;
    migrateManualEntries(s.out);
    return { meta: m.out, settings: s.out, warns };
  }
  // فایل کناریِ قدیمیِ قیمت‌ها: فقط ورودی‌های دستی
  const s = defaultSettings();
  warns.push(...applyManualEntries(s, p as unknown as ManualEntriesPayload));
  return { meta: null, settings: s, warns };
}

/**
 * پروژهٔ جدید از روی پروژهٔ فعلی (فاز E-۵): فیلدهای هویتی/زمانی پاک
 * می‌شوند و سابقهٔ ویرایش از صفر با رکوردِ «کپی از پروژهٔ X» شروع می‌شود.
 * قیمت‌های دستی با سوابقِ سندشان نگه داشته می‌شوند.
 */
export function copyProject(
  s: ProjectSettings,
  meta: ProjectMeta,
): { meta: ProjectMeta; settings: ProjectSettings } {
  const srcName = meta.projectName ?? "";
  const newMeta: ProjectMeta = { ...meta };
  (
    ["reportType", "periodStart", "periodEnd", "contractNo", "contractDate"] as const
  ).forEach((k) => {
    newMeta[k] = "";
  });
  newMeta.reportNo = "۱";
  newMeta.projectName = srcName ? `کپی از ${srcName}` : "";

  const newS: ProjectSettings = { ...s };
  (
    [
      "proposalDate",
      "proposalDeadline",
      "workPeriodStart",
      "workPeriodEnd",
      "finalOfferDate",
      "lastProvisionalDate",
    ] as const
  ).forEach((k) => {
    (newS as unknown as Record<string, unknown>)[k] = "";
  });
  newS.proposalCoef = 1.0;
  // فاز E-6: وضعیت اتمام کار پروژهٔ جدید نامشخص است (k = ۰٫۹۵)
  newS.completedWithinTerm = null;
  // فاز E-6 Part C: تمدیدها و وضعیت خاتمهٔ پروژهٔ قدیمی معنی ندارند؛
  // مساحت طبقات هم مالِ ساختمانِ پروژهٔ قبلی است. فلگ‌ها و شاخص‌های
  // دستی نگه داشته می‌شوند (درخواست کاربر، گام ۱۰).
  newS.contractExtensions = [];
  newS.contractStatus = "فعال";
  newS.contractDurationMonths = null;
  newS.floorsData = {};
  newS.priceAudit = [];
  appendAudit(
    newS,
    "پروژه",
    "copy",
    srcName,
    newMeta.projectName,
    "دکمهٔ پروژهٔ جدید از روی این پروژه",
    "meta",
  );
  return { meta: newMeta, settings: newS };
}
