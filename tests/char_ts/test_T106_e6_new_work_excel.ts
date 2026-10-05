// ─────────────────────────────────────────────────────────────
// T106 — فاز E-6 Part C گام ۵: ردیفِ «کار جدید» در خروجی Excel
//
// هر سه ناحیه‌ای که ردیفِ کار جدید باید ظاهر شود:
//   ۱) شیتِ «تعدیل پیمان» (جزئیاتِ فصول + تجهیز + کار جدید)
//   ۲) شیتِ «برآورد به‌هنگام» (جزئیاتِ فصول + تجهیر + کار جدید)
//   ۳) شیتِ «بخش قطعی و علی‌الحساب» (مبلغ + delta قطعی/علی‌الحساب)
//
// پاریتی با Python: نسخهٔ Python
// (tests/char_python/test_T106_e6_new_work_excel.py) همان اعداد را از
// همان موتور می‌خواند. نکته: app.py مقادیر را با fa_float به‌صورتِ متنِ
// فارسیِ قالب‌بندی‌شده در سلول می‌نویسد، در حالی که TS سلولِ عددی می‌نویسد
// (تفاوتِ از‌پیش‌موجودِ هر دو پیاده‌سازی برای همهٔ ردیف‌ها)؛ پاریتی روی
// اعداد بررسی می‌شود، نه روی بایت‌های سلول.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { exportWorkbook } from "../../src/lib/exporters";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { parseFehrestText, mergeFehrest } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");

// اعداد مرجعِ کار جدید (رشتهٔ ابنیه، ۳-۲، مبلغ ۱e۹، مبنا ۱۴۰۴Q۲)
const REF = {
  amount: 883664623.308789, // ۱e۹ × (۹۷۴۴٫۷/۱۱۶۰۸)/۰٫۹۵
  io: 9744.7,
  itTadil: 12460.173698630137,
  ratioTadil: 1.2786616005244016,
  valueTadil: 234449540.05814552,
  itBaravord: 14333.1,
  ratioBaravord: 1.470861083460753,
  valueBaravord: 1299747905.2559035,
};

function settings(): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    baravordEnabled: true,
    proposalDate: "۱۴۰۳/۱۲/۲۹",
    workPeriodStart: "۱۴۰۴/۰۱/۰۱",
    workPeriodEnd: "۱۴۰۴/۱۲/۲۹",
    newItemMethod: "فهرست پایه",
    newItemAmount: 1_000_000_000,
    newItemBasePeriod: "1404Q2",
  };
}

function realPipeline(s: ProjectSettings) {
  const revitDir = path.join(ROOT, "data", "export revit");
  const tables = fs.readdirSync(revitDir).sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(revitDir, f), "utf-8")));
  const rows: any[] = [];
  const dynamoDir = path.join(ROOT, "data", "dynamo");
  for (const sub of fs.readdirSync(dynamoDir).sort()) {
    const subDir = path.join(dynamoDir, sub);
    if (!fs.statSync(subDir).isDirectory()) continue;
    for (const fn of fs.readdirSync(subDir).sort()) {
      if (!fn.endsWith(".txt")) continue;
      const b = fs.readFileSync(path.join(subDir, fn));
      rows.push(...parseDynamoMapping(
        b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as never, fn).rows);
    }
  }
  const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
  const fehrestFile = path.join(ROOT, "data", "fehrest baha 1404", "all 1404 fehrest.txt");
  const db = mergeFehrest(OFFICIAL_1404_FEHREST, parseFehrestText(fs.readFileSync(fehrestFile, "utf-8")));
  return computeProject(tables as never, db, s, mapping as never);
}

/** ردیف‌های «کار جدید» را از هر شیت برمی‌گردارد: {sheet: rowArray}. */
function newWorkRows(result: any, s: ProjectSettings): Record<string, any[]> {
  let wb: any;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: any) => { wb = value; });
  try {
    exportWorkbook({ projectName: "T106", reportNo: "1" } as any, result, s, []);
  } finally {
    mock.mockRestore();
  }
  const out: Record<string, any[]> = {};
  for (const sheet of wb.SheetNames) {
    const rows = XLSX.utils.sheet_to_json<any[]>(wb.Sheets[sheet], { header: 1 });
    for (const r of rows) {
      if (r[0] === "کار جدید") out[sheet] = r;
    }
  }
  return out;
}

