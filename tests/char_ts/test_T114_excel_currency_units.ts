// ─────────────────────────────────────────────────────────────
// T114 — یکدستیِ واحدِ پول در خروجیِ Excel (فاز E-۷ بخش ۲)
// (آینهٔ test_T114_excel_currency_units.py)
//
// قاعده: هر ستونِ پولی (و هر برچسبِ ردیفِ پولی) در همهٔ شیت‌های Excel باید
// واحدِ «ریال» را در برچسب خود داشته باشد. واحدِ استانداردِ پروژه ریال است؛
// تومان فقط در نمایشِ انتخابیِ کاربر (fmtMoneyVal) دیده می‌شود و هرگز در
// خروجیِ Excel نمی‌آید.
//
// این آزمون:
//   ۱) برچسب‌های پولیِ مورد انتظار را بررسی می‌کند (همگی «ریال» دارند)؛
//   ۲) متغیرهایِ بدونِ «ریال» را ممنوع می‌کند (در صورتِ افزودنِ ستونِ
//      پولیِ بدونِ برچسب، آزمون شکست می‌خورد).
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { exportWorkbook } from "../../src/lib/exporters";
import { fmtMoneyVal } from "../../src/lib/farsi";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const PROV_COEF = 1.1530518586507572;

// برچسب‌های پولی که باید «ریال» داشته باشند (ستون‌ها و ردیف‌های جمع)
const MONEY_LABELS = [
  // شیتِ خلاصهٔ مالی و برآورد
  "مبلغ (ریال)", "مبلغ کل (ریال)",
  // شیتِ صورت وضعیت
  "بهای واحد (ریال)", "بهای کل (پایه، ریال)", "بهای کل (به‌هنگام، ریال)",
  "بهای فهرست (ریال)", "بهای دستی (ریال)",
  // شیتِ سوابق صورت وضعیت
  "ناخالص تجمعی (ریال)", "کسورات تجمعی (ریال)", "خالص تجمعی (ریال)",
  "کارکرد این دوره (ریال)",
  // شیتِ تعدیل پیمان / برآورد به‌هنگام / بخش قطعی
  "مبلغ پایه (A_c، ریال)", "مبلغ تعدیل (ΔP_c، ریال)",
  "مبلغ به‌هنگام‌شده (ریال)",
  "بخش قطعی (ریال)", "بخش علی‌الحساب (ریال)",
  "جمع تعدیل (شامل علی‌الحساب، ریال)",
  "بخش قطعی (شاخص‌های قطعی ۱۴۰۴، ریال)",
  "بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1، ریال)",
  "مابه‌التفاوت k = ۰٫۹۵ → ۱ (تبصرهٔ ۲ — همراه قطعی، بند ۸-۴، ریال)",
  "کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷، ریال)",
  "مبلغ نهایی (A + جمع تعدیل، ریال)",
  "برآورد به‌هنگام‌شده (ریال)",
  "زنجیرهٔ مبلغ پایه (A) — مبالغ به ریال",
  // شیتِ ضرایب
  "تجهیز و برچیدن کارگاه (ریال)",
];

// متغیرهایِ ممنوع: برچسب‌های پولیِ بدونِ «ریال» (نگه‌دارندهٔ رگرسیون).
// توجه: اینها زیررشتهٔ برچسب‌هایِ مجاز هستند، پس با includes() بررسی
// نمی‌شوند — باید به‌عنوانِ مقدارِ دقیقِ یک سلول ظاهر نشوند.
const FORBIDDEN_EXACT = [
  "بهای واحد", "بهای کل (پایه)", "بهای کل (به‌هنگام)",
  "بهای فهرست", "بهای دستی",
  "ناخالص تجمعی", "کسورات تجمعی", "خالص تجمعی", "کارکرد این دوره",
  "مبلغ پایه (A_c)", "مبلغ تعدیل (ΔP_c)", "مبلغ به‌هنگام‌شده",
  "جمع تعدیل (شامل علی‌الحساب)", "مبلغ نهایی (A + جمع تعدیل)",
  "برآورد به‌هنگام‌شده",
];

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function pipeline(settings: ProjectSettings): ProjectResult {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .filter((f) => f.endsWith(".txt"))
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows: unknown[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const sd = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(sd).isDirectory()) continue;
    for (const fn of fs.readdirSync(sd).sort()) {
      if (!fn.endsWith(".txt")) continue;
      (rows as unknown[]).push(
        ...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows);
    }
  }
  return computeProject(tables, OFFICIAL_1404_FEHREST, settings, {
    rows: rows as never,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
}

const XLS_EXTRA: Partial<ProjectSettings> = {
  tadilEnabled: true,
  baravordEnabled: true,
  proposalDate: "۱۴۰۳/۱۲/۲۹",
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
  provisionalCoef1405q1: PROV_COEF,
  completedWithinTerm: true,
  contractStatus: "فسخ با قصور",
};

function exportWb(result: ProjectResult, settings: ProjectSettings): XLSX.WorkBook {
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook(
      { projectName: "T114", reportNo: "1" } as never,
      result,
      settings,
      [] as never,
    );
  } finally {
    mock.mockRestore();
  }
  return wb as XLSX.WorkBook;
}

