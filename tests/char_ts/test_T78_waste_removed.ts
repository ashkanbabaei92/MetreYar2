// T78 — حذف کامل ضریب پرت مصالح (مرحلهٔ ۱۱ بخش ۱).
//
// کلیات فهرست‌بهای ۱۴۰۴ (بند ۳ و بند ۱۴) و فصل ۸ بند ۴: افت تراکم کارگاهی،
// اتلاف ناشی از حمل و تخلیه و پرت مصالح، در بهای واحد ردیف‌های فهرست‌بها
// لحاظ شده است. بنابراین هیچ ضریب پرت جداگانه‌ای روی کمیت اعمال نمی‌شود
// و «مقدار نهایی» وجود ندارد: کمیت واحد است و مبلغ = کمیت × بها.
//
// مکانیزم پرت به‌طور کامل حذف شده است — حتی تنظیم پنهانی در UI باقی نمانده.
// اضافه‌بهای مقاومت سقف تیرچه‌بلوک (100701/100702) روی همان مساحت ۱۰۰۳۰۵
// محاسبه می‌شود — بدون ضریب ۱٫۰۳.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { OVERHEAD_PRESETS } from "../../src/lib/types";
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

describe("T78 — حذف ضریب پرت", () => {
  it("هیچ ردیفی ضریب پرت یا مقدار نهایی ندارد؛ کمیت و مبلغ one-to-one هستند", () => {
    const r = pipeline(defaultSettings());
    expect(r.lines).toHaveLength(17);
    for (const l of r.lines) {
      expect("wastePct" in l).toBe(false);
      expect("qtyFinal" in l).toBe(false);
      expect("waste" in l).toBe(false);
      // مبلغ = کمیت × بها (هیچ ضریب اضافی روی مقدار نیست)
      expect(l.total).toBeCloseTo(l.qty * l.price, 6);
      expect(l.totalIndexed).toBeCloseTo(l.total, 6);
    }
  }, 30000);

  it("تنظیمات پیش‌فرض هیچ کلید پرتی دارد (حتی خاموش)", () => {
    const s = defaultSettings() as Record<string, unknown>;
    for (const k of Object.keys(s)) {
      expect(k.toLowerCase()).not.toContain("waste");
      expect(k).not.toContain("پرت");
    }
    expect(OVERHEAD_PRESETS).toHaveLength(4);
    for (const [, val] of OVERHEAD_PRESETS) {
      expect([1.2, 1.3, 1.4]).toContain(val);
    }
  });

  it("اضافه‌بهای مقاومت سقف تیرچه‌بلوک روی مساحت خالص ۱۰۰۳۰۵ است", () => {
    const r = pipeline(defaultSettings());
    const jb = r.lines.find((l: any) => l.id === "joist-block");
    const sc = r.lines.find((l: any) => l.id === "joist-strength-surcharge");
    expect(jb).toBeDefined();
    expect(sc).toBeDefined();
    // مساحت خالص = طول تیرچه × فاصلهٔ محوری = 74.48456 × 0.55
    expect(jb.qty).toBeCloseTo(40.966508, 6);
    expect(sc.qty).toBeCloseTo(jb.qty, 9); // بدون هیچ ضریبی
    expect(sc.code).toBe("100701");
    expect(sc.total).toBeCloseTo(sc.qty * sc.price, 6);
    // ردیف ۱۰۰۷۰۲ (مقاومت بتن ۳۰MPa) هم روی همان مساحت است
    const r30 = pipeline({ ...defaultSettings(), joistBlockConcreteMpa: 30 });
    const sc30 = r30.lines.find((l: any) => l.id === "joist-strength-surcharge");
    const jb30 = r30.lines.find((l: any) => l.id === "joist-block");
    expect(sc30.code).toBe("100702");
    expect(sc30.qty).toBeCloseTo(jb30.qty, 9);
  }, 60000);

  it("کمیت‌های اصلی مساوی جمع خام رکوردها هستند (بدون ۵٪)", () => {
    const r = pipeline(defaultSettings());
    const by: Record<string, number> = {};
    for (const l of r.lines) by[l.code] = l.qty;
    // آرماتور خام پروژه: ۱۱۵۵۰٫۵۵۵۳۰۳ kg (بدون ×۱٫۰۵)
    expect(by["070202"]).toBeCloseTo(11550.555303, 3);
    // بتن ستون/تیر خالص: ۲۴۱٫۹۴ m³ (بدون ×۱٫۰۵)
    expect(by["080107"]).toBeCloseTo(241.94, 6);
    // بتن مگر خالص: ۱۸٫۶۵ m³ (بدون ×۱٫۰۵)
    expect(by["080102"]).toBeCloseTo(18.65, 6);
  }, 30000);
});
