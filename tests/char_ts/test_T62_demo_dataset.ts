// T62 - مسیر دادهٔ نمونهٔ داخلی (DEMO_FILES) با golden اختصاصی
//
// پروژهٔ نمونهٔ تعبیه‌شده («بارگذاری دادهٔ نمونهٔ واقعی» در UI) یک زیرمجموعهٔ
// قدیمی‌تر از فایل‌های data/export revit است: ۹ جدول در برابر ۱۰، جدول
// بتن‌ریزی پی را ندارد، جدول آرماتور فقط یک «بخش نمونه» است، و فرمت
// نقل‌قول‌گذاری CSV استاندارد است (نه doubled-quote خروجی واقعی Revit).
// به همین دلیل مجموع آن با مسیر فایل‌های واقعی متفاوت است و golden
// مستقلی دارد. این تست تضمین می‌کند که مسیر دمو در دو زبان یکسان می‌ماند.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { mergeFehrest, parseFehrestText } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { DEMO_FILES } from "../../src/data/demo";
import { record } from "./helper";

const ROOT = path.join(__dirname, "..", "..");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const FEHREST_FILE = path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt");

function loadMergedMapping() {
  const rows: any[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const subDir = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(subDir).isDirectory()) continue;
    for (const fn of fs.readdirSync(subDir).sort()) {
      if (!fn.endsWith(".txt")) continue;
      const b = fs.readFileSync(path.join(subDir, fn));
      const buf = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
      rows.push(...parseDynamoMapping(buf, fn).rows);
    }
  }
  return { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
}

function demoPipeline() {
  const tables = DEMO_FILES.map((d) => parseRevitFile(d.name, d.text));
  const rows = parseFehrestText(fs.readFileSync(FEHREST_FILE, "utf-8"));
  const db = mergeFehrest(OFFICIAL_1404_FEHREST, rows);
  const r = computeProject(tables as never, db, defaultSettings(), loadMergedMapping());
  return { tables, r };
}

describe("T62 — مسیر دادهٔ نمونهٔ داخلی", () => {
  it("دادهٔ نمونه با فایل‌های واقعی فرق دارد", () => {
    const revitDir = path.join(ROOT, "data", "export revit");
    const diskNames = fs.readdirSync(revitDir).sort().filter((f) => f.endsWith(".txt"));
    const demoNames = DEMO_FILES.map((d) => d.name).sort();
    expect(demoNames).not.toEqual(diskNames);
    expect(demoNames).toHaveLength(9);
    expect(diskNames).toHaveLength(10);
  });

  it("golden مسیر دمو پایدار است و با پایتون یکسان", () => {
    const { tables, r } = demoPipeline();
    const snap = {
      tables: tables.length,
      lines: r.lines.length,
      base_total: Math.round(r.baseTotal * 100) / 100,
      grand_total: Math.round(r.grandTotal * 100) / 100,
    };
    record("T62_demo_pipeline", snap, process.env.GENERATE === "1");
    expect(snap.tables).toBe(9);
    expect(snap.lines).toBe(16);
    expect(snap.base_total).toBeCloseTo(20380352396.27, 0);
    // مرحلهٔ ۱۳: ضریب منطقه‌ای پیش‌فرض (گرگان ۱٫۰۴) در زنجیره اعمال می‌شود.
    expect(snap.grand_total).toBeCloseTo(20380352396.27 * 1.3 * 1.04, 0);
  });
});
