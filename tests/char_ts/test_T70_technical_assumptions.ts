// T70 - فرض\u200cهای فنی پروژه به\u200cعنوان تنظیمات رابط کاربری (مرحلهٔ ۷).
//
// مقاومت فشاری بتن به تفکیک گروه، عیار سیمان بتن مگر و ضخامت سقف
// تیرچه\u200cبلوک دیگر در buildPlans() ثابت نیستند؛ از تنظیمات خوانده می\u200cشوند
// و کد فهرست\u200cبها از جداول نگاشتِ ماژول انتخاب می\u200cشود:
//   MPa:  ۱۲→۰۸۰۱۰۳  ۱۶→۰۸۰۱۰۴  ۲۰→۰۸۰۱۰۵  ۲۵→۰۸۰۱۰۶  ۳۰→۰۸۰۱۰۷  ۳۵→۰۸۰۱۰۸  ۴۰→۰۸۰۱۰۹
//   مگر:  ۱۰۰→۰۸۰۱۰۱  ۱۵۰→۰۸۰۱۰۲
//   سقف:  ۲۵→۱۰۰۳۰۵  ۳۰→۱۰۰۳۰۶
// قیمت ردیف از فایل رسمی ۱۴۰۴ خوانده می\u200cشود (matchMethod=rule-exact).
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import {
  buildPlans,
  computeProject,
  defaultSettings,
} from "../../src/lib/engine";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import {
  CONCRETE_STRENGTH_CODES,
  JOIST_BLOCK_THICKNESS_CODES,
  LEAN_CEMENT_CODES,
  type ProjectSettings,
} from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

const CONC_IDS = ["conc-foundation", "conc-col-beam", "conc-slab", "conc-stair"] as const;

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

describe("T70 — فرض\u200cهای فنی پروژه در تنظیمات", () => {
  it("پیش\u200cفرض دقیقاً همان مقادیر قبلی است → اعداد مرجع", () => {
    const s = defaultSettings();
    expect(s.concreteStrengthMpa).toEqual({ foundation: 20, columnBeam: 30, slab: 25, stair: 20 });
    expect(s.leanCementKg).toBe(150);
    expect(s.joistBlockThicknessCm).toBe(25);

    const r = pipeline(s);
    expect(r.lines.length).toBe(17);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 1);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 1);
    expect(line(r, "lean").code).toBe("080102");
    // پی از نام متریال Revit: ۳۵ مگاپاسکال (ایراد ۱)
    expect(line(r, "conc-foundation").code).toBe("080108");
    expect(line(r, "conc-col-beam").code).toBe("080107");
    expect(line(r, "conc-slab").code).toBe("080106");
    expect(line(r, "conc-stair").code).toBe("080105");
    expect(line(r, "joist-block").code).toBe("100305");
  }, 30000);

  it("جداول نگاشت تنها منبع انتخاب کد هستند", () => {
    expect(CONCRETE_STRENGTH_CODES).toEqual({
      12: ["080103", 17996000],
      16: ["080104", 18904000],
      20: ["080105", 19535000],
      25: ["080106", 20162000],
      30: ["080107", 20924000],
      35: ["080108", 21422000],
      40: ["080109", 22200000],
    });
    expect(LEAN_CEMENT_CODES).toEqual({ 100: ["080101", 16039000], 150: ["080102", 17152000] });
    expect(JOIST_BLOCK_THICKNESS_CODES).toEqual({ 25: ["100305", 8391000], 30: ["100306", 9101000] });
  });

  it("هر مقدار مجاز → کد و بهای درست از فایل ۱۴۰۴", () => {
    const database = db();
    for (const [mpa, [code, price]] of Object.entries(CONCRETE_STRENGTH_CODES)) {
      const s = defaultSettings();
      s.concreteStrengthMpa = { foundation: +mpa, columnBeam: +mpa, slab: +mpa, stair: +mpa };
      const plans = buildPlans(s);
      for (const pid of CONC_IDS) {
        const p = plans.find((x) => x.id === pid)!;
        expect(p.targetCode).toBe(code);
        expect(p.fallbackPrice).toBeCloseTo(price, 1);
      }
      const row = database.find((r: any) => r.code === code);
      expect(row, `code ${code} must exist in fehrest`).toBeDefined();
      expect(row.price).toBeCloseTo(price, 1);
    }
    for (const [kg, [code, price]] of Object.entries(LEAN_CEMENT_CODES)) {
      const s = defaultSettings();
      s.leanCementKg = +kg;
      const p = buildPlans(s).find((x) => x.id === "lean")!;
      expect(p.targetCode).toBe(code);
      expect(p.fallbackPrice).toBeCloseTo(price, 1);
    }
    for (const [cm, [code, price]] of Object.entries(JOIST_BLOCK_THICKNESS_CODES)) {
      const s = defaultSettings();
      s.joistBlockThicknessCm = +cm;
      const p = buildPlans(s).find((x) => x.id === "joist-block")!;
      expect(p.targetCode).toBe(code);
      expect(p.fallbackPrice).toBeCloseTo(price, 1);
    }
  });

  it("سناریو ۱: همهٔ بتن\u200cها ۳۰ مگاپاسکال → همه ۰۸۰۱۰۷", () => {
    const s = defaultSettings();
    s.concreteStrengthMpa = { foundation: 30, columnBeam: 30, slab: 30, stair: 30 };
    const r = pipeline(s);
    expect(r.lines.length).toBe(17);
    // استثنا (ایراد ۱): پی از نام متریال Revit (۳۵ مگاپاسکال) مشخص شده و
    // تقدم متریال > تنظیمات دارد → ۰۸۰۱۰۸ می‌ماند.
    for (const pid of CONC_IDS) {
      const l = line(r, pid);
      if (pid === "conc-foundation") {
        expect(l.code).toBe("080108");
        expect(l.price).toBeCloseTo(21422000, 1);
      } else {
        expect(l.code).toBe("080107");
        expect(l.price).toBeCloseTo(20924000, 1);
      }
      expect(l.matchMethod).toBe("rule-exact");
    }
    expect(line(r, "lean").code).toBe("080102");
    expect(line(r, "joist-block").code).toBe("100305");
    expect(r.baseTotal).toBeCloseTo(23230359693.06, 1);
    expect(r.grandTotal).toBeCloseTo(31407446305.01, 1);
  }, 30000);

  it("سناریو ۲ و ۳: سقف ۳۰cm → ۱۰۰۳۰۶؛ مگر ۱۰۰ → ۰۸۰۱۰۱", () => {
    const s = defaultSettings();
    s.joistBlockThicknessCm = 30;
    s.leanCementKg = 100;
    const r = pipeline(s);
    expect(line(r, "joist-block").code).toBe("100306");
    expect(line(r, "joist-block").price).toBeCloseTo(9101000, 1);
    expect(line(r, "lean").code).toBe("080101");
    expect(line(r, "lean").price).toBeCloseTo(16039000, 1);
    expect(line(r, "conc-foundation").code).toBe("080108");
    expect(line(r, "conc-col-beam").code).toBe("080107");
    expect(line(r, "conc-slab").code).toBe("080106");
    expect(line(r, "conc-stair").code).toBe("080105");
    expect(r.baseTotal).toBeCloseTo(23226710107.69, 1);
    expect(r.grandTotal).toBeCloseTo(31402512065.6, 1);
  }, 30000);
});
