// T116 — برچسب‌گذاریِ برآورد به‌هنگام (فاز E-8 بخش ۳).
//
// قاعده: هیچ خروجیِ برآوردی (Excel / UI) بدون برچسبِ «دورهٔ It» و
// «وضعیت موقت/قطعی» ساخته نمی‌شود. اگر It موقت (۱۴۰۵Q1) باشد، ضریبِ
// موقت هم باید نمایش داده شود.
//
// این آزمون:
//   ۱) موتور: خروجیِ baravord فیلدهای it_status / prov / prov_manual /
//      prov_trace را دارد (هر دو مسیر: قطعی و موقت)؛
//   ۲) شیتِ Excel «برآورد به‌هنگام»: برچسبِ «دورهٔ انجام کار (It)» و
//      «وضعیت دورهٔ It» همیشه موجودند؛
//   ۳) مسیرِ قطعی (q4): وضعیت = «قطعی» و ردیفِ ضریبِ موقت وجود ندارد؛
//   ۴) مسیرِ موقت (۱۴۰۵Q1): وضعیت = «موقت» و ردیفِ «ضریب موقت (۱۴۰۵Q1)»
//      با عددِ ضریب ساخته می‌شود.
//
// آینهٔ test_T116_baravord_labels.py.
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
import type { ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const PROV_COEF = 1.1530518586507572;

const BASE: Partial<ProjectSettings> = {
  tadilEnabled: true,
  baravordEnabled: true,
  proposalDate: "۱۴۰۳/۱۲/۲۹",
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
  provisionalCoef1405q1: PROV_COEF,
};

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function pipeline(extra: Partial<ProjectSettings>): ProjectResult {
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
  return computeProject(tables, OFFICIAL_1404_FEHREST, s, {
    rows: rows as never,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
}

function exportWb(result: ProjectResult, settings: ProjectSettings): XLSX.WorkBook {
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook(
      { projectName: "T116", reportNo: "1" } as never,
      result,
      settings,
      [] as never,
    );
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
    else if (typeof c?.v === "number") out.push(String(c.v));
  }
  return out;
}

/** همهٔ اعدادِ یک شیت (TS اعداد را به‌صورتِ سلولِ عددی می‌نویسد). */
function sheetNumbers(wb: XLSX.WorkBook, name: string): number[] {
  const ws = wb.Sheets[name] ?? {};
  const out: number[] = [];
  for (const addr in ws) {
    if (addr.startsWith("!")) continue;
    const c = ws[addr as never] as { v?: unknown } | undefined;
    if (typeof c?.v === "number") out.push(c.v);
  }
  return out;
}

describe("T116 — برچسب‌گذاریِ برآورد به‌هنگام (E-8 §۳)", () => {
  // ۱) موتور: فیلدهای جدید در خروجیِ برآورد (قطعی)
  it("engine final path has it_status and prov fields", () => {
    const res = pipeline({ baravordItPeriod: "q4" });
    const b = res.adjustment.baravord;
    expect(b).not.toBeNull();
    expect(b!.it_status).toBe("قطعی");
    expect(b!.prov).not.toBeNull();      // از ورودیِ دستی خوانده می‌شود
    expect(b!.prov_manual).toBe(true);   // PROV_COEF از ورودیِ دستی آمده
    expect(typeof b!.prov_trace).toBe("object");
    // در مسیرِ قطعی، ضریبِ موقت استفاده نمی‌شود (فقط برای It موقت است)
  });

  // ۲) موتور: فیلدهای جدید در خروجیِ برآورد (موقت)
  it("engine provisional path has prov value", () => {
    const res = pipeline({ baravordItPeriod: "1405Q1" });
    const b = res.adjustment.baravord;
    expect(b).not.toBeNull();
    expect(b!.it_status).toBe("موقت");
    expect(b!.prov).toBeCloseTo(PROV_COEF, 10);
    expect(b!.prov_manual).toBe(true);
    expect(typeof b!.prov_trace).toBe("object");
  });

  // ۳) شیتِ Excel: برچسب‌های It همیشه موجودند (مسیرِ قطعی)
  it("excel final sheet has It labels and no provisional row", () => {
    const s = { ...defaultSettings(), ...BASE, baravordItPeriod: "q4" };
    const res = pipeline({ baravordItPeriod: "q4" });
    const wb = exportWb(res, s);
    expect(wb.SheetNames).toContain("برآورد به‌هنگام");
    const strs = sheetStrings(wb, "برآورد به‌هنگام");
    const joined = strs.join("\n");
    expect(joined).toContain("دورهٔ مبنا (Io)");
    expect(joined).toContain("دورهٔ انجام کار (It)");
    expect(joined).toContain("وضعیت دورهٔ It");
    expect(joined).toContain("قطعی");
    // مسیرِ قطعی ⇒ ردیفِ ضریبِ موقت نباید باشد
    expect(joined).not.toContain("ضریب موقت (۱۴۰۵Q1)");
    // عددِ برآورد باید برچسبِ It داشته باشد (§۳.۲ — بدون It ممنوع)
    expect(joined).toContain("برآورد به‌هنگام‌شده (ریال)");
  });

  // ۴) شیتِ Excel: مسیرِ موقت ⇒ ضریبِ موقت نمایش داده می‌شود
  it("excel provisional sheet shows the provisional coefficient", () => {
    const s = { ...defaultSettings(), ...BASE, baravordItPeriod: "1405Q1" };
    const res = pipeline({ baravordItPeriod: "1405Q1" });
    const wb = exportWb(res, s);
    const strs = sheetStrings(wb, "برآورد به‌هنگام");
    const joined = strs.join("\n");
    expect(joined).toContain("وضعیت دورهٔ It");
    expect(joined).toContain("موقت");
    expect(joined).toContain("ضریب موقت (۱۴۰۵Q1)");
    // خودِ عددِ ضریب به‌صورتِ سلولِ عددی در شیت است
    const nums = sheetNumbers(wb, "برآورد به‌هنگام");
    expect(nums.some((n) => Math.abs(n - PROV_COEF) < 1e-9)).toBe(true);
    // راهنمایِ معنیِ ضریبِ موقت هم هست
    expect(joined).toContain("موقت = این ضریب × آخرین شاخص قطعی");
  });

  // ۵) شیتِ Excel در هر دو مسیر ساخته می‌شود
  it("excel sheet present with matching status in both paths", () => {
    for (const [extra, want] of [
      [{ baravordItPeriod: "q4" }, "قطعی"],
      [{ baravordItPeriod: "1405Q1" }, "موقت"],
    ] as const) {
      const res = pipeline(extra);
      const wb = exportWb(res, { ...defaultSettings(), ...BASE, ...extra });
      expect(wb.SheetNames).toContain("برآورد به‌هنگام");
      expect(sheetStrings(wb, "برآورد به‌هنگام").join("\n")).toContain(want);
    }
  });
});
