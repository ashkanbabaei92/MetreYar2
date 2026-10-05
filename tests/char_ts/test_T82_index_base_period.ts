// T82 — لایهٔ شاخص تعدیل: دورهٔ هدف = دورهٔ مبنا (مرحلهٔ ۱۱ بخش ۵).
//
// کلیات فهرست‌بهای ۱۴۰۴ بند ۲۲: ضریب تعدیل هر فصل = I(دورهٔ هدف) ÷
// I(دورهٔ مبنا) روی مبلغ ردیف، قبل از ضرایب زنجیرهٔ مالی. اگر دورهٔ هدف
// برابر دورهٔ مبنا باشد ضریب همهٔ فصل‌ها ۱ است و خروجی bit-identical با
// حالت بدون شاخص می‌ماند — همین رفتار آزمون می‌شود.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { IndexTable } from "../../src/lib/indices";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function loadAllMappingRows() {
  const rows: any[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const subDir = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(subDir).isDirectory()) continue;
    for (const fn of fs.readdirSync(subDir).sort()) {
      if (!fn.endsWith(".txt")) continue;
      rows.push(...parseDynamoMapping(toBuffer(path.join(subDir, fn)), fn).rows);
    }
  }
  return rows;
}

// پایگاه پیش‌فرض: معادل دقیق _default_fehrest_db در پایتون.
function db() {
  return OFFICIAL_1404_FEHREST;
}

function pipeline(settings: ProjectSettings): any {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows = loadAllMappingRows();
  const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
  return computeProject(tables as never, db(), settings, mapping as never);
}

describe("T82 — شاخص تعدیل در دورهٔ مبنا", () => {
  it("فایل indices/abnieh.json: دورهٔ مبنا ۱۴۰۳Q4، همهٔ فصل‌ها قطعی و ۱٫۰", () => {
    const it = IndexTable.load();
    expect(it.basePeriod).toBe("1403Q4");
    expect(it.periods).toEqual(["1403Q4"]);
    const chapters = new Set(it.records.map((r) => r.chapter));
    expect(chapters.size).toBeGreaterThanOrEqual(28);
    for (const r of it.records) {
      expect(r.kind).toBe("قطعی");
      expect(r.value).toBeCloseTo(1.0, 6);
      expect(r.source.length).toBeGreaterThan(0); // هر رکورد منبع بخشنامه دارد
    }
    // ضریب هر کد در دورهٔ مبنا = ۱
    for (const code of ["080106", "070202", "100305", "060501", "280101", "080102"]) {
      expect(it.factor(code, "1403Q4")).toBeCloseTo(1.0, 6);
    }
  });

  it("پیش‌فرض indexTargetPeriod=null → دورهٔ مبنا → همهٔ ضرایب ۱", () => {
    const r = pipeline(defaultSettings());
    expect(defaultSettings().indexTargetPeriod).toBe(null);
    for (const l of r.lines) {
      expect(l.indexFactor).toBeCloseTo(1.0, 6);
      expect(l.totalIndexed).toBeCloseTo(l.total, 6);
    }
    expect(r.index).toBe(null); // گزارش شاخص فقط هنگام تعدیل واقعی تولید می‌شود
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 0);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 0);
  }, 30000);

  it("تعیین صریح دورهٔ مبنا به‌عنوان هدف → همان خروجی دقیق", () => {
    const rImplicit = pipeline(defaultSettings());
    const rExplicit = pipeline({
      ...defaultSettings(),
      indexTargetPeriod: "1403Q4",
    });
    expect(rExplicit.lines).toHaveLength(rImplicit.lines.length);
    for (const [a, b] of rImplicit.lines.map((x: any, i: number) => [x, rExplicit.lines[i]])) {
      expect(b.code).toBe(a.code);
      expect(b.indexFactor).toBeCloseTo(1.0, 6);
      expect(b.totalIndexed).toBeCloseTo(a.totalIndexed, 6);
    }
    expect(rExplicit.baseTotal).toBeCloseTo(rImplicit.baseTotal, 4);
    expect(rExplicit.grandTotal).toBeCloseTo(rImplicit.grandTotal, 4);
  }, 60000);

  it("جدول خالی (بدون دورهٔ مبنا) → هیچ تعدیلی؛ ضریب ۱ برای هر کد", () => {
    const it = IndexTable.empty();
    expect(it.basePeriod).toBe(null);
    expect(it.factor("080106", "anything")).toBeCloseTo(1.0, 6);
    const r = computeProject([], db(), defaultSettings(), undefined, IndexTable.empty());
    expect(r.index).toBe(null);
  });
});
