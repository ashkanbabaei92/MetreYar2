import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import {
  parseFehrestText,
  mergeFehrest,
} from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

// ── T56: اصلاح تشخیص واحدهای فهرست‌بهای ۱۴۰۴ + پاریتی کامل Python/TS ──
//
// پیشینه: تشخیص واحد، واحدهای خط‌تیره‌دار را نمی‌شناخت. نتیجه:
//   • 280101 (حمل) واحد واقعی «تن-کیلومتر» داشت ولی به‌جای آن از روی
//     واژهٔ «آهن‌آلات» در شرح، «کیلوگرم» حدس زده می‌شد.
//   • ردیف‌های «دسیمترمکعب» (مثل 080501 گروت) و «رشته» (070705) نیز
//     از روی شرح حدس زده می‌شدند.
// اصلاح: افزودن تن-کیلومتر/دسیمترمکعب/رشته به UNIT_WORDS، پذیرش پیشوند
// با خط تیره (w.startsWith(u + "-")) و قرار دادن واحدهای مرکب پیش از
// پایهٔ آن‌ها (تن-کیلومتر قبل از تن).
//
// تمام مقادیر مورد انتظار از خروجی واقعی Python (app.py پس از اصلاح)
// گرفته شده‌اند → تطابق کامل دو زبان روی فایل رسمی ۱۴۰۴.

const FEHREST_FILE = path.join(
  __dirname,
  "..",
  "..",
  "data",
  "fehrest baha 1404",
  "all 1404 fehrest.txt",
);

function loadRealFehrest() {
  return parseFehrestText(fs.readFileSync(FEHREST_FILE, "utf-8"));
}

function loadAllTables() {
  const dir = path.join(__dirname, "..", "..", "data", "export revit");
  return fs
    .readdirSync(dir)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(dir, f), "utf-8")));
}

