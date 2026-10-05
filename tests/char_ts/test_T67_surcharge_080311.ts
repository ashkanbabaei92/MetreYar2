// T67 - اضافه‌بهای سختی ارتعاش بتن (ردیف ۰۸۰۳۱۱ فهرست‌بهای ۱۴۰۴).
//
// شرط رسمی: «اضافه‌بها به ردیف‌های بتن‌ریزی برای سختی ارتعاش بتن، در صورتی
// که میلگرد به کار رفته بیش از ۱۸۰ کیلوگرم در مترمکعب بتن باشد» (۳۶۳٬۵۰۰
// ریال/m³). پیاده‌سازی: تراکم = مجموع وزن آرماتور ÷ حجم بتن‌های سازه‌ای
// (بدون بتن‌مگر)؛ چون از ۱۸۰ بیشتر شود، ردیفی به ازای مقدار نهایی بتن
// سازه‌ای افزوده می‌شود. این ردیف **اختیاری** است و تنظیم بولین
// `surchargeRebarDensity` (پیش‌فرض false) آن را فعال می‌کند.
//
// نکتهٔ مهم: جدول آرماتورِ پروژهٔ نمونه یک استخراج نمونه است؛ تراکم واقعی
// پروژه ≈ ۳۰ kg/m³ است و زیر آستانه می‌ماند. بنابراین در دادهٔ واقعی،
// فعال کردن این تنظیم هیچ ردیفی اضافه نمی‌کند و totals بی‌تغییر می‌مانند —
// همین رفتار آزمون می‌شود (و در سمت Python نیز دقیقاً همین خروجی به دست
// می‌آید → برابری دو زبان).
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import {
  computeProject,
  defaultSettings,
  rebarDensity,
  REBAR_DENSITY_THRESHOLD,
} from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
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

describe("T67 — اضافه‌بهای سختی ارتعاش بتن (۰۸۰۳۱۱)", () => {
  it("تابع تراکم: تقسیم ساده، بازگشت صفر برای حجم صفر، عبور از آستانه", () => {
    // مقادیر واقعی پروژهٔ نمونه: ۱۲٬۵۳۶٫۳۷ کیلوگرم آرماتور بر ۴۰۴٫۵۸ m³ بتن سازه‌ای
    const d = rebarDensity(12536.368737, 404.581675);
    expect(d).toBeCloseTo(30.99, 1);
    expect(d).toBeLessThan(REBAR_DENSITY_THRESHOLD);
    // تراکم فرضی بالای آستانه (مثلاً پروژهٔ دیوار برشی متراکم)
    expect(rebarDensity(75000, 404.581675)).toBeGreaterThan(REBAR_DENSITY_THRESHOLD);
    // حجم صفر → تراکم صفر (تقسیم بر صفر ممنوع)
    expect(rebarDensity(1000, 0)).toBe(0);
  });

  it("پیش‌فرض: تنظیم خاموش است و ردیف ۰۸۰۳۱۱ وجود ندارد و totals مرجع است", () => {
    expect(defaultSettings().surchargeRebarDensity).toBe(false);
    const r = pipeline(defaultSettings());
    expect(r.lines).toHaveLength(17);
    expect(r.lines.some((l: any) => l.code === "080311")).toBe(false);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 0);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 0);
  }, 30000);

  it("فعال‌سازی روی دادهٔ نمونه: تراکم ≈ ۳۰ < ۱۸۰ → ردیفی افزوده نمی‌شود", () => {
    const off = pipeline(defaultSettings());
    const on = pipeline({ ...defaultSettings(), surchargeRebarDensity: true });

    // تراکم از روی ردیف‌های واقعی محاسبه می‌شود تا شرط اثبات گردد
    const rebarNet = off.lines
      .filter((l: any) => l.id.startsWith("rebar-"))
      .reduce((a: number, l: any) => a + l.qty, 0);
    const concNet = off.lines
      .filter((l: any) => l.id.startsWith("conc-"))
      .reduce((a: number, l: any) => a + l.qty, 0);
    expect(rebarDensity(rebarNet, concNet)).toBeLessThan(REBAR_DENSITY_THRESHOLD);

    expect(on.lines).toHaveLength(17);
    expect(on.lines.some((l: any) => l.code === "080311")).toBe(false);
    expect(on.baseTotal).toBe(off.baseTotal);
    expect(on.grandTotal).toBe(off.grandTotal);
    expect(on.baseTotal).toBeCloseTo(23218381337.01, 0);
  }, 30000);
});
