import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

// ── T09: engine multi-file — هر ۱۰ فایل واقعی با هم به computeProject ──
// مقادیر مورد انتظار از خروجی TechnicalOfficeEngine.compute در app.py با
// تمام ۱۰ جدول (map_df=None) و پایگاه فهرست‌بهای واقعی ۱۴۰۴ گرفته شده‌اند.
// کدهای هدف پس از بازنگاشت مرحلهٔ ۲: بتن مگر ۰۸۰۱۰۲، پی/پله ۲۰MPa ۰۸۰۱۰۵،
// سقف ۲۵MPa ۰۸۰۱۰۶، ستون/تیر ۳۰MPa ۰۸۰۱۰۷، تیرچه‌بلوک ۲۵cm ۱۰۰۳۰۵،
// حمل ۲۸۰۱۰۱ (تن-کیلومتر).

function loadAllTables() {
  const dir = path.join(__dirname, "..", "..", "data", "export revit");
  return fs
    .readdirSync(dir)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(dir, f), "utf-8")));
}

// شناسهٔ ردیف موتور → (code, qty) — منطبق با خروجی Python
// روی ۱۰ جدول. هر ردیف با شناسهٔ plan کلید می‌شود چون پی و پله هر دو ۰۸۰۱۰۵
// هستند.
const BY_ID: Record<string, { code: string; qty: number }> = {
  lean: { code: "080102", qty: 18.65, waste: 5, qtyFinal: 19.5825 }, // بتن مگر (۱۵۰kg سیمان)
  "conc-foundation": { code: "080108", qty: 152.83 }, // پی (G1: فقط Foundation Concrete) — ۳۵MPa از متریال (ایراد ۱)
  "conc-stair": { code: "080105", qty: 7.18 }, // پله
  "conc-slab": { code: "080106", qty: 2.6316745999999998 }, // سقف + پاشنه تیرچه
  "conc-col-beam": { code: "080107", qty: 241.94 }, // ستون/تیر (المان‌های تیرچه مستثنی)
  "form-foundation": { code: "060101", qty: 167.3 }, // قالب پی
  "form-column": { code: "060301", qty: 668 }, // قالب ستون
  "form-beam": { code: "060501", qty: 1459 }, // قالب تیر (المان‌های تیرچه مستثنی)
  "form-slab": { code: "060401", qty: 11 }, // قالب دال مستقل (ایراد ۲ — ارتفاع ۳٫۵m)
  "form-stair": { code: "060701", qty: 69 }, // قالب پله
  "rebar-070101": { code: "070101", qty: 125.57 }, // آرماتور ساده
  "rebar-070201": { code: "070201", qty: 575.978837 }, // آرماتور ≤۱۰
  "rebar-070202": { code: "070202", qty: 11550.555303000006 }, // آرماتور ≤۱۸
  "rebar-070203": { code: "070203", qty: 284.1 }, // آرماتور >۱۸
  "joist-block": { code: "100305", qty: 40.966508000000005 }, // سقف تیرچه بلوک ۲۵cm
  "joist-strength-surcharge": { code: "100701", qty: 40.966508000000005 }, // اضافه‌بهای مقاومت ۲۵MPa (بند ۸ فصل دهم)
  "transport-rebar": { code: "280101", qty: 250.72408280000016 }, // حمل: ۱۲.۵۳۶تن × ۲۰km
};

const PY_BASE_TOTAL = 23218306845.90272;
const PY_GRAND_TOTAL = 31391150855.66048; // base × 1.3 (بالاسری) × 1.04 (منطقه‌ای — ایراد ۴)

