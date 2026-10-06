// T125 — قفلِ خروجیِ نهاییِ تعدیل (فاز E-10 §۲).
//
// قاعده: در «تعدیل صورت‌وضعیت» اگر دورهٔ کارکرد خالی باشد، Excel نهایی
// نباید ساخته شود — فقط «پیش‌نویس» با واترمارکِ «پیش‌نویس – دورهٔ کارکرد
// وارد نشده» روی همهٔ شیت‌ها. اگر completedWithinTerm نامشخص باشد، خروجی
// مجاز است ولی با برچسب «علی‌الحساب – k = ۰٫۹۵» (بند ۱-۸ بخشنامهٔ ۲۰۸۰).
//
// این آزمون:
//   ۱) موتور: work_period_missing وقتی دوره خالی است true و وقتی پر است false؛
//   ۲) موتور: k_provisional وقتی completedWithinTerm نامشخص است true و
//      k = ۰٫۹۵ است، و وقتی کار در مدت تمام شده false و k = ۱ است؛
//   ۳) export با reportType نهایی + دورهٔ خالی ⇒ خطا با نامِ فیلدها؛
//   ۴) export با reportType پیش‌نویس + دورهٔ خالی ⇒ ساخته می‌شود و واترمارک
//      روی همهٔ شیت‌ها می‌نشیند؛
//   ۵) export با دورهٔ پر ⇒ ساخته می‌شود و واترمارک نیست؛
//   ۶) برچسبِ «علی‌الحساب — k = ۰٫۹۵» در شیتِ تعدیل هست وقتی تکلیف نامشخص است.
//
// آینهٔ test_T125_tadil_final_lock.py.
import path from "node:path";
import fs from "node:fs";
import { describe, expect, it, vi } from "vitest";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";

import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { exportWorkbook } from "../../src/lib/exporters";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectMeta, ProjectResult, ProjectSettings } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

const BANNER = "پیش‌نویس – دورهٔ کارکرد وارد نشده";
const K_PROV_LABEL = "علی‌الحساب — k = ۰٫۹۵";

const BASE: Partial<ProjectSettings> = {
  tadilEnabled: true,
  baravordEnabled: false,
  proposalDate: "۱۴۰۳/۱۲/۲۹",
  provisionalCoef1405q1: 1.1530518586507572,
};

const WP_EMPTY: Partial<ProjectSettings> = { workPeriodStart: "", workPeriodEnd: "" };
const WP_FULL: Partial<ProjectSettings> = {
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
};

const memo = new Map<string, ProjectResult>();

function pipeline(extra: Partial<ProjectSettings>): ProjectResult {
  const key = JSON.stringify(extra);
  const hit = memo.get(key);
  if (hit) return hit;
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
      (rows as unknown[]).push(
        ...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows);
    }
  }
  const s = { ...defaultSettings(), ...BASE, ...extra };
  const res = computeProject(tables, OFFICIAL_1404_FEHREST, s, {
    rows: rows as never,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
  memo.set(key, res);
  return res;
}

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function baseMeta(over: Partial<ProjectMeta> = {}): ProjectMeta {
  return {
    projectName: "T125",
    employer: "کارفرما",
    contractor: "پیمانکار",
    consultant: "مشاور",
    contractNo: "۱",
    contractDate: "۱۴۰۴/۰۱/۰۱",
    location: "گرگان",
    reportNo: "۱",
    reportType: "موقت",
    periodStart: "",
    periodEnd: "",
    ...over,
  } as ProjectMeta;
}

function exportWb(result: ProjectResult, meta: ProjectMeta): XLSX.WorkBook {
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook(meta, result, { ...defaultSettings(), ...BASE } as never, [] as never);
  } finally {
    mock.mockRestore();
  }
  return wb as XLSX.WorkBook;
}

function sheetStrings(wb: XLSX.WorkBook, name: string): string[] {
  const ws = wb.Sheets[name] ?? {};
  const out: string[] = [];
  for (const addr in ws) {
    if (addr.startsWith("!")) continue;
    const c = ws[addr as never] as { v?: unknown } | undefined;
    if (typeof c?.v === "string") out.push(c.v);
  }
  return out;
}

