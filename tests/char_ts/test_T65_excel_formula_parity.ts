// T65 - تطابق فرمول‌های زندهٔ Excel میان خروجی Python و TypeScript.
//
// صادرکنندهٔ TS اکنون (پاریتی با app.py) سه فرمول =SUM زنده همراه با
// مقدار کش‌شده (v) و قالب عدد (z) می‌نویسد:
//   1. جمع مبالغ فصول در برگهٔ «خلاصه مالی» (ستون C)
//   2. جمع کل بهای کل در برگهٔ «صورت وضعیت» (ستون J)
//   3. جمع کل مقدار در برگهٔ «صورت وضعیت» (ستون F)
//
// این تست:
//   • سلول‌های فرمول‌دار را از خروجی واقعی استخراج می‌کند،
//   • مقدار کش‌شده را برابر با جمع واقعی سلول‌های بازه می‌سنجد،
//   • نتیجه را با golden تولیدشده توسط Python (test_T65_excel_formula_parity.py)
//     مقایسه می‌کند → تطابق کامل دو زبان.
import { describe, it, expect, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { exportWorkbook } from "../../src/lib/exporters";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { parseFehrestText, mergeFehrest } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { record, loadJson, goldenPath } from "./helper";

const ROOT = path.join(__dirname, "..", "..");

function realPipeline() {
  const revitDir = path.join(ROOT, "data", "export revit");
  const tables = fs.readdirSync(revitDir).sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(revitDir, f), "utf-8")));
  const rows: any[] = [];
  const dynamoDir = path.join(ROOT, "data", "dynamo");
  for (const sub of fs.readdirSync(dynamoDir).sort()) {
    const subDir = path.join(dynamoDir, sub);
    if (!fs.statSync(subDir).isDirectory()) continue;
    for (const fn of fs.readdirSync(subDir).sort()) {
      if (!fn.endsWith(".txt")) continue;
      const b = fs.readFileSync(path.join(subDir, fn));
      rows.push(...parseDynamoMapping(
        b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as never, fn).rows);
    }
  }
  const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
  const fehrestFile = path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt");
  const db = mergeFehrest(OFFICIAL_1404_FEHREST, parseFehrestText(fs.readFileSync(fehrestFile, "utf-8")));
  return computeProject(tables as never, db, defaultSettings(), mapping as never);
}

/** استخراج سلول‌های فرمول‌دار از کتاب‌کار صادرشده:
 * {«برگه!آدرس»: {f, v, z}} — مانند نسخهٔ پایتون. */
function formulaCells(result: any, settings: any): Record<string, any> {
  let wb: any;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: any) => { wb = value; });
  try {
    exportWorkbook({ projectName: "T65", reportNo: "1" } as any, result, settings, []);
  } finally {
    mock.mockRestore();
  }
  const out: Record<string, any> = {};
  for (const sheet of wb.SheetNames) {
    const ws = wb.Sheets[sheet];
    const ref = (ws["!ref"] as string) || "A1";
    const range = XLSX.utils.decode_range(ref);
    for (let r = range.s.r; r <= range.e.r; r++) {
      for (let c = range.s.c; c <= range.e.c; c++) {
        const addr = XLSX.utils.encode_cell({ r, c });
        const cell = ws[addr];
        if (cell && cell.f) {
          out[`${sheet}!${addr}`] = { f: cell.f, v: cell.v, z: cell.z };
        }
      }
    }
  }
  return out;
}

describe("T65 — فرمول‌های زندهٔ Excel برابر خروجی Python", () => {
  it("هر سه فرمول زنده وجود دارند", () => {
    const r = realPipeline();
    const fx = formulaCells(r, defaultSettings());
    expect(Object.keys(fx)).toHaveLength(3);
    const fs_ = Object.values(fx).map((x: any) => x.f);
    expect(fs_.some((f) => f.startsWith("SUM(C"))).toBe(true);
    expect(fs_.some((f) => f.startsWith("SUM(J"))).toBe(true);
    expect(fs_.some((f) => f.startsWith("SUM(F"))).toBe(true);
  });

  it("مقدار کش‌شده برابر جمع سلول‌های بازه است", () => {
    const r = realPipeline();
    const fx = formulaCells(r, defaultSettings());
    let wb: any;
    const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: any) => { wb = value; });
    exportWorkbook({ projectName: "T65", reportNo: "1" } as any, r, defaultSettings(), []);
    mock.mockRestore();

    for (const [addr, info] of Object.entries(fx)) {
      const [sheet, coord] = [addr.slice(0, addr.indexOf("!")), addr.slice(addr.indexOf("!") + 1)];
      const m = /^SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)$/.exec(info.f);
      expect(m, `unparsed formula: ${info.f}`).not.toBeNull();
      const col1 = m![1], r1 = +m![2], r2 = +m![4];
      const ws = wb.Sheets[sheet];
      let total = 0;
      for (let row = r1; row <= r2; row++) {
        const v = ws[`${col1}${row}`]?.v;
        if (typeof v === "number") total += v;
      }
      expect(info.v).toBeCloseTo(total, 2);
    }
  });

  it("با golden تولیدشده توسط Python برابر است", () => {
    const r = realPipeline();
    const fx = formulaCells(r, defaultSettings());
    const snap: Record<string, any> = {};
    for (const [k, v] of Object.entries(fx).sort()) {
      snap[k] = {
        f: v.f,
        v: typeof v.v === "number" ? Math.round(v.v * 1e6) / 1e6 : v.v,
        z: v.z,
      };
    }
    record("T65_excel_formulas", { formulas: snap }, process.env.GENERATE === "1");
    const golden = loadJson(goldenPath("T65_excel_formulas"));
    expect(snap).toEqual(golden.formulas);
  });
});
