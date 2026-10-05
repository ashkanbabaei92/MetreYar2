import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { loadFixture } from "./helper";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

// ── T06: فرمت خروجی واقعی Revit با doubled-quote («""field"",""field"») ──

describe("T06 doubled-quote real Revit export format", () => {
  it("T06a: fixture parses into real columns (headers/colMap/rows/values)", () => {
    const text = loadFixture("revit/R6_doubled_quote.txt");
    const t = parseRevitFile("R6_doubled_quote.txt", text);

    // سرستون‌ها باید به بیش از یک فیلد تجزیه شوند (نه یک رشتهٔ یکپارچه)
    expect(t.headers.length).toBeGreaterThan(1);
    expect(t.headers).toEqual(["Mark", "Family and Type", "Volume", "Area"]);

    // colMap نباید خالی باشد و باید volume را نگاشت کند
    expect(Object.keys(t.colMap).length).toBeGreaterThan(0);
    expect(t.colMap).toHaveProperty("volume");
    expect(t.colMap.volume).toBe(2);

    // حداقل یک ردیف داده با values غیرخالی
    const dataRows = t.rows.filter((r) => !r.isSubtotal);
    expect(dataRows.length).toBeGreaterThanOrEqual(1);
    const withValues = dataRows.find((r) => Object.keys(r.values).length > 0);
    expect(withValues).toBeDefined();
    expect(withValues!.values.volume).toBeCloseTo(18.65, 5);
    expect(withValues!.values.area).toBeCloseTo(187.0, 5);
    expect(withValues!.texts.mark).toBe("LC-01");

    // سطر جداکنندهٔ خالی نباید به‌عنوان داده ثبت شود
    expect(t.rows.length).toBe(2);

    // BOM نباید در عنوان باقی بماند
    expect(t.title).not.toMatch(/\ufeff/);
    expect(t.kind).toBe("lean_concrete");
  });

  it("T06b: parity with Python parser on the real Foundation Concrete export", () => {
    const dir = path.join(__dirname, "..", "..", "data", "export revit");
    const fname = "جدول بتن\u200cریزی پی - Foundation Concrete Schedule.txt";
    const text = fs.readFileSync(path.join(dir, fname), "utf-8");
    const t = parseRevitFile(fname, text);

    // هماهنگی با نتیجهٔ پارسر پایتون روی همان فایل واقعی
    expect(t.kind).toBe("structural_concrete");
    expect(t.colMap).toHaveProperty("volume");
    expect(t.colMap).toHaveProperty("mark");

    // قبلاً ۱۵ ردیف (آلوده به سطرهای جداکننده) می‌شد؛ اکنون باید ۱۳ باشد
    expect(t.rows.length).toBe(13);

    // grand_total باید شناسایی شود و volume برابر ۱۵۲.۸۴ باشد
    expect(t.grandTotal).toBeDefined();
    expect(t.grandTotal!.volume).toBeCloseTo(152.84, 1);
    expect(t.grandTotal!.length).toBeCloseTo(92.94691, 4);
  });
});
