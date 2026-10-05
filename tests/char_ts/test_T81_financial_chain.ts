// T81 — زنجیرهٔ مالی (مرحلهٔ ۱۱ بخش ۴ — دستورالعمل کاربرد بندهای ۲-۷/۲-۸).
//
// ترتیب: جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای +
// تجهیز و برچیدن کارگاه = ناخالص پرداختی (= مبلغ نهایی).
// • بالاسری: تنظیم کاربر با ۴ پیش‌فرض (عمرانی: مناقصه ۱٫۳ / ترک تشریفات
//   ۱٫۲؛ غیرعمرانی: ۱٫۴ / ۱٫۳).
// • تجهیز و برچیدن: مبلغ واردشده توسط کاربر (نه ضریب خودکار)؛ سقف ۴٪
//   فقط هشدار است و مبلغ کامل محاسبه می‌شود.
// • کسورات قانونی (۲۲٫۸٪) جزو ناخالص نیستند؛ فقط در خروجی جداگانهٔ
//   «خالص پرداختی» محاسبه می‌شوند.
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

// پایگاه پیش‌فرض: معادل دقیق _default_fehrest_db در پایتون —
// فهرست‌بهای رسمی ۱۴۰۴ مرج‌شده بر روی ردیف‌های embedded.
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

describe("T81 — زنجیرهٔ مالی", () => {
  it("پیش‌فرض: base × ۱ (طبقات ناقص) × ۱٫۳ × ۱٫۰۴ (گرگان) + ۰ = ناخالص", () => {
    const r = pipeline(defaultSettings());
    expect(r.floorsAmount).toBeCloseTo(r.baseTotal * 1.0, 6);
    expect(r.overheadAmount).toBeCloseTo(r.floorsAmount * 1.3, 6);
    expect(r.regionalAmount).toBeCloseTo(r.overheadAmount * 1.04, 6);
    expect(r.siteSetup).toBe(0);
    expect(r.grossPayable).toBeCloseTo(r.regionalAmount, 6);
    expect(r.grandTotal).toBe(r.grossPayable);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 0);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 0);
  }, 30000);

  it("۴ حالت بالاسری (نوع پروژه × نوع قرارداد) ضریب درست تولید می‌کنند", () => {
    const presets = new Map(OVERHEAD_PRESETS.map(([k, v]) => [k, v]));
    expect(presets).toEqual(
      new Map([
        ["overhead_civil_tender", 1.3],
        ["overhead_civil_direct", 1.2],
        ["overhead_noncivil_tender", 1.4],
        ["overhead_noncivil_direct", 1.3],
      ]),
    );
    // یک ضریب غیرپیش‌فرض (۱٫۴) سراسر زنجیره را تغییر می‌دهد (ضریب منطقه‌ای ۱٫۰۴)
    const base = pipeline(defaultSettings()).baseTotal;
    const r = pipeline({ ...defaultSettings(), overheadCoef: 1.4 });
    expect(r.overheadAmount).toBeCloseTo(base * 1.4, 6);
    expect(r.grossPayable).toBeCloseTo(base * 1.4 * 1.04, 6);
    expect(r.grandTotal).toBeCloseTo(base * 1.4 * 1.04, 6);
  }, 60000);

  it("تجهیز و برچیدن مبلغ مستقیم است و کامل به ناخالص اضافه می‌شود", () => {
    const amount = 500_000_000;
    const base = pipeline(defaultSettings()).baseTotal;
    const r = pipeline({ ...defaultSettings(), siteSetupAmount: amount });
    expect(r.siteSetup).toBe(amount);
    expect(r.grossPayable).toBeCloseTo(base * 1.3 * 1.04 + amount, 6);
    expect(r.grandTotal).toBe(r.grossPayable);
  }, 60000);

  it("سقف ۴٪ تجهیز فقط هشدار است؛ مبلغ کامل محاسبه می‌شود", () => {
    const r0 = pipeline(defaultSettings());
    const huge = 10 * (0.04 * r0.regionalAmount); // ده برابر سقف
    const r = pipeline({ ...defaultSettings(), siteSetupAmount: huge });
    expect(huge).toBeGreaterThan(0.04 * r0.regionalAmount);
    expect(r.grossPayable).toBeCloseTo(r0.regionalAmount + huge, 6);
    expect(r.grandTotal).toBe(r.grossPayable);
  }, 60000);

  it("ضرایب طبقات و منطقه‌ای در جای درست زنجیره ضرب می‌شوند", () => {
    // ورودی دستی (floorsAuto=false، regionalCoef) بر محاسبهٔ خودکار تقدم
    // دارد. ضریب طبقات فقط روی ردیف‌های مشمول (کار ساختمان) اعمال می‌شود —
    // فصل ۲۸ (حمل و نقل) مستثنی است.
    const ref = pipeline(defaultSettings());
    const fc = ref.coefs.floors;
    const eligible = fc.eligibleTotal;
    const excluded = fc.excludedTotal;
    const fa = eligible * 1.05 + excluded;
    const r = pipeline({
      ...defaultSettings(),
      floorsAuto: false,
      floorsCoef: 1.05,
      regionalCoef: 1.1,
    });
    expect(r.floorsAmount).toBeCloseTo(fa, 6);
    expect(r.overheadAmount).toBeCloseTo(fa * 1.3, 6);
    expect(r.regionalAmount).toBeCloseTo(fa * 1.3 * 1.1, 6);
    expect(r.grossPayable).toBeCloseTo(fa * 1.3 * 1.1, 6);
  }, 60000);

  it("کسورات ۲۲٫۸٪ فقط در «خالص پرداختی» هستند؛ بر ناخالص اثر ندارند", () => {
    const plain = pipeline(defaultSettings());
    const r = pipeline({
      ...defaultSettings(),
      insurancePct: 7.8,
      taxPct: 5.0,
      goodJobPct: 10.0,
      advancePayment: 1_000_000_000,
    });
    expect(r.grandTotal).toBeCloseTo(plain.grandTotal, 6);
    expect(r.grossPayable).toBeCloseTo(plain.grossPayable, 6);
    // خالص پرداختی = ناخالص − کسورات
    expect(r.insurance).toBeCloseTo(r.grossPayable * 0.078, 6);
    expect(r.tax).toBeCloseTo(r.grossPayable * 0.05, 6);
    expect(r.goodJob).toBeCloseTo(r.grossPayable * 0.1, 6);
    expect(r.advancePayment).toBe(1_000_000_000);
    expect(r.totalDeductions).toBeCloseTo(
      r.insurance + r.tax + r.goodJob + r.advancePayment,
      4,
    );
    expect(r.netPayable).toBeCloseTo(r.grossPayable - r.totalDeductions, 4);
    expect(r.netPayable).toBeLessThan(r.grossPayable);
  }, 60000);
});
