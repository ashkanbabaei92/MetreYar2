import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import type { TableKind } from "../../src/lib/types";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

// ── T07: parity جامع پارسر TS با پارسر Python روی هر ۱۰ فایل واقعی ──
// مقادیر مورد انتظار از خروجی RevitScheduleParser.parse(app.py) روی همین
// فایل‌ها استخراج شده‌اند (شناسهٔ پرونده: بررسی parity در تحقیقات قبل).

interface Expect {
  kind: TableKind;
  rows: number;
  subtotals: number;
  // null یعنی Python هم grand_total خالی دارد
  grandTotal: Record<string, number> | null;
  colMap: string[];
}

const EXPECTED: Expect[] = [
  { kind: "structural_concrete", rows: 13, subtotals: 0,
    grandTotal: { length: 92.94691, volume: 152.84, area: 169.82 },
    colMap: ["area", "familyType", "length", "mark", "volume"] },
  { kind: "rebar_detailed", rows: 117, subtotals: 0,
    grandTotal: { col7: 2359, length: 7832.02, volume: 1.5418, weight: 12103.47 },
    // «hostCategory» و «hostMark» از مرحلهٔ ۶/۱۱ به بعد نگه داشته می‌شوند
    // (مبنای ردیف ۰۸۰۳۱۱ per-element — بند ۳-۶ فصل ۸)
    colMap: ["diameter", "hostCategory", "hostMark", "length", "material", "shape", "spacing", "volume", "weight"] },
  { kind: "rebar_connection", rows: 13, subtotals: 0,
    grandTotal: { weight: 99.43 },
    colMap: ["diameter", "length", "mark", "weight"] },
  { kind: "rebar_joist", rows: 6, subtotals: 3,
    grandTotal: { volume: 0.04, weight: 333.31414 },
    colMap: ["familyType", "mark", "material", "volume", "weight"] },
  { kind: "lean_concrete", rows: 1, subtotals: 0,
    grandTotal: null,
    colMap: ["area", "familyType", "mark", "volume"] },
  { kind: "structural_concrete", rows: 130, subtotals: 0,
    grandTotal: { volume: 433.72 },
    colMap: ["category", "level", "mark", "material", "volume"] },
  { kind: "joist_floor", rows: 13, subtotals: 0,
    grandTotal: { length: 74.48456, count: 13, volume: 8.42 },
    colMap: ["count", "familyType", "length", "level", "mark", "volume"] },
  { kind: "formwork_super", rows: 116, subtotals: 0,
    grandTotal: { area: 2419 },
    colMap: ["area", "category", "familyType", "level", "mark", "material"] },
  { kind: "formwork_foundation", rows: 13, subtotals: 0,
    grandTotal: { area: 167.3 },
    colMap: ["area", "familyType", "length", "mark", "width"] },
  { kind: "joist_materials", rows: 4, subtotals: 2,
    grandTotal: { volume: 8.38 },
    colMap: ["familyType", "mark", "material", "volume"] },
];

function loadRealFiles(): { name: string; text: string }[] {
  const dir = path.join(__dirname, "..", "..", "data", "export revit");
  return fs
    .readdirSync(dir)
    .sort()
    .map((name) => ({ name, text: fs.readFileSync(path.join(dir, name), "utf-8") }));
}

describe("T07 parity: all 10 real Revit exports vs Python parser", () => {
  it("exposes exactly 10 real export files", () => {
    expect(loadRealFiles().length).toBe(10);
  });

  it.each(EXPECTED.map((e, i) => ({ e, i })))(
    "file #$i matches Python: kind=$e.kind rows=$e.rows subtotals=$e.subtotals",
    ({ e, i }) => {
      const files = loadRealFiles();
      const f = files[i];
      const t = parseRevitFile(f.name, f.text);

      // نوع جدول
      expect(t.kind).toBe(e.kind);

      // تعداد ردیف‌های داده (بدون سطرهای جداکنندهٔ آلوده)
      expect(t.rows.length).toBe(e.rows);

      // تعداد ردیف‌های جمع‌جزئی
      expect(t.rows.filter((r) => r.isSubtotal).length).toBe(e.subtotals);

      // کلیدهای colMap (مرتب‌شده) باید با Python یکی باشد
      expect(Object.keys(t.colMap).sort()).toEqual(e.colMap);

      // grand_total: برای فایل‌هایی که Python مقدار دارد باید غیرخالی و برابر باشد
      if (e.grandTotal) {
        expect(t.grandTotal).toBeDefined();
        for (const [k, v] of Object.entries(e.grandTotal)) {
          expect(t.grandTotal![k]).toBeCloseTo(v, 4);
        }
      } else {
        // Python در این فایل grand_total خالی دارد
        expect(Object.keys(t.grandTotal ?? {}).length).toBe(0);
      }

      // هیچ هشدار غیرمنتظره‌ای نباید باشد
      expect(t.warnings).toEqual([]);
    },
  );
});
