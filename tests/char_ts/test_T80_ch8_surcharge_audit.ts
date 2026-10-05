// T80 — حسابرسی پایهٔ اضافه‌بهای فصل ۸ (مرحلهٔ ۱۱ بخش ۳).
//
// فصل ۸ بند ۳-۵: ردیف‌های ۰۸۰۳۰۱/۰۸۰۳۰۲/۰۸۰۳۰۴/۰۸۰۳۱۰/۰۸۰۳۱۱ به سقف
// تیرچه‌بلوک تعلق نمی‌گیرد → حجم JSL (تیرچه + رویهٔ JSL-TOP*) از پایهٔ
// همهٔ اضافه‌بها کسر می‌شود.
// فصل ۸ بند ۳-۳ (۰۸۰۳۰۴): فقط دال روی زمین (ردیفی که در جدول خودش هم
// حجم و هم مساحت دارد)؛ سقف‌های معلق شامل نمی‌شوند.
// فصل ۸ بند ۳-۶ (۰۸۰۳۱۰): per-element — فقط المان‌های با تراکم خودشان
// بالای ۱۸۰ kg/m³، نه میانگین پروژه.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import {
  computeProject,
  defaultSettings,
  joistSystemRefs,
  rebarDensity,
  REBAR_DENSITY_THRESHOLD,
  thinConcreteNet,
} from "../../src/lib/engine";
import { parseFehrestText, mergeFehrest } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, RevitTable } from "../../src/lib/types";

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

function db() {
  const fehrestFile = path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt");
  return mergeFehrest(
    OFFICIAL_1404_FEHREST,
    parseFehrestText(fs.readFileSync(fehrestFile, "utf-8")),
  );
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

function loadTables(): RevitTable[] {
  return fs
    .readdirSync(REVIT_DIR)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
}

function mkTable(kind: RevitTable["kind"], rows: [Record<string, number>, Record<string, string>][]): RevitTable {
  return {
    id: "t1",
    fileName: "t.txt",
    title: "T",
    headers: [],
    kind,
    kindConfidence: 0.9,
    colMap: {},
    warnings: [],
    grandTotal: {},
    rows: rows.map(([values, texts]) => ({ cells: [], values, texts, isSubtotal: false })),
  };
}

describe("T80 — حسابرسی پایهٔ اضافه‌بهای فصل ۸", () => {
  it("روی پروژهٔ نمونه با هر سه تنظیم فعال، فقط ۰۸۰۳۰۴ اضافه می‌شود", () => {
    // ۰۸۰۳۱۱: تراکم ≈ ۳۱ kg/m³ < ۱۸۰. ۰۸۰۳۱۰: بالاترین تراکم المانی
    // (B04-ST01) = ۱۵۳٫۹۷ < ۱۸۰. ۰۸۰۳۰۴: بتن مگر کف روی زمین (۹٫۹۷ cm).
    const off = pipeline(defaultSettings());
    const on = pipeline({
      ...defaultSettings(),
      surchargeRebarDensity: true,
      surchargeReinforcedConcrete: true,
      surchargeThinConcrete: true,
    });
    const codes = on.lines.map((l: any) => l.code);
    expect(codes.filter((c: string) => c === "080304")).toHaveLength(1);
    expect(codes).not.toContain("080310");
    expect(codes).not.toContain("080311");
    expect(on.lines).toHaveLength(off.lines.length + 1);
    const thin = on.lines.find((l: any) => l.code === "080304");
    expect(thin.qty).toBeCloseTo(18.65, 6);
    expect(on.baseTotal).toBeCloseTo(off.baseTotal + thin.total, 0);
  }, 60000);

  it("پایهٔ ۰۸۰۳۰۴: فقط ردیف دارای حجم+مساحت در جدول خودش (دال روی زمین)", () => {
    const tables = loadTables();
    // بتن مگر: 18.65 m³ بر 125 m² → 14.97 cm ≤ 15 ✓
    expect(thinConcreteNet(tables as never)).toBeCloseTo(18.65, 6);
    // JSL-TOP01 (رویهٔ سقف معلق) جزو سیستم تیرچه است
    expect(joistSystemRefs(tables as never).has("JSL-TOP01-ST01")).toBe(true);
  }, 30000);

  it("پایهٔ هر سه اضافه‌بها حجم JSL را کسر می‌کند (بند ۳-۵)", () => {
    // المان‌ها: DENSE-01 (ستون ۱ m³، ۲۰۰ kg → ۲۰۰ > ۱۸۰)، SL-G (دال روی
    // زمین ۱ m³ و ۸ m² → ۱۲٫۵ cm ≤ ۱۵ ✓)، JSL-TOP01 (رویهٔ ۲٫۵۸ m³، ۵۰۰ kg
    // → ۱۹۳٫۸ > ۱۸۰ اما مستثنی).
    const tables = [
      mkTable("structural_concrete", [
        [{ volume: 1.0 }, { mark: "DENSE-01", category: "Structural Column", familyType: "Column" }],
        [{ volume: 1.0, area: 8.0 }, { mark: "SL-G", category: "Floor", familyType: "Slab" }],
        [{ volume: 2.58 }, { mark: "JSL-TOP01", category: "Floor", familyType: "Slab" }],
      ]),
      mkTable("joist_floor", [
        [{ length: 5.0, count: 1 }, { mark: "JSL01-ST01", level: "L0" }],
      ]),
      mkTable("rebar_detailed", [
        [{ weight: 200.0 }, { hostMark: "DENSE-01" }],
        [{ weight: 500.0 }, { hostMark: "JSL-TOP01" }],
      ]),
    ];
    const r = computeProject(
      tables as never,
      db(),
      {
        ...defaultSettings(),
        surchargeRebarDensity: true,
        surchargeReinforcedConcrete: true,
        surchargeThinConcrete: true,
      },
    );
    const by: Record<string, number> = {};
    for (const l of r.lines) by[l.code] = l.qty;

    // ۰۸۰۳۰۴: فقط SL-G (دال روی زمین)؛ JSL-TOP01 مستثنی (سقف معلق)
    expect(by["080304"]).toBeCloseTo(1.0, 9);
    // ۰۸۰۳۱۰: فقط DENSE-01؛ JSL-TOP01 با وجود تراکم ۱۹۳٫۸ > ۱۸۰ مستثنی است
    expect(by["080310"]).toBeCloseTo(1.0, 9);
    // ۰۸۰۳۱۱: پایه = حجم سازه‌ای بدون JSL = ۱ + ۱ = ۲ m³ (رویه مستثنی)
    expect(by["080311"]).toBeCloseTo(2.0, 9);
    // تراکمی که اضافه‌بها را روشن می‌کند: ۷۰۰ kg ÷ ۲ m³ = ۳۵۰ > ۱۸۰
    expect(rebarDensity(700.0, 2.0)).toBeGreaterThan(REBAR_DENSITY_THRESHOLD);
  }, 30000);
});
