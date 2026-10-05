import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

// ── T55: رفع دوباره‌شماری آرماتور Mapping v1 + استخراج v1/v2 در TS ──
//
// پیشینه: extractRebar در engine.ts پارامتر mapping را می‌گرفت ولی نادیده
// می‌گرفت (باگ ۱)، و parseV1Lines در mappingParser.ts طول mm را به m تبدیل
// نمی‌کرد (باگ ۲). نتیجهٔ باگ ۱: خروجی TS با mapping دقیقاً مساوی خروجی
// بدون mapping بود. حالا هر دو fix شده‌اند و revitMarks dedup مطابق
// app.py:_extract_rebar پیاده‌سازی شده.
//
// مقادیر مورد انتظار از خروجی Python (app.py پس از fix) با ۱۰ فایل واقعی
// Revit + هر دو خروجی داینامو و پایگاه فهرست‌بهای واقعی ۱۴۰۴ گرفته شده‌اند.

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

describe("T55 — mapping rebar extraction + dedup (parity with fixed Python)", () => {
  it("baseTotal شامل آرماتور تکراری v1 نیست", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings(), loadMergedMapping());
    // مقدار مورد انتظار با پایگاه واقعی ۱۴۰۴ پس از مرحلهٔ ۱۱ (حذف ضریب پرت،
    // بقایای تیرچه، زنجیرهٔ مالی جدید) و مرحلهٔ ۱۳ (ایراد ۱/۲/۴).
    expect(r.baseTotal).toBeCloseTo(23218381337.01, -1);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, -1);
  });

  it("سینی ۰۷۰۱۰۱ تورم ندارد (۱۲۵.۷۳ به‌جای ۱۷۲.۶۶)", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings(), loadMergedMapping());
    const line = r.lines.find((l) => l.code === "070101");
    expect(line).toBeDefined();
    expect(line!.qty).toBeCloseTo(125.7346, 1);
  });

  it("سینی‌های ۰۷ مطابق Revit-only + تنها افزودنی اختصاصی v1", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings(), loadMergedMapping());
    const byCode: Record<string, number> = {};
    for (const l of r.lines) byCode[l.code] = l.qty;
    expect(byCode["070201"]).toBeCloseTo(575.978837, 1);
    expect(byCode["070202"]).toBeCloseTo(11550.555303, 1);
    expect(byCode["070203"]).toBeCloseTo(284.1, 1);
  });

  it("فقط ۱ ردیف آرماتور v1 نگه داشته شده (۲۷۶ تکراری skip)", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings(), loadMergedMapping());
    const kept = r.rebar.filter((l) => l.source === "Mapping v1");
    expect(kept).toHaveLength(1);
    expect(kept[0].weight).toBeCloseTo(0.1646, 3);
    expect(kept[0].diameter).toBeCloseTo(8, 6);
  });

  it("بدون mapping، خروجی تغییر نکرده (dedup فقط روی v1 اثر می‌گذارد)", () => {
    const r = computeProject(loadAllTables(), OFFICIAL_1404_FEHREST, defaultSettings(), {
      rows: [],
      format: "v2",
      recordCount: 0,
      warnings: [],
    });
    // ۱۲.۵۳۶ تن × ۲۰ کیلومتر = ۲۵۰.۷۲ تن-کیلومتر (بدون افزودنی v1)
    expect(r.baseTotal).toBeCloseTo(23218306845.90, -1);
    const line = r.lines.find((l) => l.code === "070101");
    expect(line!.qty).toBeCloseTo(125.57, 1);
  });
});
