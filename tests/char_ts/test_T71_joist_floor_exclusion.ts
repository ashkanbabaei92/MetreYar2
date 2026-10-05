// T71/T72/T73 - مرحلهٔ ۹: رفع دوبارشماری سقف تیرچه\u200cبلوک + اضافه\u200cبهای مقاومت.
//
// مبنا: فهرست\u200cبهای ابنیه ۱۴۰۴، فصل دهم، الزامات عمومی:
//   بند ۳: ردیف\u200cهای سقف تیرچه\u200cبلوک شامل شمع\u200cبندی، داربست، قالب\u200cبندی،
//          بتن\u200cریزی و نگهداری است → المان تیرچه نباید بتن (۰۸۰۱۰۵..۰۸۰۱۰۷)
//          یا قالب (فصل ۰۶، از جمله ۰۶۰۵۰۱) جداگانه تولید کند.
//   بند ۸: بتن سقف ۲۰ MPa فرض؛ بیش از ۲۰ تا ۲۵ → ۱۰۰۷۰۱ (۵۹٬۵۰۰ ریال/m²)،
//          بیش از ۲۵ تا ۳۰ → ۱۰۰۷۰۲ (۷۶٬۵۰۰ ریال/m²) روی کل مساحت سقف.
//   بند ۹: ضخامت سقف = زیر تیرچه تا ۵ cm بتن روی بلوک داخل نرخ ۱۰۰۳۰۵ است؛
//          فقط بتن مازاد بر ۵ cm (طبق مشخصات فنی) جداگانه حساب می\u200cشود.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { JOIST_BLOCK_STRENGTH_SURCHARGE, type ProjectSettings } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

// مرجع مرحلهٔ ۸ (قبل از رفع دوبارشماری) — برای تطبیق اختلاف کمیت.
const STAGE8_CONC_COL_BEAM = 250.36; // m³ شامل ۸٫۴۲ m³ تیرچه
const STAGE8_FORM_BEAM = 1621.0; // m² شامل ۱۶۲ m² تیرچه

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

function line(result: any, planId: string): any {
  return result.lines.find((l: any) => l.id === planId);
}

// ── T71: المان\u200cهای سقف تیرچه\u200cبلوک ردیف بتن/قالب تولید نمی\u200cکنند ──

describe("T71 — رفع دوبارشماری سقف تیرچه\u200cبلوک", () => {
  it("JSL01: حذف ۸٫۴۲ m³ از ۰۸۰۱۰۷ و ۱۶۲ m² از ۰۶۰۵۰۱؛ ۱۰۰۳۰۵ بدون تغییر", () => {    const r = pipeline(defaultSettings());
    // بتن ستون/تیر: ۲۵۰٫۳۶ − ۸٫۴۲ (JSL01) = ۲۴۱٫۹۴
    const cb = line(r, "conc-col-beam");
    expect(cb.code).toBe("080107");
    expect(cb.qty).toBeCloseTo(241.94, 4);
    // قالب تیر: ۱۶۲۱ − ۱۶۲ (JSL01) = ۱۴۵۹
    const fb = line(r, "form-beam");
    expect(fb.code).toBe("060501");
    expect(fb.qty).toBeCloseTo(1459, 4);
    // سقف تیرچه\u200cبلوک دست\u200cنخورده
    const jb = line(r, "joist-block");
    expect(jb.code).toBe("100305");
    expect(jb.qty).toBeCloseTo(40.966508, 6);
  }, 30000);

  it("جدول‌های جدا: با دو جدول (Structural Concrete + Joist Floor) تیرچه در بتن نیست", () => {
    const read = (fname: string) =>
      parseRevitFile(fname, fs.readFileSync(path.join(REVIT_DIR, fname), "utf-8"));
    const all = fs.readdirSync(REVIT_DIR).sort();
    const concName = all.find((f) => f.includes("حجم بتن سازه‌ای") && f.includes("Structural Concrete"))!;
    const joistName = all.find((f) => f.includes("سقف تیرچه بلوک") && f.includes("Joist Floor"))!;
    const tables = [read(concName), read(joistName)];
    const r = computeProject(tables as never, db(), defaultSettings());
    // ۸٫۴۲ m³ تیرچه در structural_concrete هست ولی نباید به ردیفی برود.
    const codes = r.lines.map((l: any) => l.code);
    expect(codes).toContain("080107"); // ستون/تیرهای واقعی (۲۴۱٫۹۴)
    expect(codes).toContain("100305");
    expect(line(r, "conc-col-beam").qty).toBeCloseTo(241.94, 4);
  }, 30000);

  it("تطبیق با مرجع مرحلهٔ ۸: −۸۷۹٬۶۴۵٬۰۸۴ (بتن+قالب) به\u200cعلاوهٔ ۱۰۰۷۰۱", () => {
    // با مقاومت ۲۰ MPa (بدون اضافه\u200cبها) اختلاف دقیقاً برابر حذف
    // دوبارشماری است؛ پیش\u200cفرض ۲۵ MPa اضافه\u200cبهای ۱۰۰۷۰۱ را روی آن می\u200cنهد.
    const s20 = defaultSettings();
    s20.joistBlockConcreteMpa = 20;
    const r20 = pipeline(s20);
    const cb = line(r20, "conc-col-beam");
    const fb = line(r20, "form-beam");
    expect(cb.qty + 8.42).toBeCloseTo(STAGE8_CONC_COL_BEAM, 4);
    expect(fb.qty + 162.0).toBeCloseTo(STAGE8_FORM_BEAM, 4);
    expect(r20.lines.some((l: any) => l.code === "100701" || l.code === "100702")).toBe(false);

    const r25 = pipeline(defaultSettings());
    const surcharge = line(r25, "joist-strength-surcharge");
    expect(r25.baseTotal).toBeCloseTo(r20.baseTotal + surcharge.total, 0);
  }, 30000);
});

