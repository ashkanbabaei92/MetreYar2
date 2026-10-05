// T79 — بقایای سقف تیرچه‌بلوک در ردیف بتن (مرحلهٔ ۱۱ بخش ۲).
//
// فصل ۱۰ بند ۳ (الزامات عمومی): نرخ ۱۰۰۳۰۵ شامل تمام مصالح سقف به‌جز
// میلگرد است → بتن پاشنهٔ تیرچه (joist_materials) دیگر به ۰۸۰۱۰۶ اضافه
// نمی‌شود؛ پاشنه کلاً حذف می‌شود.
//
// فصل ۱۰ بند ۹: بتن تا ۵ cm روی بلوک داخل نرخ ۱۰۰۳۰۵ است → معادل
// ۰٫۰۵ × مساحت ۱۰۰۳۰۵ از حجم رویهٔ JSL-TOP* کسر می‌شود و فقط مازاد بر آن
// در ردیف ۰۸۰۱۰۶ می‌ماند:
//     مساحت ۱۰۰۳۰۵ = 74.48456 × 0.55 = 40.966508 m²
//     سهم داخل نرخ = 0.05 × 40.966508 = 2.048325 m³
//     حجم رویهٔ JSL-TOP01 = 2.58 m³ → باقی‌مانده = 0.531675 m³
// دال ساده (SL01) سراسر محاسبه می‌شود (تغییری نمی‌یابد).
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
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

describe("T79 — بقایای سقف تیرچه‌بلوک", () => {
  it("پاشنهٔ تیرچه (JSL01-ST01، ۰٫۳۴ m³) از همهٔ ردیف‌ها حذف می‌شود", () => {
    const r = pipeline(defaultSettings());
    for (const l of r.lines) {
      for (const src of l.sources ?? []) {
        expect(src.kind).not.toBe("joist_materials");
      }
    }
    // ردیف ۰۸۰۱۰۶ شامل دال ساده + باقی‌ماندهٔ رویه است؛ پاشنه در آن نیست
    const slab = r.lines.find((l: any) => l.id === "conc-slab");
    const refs = new Set(slab.sources.map((s: any) => s.ref));
    expect(refs.has("SL01-ST01")).toBe(true);
    expect(refs.has("JSL-TOP01-ST01")).toBe(true);
    // هیچ منبعی مقدار ۰٫۳۴ (پاشنه) ندارد
    const has034 = r.lines.some((l: any) =>
      (l.sources ?? []).some((s: any) => Math.abs((s.qty ?? 0) - 0.34) < 1e-9));
    expect(has034).toBe(false);
  }, 30000);

  it("مقادیر دقیق: مساحت، سهم داخل نرخ، باقی‌مانده و کمیت نهایی سقف", () => {
    const r = pipeline(defaultSettings());
    const slab = r.lines.find((l: any) => l.id === "conc-slab");
    const jb = r.lines.find((l: any) => l.id === "joist-block");
    const area = jb.qty;
    expect(area).toBeCloseTo(40.966508, 6);
    const allowance = 0.05 * area;
    expect(allowance).toBeCloseTo(2.0483254, 6);
    // باقی‌ماندهٔ رویه = ۲٫۵۸ − سهم داخل نرخ
    const topping = slab.sources.filter((s: any) =>
      String(s.ref ?? "").startsWith("JSL-TOP"));
    const residual = topping.reduce((a: number, s: any) => a + s.qty, 0);
    expect(residual).toBeCloseTo(2.58 - allowance, 6);
    expect(residual).toBeCloseTo(0.531675, 6);
    // دال ساده سراسر + باقی‌مانده
    const plain = slab.sources.filter((s: any) =>
      !String(s.ref ?? "").startsWith("JSL-TOP"));
    expect(plain.reduce((a: number, s: any) => a + s.qty, 0)).toBeCloseTo(2.1, 6);
    expect(slab.qty).toBeCloseTo(2.1 + residual, 6);
    expect(slab.qty).toBeCloseTo(2.631675, 6);
  }, 30000);

  it("SL01 تغییر نمی‌کند و یادداشت ردیف کسر را مستند می‌کند", () => {
    const r = pipeline(defaultSettings());
    const slab = r.lines.find((l: any) => l.id === "conc-slab");
    const sl01 = slab.sources.filter((s: any) => s.ref === "SL01-ST01");
    expect(sl01).toHaveLength(1);
    expect(sl01[0].qty).toBeCloseTo(2.1, 6);
    const note = String(slab.note ?? "");
    expect(note).toContain("۱۰۰۳۰۵");
    expect(note).toContain("بند ۹");
  }, 30000);

  it("قاعدهٔ عام برای هر تعداد علامت JSL-TOP*: کسر متناسب با حجم", () => {
    // دو رویهٔ ۱ m³ هر کدام + یک دال ۲٫۵ m³ + ۱۰ m تیرچه → مساحت ۵٫۵ m²،
    // سهم داخل نرخ ۰٫۲۷۵ m³، سهم هر رویه ۰٫۱۳۷۵ m³ → باقی‌ماندهٔ هر کدام
    // ۰٫۸۶۲۵ m³؛ کمیت سقف = ۲٫۵ + ۱٫۷۲۵ = ۴٫۲۲۵ m³.
    const tables = [
      mkTable("structural_concrete", [
        [{ volume: 1.0 }, { mark: "JSL-TOP01", category: "Floor", familyType: "Slab" }],
        [{ volume: 1.0 }, { mark: "JSL-TOP02", category: "Floor", familyType: "Slab" }],
        [{ volume: 2.5 }, { mark: "SL01", category: "Floor", familyType: "Slab" }],
      ]),
      mkTable("joist_floor", [
        [{ length: 10.0, count: 1 }, { mark: "JSL01-ST01", level: "L0" }],
      ]),
    ];
    const r = computeProject(tables as never, db(), defaultSettings());
    const slab = r.lines.find((l: any) => l.id === "conc-slab");
    expect(slab.qty).toBeCloseTo(4.225, 9);
    const jb = r.lines.find((l: any) => l.id === "joist-block");
    expect(jb.qty).toBeCloseTo(5.5, 9);
    // هر دو علامت رویه با کسر متناسب
    const byRef: Record<string, number> = {};
    for (const s of slab.sources) byRef[s.ref] = s.qty;
    expect(byRef["JSL-TOP01"]).toBeCloseTo(0.8625, 9);
    expect(byRef["JSL-TOP02"]).toBeCloseTo(0.8625, 9);
    expect(byRef["SL01"]).toBeCloseTo(2.5, 9);
  }, 30000);
});