describe("T125 — قفلِ خروجیِ نهاییِ تعدیل (E-10 §۲)", () => {
  // ۱) موتور: پرچمِ work_period_missing
  it("engine sets work_period_missing when the work period is empty", () => {
    const res = pipeline(WP_EMPTY);
    const t = res.adjustment.tadil;
    expect(t).not.toBeNull();
    expect(t!.work_period_missing).toBe(true);
    // هشدارِ هدایت‌کنندهٔ به فیلد هم صادر می‌شود (قاعدهٔ طلایی)
    expect(res.warnings.some((w) => w.item === "work_period_missing_for_it")).toBe(true);
  });

  it("engine clears work_period_missing when the work period is set", () => {
    const res = pipeline(WP_FULL);
    const t = res.adjustment.tadil;
    expect(t).not.toBeNull();
    expect(t!.work_period_missing).toBe(false);
    expect(res.warnings.some((w) => w.item === "work_period_missing_for_it")).toBe(false);
  });

  // ۲) موتور: k علی‌الحساب در برابر قطعی
  it("k is provisional (0.95) when completedWithinTerm is unset", () => {
    const res = pipeline(WP_EMPTY);
    const t = res.adjustment.tadil!;
    expect(t.k_provisional).toBe(true);
    expect(t.coef).toBeCloseTo(0.95);
    expect(t.k_status).toContain("علی‌الحساب");
  });

  it("k is definitive (1.0) when completedWithinTerm is true", () => {
    const res = pipeline({ ...WP_EMPTY, completedWithinTerm: true });
    const t = res.adjustment.tadil!;
    expect(t.k_provisional).toBe(false);
    expect(t.coef).toBeCloseTo(1.0);
  });

  // ۳) export: خروجیِ نهایی وقتی دوره خالی است ممنوع است
  it("export refuses final output when work period is missing", () => {
    const res = pipeline(WP_EMPTY);
    expect(() =>
      exportWorkbook(baseMeta(), res, { ...defaultSettings(), ...BASE } as never, [] as never),
    ).toThrow(/تاریخ شروع دورهٔ صورت‌وضعیت/);
  });

  // ۴) export: پیش‌نویس مجاز است با واترمارک روی همهٔ شیت‌ها
  it("export allows draft with watermark on all sheets", () => {
    const res = pipeline(WP_EMPTY);
    const wb = exportWb(res, baseMeta({ reportType: "پیش‌نویس — موقت" }));
    expect(wb.SheetNames.length).toBeGreaterThan(1);
    for (const name of wb.SheetNames) {
      expect(sheetStrings(wb, name)).toContain(BANNER);
    }
  });

  // ۵) export: وقتی دوره پر است واترمارکی نیست
  it("export has no watermark when work period is present", () => {
    const res = pipeline(WP_FULL);
    const wb = exportWb(res, baseMeta());
    for (const name of wb.SheetNames) {
      expect(sheetStrings(wb, name)).not.toContain(BANNER);
    }
  });

  // ۶) export: برچسبِ علی‌الحسابِ k در شیتِ تعدیل
  it("export shows provisional k label when cwt is unset", () => {
    const res = pipeline(WP_FULL);
    const wb = exportWb(res, baseMeta());
    const tadilSheet = wb.SheetNames.find((n) => n.includes("تعدیل پیمان"));
    expect(tadilSheet).toBeDefined();
    const strs = sheetStrings(wb, tadilSheet as string);
    expect(strs.some((s) => s.includes(K_PROV_LABEL))).toBe(true);
  });

  it("export has no provisional k label when cwt is true", () => {
    const res = pipeline({ ...WP_FULL, completedWithinTerm: true });
    const wb = exportWb(res, baseMeta());
    const tadilSheet = wb.SheetNames.find((n) => n.includes("تعدیل پیمان"));
    expect(tadilSheet).toBeDefined();
    const strs = sheetStrings(wb, tadilSheet as string);
    expect(strs.some((s) => s.includes(K_PROV_LABEL))).toBe(false);
  });
});
