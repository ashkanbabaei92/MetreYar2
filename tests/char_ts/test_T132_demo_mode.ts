// ─────────────────────────────────────────────────────────────
// T132 — حالتِ ارائه (فاز E-10.1 §۳)
// (آینهٔ test_T132_demo_mode.py)
//
// پرچمِ demoMode واترمارکِ «نسخهٔ نمایشی – اعتبارسنجی‌نشده با صورت‌وضعیت
// تأییدشده» را روی همهٔ برگه‌های Excel و همهٔ مراحلِ UI می‌نشاند. این
// آزمون قفل می‌کند:
//   ۱) demoMode=true → واترمارک در همهٔ شیت‌های Excel هست؛
//   ۲) demoMode=false → واترمارک در هیچ شیتی نیست؛
//   ۳) واترمارکِ دمو و واترمارکِ «پیش‌نویس» کنار هم کار می‌کنند؛
//   ۴) پروژهٔ نمونه (examples/sample_project) در demoMode بارگذاری می‌شود.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { DEMO_BANNER, exportWorkbook } from "../../src/lib/exporters";
import { loadProjectProfileJson } from "../../src/lib/manualEntries";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectMeta, ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const SAMPLE_DIR = path.join(ROOT, "examples", "sample_project");

const DRAFT_BANNER = "پیش‌نویس – دورهٔ کارکرد وارد نشده";

const META: ProjectMeta = {
  projectName: "پروژه نمونه", employer: "کارفرما", contractor: "پیمانکار",
  consultant: "مشاور", contractNo: "۱", contractDate: "۱۴۰۴/۰۱/۰۱",
  location: "گرگان", reportNo: "۱", reportType: "دوره‌ای",
  periodStart: "۱۴۰۴/۰۱/۰۱", periodEnd: "۱۴۰۴/۰۳/۳۱",
};

const XLS_EXTRA: Partial<ProjectSettings> = {
  tadilEnabled: true,
  baravordEnabled: true,
  proposalDate: "۱۴۰۳/۱۲/۲۹",
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
  provisionalCoef1405q1: 1.1530518586507572,
  completedWithinTerm: true,
  contractStatus: "فسخ با قصور",
};

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function pipeline(over: Partial<ProjectSettings> = {}): ProjectResult {
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
  return computeProject(
    tables,
    OFFICIAL_1404_FEHREST,
    { ...defaultSettings(), ...XLS_EXTRA, ...over },
    { rows: rows as never, format: "v2", recordCount: rows.length, warnings: [] } as never,
  );
}

function exportWb(
  result: ProjectResult,
  settings: ProjectSettings,
  metaOverride?: Partial<ProjectMeta>,
): XLSX.WorkBook {
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook({ ...META, ...metaOverride } as ProjectMeta, result, settings, [] as never);
  } finally {
    mock.mockRestore();
  }
  return wb as XLSX.WorkBook;
}

function sheetValues(wb: XLSX.WorkBook): Record<string, unknown[]> {
  const out: Record<string, unknown[]> = {};
  for (const name of wb.SheetNames) {
    const rows = XLSX.utils.sheet_to_json<unknown[]>(wb.Sheets[name], { header: 1 });
    out[name] = rows.flat();
  }
  return out;
}

function sheetsWithout(values: Record<string, unknown[]>, needle: string): string[] {
  return Object.entries(values)
    .filter(([, vals]) => !vals.some((v) => typeof v === "string" && v.includes(needle)))
    .map(([name]) => name);
}

describe("T132 — حالتِ ارائه (فاز E-10.1 §۳)", () => {
  it("متنِ واترمارک دقیقاً پین شده است", () => {
    expect(DEMO_BANNER).toBe("نسخهٔ نمایشی – اعتبارسنجی‌نشده با صورت‌وضعیت تأییدشده");
  });

  it("demoMode=true → واترمارک روی همهٔ شیت‌ها", () => {
    const res = pipeline();
    const wb = exportWb(res, { ...defaultSettings(), ...XLS_EXTRA, demoMode: true });
    const values = sheetValues(wb);
    expect(Object.keys(values).length).toBeGreaterThan(0);
    expect(sheetsWithout(values, DEMO_BANNER)).toEqual([]);
  });

  it("demoMode=false → هیچ واترمارکی نیست", () => {
    const res = pipeline();
    const wb = exportWb(res, { ...defaultSettings(), ...XLS_EXTRA, demoMode: false });
    const hit = Object.entries(sheetValues(wb))
      .filter(([, vals]) => vals.some((v) => typeof v === "string" && v.includes(DEMO_BANNER)))
      .map(([name]) => name);
    expect(hit).toEqual([]);
  });

  it("demoMode و واترمارکِ پیش‌نویس کنار هم کار می‌کنند", () => {
    const res = pipeline({ workPeriodStart: "", workPeriodEnd: "" });
    // بدونِ دورهٔ کارکرد، خروجیِ نهایی ممنوع است — فقط پیش‌نویس مجاز است
    const wb = exportWb(
      res,
      { ...defaultSettings(), ...XLS_EXTRA, demoMode: true },
      { reportType: "پیش‌نویس" },
    );
    const values = sheetValues(wb);
    expect(sheetsWithout(values, DEMO_BANNER)).toEqual([]);
    expect(sheetsWithout(values, DRAFT_BANNER)).toEqual([]);
  });

  it("پروژهٔ نمونه در demoMode بارگذاری می‌شود", () => {
    const text = fs.readFileSync(
      path.join(SAMPLE_DIR, "project_profile.json"), "utf-8");
    const raw = JSON.parse(text);
    expect(raw.settings.demo_mode).toBe(true);
    // بارگذارِ پروفایل باید snake_case را به camelCase تبدیل کند
    const loaded = loadProjectProfileJson(text);
    expect(loaded.settings?.demoMode).toBe(true);
    // و خودِ Excelِ نمونه هم واترمارک دارد
    const buf = fs.readFileSync(path.join(SAMPLE_DIR, "sample_output.xlsx"));
    const wb = XLSX.read(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
    expect(sheetsWithout(sheetValues(wb), DEMO_BANNER)).toEqual([]);
  });
});
