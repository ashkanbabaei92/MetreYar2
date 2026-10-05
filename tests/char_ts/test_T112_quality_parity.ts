/**
 * T112 — پاریتیِ معیارهای quality و زنجیرهٔ مالی (Part E، شکاف ۷).
 *
 * این آزمون بنابر شکافِ §۱۶-۶ شمارهٔ ۷ ساخته شد: شیتِ Excelِ «کیفیت تطبیق»
 * در پایتون ۹ ردیفِ معیار دارد ولی در TypeScript ۸ ردیف (ردیفِ
 * «رکوردهای Mapping» نیست) و یک شمارش (۸۳۵ = mapping_records) در TS وجود ندارد.
 *
 * تحقیق (این جلسه): موتورها رویِ خطِ لولهٔ یکسان **دقیقاً برابر** هستند —
 * تمامِ معیارهای مشترک و baseTotal/grandTotal bit-identical تأیید شد.
 * اختلاف صرفاً نمایشی (یک ردیفِ کمتر در شیت + برچسب‌ها) است و هیچ اثرِ
 * مالی ندارد. این آزمون آن معیارها را به‌عنوان مرجعِ مشترک تثبیت می‌کند.
 *
 * خطِ لوله: DEMO_FILES (۹ جدول) + fehrest واقعی ۱۴۰۴، بدون mapping،
 * تنظیماتِ پیش‌فرض.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { DEMO_FILES } from "../../src/data/demo";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";

// ── مرجعِ مشترک (در هر دو زبان یکسان — با همین خطِ لوله بررسی شده) ──
const EXPECTED_QUALITY = {
  tablesParsed: 9,
  tablesUnknown: 0,
  rowsRead: 97,
  linesMatched: 15,
  linesExact: 15,
  linesFuzzy: 0,
  linesEstimatedPrice: 0,
  linesNeedReview: 1,
};
const EXPECTED_WARNINGS = 1;
const EXPECTED_BASE_TOTAL = 19659382497.83152;
const EXPECTED_GRAND_TOTAL = 26579485137.06822;

// ── حالتِ دوم: mapping تک‌فایل (مثل UI واقعی) — bit-identical با Python ──
const EXPECTED_MAP2 = {
  lines: 16,
  baseTotal: 20380352396.269382,
  grandTotal: 27554236439.75621,
};

function run() {
  const tables = DEMO_FILES.map((f) => parseRevitFile(f.name, f.text));
  return computeProject(tables, OFFICIAL_1404_FEHREST, defaultSettings());
}

function runWithMap2() {
  const p = path.resolve(__dirname, "..", "..", "data", "dynamo", "mapping2", "map2.txt");
  const raw = fs.readFileSync(p);
  const map = parseDynamoMapping(raw.buffer, "map2.txt");
  const tables = DEMO_FILES.map((f) => parseRevitFile(f.name, f.text));
  return computeProject(tables, OFFICIAL_1404_FEHREST, defaultSettings(), map);
}

describe("T112 — پاریتیِ معیارهای quality (شکاف ۷)", () => {
  it("معیارهای مشترکِ quality با مرجع برابرند (پاریتی با Python)", () => {
    const r = run();
    const q = r.quality;
    for (const [key, want] of Object.entries(EXPECTED_QUALITY)) {
      expect(q[key as keyof typeof q], key).toBe(want);
    }
    expect((q.warnings ?? []).length).toBe(EXPECTED_WARNINGS);
  });

  it("زنجیرهٔ مالی bit-identical با Python است", () => {
    const r = run();
    expect(r.baseTotal).toBeCloseTo(EXPECTED_BASE_TOTAL, 6);
    expect(r.grandTotal).toBeCloseTo(EXPECTED_GRAND_TOTAL, 6);
  });

  it("تعداد خطوط = linesMatched", () => {
    const r = run();
    expect(r.lines.length).toBe(EXPECTED_QUALITY.linesMatched);
  });

  it("TS یک معیارِ کمتر از Python دارد — تفاوتِ نمایشیِ مجاز (§۱۶-۶ شکاف ۷)", () => {
    // پایتون «mapping_records» را هم در شیتِ «کیفیت تطبیق» می‌نویسد (۸۳۵ رکورد
    // رویِ mapping واقعی) ولی TS این معیار را محاسبه نمی‌کند. هیچ اثرِ مالی
    // ندارد — مرجعِ مشترکِ بالا در هر دو زبان برابر است.
    const q = run().quality as Record<string, unknown>;
    expect("mappingRecords" in q).toBe(false);
  });

  it("کلیدهای quality دقیقاً مجموعهٔ مشترک هستند", () => {
    const q = run().quality as Record<string, unknown>;
    const keys = Object.keys(q).filter((k) => k !== "warnings").sort();
    expect(keys).toEqual(Object.keys(EXPECTED_QUALITY).sort());
  });

  it("حالتِ mapping تک‌فایل (مثل UI): نتایج bit-identical با Python است", () => {
    // §۱۸-۹-۱ یادداشتِ شکاف ۷: یک بررسیِ اولیه به‌اشتباه py-با-mapping را
    // با TS-بدون-mapping مقایسه کرد (۱۶ در برابر ۱۵ خط). رویِ پیکربندیِ
    // یکسان نتایج دقیقاً برابر است — این آزمون آن را قفل می‌کند.
    const r = runWithMap2();
    expect(r.lines.length).toBe(EXPECTED_MAP2.lines);
    expect(r.baseTotal).toBeCloseTo(EXPECTED_MAP2.baseTotal, 6);
    expect(r.grandTotal).toBeCloseTo(EXPECTED_MAP2.grandTotal, 6);
  });
});
