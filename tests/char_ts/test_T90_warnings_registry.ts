// T90 — رجیستری مرکزی هشدارها (ایراد ۱۰) و چگالی میلگرد (ایراد ۱۴).
//
// هر ردیف needs_review باید هشدار متناظر داشته باشد. همهٔ هشدارها
// ساختاریافته‌اند: سطح | دسته | المان | شرح | اقدام | بند مرجع.
// چگالی میلگرد هر گروه = وزن ÷ حجم بتن؛ خارج از محدوده → هشدار خطا
// (اپ عدد را تغییر نمی‌دهد).
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings, rebarDensityWarnings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import REBAR_DENSITY_CFG from "../../config/rebar_density_thresholds.json";
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

function pipeline(settings: ProjectSettings): any {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows = loadAllMappingRows();
  const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
  return computeProject(tables as never, OFFICIAL_1404_FEHREST, settings, mapping as never);
}

/** ساخت ردیف حداقلی برای آزمایش مستقیم تابع چگالی (مانند _mkline پایتون). */
function mkLines(entries: [code: string, unit: string, group: string, qty: number][]) {
  return entries.map(([code, unit, group, qty]) => ({
    code,
    unit,
    sources: [{ group, qty }],
  }));
}

describe("T90 — رجیستری مرکزی هشدارها و چگالی میلگرد", () => {
  it("هر هشدار شامل همهٔ فیلدهای الزامی است", () => {
    const r = pipeline(defaultSettings());
    expect(r.warnings.length).toBeGreaterThan(0);
    for (const w of r.warnings) {
      expect(Object.keys(w).sort()).toEqual(
        ["action", "category", "item", "level", "message", "ref"].sort(),
      );
      expect(["خطا", "هشدار", "اطلاع"]).toContain(w.level);
      expect(w.message.length).toBeGreaterThan(0);
    }
  }, 60000);

  it("قاعدهٔ کیفی: هر خط needs_review یک هشدار دارد", () => {
    const r = pipeline(defaultSettings());
    const review = r.lines.filter((l: any) => l.needsReview);
    const items = new Set(
      r.warnings.filter((w: any) => w.category === "تطبیق ردیف").map((w: any) => w.item),
    );
    for (const l of review) {
      expect(items.has(l.code)).toBe(true);
      expect(
        r.warnings.some((w: any) => w.item === l.code && w.message.includes("بازبینی")),
      ).toBe(true);
    }
  }, 60000);

  it("آستانه‌ها از config/rebar_density_thresholds.json", () => {
    const th = (REBAR_DENSITY_CFG as Record<string, any>).thresholds_kg_m3;
    expect(th["پی"]).toEqual([50, 120]);
    expect(th["ستون"]).toEqual([100, 250]);
    expect(th["تیر"]).toEqual([100, 200]);
    expect(th["دال"]).toEqual([60, 120]);
    expect(th["پله"]).toEqual([60, 120]);
  });

  it("چگالی ۲۰۰ kg/m³ برای پی (محدودهٔ ۵۰–۱۲۰) → هشدار خطا", () => {
    const lines = mkLines([
      ["080105", "مترمکعب", "پی", 100.0],
      ["070202", "کیلوگرم", "پی", 20000.0],
    ]);
    const warns: any[] = [];
    rebarDensityWarnings(lines as never, defaultSettings(), warns);
    expect(warns).toHaveLength(1);
    expect(warns[0].level).toBe("خطا");
    expect(warns[0].item).toBe("پی");
    expect(warns[0].message).toContain("۲۰۰");
    expect(warns[0].message).toContain("۵۰");
    expect(warns[0].message).toContain("۱۲۰");
  });

  it("چگالی ۱۰۰ kg/m³ داخل محدوده → بدون هشدار", () => {
    const lines = mkLines([
      ["080105", "مترمکعب", "ستون", 100.0],
      ["070202", "کیلوگرم", "ستون", 10000.0],
    ]);
    const warns: any[] = [];
    rebarDensityWarnings(lines as never, defaultSettings(), warns);
    expect(warns).toEqual([]);
  });

  it("وزن دستی میلگرد → هشدار اطلاع (دست‌نخوردن عدد مدل)", () => {
    const s = { ...defaultSettings(), rebarManualWeight: { "پی": 20000.0 } };
    const lines = mkLines([
      ["080105", "مترمکعب", "پی", 100.0],
      ["070202", "کیلوگرم", "پی", 20000.0],
    ]);
    const warns: any[] = [];
    rebarDensityWarnings(lines as never, s, warns);
    expect(warns).toHaveLength(1);
    expect(warns[0].level).toBe("اطلاع");
  });

  it("شمارش سطوح و پرچم «ناقص» در حالت پیش‌فرض (طبقات ناقص)", () => {
    const r = pipeline(defaultSettings());
    expect(r.warningsByLevel["خطا"]).toBe(1);
    expect(r.status.errors).toBe(1);
    expect(r.status.complete).toBe(false);
    // با تکمیل مساحت طبقات دیگر خطایی نباید باشد
    const areas: Record<string, number> = {};
    for (const n of ["Foundation Top", "Story1", "Story2", "Story3", "Story4", "Story5", "Story6"]) {
      areas[n] = 63.0;
    }
    const r2 = pipeline({ ...defaultSettings(), floorsData: areas });
    expect(r2.status.errors).toBe(0);
    expect(r2.status.complete).toBe(true);
    // ضریب طبقات محاسبه‌شده و در زنجیره اعمال شده
    expect(r2.coefs.floors.status).toBe("محاسبه‌شده");
    // صورت = ۶۳×(۱+۲+۳+۴) [Story2..5] = ۶۳۰ (Foundation Top غیرطبقه‌ای،
    // Story6 بام — هر دو مستثنی)؛ مخرج = ۱۰۰×۵×۶۳ = ۳۱۵۰۰ → P = ۱ + ۶۳۰/۳۱۵۰۰
    expect(r2.coefs.floors.value).toBeCloseTo(1 + 630 / 31500, 6);
    const eligible = r2.coefs.floors.eligibleTotal;
    const excluded = r2.coefs.floors.excludedTotal;
    expect(r2.floorsAmount).toBeCloseTo(
      eligible * (r2.coefs.floors.value as number) + excluded,
      0,
    );
    expect(r2.floorsAmount).toBeGreaterThan(r2.baseTotal);
    expect(r2.grandTotal).toBeGreaterThan(r.baseTotal * 1.3 * 1.04);
  }, 60000);
});