describe("T106 — کار جدید در خروجی Excel (۳ ناحیه)", () => {
  // ── ۱) ردیفِ کار جدید در هر سه ناحیه هست ──
  it("row present in all three sheets", () => {
    const r = realPipeline(settings());
    const rows = newWorkRows(r, settings());
    expect(Object.keys(rows).sort()).toEqual(
      ["برآورد به‌هنگام", "تعدیل پیمان", "بخش قطعی و علی‌الحساب"].sort(),
    );
  });

  // ── ۲) شیتِ تعدیل پیمان: مقدار/شاخص‌ها/مبلغ تعدیل ──
  it("tadil detail row carries engine values", () => {
    const s = settings();
    const r = realPipeline(s);
    const rows = newWorkRows(r, s);
    const nr = r.adjustment.tadil.new_work_row;
    const v = rows["تعدیل پیمان"];
    expect(v[1]).toBe("کار جدید (فهرست پایه) - بندهای ۳-۱..۳-۵");
    expect(v[2]).toBe(Math.round(nr.amount));
    expect(v[3]).toBeCloseTo(nr.io, 4);
    expect(v[4]).toBeCloseTo(nr.it, 4);
    expect(v[5]).toBeCloseTo(nr.ratio, 6);
    expect(v[6]).toBe(Math.round(nr.value));
    expect(v[7]).toBe(`${nr.status} - ${nr.src}`);
    // اعدادِ مرجع
    expect(nr.amount).toBeCloseTo(REF.amount, 4);
    expect(nr.io).toBeCloseTo(REF.io, 4);
    expect(nr.it).toBeCloseTo(REF.itTadil, 4);
    expect(nr.ratio).toBeCloseTo(REF.ratioTadil, 8);
    expect(nr.value).toBeCloseTo(REF.valueTadil, 4);
  });

  // ── ۳) شیتِ برآورد به‌هنگام: It برآوردی متفاوت ──
  it("baravord detail row carries engine values", () => {
    const s = settings();
    const r = realPipeline(s);
    const rows = newWorkRows(r, s);
    const nr = r.adjustment.baravord.new_work_row;
    const v = rows["برآورد به‌هنگام"];
    expect(v[1]).toBe("کار جدید (فهرست پایه) - بندهای ۳-۱..۳-۵");
    expect(v[2]).toBe(Math.round(nr.amount));
    expect(v[3]).toBeCloseTo(nr.io, 4);
    expect(v[4]).toBeCloseTo(nr.it, 4);
    expect(v[5]).toBeCloseTo(nr.ratio, 6);
    expect(v[6]).toBe(Math.round(nr.value));
    expect(nr.amount).toBeCloseTo(REF.amount, 4);
    expect(nr.it).toBeCloseTo(REF.itBaravord, 4);
    expect(nr.ratio).toBeCloseTo(REF.ratioBaravord, 8);
    expect(nr.value).toBeCloseTo(REF.valueBaravord, 4);
  });

  // ── ۴) شیتِ بخش قطعی و علی‌الحساب: تجمیع در td/tp ──
  it("definitive/provisional row carries delta split", () => {
    const s = settings();
    const r = realPipeline(s);
    const rows = newWorkRows(r, s);
    const nr = r.adjustment.tadil.new_work_row;
    const v = rows["بخش قطعی و علی‌الحساب"];
    expect(v[2]).toBe(Math.round(nr.amount));
    expect(v[3]).toBe(Math.round(nr.deltaDefinitive));
    expect(v[4]).toBe(Math.round(nr.delta - nr.deltaDefinitive));
    expect(v[5]).toBe(Math.round(nr.delta));
    expect(v[6]).toBe("همان منطقِ تجهیز (شاخص رشته)");
    expect(nr.delta).toBeCloseTo(REF.valueTadil, 4);
    expect(nr.deltaDefinitive).toBeCloseTo(REF.valueTadil, 4);
  });

  // ── ۵) بدون کار جدید، ردیفی در هیچ شیت نیست ──
  it("no new work ⇒ no row in any sheet", () => {
    const s = settings();
    (s as any).newItemMethod = "فهرست پیمان";
    (s as any).newItemAmount = 0;
    const r = realPipeline(s);
    const rows = newWorkRows(r, s);
    expect(Object.keys(rows)).toHaveLength(0);
  });
});
