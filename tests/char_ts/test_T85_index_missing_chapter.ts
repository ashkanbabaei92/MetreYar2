// T85 — شاخص تعدیل: فصل مفقود → خطای صریح (مرحلهٔ ۱۱ بخش ۵).
//
// اگر برای دورهٔ هدف شاخص یکی از فصل‌ها در indices/abnieh.json موجود
// نباشد، موتور باید با یک پیام خطای روشن متوقف شود — نه آنکه ساکت
// ضریب ۱ فرض کند (تعدیل پنهان می‌شود) و نه آنکه عددی از حافظه بسازد.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { IndexTable } from "../../src/lib/indices";
import { parseFehrestText, mergeFehrest } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { IndexTableData, ProjectSettings, RevitTable } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const TARGET = "1404Q1";

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

function db() {
  const fehrestFile = path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt");
  return mergeFehrest(
    OFFICIAL_1404_FEHREST,
    parseFehrestText(fs.readFileSync(fehrestFile, "utf-8")),
  );
}

function loadTablesAndMapping(): [RevitTable[], any] {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows = loadAllMappingRows();
  const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
  return [tables as never, mapping];
}

function tableMissingChapter(missing: string): IndexTable {
  // دورهٔ هدف که شاخص همهٔ فصل‌ها را دارد به‌جز «missing»
  const base = IndexTable.load();
  const targetRecs = base.records
    .filter((r) => r.chapter !== missing)
    .map((r) => ({ ...r, period: TARGET }));
  return new IndexTable({
    base_period: base.basePeriod,
    periods: [...base.periods, TARGET],
    indices: [...base.records, ...targetRecs],
  });
}

describe("T85 — فصل مفقود در شاخص", () => {
  it("factor برای کد فصل مفقود خطا می‌دهد", () => {
    const it = tableMissingChapter("08");
    expect(() => it.factor("080106", TARGET)).toThrow(/فصل 08/);
    expect(() => it.factor("080105", TARGET)).toThrow();
  });

  it("موتور قبل از هر خروجی ناقص متوقف می‌شود", () => {
    const [tables, mapping] = loadTablesAndMapping();
    const it = tableMissingChapter("08");
    expect(() =>
      computeProject(
        tables,
        db(),
        { ...defaultSettings(), indexTargetPeriod: TARGET } as ProjectSettings,
        mapping,
        it,
      ),
    ).toThrow(/شاخص/);
  }, 60000);

  it("گزارش، فصل مفقود را با ضریب null نشان می‌دهد (نه ۱)", () => {
    const it = tableMissingChapter("10");
    const rep = it.report(TARGET);
    const row10 = rep.chapters.find((row: any) => row.chapter === "10");
    expect(row10.factor).toBe(null);
    const row08 = rep.chapters.find((row: any) => row.chapter === "08");
    expect(row08.factor).toBeCloseTo(1.0, 6);
  });

  it("شاخص دورهٔ مبنا صفر → خطای صریح (تقسیم بر صفر ممنوع)", () => {
    const it = new IndexTable({
      base_period: "1403Q4",
      periods: ["1403Q4", "1404Q1"],
      indices: [
        { period: "1403Q4", chapter: "08", value: 0.0, kind: "قطعی", source: "s" },
        { period: "1404Q1", chapter: "08", value: 1.5, kind: "قطعی", source: "s" },
      ],
    } as IndexTableData);
    expect(() => it.factor("080106", "1404Q1")).toThrow();
  });
});
