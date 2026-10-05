// ─────────────────────────────────────────────────────────────
// T113 — ریشه‌یابیِ اختلافِ برآورد ۱۴۰۵Q1 (فاز E-۷ بخش ۱)
// (آینهٔ test_T113_baravord_reference_numbers.py)
//
// دو عددِ مرجع که نیاز به توضیح داشتند:
//   ۴۵٬۴۳۷٬۷۴۲٬۸۲۰٫۳۲  ← baravordItPeriod = "q4"       (۱۴۰۴Q4 قطعی، پیش‌فرض)
//   ۵۲٬۳۹۲٬۰۷۳٬۸۱۱٫۸۷  ← baravordItPeriod = "1405Q1"  (موقت، CPI + m)
//
// نتیجهٔ ریشه‌یابی: باگ نیست. این دو عدد دو سناریوی متفاوت‌اند (دورهٔ هدفِ
// It). نسبتِ آن‌ها دقیقاً ضریبِ موقتِ ۱۴۰۵Q1 است:
//   ۱ + ۰٫۷ × (۶۱۹٫۶ ÷ میانگین(۴۶۹٫۴، ۵۱۳٫۶، ۵۴۲٫۳) − ۱) = ۱٫۱۵۳۰۵۱۸۵۸۶۵
// و عددِ ۵۲٫۳۹ میلیارد ریال دقیقاً با It = ۱۴۰۵Q1 بازتولید می‌شود.
//
// این آزمون‌ها هر دو عدد را روی خطِ لولهٔ کاملِ پروژهٔ مرجع قفل می‌کنند.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

// ضریب موقت ۱۴۰۵Q1 (بخشنامهٔ ۱۴۴۳۷۳، m=۰٫۷ ابنیه)
const PROV_COEF = 1.1530518586507572;

// ── مقادیرِ مرجعِ استخراج‌شده از موتور (خطِ لولهٔ کامل) ──
const RESULT_Q4 = 45_437_742_820.323151;
const RESULT_1405Q1 = 52_392_073_811.868721;
const GRAND_CURRENT = 31_391_251_567.639599;

// فصل | مبلغ پایه | Io | It(۱۴۰۴Q4) | نسبت | مبلغ به‌هنگام‌شده
const CHAPTERS_Q4: Record<
  string,
  { amount: number; io: number; it: number; ratio: number; value: number }
> = {
  "06": { amount: 12_526_794_300.800001, io: 7273.8, it: 10632.1,
          ratio: 1.461698149523, value: 18_310_392_048.933941 },
  "08": { amount: 11_964_500_668.921591, io: 9787.4, it: 14154.7,
          ratio: 1.446216564154, value: 17_303_259_049.224968 },
  "07": { amount: 6_422_284_001.701364, io: 10794.8, it: 15334.7,
          ratio: 1.420563604699, value: 9_123_262_911.854774 },
  "10": { amount: 468_045_467.354608, io: 8507.9, it: 12489.6,
          ratio: 1.468000329106, value: 687_090_900.113085 },
  "28": { amount: 9_627_128.862033, io: 13243.1, it: 18897.9,
          ratio: 1.426999720609, value: 13_737_910.196390 },
};

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

/** خط لولهٔ مرجع: ۱۰ جدول Revit + نگاشت Dynamo + فهرست‌بهای رسمی ۱۴۰۴. */
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

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    baravordEnabled: true,
    baravordApproved: true,
    ...extra,
  };
}

describe("T113 — ریشه‌یابیِ اختلافِ برآورد ۱۴۰۵Q1", () => {
  it("It = ۱۴۰۴Q4 (پیش‌فرض) ⇒ ۴۵٬۴۳۷٬۷۴۲٬۸۲۰٫۳۲", () => {
    const b = pipeline(on()).adjustment.baravord!;
    expect(b.it_q).toBe("1404Q4");
    expect(b.result_amount).toBeCloseTo(RESULT_Q4, 6);
    expect(b.grand_updated).toBeCloseTo(RESULT_Q4, 6);
    expect(b.grand_current).toBeCloseTo(GRAND_CURRENT, 6);
  }, 120000);

  it("It = ۱۴۰۵Q1 موقت ⇒ ۵۲٬۳۹۲٬۰۷۳٬۸۱۱٫۸۷", () => {
    const b = pipeline(
      on({ baravordItPeriod: "1405Q1", provisionalCoef1405q1: PROV_COEF }),
    ).adjustment.baravord!;
    expect(b.it_q).toBe("1405Q1");
    expect(b.result_amount).toBeCloseTo(RESULT_1405Q1, 6);
  }, 120000);

  it("نسبتِ دو عدد = ضریبِ موقت (علتِ ریشه‌ای)", () => {
    const q4 = pipeline(on()).adjustment.baravord!.result_amount;
    const prov = pipeline(
      on({ baravordItPeriod: "1405Q1", provisionalCoef1405q1: PROV_COEF }),
    ).adjustment.baravord!.result_amount;
    expect(prov / q4).toBeCloseTo(PROV_COEF, 9);
    expect(prov - q4).toBeCloseTo(6_954_330_991.54557, 4);
  }, 240000);

  it("جدولِ فصل‌به‌فصل (It = ۱۴۰۴Q4)", () => {
    const b = pipeline(on()).adjustment.baravord!;
    const rows = new Map(b.chapters.map((r) => [r.chapter, r]));
    expect([...rows.keys()].sort()).toEqual(Object.keys(CHAPTERS_Q4).sort());
    for (const [code, exp] of Object.entries(CHAPTERS_Q4)) {
      const r = rows.get(code)!;
      expect(r.amount).toBeCloseTo(exp.amount, 4);
      expect(r.io).toBeCloseTo(exp.io, 6);
      expect(r.it).toBeCloseTo(exp.it, 6);
      expect(r.ratio).toBeCloseTo(exp.ratio, 9);
      expect(r.value).toBeCloseTo(exp.value, 4);
      expect(r.status).toBe("قطعی");
    }
    // Σ مبالغِ فصل = جمع کلِ فعلی (A)
    expect(b.chapters.reduce((a, r) => a + r.amount, 0)).toBeCloseTo(
      GRAND_CURRENT, 4);
    // Σ مبالغِ به‌هنگام‌شده = نتیجه
    expect(b.chapters.reduce((a, r) => a + r.value, 0)).toBeCloseTo(
      RESULT_Q4, 4);
  }, 120000);

  it("جدولِ فصل‌به‌فصل (It = ۱۴۰۵Q1): همگی موقت، It = قطعی × ضریب", () => {
    const prov = pipeline(
      on({ baravordItPeriod: "1405Q1", provisionalCoef1405q1: PROV_COEF }),
    ).adjustment.baravord!;
    const q4 = new Map(
      pipeline(on()).adjustment.baravord!.chapters.map((r) => [r.chapter, r]));
    for (const r of prov.chapters) {
      expect(r.status).toBe("موقت");
      const q = q4.get(r.chapter)!;
      expect(r.amount).toBeCloseTo(q.amount, 8);
      expect(r.io).toBeCloseTo(q.io, 8);
      // It موقت = It قطعی × ضریب موقت
      expect(r.it).toBeCloseTo(q.it * PROV_COEF, 7);
    }
  }, 240000);
});