describe("T09 engine multi-file: all 10 real files together vs Python", () => {
  it("produces exactly the expected 17 lines", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    expect(r.lines.length).toBe(17);
    expect(r.lines.map((l) => l.id).sort()).toEqual(Object.keys(BY_ID).sort());
  });

  it("G1 precedence: foundation concrete comes only from Foundation Concrete (qty=152.83)", () => {
    // نه مجموع ۱۵۲.۸۳ + ۱۷۱.۴۸ (Structural Concrete)؛ جدول اختصاصی پی تقدم دارد.
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    const l = r.lines.find((x) => x.id === "conc-foundation");
    expect(l).toBeDefined();
    expect(l!.code).toBe("080108");
    expect(l!.qty).toBeCloseTo(152.83, 6);
  });

  it("lean concrete is separate as 080102 (qty=18.65)", () => {
    // بتن مگر نباید داخل ردیف پی ادغام شود (LC-01 جدا)
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    const l = r.lines.find((x) => x.id === "lean");
    expect(l).toBeDefined();
    expect(l!.code).toBe("080102");
    expect(l!.qty).toBeCloseTo(18.65, 6);
  });

  it("structural concrete yields 080107/080106/080105 without touching foundation", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    // ستون/تیر — ۸٫۴۲ m³ المان JSL01 تیرچه مستثنی (داخل نرخ ۱۰۰۳۰۵ است)
    const cb = r.lines.find((x) => x.id === "conc-col-beam");
    expect(cb!.code).toBe("080107");
    expect(cb!.qty).toBeCloseTo(241.94, 6);
    // سقف: ۲٫۱ (دال ساده) + ۰٫۵۳۱۶۷۵ (باقی‌ماندهٔ رویهٔ JSL-TOP01 پس از
    // کسر ۲٫۰۴۸۳۲۵ m³ داخل نرخ ۱۰۰۳۰۵ — بند ۹ فصل دهم) = ۲٫۶۳۱۶۷۵
    const slab = r.lines.find((x) => x.id === "conc-slab");
    expect(slab!.code).toBe("080106");
    expect(slab!.qty).toBeCloseTo(2.631675, 6);
    // پله (همان کد ۲۰MPa پی، اما ردیفی جدا)
    const stair = r.lines.find((x) => x.id === "conc-stair");
    expect(stair!.code).toBe("080105");
    expect(stair!.qty).toBeCloseTo(7.18, 6);
  });

  it("joist block maps to 100305 (یونولیت ۲۵cm) with joist area qty", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    const l = r.lines.find((x) => x.id === "joist-block");
    expect(l).toBeDefined();
    expect(l!.code).toBe("100305");
    expect(l!.qty).toBeCloseTo(40.966508, 6);
  });

  it("transport is 280101 ton-kilometers: tons × (haul 50 − 30) km", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    const l = r.lines.find((x) => x.id === "transport-rebar");
    expect(l).toBeDefined();
    expect(l!.code).toBe("280101");
    expect(l!.unit).toBe("تن-کیلومتر");
    // ۱۲۵۳۶.۰۴ kg → ۱۲.۵۳۶ تن × ۲۰ کیلومتر = ۲۵۰.۷۲ تن-کیلومتر
    expect(l!.qty).toBeCloseTo(250.724083, 4);
  });

  it("rebar buckets 070201/070202/070203 aggregate across all rebar tables", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    const b201 = r.lines.find((x) => x.code === "070201");
    expect(b201!.qty).toBeCloseTo(575.978837, 6); // ۳۰۸.۷۹ + ۲۶۷.۱۹


    const b202 = r.lines.find((x) => x.code === "070202");
    expect(b202!.qty).toBeCloseTo(11550.555303000006, 6); // ۱۱۳۸۵ + ۹۹.۴۳ + ۶۶.۱۳


    const b203 = r.lines.find((x) => x.code === "070203");
    expect(b203!.qty).toBeCloseTo(284.1, 6);

  });

  it("every line matches Python code/qty and is rule-exact @0.99", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    for (const l of r.lines) {
      const want = BY_ID[l.id];
      expect(want, `unexpected line id ${l.id}`).toBeDefined();
      expect(l.code).toBe(want.code);
      expect(l.qty).toBeCloseTo(want.qty, 6);
      // مرحلهٔ ۱۱: ضریب پرت حذف شد؛ ضریب شاخص دورهٔ مبنا = ۱
      expect(l.indexFactor).toBeCloseTo(1, 6);
      expect(l.totalIndexed).toBeCloseTo(l.total, 2);
      // پایگاه رسمی: همهٔ ردیف‌ها rule-exact و غیرتخمینی
      expect(l.matchMethod).toBe("rule-exact");
      expect(l.confidence).toBeCloseTo(0.99, 6);
      expect(l.estimatedPrice).toBe(false);
    }
  });

  it("project base_total and grand_total match Python", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings());
    expect(r.baseTotal).toBeCloseTo(PY_BASE_TOTAL, 2);
    expect(r.grandTotal).toBeCloseTo(PY_GRAND_TOTAL, 2);
  });
});