function loadMergedMapping() {
  const dir = path.join(__dirname, "..", "..", "data", "dynamo");
  const rows: any[] = [];
  for (const sub of fs.readdirSync(dir).sort()) {
    const subDir = path.join(dir, sub);
    if (!fs.statSync(subDir).isDirectory()) continue;
    for (const fn of fs.readdirSync(subDir).sort()) {
      if (!fn.endsWith(".txt")) continue;
      const b = fs.readFileSync(path.join(subDir, fn));
      const buf = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
      rows.push(...parseDynamoMapping(buf, fn).rows);
    }
  }
  return { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
}

describe("T56 — unit detection fix (ton-kilometer / cubic-decimeter / band)", () => {
  it("280101 has the official unit تن-کیلومتر, not a desc-based guess", () => {
    const { rows } = loadRealFehrest();
    const r = rows.find((x) => x.code === "280101");
    expect(r).toBeDefined();
    expect(r!.unit).toBe("تن-کیلومتر");
    expect(r!.price).toBe(28400);
    expect(r!.chapter).toBe("28");
  });

  it("all 8 land-transport rows of chapter 28 are تن-کیلومتر", () => {
    const { rows } = loadRealFehrest();
    const land = rows.filter(
      (x) => x.code.startsWith("28") && x.unit !== "تن - مابل دریایی",
    );
    expect(land.length).toBe(8);
    for (const r of land) expect(r.unit).toBe("تن-کیلومتر");
  });

  it("marine transport keeps its compound unit تن - مابل دریایی", () => {
    const { rows } = loadRealFehrest();
    const marine = rows.filter((x) =>
      ["280501", "280502", "280503", "280504", "280505"].includes(x.code),
    );
    expect(marine.length).toBe(5);
    for (const r of marine) expect(r.unit).toBe("تن - مابل دریایی");
  });

  it.each(["080501", "080502", "060912", "060916"])(
    "%s is detected as دسیمترمکعب (not guessed from desc)",
    (code) => {
      const { rows } = loadRealFehrest();
      const r = rows.find((x) => x.code === code);
      expect(r).toBeDefined();
      expect(r!.unit).toBe("دسیمترمکعب");
    },
  );

  it("070705 is detected as رشته", () => {
    const { rows } = loadRealFehrest();
    const r = rows.find((x) => x.code === "070705");
    expect(r).toBeDefined();
    expect(r!.unit).toBe("رشته");
  });

  it("the compound unit مترمربع-ماه is still detected", () => {
    const { rows } = loadRealFehrest();
    expect(rows.some((x) => x.unit === "مترمربع-ماه")).toBe(true);
  });

  // ─────────────── توزیع کامل واحدها — یکسان با Python ───────────────
  const EXPECTED_UNITS: Record<string, number> = {
    اصله: 8,
    تن: 6,
    "تن - مابل دریایی": 5,
    "تن-کیلومتر": 8,
    درصد: 8,
    دستگاه: 3,
    دسیمترمکعب: 8,
    رشته: 1,
    عدد: 38,
    لنگه: 2,
    مترطول: 133,
    مترمربع: 859,
    "مترمربع-ماه": 1,
    مترمکعب: 191,
    "مترمکعب -  کیلومتر\u200f": 3,
    مقطوع: 50,
    کیلوگرم: 241,
  };

  it("unit distribution matches Python exactly (17 unit kinds)", () => {
    const { rows } = loadRealFehrest();
    const units: Record<string, number> = {};
    for (const r of rows) units[r.unit] = (units[r.unit] || 0) + 1;
    expect(units).toEqual(EXPECTED_UNITS);
  });

  // ─────── تطابق کد/قیمت/واحد برای کدهای خروجی موتور — یکسان با Python ───────
  // کدهای هدف موتور پس از بازنگاشت مرحلهٔ ۲ روی فهرست‌بهای واقعی ۱۴۰۴.
  const EXPECTED_ENGINE_CODES: Record<string, { unit: string; price: number }> = {
    "080102": { unit: "مترمکعب", price: 17152000 }, // lean — ۱۵۰kg سیمان
    "080105": { unit: "مترمکعب", price: 19535000 }, // پی و پله — ۲۰ MPa
    "080106": { unit: "مترمکعب", price: 20162000 }, // سقف — ۲۵ MPa
    "080107": { unit: "مترمکعب", price: 20924000 }, // ستون/تیر — ۳۰ MPa
    "060101": { unit: "مترمربع", price: 2538000 },
    "060301": { unit: "مترمربع", price: 3378000 },
    "060501": { unit: "مترمربع", price: 4288000 },
    "060701": { unit: "مترمربع", price: 4100000 },
    "070101": { unit: "کیلوگرم", price: 452000 },
    "070201": { unit: "کیلوگرم", price: 441500 },
    "070202": { unit: "کیلوگرم", price: 375500 },
    "070203": { unit: "کیلوگرم", price: 358500 },
    "100305": { unit: "مترمربع", price: 8391000 }, // یونولیت ۲۵cm
    "280101": { unit: "تن-کیلومتر", price: 28400 }, // حمل ۳۰–۷۵km
  };

  it.each(Object.keys(EXPECTED_ENGINE_CODES).sort())(
    "engine code %s has the same unit and price as Python",
    (code) => {
      const { rows } = loadRealFehrest();
      const r = rows.find((x) => x.code === code);
      expect(r).toBeDefined();
      const { unit, price } = EXPECTED_ENGINE_CODES[code];
      expect(r!.unit).toBe(unit);
      expect(r!.price).toBe(price);
    },
  );

  it("080303 is absent from the real 1404 file (kept only via embedded)", () => {
    const { rows } = loadRealFehrest();
    expect(rows.find((x) => x.code === "080303")).toBeUndefined();
  });

  it("parse counts are stable: 1565 rows, 34 skipped", () => {
    const { rows, skipped } = loadRealFehrest();
    expect(rows.length).toBe(1565);
    expect(skipped).toBe(34);
  });

  // ───────────────────────────── merge ─────────────────────────────
  it("mergeFehrest keeps embedded-only codes and overrides with real prices", () => {
    const { rows } = loadRealFehrest();
    const merged = new Map(mergeFehrest(rows).map((r) => [r.code, r]));

    expect(merged.has("080303")).toBe(true); // survives via embedded base
    expect(merged.get("080303")!.price).toBe(7200000);
    // قیمت واقعی جایگزین قیمت تخمینی embedded
    expect(merged.get("070202")!.price).toBe(375500);
    expect(merged.get("070202")!.estimated).toBe(false);
    expect(merged.get("060101")!.price).toBe(2538000);
  });

  // ─────── حفظ خروجی فعلی: ۱۰ جدول Revit + ۲ mapping (مسیر پیش‌فرض) ───────
  it("the default pipeline output is stable with the official 1404 db", () => {
    const r = computeProject(
      loadAllTables(),
      OFFICIAL_1404_FEHREST,
      defaultSettings(),
      loadMergedMapping(),
    );
    expect(r.lines.length).toBe(17);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 1);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 1);
  });
});
