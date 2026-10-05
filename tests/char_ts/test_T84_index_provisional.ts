// T84 — شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل (مرحلهٔ ۱۱ بخش ۵).
//
// رکورد موقت مقدارش یک «ضریب» نسبت به آخرین شاخص قطعیِ قبل از آن دوره
// است: I(موقت) = value × I(قطعی دورهٔ قبل). ضریب تعدیل = I(هدف) ÷ I(مبنا).
// گزارش، شاخص موقت را با پرچم provisional و برچسب «موقت» نشان می‌دهد.
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

function tableWithProvisional07(factor: number): IndexTable {
  // دورهٔ هدف: فصل ۰۷ موقت با ضریب داده‌شده، بقیه قطعی ۱٫۰
  const base = IndexTable.load();
  const targetRecs = base.records.map((r) => {
    const nr = { ...r, period: TARGET };
    if (r.chapter === "07") {
      nr.kind = "موقت";
      nr.value = factor;
      nr.source = "بخشنامهٔ موقت آزمایشی — شماره ۹۹/۹۹۹۹۹";
    }
    return nr;
  });
  return new IndexTable({
    base_period: base.basePeriod,
    periods: [...base.periods, TARGET],
    indices: [...base.records, ...targetRecs],
  });
}

describe("T84 — شاخص موقت", () => {
  it("موقت ۱٫۵ روی قطعی ۳٫۰ → مستوى ۴٫۵ → ضریب ۴٫۵ برای فصل ۰۷", () => {
    const base = IndexTable.load();
    const mid = "1404Q1";
    const target = "1404Q2";
    const recs = [...base.records]; // 1403Q4 همه ۱٫۰
    for (const r of base.records) {
      // دورهٔ میانی: فصل ۰۷ قطعی ۳٫۰
      const nr = { ...r, period: mid };
      if (r.chapter === "07") nr.value = 3.0;
      recs.push(nr);
    }
    for (const r of base.records) {
      // دورهٔ هدف: فصل ۰۷ موقت ۱٫۵
      const nr = { ...r, period: target, kind: "موقت" as const,
                   source: "بخشنامهٔ موقت آزمایشی" };
      if (r.chapter === "07") nr.value = 1.5;
      recs.push(nr);
    }
    const it = new IndexTable({
      base_period: base.basePeriod,
      periods: [...base.periods, mid, target],
      indices: recs,
    } as IndexTableData);
    expect(it.factor("070202", target)).toBeCloseTo(4.5, 6);
    // سایر فصل‌ها: موقت ۱٫۰ × قطعی ۱٫۰ = ۱٫۰
    expect(it.factor("080106", target)).toBeCloseTo(1.0, 6);
    expect(it.factor("100305", target)).toBeCloseTo(1.0, 6);
  });

  it("موتور شاخص موقت را با پرچم provisional در گزارش نشان می‌دهد", () => {
    const it = tableWithProvisional07(1.5);
    const [tables, mapping] = loadTablesAndMapping();
    const r = computeProject(
      tables,
      db(),
      { ...defaultSettings(), indexTargetPeriod: TARGET } as ProjectSettings,
      mapping,
      it,
    );
    const rep = r.index;
    expect(rep).not.toBe(null);
    expect(rep.provisional).toBe(true);
    const kinds: Record<string, string> = {};
    const factors: Record<string, number> = {};
    for (const row of rep.chapters) {
      kinds[row.chapter] = row.kind;
      factors[row.chapter] = row.factor;
    }
    expect(kinds["07"]).toBe("موقت");
    // فصل ۰۷ موقت ۱٫۵ × قطعی ۱٫۰ = ۱٫۵
    expect(factors["07"]).toBeCloseTo(1.5, 6);
    for (const [ch, f] of Object.entries(factors)) {
      if (ch !== "07") expect(f).toBeCloseTo(1.0, 6);
    }
    for (const l of r.lines) {
      if (l.code.startsWith("07")) expect(l.indexFactor).toBeCloseTo(1.5, 6);
      else expect(l.indexFactor).toBeCloseTo(1.0, 6);
    }
    // منبع بخشنامه در گزارش هست
    const row07 = rep.chapters.find((row: any) => row.chapter === "07");
    expect(row07.source.length).toBeGreaterThan(0);
  }, 60000);

  it("شاخص موقت بدون شاخص قطعیِ دورهٔ قبل → خطای صریح", () => {
    const it = new IndexTable({
      base_period: "1403Q4",
      periods: ["1403Q4", "1404Q1"],
      indices: [
        { period: "1403Q4", chapter: "08", value: 1.0, kind: "موقت",
          source: "s" }, // مبنا هم موقت!
        { period: "1404Q1", chapter: "08", value: 1.5, kind: "موقت", source: "s" },
      ],
    } as IndexTableData);
    expect(() => it.factor("080106", "1404Q1")).toThrow();
  });
});
