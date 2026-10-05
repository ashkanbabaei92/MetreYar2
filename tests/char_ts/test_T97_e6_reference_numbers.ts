// ─────────────────────────────────────────────────────────────
// T97 (بخش دوم) — فاز E-6: اعداد مرجع موتور تعدیل با گردکردن بند ۸-۲
// و ردیف مابه‌التفاوت تبصرهٔ ۲ (بند ۸-۴) روی دادهٔ مرجع پروژه
// (آینهٔ test_T97_e6_reference_numbers.py — خروجی‌ها باید bit-identical باشند).
//
// اعداد مرجع (سناریوی §۱۴-۶، دورهٔ ۱۴۰۴/۰۱/۰۱ تا ۱۴۰۵/۰۲/۱۵):
//   گردکردن خاموش (میراث پیش از E-6):
//     ΔP = ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴   قطعی = ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰   علی‌الحساب = ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴
//   گردکردن روشن (پیش‌فرض E-6، بند ۸-۲):
//     ΔP = ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲   قطعی = ۷٬۷۶۱٬۰۴۵٬۲۰۹٫۹۴   علی‌الحساب = ۲٬۲۲۳٬۲۳۲٬۱۹۸٫۲۸
//   گردکردن روشن + completedWithinTerm = true (k = ۱، تبصرهٔ ۲):
//     ΔP = ۱۰٬۴۸۹٬۵۹۴٬۳۶۹٫۰۷   k_diff = ۵۰۵٬۳۱۶٬۹۶۰٫۸۶ (بند ۸-۴)
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { roundCoef2080, splitRounded } from "../../src/lib/adjustment";
import { exportWorkbook } from "../../src/lib/exporters";
import type { ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const PROV_COEF = 1.1530518586507572;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹";

const REF: Partial<ProjectSettings> = {
  baravordEnabled: true,
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
  provisionalCoef1405q1: PROV_COEF,
};
// سناریوی همه-قطعی: دوره تا ۱۴۰۴/۱۲/۲۹ (شاخص ۱۴۰۵Q1 موقت دیگر کاربرد ندارد)
const REF_ALLDEF: Partial<ProjectSettings> = {
  ...REF,
  workPeriodEnd: "۱۴۰۴/۱۲/۲۹",
};

// اعداد خام موتور (دقیق) — از اجرای مرجع
const DP_ROUND = 9984277408.217051;
const DP_ROUND_DEF = 7761045209.936075;
const DP_ROUND_PROV = 2223232198.280975;
const DP_ROUND_SPLIT: [number, number, number] = [
  9984277408.22, 7761045209.94, 2223232198.28,
];
const DP_LEGACY = 9937407877.639488;
const DP_LEGACY_SPLIT: [number, number, number] = [
  9937407877.64, 7709893479.4, 2227514398.24,
];
const DP_CWT = 10489594369.074144;
const K_DIFF = 505316960.857094;

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function pipeline(settings: ProjectSettings): ProjectResult {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .filter((f) => f.endsWith(".txt"))
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows: unknown[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const sd = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(sd).isDirectory()) continue;
    for (const fn of fs.readdirSync(sd).sort()) {
      if (!fn.endsWith(".txt")) continue;
      (rows as unknown[]).push(...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows);
    }
  }
  return computeProject(tables, OFFICIAL_1404_FEHREST, settings, {
    rows,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return { ...defaultSettings(), tadilEnabled: true, proposalDate: PROPOSAL_DATE, ...extra };
}

describe("T97 فاز E-6 — اعداد مرجع موتور تعدیل", () => {
  it("گردکردن بند ۸-۲ پیش‌فرض است", () => {
    expect(defaultSettings().coefRounding2080).toBe(true);
  });

  it("هر فصل، ضریب خام و گردشده را همراه دارد", () => {
    const t = pipeline(on(REF)).adjustment.tadil!;
    expect(t.coef_rounding).toBe(true);
    for (const r of t.chapters) {
      expect(r.coef_rows?.length ?? 0).toBeGreaterThan(0);
      for (const [, raw, used] of r.coef_rows!) {
        expect(used).toBeCloseTo(roundCoef2080(raw) as number, 12);
      }
    }
    const sr = t.setup_row;
    if (sr) expect(sr.delta_k095).not.toBeNull();
  }, 120000);

  it("ΔP با گردکردن روشن (اعداد مرجع E-6)", () => {
    const t = pipeline(on(REF)).adjustment.tadil!;
    expect(t.delta_p).toBeCloseTo(DP_ROUND, 6);
    expect(t.delta_p_definitive).toBeCloseTo(DP_ROUND_DEF, 6);
    expect(t.delta_p_provisional).toBeCloseTo(DP_ROUND_PROV, 6);
    // نامساوی کلیدی: قطعی + علی‌الحساب ≡ ΔP (دقیق)
    expect(t.delta_p_definitive + t.delta_p_provisional).toBeCloseTo(t.delta_p, 9);
    const [r, a, b] = splitRounded(t.delta_p, t.delta_p_definitive, 2);
    expect(a + b).toBeCloseTo(r, 6);
    expect(r).toBeCloseTo(DP_ROUND_SPLIT[0], 6);
    expect(a).toBeCloseTo(DP_ROUND_SPLIT[1], 6);
    expect(b).toBeCloseTo(DP_ROUND_SPLIT[2], 6);
  }, 120000);

  it("ΔP با گردکردن خاموش = مقدارهای میراث پیش از E-6", () => {
    const t = pipeline(on({ ...REF, coefRounding2080: false })).adjustment.tadil!;
    expect(t.coef_rounding).toBe(false);
    expect(t.delta_p).toBeCloseTo(DP_LEGACY, 6);
    const [r, a, b] = splitRounded(t.delta_p, t.delta_p_definitive, 2);
    expect(a + b).toBeCloseTo(r, 6);
    expect(r).toBeCloseTo(DP_LEGACY_SPLIT[0], 6);
    expect(a).toBeCloseTo(DP_LEGACY_SPLIT[1], 6);
    expect(b).toBeCloseTo(DP_LEGACY_SPLIT[2], 6);
  }, 120000);

  it("k_diff صفر است وقتی وضعیت اتمام کار نامشخص یا تمام‌نشده", () => {
    const t = pipeline(on(REF)).adjustment.tadil!;
    expect(t.completed_within_term).toBe(false);
    expect(t.k_diff).toBe(0.0);
    const t2 = pipeline(on({ ...REF, completedWithinTerm: null })).adjustment.tadil!;
    expect(t2.k_diff).toBe(0.0);
  }, 120000);

  it("تبصرهٔ ۲: k = ۱ و k_diff در بخش قطعی (بند ۸-۴)", () => {
    const tTrue = pipeline(on({ ...REF, completedWithinTerm: true })).adjustment.tadil!;
    const tFalse = pipeline(on({ ...REF, completedWithinTerm: false })).adjustment.tadil!;
    expect(tTrue.coef).toBe(1.0);
    expect(tTrue.completed_within_term).toBe(true);
    // مابه‌التفاوت k = ۱ نسبت به k = ۰٫۹۵
    expect(tTrue.k_diff).toBeCloseTo(K_DIFF, 2);
    expect(tTrue.k_diff).toBeCloseTo(tTrue.delta_p - tFalse.delta_p, 2);
    expect(tTrue.delta_p).toBeCloseTo(DP_CWT, 6);
    // invariant کلی حفظ می‌شود
    expect(tTrue.delta_p_definitive + tTrue.delta_p_provisional).toBeCloseTo(
      tTrue.delta_p,
      9,
    );
    const [r, a, b] = splitRounded(tTrue.delta_p, tTrue.delta_p_definitive, 2);
    expect(a + b).toBeCloseTo(r, 6);
  }, 120000);

  it("تبصرهٔ ۲ در سناریوی همه-قطعی: k_diff کامل به قطعی می‌نشیند", () => {
    const t = pipeline(on({ ...REF_ALLDEF, completedWithinTerm: true })).adjustment
      .tadil!;
    expect(t.delta_p_definitive).toBeCloseTo(t.delta_p + t.k_diff, 9);
    expect(t.delta_p_provisional).toBeCloseTo(-t.k_diff, 9);
    expect(t.k_diff).toBeGreaterThan(0);
  }, 120000);
});


// ═══ فاز E-6: شیت‌های Excel ═══

/** صادر کردن کتاب‌کار با ضبطِ workbook (mock روی writeFile). */
function exportWb(result: ProjectResult, settings: ProjectSettings): XLSX.WorkBook {
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook(
      { projectName: "T97", reportNo: "1" } as never,
      result,
      settings,
      [] as never,
    );
  } finally {
    mock.mockRestore();
  }
  return wb as XLSX.WorkBook;
}

/** همهٔ رشته‌های یک کتاب‌کار (معادل sharedStrings در Python). */
function allStrings(wb: XLSX.WorkBook): string[] {
  const out: string[] = [];
  for (const name of wb.SheetNames) {
    const ws = wb.Sheets[name] ?? {};
    for (const addr in ws) {
      if (addr.startsWith("!")) continue;
      const c = ws[addr as never] as { v?: unknown } | undefined;
      if (typeof c?.v === "string") out.push(c.v);
    }
  }
  return out;
}

describe("T97 فاز E-6 — شیت‌های Excel", () => {
  it("شیت تعدیل: جدول ضریب خام/گردشده (بند ۸-۲)", () => {
    const res = pipeline(on(REF));
    const wb = exportWb(res, on(REF));
    const strs = allStrings(wb);
    expect(strs.some((x) => x.includes("ضریب تعدیل هر فصل در هر سه‌ماههٔ کارکرد"))).toBe(true);
    expect(strs.some((x) => x.includes("ضریب خام"))).toBe(true);
    expect(strs.some((x) => x.includes("ضریب گردشده"))).toBe(true);
  }, 120000);

  it("شیت بخش قطعی: ردیف تبصرهٔ ۲ فقط وقتی کار تمام شده باشد (بند ۸-۴)", () => {
    const wbOff = exportWb(pipeline(on(REF)), on(REF));
    const strsOff = allStrings(wbOff);
    expect(strsOff.some((x) => x.includes("مابه‌التفاوت k = ۰٫۹۵ → ۱"))).toBe(false);
    const wbOn = exportWb(
      pipeline(on({ ...REF, completedWithinTerm: true })),
      on({ ...REF, completedWithinTerm: true }),
    );
    const strsOn = allStrings(wbOn);
    expect(strsOn.some((x) => x.includes("مابه‌التفاوت k = ۰٫۹۵ → ۱"))).toBe(true);
    expect(strsOn.some((x) => x.includes("همزمان با صورت‌وضعیت قطعی"))).toBe(true);
  }, 120000);
});