/** همهٔ رشته‌های یک کتاب‌کار (معادل sharedStrings در Python). */
function allStrings(wb: XLSX.WorkBook): string[] {
  const out: string[] = [];
  for (const name of wb.SheetNames) {
    const ws = wb.Sheets[name] ?? {};
    for (const addr in ws) {
      if (addr.startsWith("!")) continue;
      const c = ws[addr as never] as { v?: unknown } | undefined;
      if (typeof c?.v === "string") out.push(c.v);
    }
  }
  return out;
}

describe("T114 — یکدستیِ واحدِ پول در Excel", () => {
  let strs: string[];
  let names: string[];

  it("تمامِ برچسب‌های پولی «ریال» دارند", () => {
    const res = pipeline({ ...defaultSettings(), ...XLS_EXTRA });
    const wb = exportWb(res, { ...defaultSettings(), ...XLS_EXTRA });
    strs = allStrings(wb);
    names = wb.SheetNames;
    const missing = MONEY_LABELS.filter((m) => !strs.includes(m));
    expect(missing).toEqual([]);
    // همهٔ برچسب‌ها واقعاً «ریال» دارند
    expect(MONEY_LABELS.every((m) => m.includes("ریال"))).toBe(true);
  }, 120000);

  it("هیچ برچسبِ پولیِ بدونِ «ریال» وجود ندارد", () => {
    expect(strs).toBeDefined();
    const bad = FORBIDDEN_EXACT.filter((f) => strs.includes(f));
    expect(bad).toEqual([]);
  }, 30000);

  it("هیچ «تومانی» در خروجیِ Excel نیست", () => {
    // خروجیِ Excel همیشه ریال است؛ «تومان» فقط در نمایشِ UIِ انتخابی است.
    expect(strs).not.toContain("میلیارد تومان");
    expect(strs).not.toContain("تومان");
  }, 30000);

  it("شیت‌های پولی موجودند", () => {
    for (const name of [
      "خلاصهٔ مالی و برآورد", "صورت وضعیت", "سوابق صورت وضعیت",
      "تعدیل پیمان", "برآورد به‌هنگام", "بخش قطعی و علی‌الحساب",
    ]) {
      expect(names).toContain(name);
    }
  }, 30000);
});

// ── تابعِ نمایشِ پول (UI): واحد همیشه present، تبدیلِ تومان = ÷۱۰ ──
// آینهٔ test_T114_excel_currency_units.py (fmt_money)

describe("T114 — تابعِ نمایشِ پول (fmtMoneyVal)", () => {
  it("واحدِ پیش‌فرض ریال و تبدیلِ تومان = ریال ÷ ۱۰", () => {
    expect(fmtMoneyVal(1234567890, { currency: "rial", rounding: false }))
      .toBe("۱,۲۳۴,۵۶۷,۸۹۰ ریال");
    expect(fmtMoneyVal(1234567890, { currency: "toman", rounding: false }))
      .toBe("۱۲۳,۴۵۶,۷۸۹.۰ تومان");
    // رندِ پیش‌فرض به ۱۰۰۰ ریال
    expect(fmtMoneyVal(1000, { currency: "toman" })).toBe("۱۰۰.۰ تومان");
    expect(fmtMoneyVal(1000, { currency: "rial" })).toBe("۱,۰۰۰ ریال");
    // بدونِ واحد
    expect(fmtMoneyVal(1234567890, { currency: "rial", rounding: false, withUnit: false }))
      .toBe("۱,۲۳۴,۵۶۷,۸۹۰");
  }, 30000);

  it("رند به ۱۰۰۰ ریال (پیش‌فرض روشن)", () => {
    expect(fmtMoneyVal(1499, { currency: "rial" })).toBe("۱,۰۰۰ ریال");
    expect(fmtMoneyVal(1500, { currency: "rial" })).toBe("۲,۰۰۰ ریال");
    expect(fmtMoneyVal(1499, { currency: "rial", rounding: false }))
      .toBe("۱,۴۹۹ ریال");
  }, 30000);

  it("هرگز خروجیِ پولی بدونِ واحدِ صریح نیست", () => {
    for (const cur of ["rial", "toman"] as const) {
      const s = fmtMoneyVal(999999999999, { currency: cur });
      expect(s.includes("ریال") || s.includes("تومان")).toBe(true);
    }
  }, 30000);
});
