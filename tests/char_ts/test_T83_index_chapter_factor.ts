// T83 — شاخص تعدیل: ضریب فصل فقط روی همان فصل اثر می‌گذارد (بخش ۵).
//
// ضریب = I(هدف) ÷ I(مبنا) بر اساس دو رقم اول کد فهرست‌بها. اگر فقط فصل ۰۷
// شاخش ۳ برابر شود، فقط ردیف‌های 07xxxx ×۳ می‌شوند و بقیه دست‌نخورده
// می‌مانند. زنجیرهٔ مالی بعد از لایهٔ شاخص اعمال می‌شود.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { IndexTable } from "../../src/lib/indices";
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

// پایگاه پیش‌فرض: معادل دقیق _default_fehrest_db در پایتون.
function db() {
  return OFFICIAL_1404_FEHREST;
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

function tableWithCh07Tripled(): IndexTable {
  // دورهٔ مبنا ۱۴۰۳Q4 (همه ۱٫۰) + دورهٔ هدف با فصل ۰۷ = ۳٫۰
  const base = IndexTable.load();
  const targetRecs = base.records.map((r) => {
    const nr = { ...r, period: TARGET };
    if (r.chapter === "07") nr.value = 3.0;
    return nr;
  });
  return new IndexTable({
    base_period: base.basePeriod,
    periods: [...base.periods, TARGET],
    indices: [...base.records, ...targetRecs],
  });
}

describe("T83 — ضریب فصل فقط روی همان فصل", () => {
  it("فقط ردیف‌های 07xxxx ×۳ می‌شوند؛ بقیه دست‌نخورده", () => {
    const it = tableWithCh07Tripled();
    const [tables, mapping] = loadTablesAndMapping();
    const r0 = computeProject(
      tables, db(), defaultSettings(), mapping, it,
    );
    const r1 = computeProject(
      tables,
      db(),
      { ...defaultSettings(), indexTargetPeriod: TARGET } as ProjectSettings,
      mapping,
      it,
    );

    const ch07 = r0.lines.filter((l: any) => l.code.startsWith("07"));
    const other = r0.lines.filter((l: any) => !l.code.startsWith("07"));
    expect(ch07.length).toBeGreaterThanOrEqual(1); // پروژهٔ نمونه ۴ ردیف 07xxxx دارد
    for (const l of r1.lines) {
      if (l.code.startsWith("07")) expect(l.indexFactor).toBeCloseTo(3.0, 6);
      else expect(l.indexFactor).toBeCloseTo(1.0, 6);
    }

    const delta = ch07.reduce((a: number, l: any) => a + l.total, 0);
    expect(r1.baseTotal).toBeCloseTo(r0.baseTotal + 2 * delta, 0);
    // زنجیرهٔ مالی بعد از شاخص: grand = base جدید × ۱٫۳ × ۱٫۰۴ (منطقه‌ای)
    expect(r1.grandTotal).toBeCloseTo(r1.baseTotal * 1.3 * 1.04, 0);
    // ردیف‌های غیر-۰۷ تغییر نکرده‌اند (کلید شناسهٔ ردیف: پی و پله هر دو ۰۸۰۱۰۵)
    const byId: Record<string, number> = {};
    for (const l of r1.lines) byId[l.id] = l.total;
    for (const l of other) expect(byId[l.id]).toBeCloseTo(l.total, 6);
  }, 60000);

  it("گزارش، ضریب هر فصل را با منبع و نوع شاخص فهرست می‌کند", () => {
    const it = tableWithCh07Tripled();
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
    expect(rep.basePeriod).toBe("1403Q4");
    expect(rep.targetPeriod).toBe(TARGET);
    expect(rep.provisional).toBe(false);
    const factors: Record<string, number> = {};
    for (const row of rep.chapters) factors[row.chapter] = row.factor;
    expect(factors["07"]).toBeCloseTo(3.0, 6);
    for (const [ch, f] of Object.entries(factors)) {
      if (ch !== "07") expect(f).toBeCloseTo(1.0, 6);
    }
    // هر سطر منبع و نوع شاخص را دارد
    for (const row of rep.chapters) {
      expect(row.kind).toBe("قطعی");
      expect(row.source.length).toBeGreaterThan(0);
    }
  }, 60000);
});
