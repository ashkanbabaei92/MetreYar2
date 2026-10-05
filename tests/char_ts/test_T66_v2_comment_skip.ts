// T66 - رد سطرهای خلاصه/کامنت (شروع با #) در پارسر Mapping نسخهٔ ۲.
//
// فایل v2 (map3.txt) با سطر پایانی «# مجموع  تعداد کل المان‌ها: ۲۷۹» تمام
// می‌شود. پیش از این، این سطر به‌عنوان یک رکورد داده‌ای با کمیت‌های صفر
// جذب می‌شد (۲۸۰ رکورد در map3، ۸۳۶ رکورد پس از merge با map2). در عمل
// بی‌اثر بود چون همهٔ کمیت‌ها صفر است، ولی شمارش رکوردها را آلوده می‌کرد.
// اکنون سطرهای #دار صریحاً رد می‌شوند (۲۷۹ / ۸۳۵) و totals بی‌تغییر می‌مانند.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { parseFehrestText, mergeFehrest } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";

const ROOT = path.join(__dirname, "..", "..");
const MAP3 = path.join(ROOT, "data", "dynamo", "mapping3", "map3.txt");
const MAP2 = path.join(ROOT, "data", "dynamo", "mapping2", "map2.txt");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function parsePath(p: string) {
  return parseDynamoMapping(toBuffer(p), path.basename(p));
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

describe("T66 — رد سطرهای #دار در v2", () => {
  it("map3 (v2) سطر خلاصهٔ #دار را رد می‌کند: ۲۷۹ رکورد، نه ۲۸۰", () => {
    const fx = parsePath(MAP3);
    expect(fx.format).toBe("v2");
    expect(fx.recordCount).toBe(279);
    expect(fx.rows.every((r: any) => !String(r.element_id).trimStart().startsWith("#")))
      .toBe(true);
  });

  it("merge دو فایل Mapping: ۵۵۶ (v1) + ۲۷۹ (v2) = ۸۳۵ رکورد، نه ۸۳۶", () => {
    const m2 = parsePath(MAP2);
    const m3 = parsePath(MAP3);
    expect(m2.format).toBe("v1");
    expect(m2.recordCount).toBe(556);
    expect(m3.format).toBe("v2");
    expect(m3.recordCount).toBe(279);
    const rows = loadAllMappingRows();
    expect(rows).toHaveLength(835);
  });

  it("حذف سطر خلاصه نباید هیچ کمیت/مبلغی را تغییر دهد", () => {
    const tables = fs.readdirSync(REVIT_DIR).sort()
      .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
    const rows = loadAllMappingRows();
    const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
    const fehrestFile = path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt");
    const db = mergeFehrest(OFFICIAL_1404_FEHREST, parseFehrestText(fs.readFileSync(fehrestFile, "utf-8")));
    const r: any = computeProject(tables as never, db, defaultSettings(), mapping as never);

    expect(r.lines).toHaveLength(17);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 0);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 0);
  });
});