// ── T72: ماتریس مقاومت بتن سقف تیرچه\u200cبلوک (بند ۸ فصل دهم) ──

describe("T72 — اضافه\u200cبهای مقاومت بتن سقف تیرچه\u200cبلوک", () => {
  it("۲۰ → هیچ / ۲۵ → ۱۰۰۷۰۱ / ۳۰ → ۱۰۰۷۰۲ با مقدار = مساحت نهایی سقف", () => {
    // ۲۰ MPa: هیچ ردیف اضافه\u200cبها
    const s20 = defaultSettings();
    s20.joistBlockConcreteMpa = 20;
    const r20 = pipeline(s20);
    expect(r20.lines.some((l: any) => l.code === "100701" || l.code === "100702")).toBe(false);
    expect(r20.lines.length).toBe(16);

    // ۲۵ و ۳۰ MPa: ردیف اضافه\u200cبها روی کل مساحت ۱۰۰۳۰۵
    for (const [mpa, code, price] of [[25, "100701", 59500], [30, "100702", 76500]] as const) {
      const s = defaultSettings();
      s.joistBlockConcreteMpa = mpa as number;
      const r = pipeline(s);
      expect(r.lines.length).toBe(17);
      const sc = line(r, "joist-strength-surcharge");
      const jb = line(r, "joist-block");
      expect(sc.code).toBe(code);
      expect(sc.unit).toBe("مترمربع");
      expect(sc.qty).toBeCloseTo(jb.qty, 9);
      expect(sc.price).toBeCloseTo(price, 1);
      expect(sc.total).toBeCloseTo(jb.qty * (price as number), 1);
      // بتن سقف تیرچه\u200cبلوک به ۰۸۰۱۰۶ نگاشت نمی\u200cشود
      expect(line(r, "conc-slab").qty).toBeCloseTo(2.631675, 6);
    }
  }, 30000);

  it("جدول نگاشت اضافه\u200cبهای مقاومت فقط سه کلید ۲۰/۲۵/۳۰ دارد", () => {
    expect(Object.keys(JOIST_BLOCK_STRENGTH_SURCHARGE).map(Number).sort()).toEqual([20, 25, 30]);
    expect(JOIST_BLOCK_STRENGTH_SURCHARGE[20]).toBeNull();
    expect(JOIST_BLOCK_STRENGTH_SURCHARGE[25]).toEqual(["100701", 59500]);
    expect(JOIST_BLOCK_STRENGTH_SURCHARGE[30]).toEqual(["100702", 76500]);
  }, 30000);
});

// ── T73: ضخامت بتن روی بلوک (بند ۹ فصل دهم) ──

describe("T73 — بتن مازاد بر ۵ cm روی بلوک", () => {
  it("ضخامت روی بلوک ۵ و ۷ cm → بتن مازاد ۰ و ۰٫۰۲×مساحت سقف", () => {
    // ۵ cm (پیش\u200cفرض): صفر مازاد
    const r5 = pipeline(defaultSettings());
    expect(line(r5, "conc-slab").qty).toBeCloseTo(2.631675, 6);

    // ۷ cm: (۷−۵)/۱۰۰ × ۴۰٫۹۶۶۵۰۸ = ۰٫۸۱۹۳۳ m³ به ۰۸۰۱۰۶ (مقاومت ۲۵)
    const s7 = defaultSettings();
    s7.joistBlockTopThicknessCm = 7;
    const r7 = pipeline(s7);
    const slab7 = line(r7, "conc-slab");
    const jb = line(r7, "joist-block");
    expect(slab7.qty).toBeCloseTo(2.631675 + 0.02 * jb.qty, 6);
    expect(slab7.qty).toBeCloseTo(3.451005, 6);
    // ۱۰۰۳۰۵ و بقیهٔ ردیف\u200cها بدون تغییر
    expect(line(r7, "joist-block").qty).toBeCloseTo(40.966508, 6);
    expect(line(r7, "conc-col-beam").qty).toBeCloseTo(241.94, 4);
    // ردیف اضافه\u200cبها روی مساحت سقف (نه روی حجم مازاد)
    expect(line(r7, "joist-strength-surcharge").qty).toBeCloseTo(jb.qty, 9);
  }, 30000);

  it("بتن مازاد به ردیف متناظر با مقاومت انتخابی می\u200cرود، نه لزوماً ۰۸۰۱۰۶", () => {
    // با مقاومت ۳۰ MPa، مازاد باید به ۰۸۰۱۰۷ (conc-col-beam) برود.
    const s = defaultSettings();
    s.joistBlockTopThicknessCm = 7;
    s.joistBlockConcreteMpa = 30;
    const r = pipeline(s);
    const excess = 0.02 * 40.966508;
    expect(line(r, "conc-col-beam").qty).toBeCloseTo(241.94 + excess, 6);
    expect(line(r, "conc-slab").qty).toBeCloseTo(2.631675, 6);
  }, 30000);
});
