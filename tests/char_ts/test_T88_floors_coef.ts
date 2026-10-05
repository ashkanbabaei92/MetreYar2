// T88 — ضریب طبقات (ایراد ۳ — مرحلهٔ ۱۳) + انتخاب دستیِ طبقه بودن هر تراز (بند ۱).
//
// پیوست ۴ فهرست‌بهای ابنیه ۱۴۰۴: P = 1 + [Σ(i×Fi) + Σ(j×Bj)] ÷ (100×S).
// تراز فونداسیون (Foundation Top) طبقه نیست — پی است، نه زیرهمکف — و در Σ
// نمی‌آید. هر تراز را می‌توان دستی «طبقه» علامت زد (→ below_base B1) یا
// غیرطبقه‌ای کرد. همتای پایتونی: tests/char_python/test_T88_floors_coef.py.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { floorsTable, levelKind } from "../../src/lib/floors";
import type { ProjectSettings, QuantityRecord } from "../../src/lib/types";

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

describe("T88 — ضریب طبقات و انتخاب دستیِ طبقه بودن ترازها", () => {
  it("levelKind: طبقه‌بندی ترازهای Revit (Foundation Top غیرطبقه‌ای)", () => {
    expect(levelKind("Story1")).toEqual(["ground", 0]);
    expect(levelKind("Story2")).toEqual(["above", 1]);
    expect(levelKind("Story6")).toEqual(["above", 5]);
    // تراز فونداسیون طبقه نیست (درخواست کاربر — بند ۱)
    expect(levelKind("Foundation Top")).toEqual(["none", 0]);
    expect(levelKind("Roof")).toBeNull();
  });

  it("جدول طبقات پروژهٔ مرجع: ۷ تراز؛ Foundation Top غیرطبقه‌ای، Story6 بام", () => {
    const r = pipeline(defaultSettings());
    const rows: QuantityRecord[] = r.records;
    const table = floorsTable(rows, defaultSettings());
    const byName = Object.fromEntries(table.map((x) => [x.name, x]));
    expect(table).toHaveLength(7);
    expect(byName["Foundation Top"].kind).toBe("none"); // پی، نه زیرهمکف
    expect(byName["Foundation Top"].autoKind).toBe("none");
    expect(byName["Foundation Top"].index).toBe(0); // مستثنی از Σ
    expect(byName["Story1"].kind).toBe("ground");
    expect(byName["Story1"].areaModel).toBeCloseTo(63.0, 6);
    expect(byName["Story2"].index).toBe(1); // F1 (بام Story6 مستثنی)
    expect(byName["Story5"].index).toBe(4); // F4
    expect(byName["Story6"].kind).toBe("roof");
    expect(byName["Story6"].areaModel).toBe(null); // نیازمند ورود دستی
  }, 120000);

  it("با ورود مساحت ۵ طبقه: صورت ۶۳۰، مخرج ۱۰۰×۳۱۵۰۰ → P = ۱/۰۲", () => {
    const areas: Record<string, number> = {
      "Foundation Top": 63.0, Story1: 63.0, Story2: 63.0,
      Story3: 63.0, Story4: 63.0, Story5: 63.0,
    };
    const r = pipeline({ ...defaultSettings(), floorsData: areas });
    const fc = r.coefs.floors;
    expect(fc.value).toBeCloseTo(1.02, 9);
    expect(fc.status).toBe("محاسبه‌شده");
    expect(fc.calc.pAlt).toBeCloseTo(3.0, 9);
    expect(r.floorsAmount).toBeCloseTo(
      fc.eligibleTotal * (fc.value as number) + fc.excludedTotal,
      0,
    );
    expect(r.grandTotal).toBeCloseTo(r.floorsAmount * 1.3 * 1.04, 0);
    expect(
      r.warnings.some((w: any) => w.category === "ضریب طبقات" && w.level === "خطا"),
    ).toBe(false);
    const byName = Object.fromEntries(fc.rows.map((x: any) => [x.name, x]));
    expect(byName["Story6"].kind).toBe("roof");
    expect(byName["Foundation Top"].kind).toBe("none");
  }, 120000);

  it("بدون استثنای بام ولی Foundation Top همچنان غیرطبقه‌ای: P = ۱/۰۲۵", () => {
    const areas: Record<string, number> = {
      "Foundation Top": 63.0, Story1: 63.0, Story2: 63.0, Story3: 63.0,
      Story4: 63.0, Story5: 63.0, Story6: 63.0,
    };
    const r = pipeline({
      ...defaultSettings(),
      floorsData: areas,
      floorsRoofLevels: [] as string[],
    });
    const fc = r.coefs.floors;
    expect(fc.value).toBeCloseTo(1.025, 9);
    expect(fc.calc.pAlt).toBeCloseTo(3.5, 9);
  }, 120000);

  it("isFloor=true: Foundation Top به B1 برمی‌گردد → P = ۶۱۱/۶۰۰", () => {
    const r = pipeline({
      ...defaultSettings(),
      floorsData: {
        "Foundation Top": { area: 63.0, isFloor: true },
        Story1: 63.0, Story2: 63.0, Story3: 63.0,
        Story4: 63.0, Story5: 63.0,
      },
    });
    const fc = r.coefs.floors;
    // صورت = (۱+۲+۳+۴)×۶۳ + ۱×۶۳ (B1) = ۶۹۳؛ مخرج ۱۰۰×۶×۶۳ = ۳۷۸۰۰
    expect(fc.value).toBeCloseTo(611 / 600, 9);
    const byName = Object.fromEntries(fc.rows.map((x: any) => [x.name, x]));
    expect(byName["Foundation Top"].kind).toBe("below_base");
    expect(byName["Foundation Top"].index).toBe(1);
  }, 120000);

  it("isFloor=false: یک طبقهٔ بالاتر از Σ خارج می‌شود (با شماره‌گذاری مجدد)", () => {
    const r = pipeline({
      ...defaultSettings(),
      floorsData: {
        Story1: 63.0,
        Story2: { area: 63.0, isFloor: false },
        Story3: 63.0, Story4: 63.0, Story5: 63.0,
      },
    });
    const fc = r.coefs.floors;
    // Story2 حذف → F1..F3 = Story3..Story5: صورت = ۶×۶۳ = ۳۷۸؛
    // مخرج ۱۰۰×۴×۶۳ = ۲۵۲۰۰ → P = ۱ + ۳۷۸/۲۵۲۰۰ = ۱/۰۱۵
    expect(fc.value).toBeCloseTo(1.015, 9);
    const byName = Object.fromEntries(fc.rows.map((x: any) => [x.name, x]));
    expect(byName["Story2"].kind).toBe("none");
  }, 120000);

  it("مخرج «S» هشدار مغایرت ثبت می‌کند: P = ۳", () => {
    const areas: Record<string, number> = {
      "Foundation Top": 63.0, Story1: 63.0, Story2: 63.0,
      Story3: 63.0, Story4: 63.0, Story5: 63.0,
    };
    const r = pipeline({
      ...defaultSettings(),
      floorsData: areas,
      floorsDivisor: "S" as never,
    });
    expect(r.coefs.floors.value).toBeCloseTo(3.0, 9);
    const dev = r.warnings.find(
      (w: any) => w.category === "ضریب طبقات" && w.level === "هشدار",
    );
    expect(dev).toBeTruthy();
    expect(dev.message).toContain("مغایر");
  }, 120000);

  // ─ـ فاز E-6 Part C گام ۱۰ (حرف d): کمتر از ۵ طبقه و S = ۰ ──
  it("کمتر از ۵ طبقه: صورت ۶۳، مخرج ۱۰۰×۱۲۶۰۰ → P = ۱/۰۰۵", () => {
    const areas: Record<string, any> = {
      "Foundation Top": 63.0, Story1: 63.0, Story2: 63.0,
      Story3: { area: 63.0, isFloor: false },
      Story4: { area: 63.0, isFloor: false },
      Story5: { area: 63.0, isFloor: false },
    };
    const r = pipeline({ ...defaultSettings(), floorsData: areas });
    const fc = r.coefs.floors;
    expect(fc.value).toBeCloseTo(1.005, 9);
    expect(fc.status).toBe("محاسبه‌شده");
    const byName = Object.fromEntries(fc.rows.map((x: any) => [x.name, x]));
    expect(byName["Story2"].index).toBe(1);
    expect(byName["Story3"].kind).toBe("none");
    expect(
      r.warnings.some(
        (w: any) => w.category === "ضریب طبقات" && w.level === "خطا",
      ),
    ).toBe(false);
  }, 120000);

  it("S = ۰ (مساحت‌های صفر): ضریب ۱ + «ناقص» + هشدار", () => {
    const areas: Record<string, number> = {
      "Foundation Top": 0, Story1: 0, Story2: 0,
      Story3: 0, Story4: 0, Story5: 0,
    };
    const r = pipeline({ ...defaultSettings(), floorsData: areas });
    const fc = r.coefs.floors;
    expect(fc.value).toBeCloseTo(1.0, 9);
    expect(fc.status).toBe("ناقص");
    expect(
      r.warnings.some(
        (w: any) =>
          w.category === "ضریب طبقات" &&
          w.level === "هشدار" &&
          w.message.includes("هیچ مساحت"),
      ),
    ).toBe(true);
  }, 120000);

  it("همهٔ ترازها غیرطبقه: صورت و مخرج صفر → ضریب ۱ + «ناقص»", () => {
    const areas: Record<string, any> = {};
    for (const k of ["Foundation Top", "Story1", "Story2", "Story3",
                     "Story4", "Story5"]) {
      areas[k] = { area: 63.0, isFloor: false };
    }
    const r = pipeline({ ...defaultSettings(), floorsData: areas });
    const fc = r.coefs.floors;
    expect(fc.value).toBeCloseTo(1.0, 9);
    expect(fc.status).toBe("ناقص");
    expect(
      r.warnings.some(
        (w: any) =>
          w.category === "ضریب طبقات" && w.message.includes("هیچ مساحت"),
      ),
    ).toBe(true);
  }, 120000);
});
