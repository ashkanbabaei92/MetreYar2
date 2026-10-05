// T119 — فاز E-9 §۳.۳ (بند ۵: فصلِ حملِ ردیف‌های مترمکعب‌کیلومتر) و
//        فاز E-9 §۳.۶ (جانشانیِ خودکارِ موقت→قطعی).
//
// §۳.۳ — بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵ (صفحهٔ ۲): ردیف‌های پایه‌ای با
//        واحدِ «مترمکعب کیلومتر» که حملِ آن‌ها در فصل‌های غیر از فصل حمل
//        منظور شده، با شاخص‌های فصل حمل همان رشته تعدیل می‌شوند.
// §۳.۶ — بند ۳ بخشنامهٔ ۱۴۴۳۷۳: هنگامی که شاخصِ قطعیِ یک سه‌ماههٔ ۱۴۰۵
//        اعلام و وارد شد، موتورها خودبه‌خود از آن استفاده می‌کنند.
//
// همتایِ Python این آزمون: tests/char_python/test_T119_clause5_definitive.py
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";
import { defaultSettings } from "../../src/lib/engine";
import {
  baravordEngine,
  haulTargetChapter,
  isHaulUnit,
  quarterDiscipline,
  quarterIndex,
  tadilEngine,
} from "../../src/lib/adjustment";

const ROOT = path.join(__dirname, "..", "..");
const REAL_CFG = JSON.parse(
  fs.readFileSync(path.join(ROOT, "config", "index_bulletins.json"), "utf-8"),
) as Record<string, any>;

const CH06: [number, number] = [7273.8, 10632.1]; // فصل ۶ قالب‌بندی — صفحهٔ ۶
const CH28: [number, number] = [13243.1, 18897.9]; // فصل ۲۸ حمل‌ونقل — صفحهٔ ۷
const A_TEST = 10_000_000_000.0;
const OH = 1.3;
const REG = 1.04;
const PROP = 1.0;
const PRICE_MULT = OH * REG * PROP; // ۱٫۳۵۲
const PROV_COEF = 1.1530518586507572;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"; // ⇒ Io = اسفند ۱۴۰۳ (مبنا)

function ctx(opts?: {
  chapters?: Record<string, number>;
  base?: number;
  haulMoved?: number;
}): AdjustmentCtx {
  const base = opts?.base ?? A_TEST;
  return {
    chapter_amounts: opts?.chapters ?? { "06": base },
    haul_moved_amount: opts?.haulMoved ?? 0,
    floors_amount: base,
    base_total: base,
    site_setup: 0,
    advance_payment: 0,
    overhead_coef: OH,
    regional_coef: REG,
    grand_total: base * PRICE_MULT,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: base,
      excluded_total: 0.0,
    },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    tadilApproved: true,
    proposalDate: PROPOSAL_DATE,
    ...extra,
  };
}

/** بارگذاریِ دوبارهٔ adjustment با config ای که definitive_1405 آن جایگزین شده.
 * قاعدهٔ طلاییِ vitest: doMock باید قبل از importِ ماژولِ تازه اجرا شود. */
async function importWithDefinitive(
  quarters: Record<string, any>,
  disciplines: any[] = [],
  chapters: any[] = [],
) {
  vi.resetModules();
  vi.doMock("../../config/index_bulletins.json", () => ({
    default: {
      ...REAL_CFG,
      definitive_1405: { quarters, disciplines, chapters_abnieh: chapters },
    },
  }));
  return await import("../../src/lib/adjustment");
}

// ═════════ §۳.۳ — بند ۵: واحدِ حمل ═════════

describe("T119 §۳.۳ — بند ۵: ردیف‌های مترمکعب کیلومتر", () => {
  it("isHaulUnit: واحدهایِ حمل شناسایی می‌شوند (فاصله/خط‌تیره/نیم‌فاصله)", () => {
    expect(isHaulUnit("مترمکعب کیلومتر")).toBe(true);
    expect(isHaulUnit("مترمکعب - کیلومتر")).toBe(true);
    expect(isHaulUnit("مترمکعب‌کیلومتر")).toBe(true); // نیم‌فاصله
    expect(isHaulUnit("مکعب کیلومتر")).toBe(true);
    // واحدهایِ غیرحمل
    expect(isHaulUnit("مترمکعب")).toBe(false);
    expect(isHaulUnit("کیلوگرم")).toBe(false);
    expect(isHaulUnit("متر مربع")).toBe(false);
    expect(isHaulUnit("")).toBe(false);
    expect(isHaulUnit(null)).toBe(false);
    expect(isHaulUnit(undefined)).toBe(false);
    expect(haulTargetChapter()).toBe("28");
  });

  it("یادداشتِ بند ۵ وقتی مبلغی منتقل شده باشد در موتور تعدیل داده می‌شود", () => {
    const w: Warning[] = [];
    const t = tadilEngine(
      on(),
      ctx({ chapters: { "06": A_TEST, "28": 2_000_000_000.0 }, haulMoved: 2_000_000_000.0 }),
      w,
    );
    expect(t.error).toBeFalsy();
    const notes = w.filter((x) => x.item === "clause5_haul");
    expect(notes).toHaveLength(1);
    expect(notes[0].level).toBe("اطلاع");
    expect(notes[0].message).toContain("فصل ۲۸");
    expect(notes[0].ref).toBe("بخشنامهٔ ۱۵۵۲۳۳، پیوست ۳، بند ۵");
  });

  it("وقتی چیزی منتقل نشده یادداشتی نیست", () => {
    const w: Warning[] = [];
    tadilEngine(on(), ctx({ chapters: { "06": A_TEST }, haulMoved: 0 }), w);
    expect(w.some((x) => x.item === "clause5_haul")).toBe(false);
  });

  it("موتور برآورد به‌هنگام هم یادداشتِ بند ۵ را می‌دهد (همان chapter_amounts)", () => {
    const w: Warning[] = [];
    const b = baravordEngine(
      on(),
      ctx({ chapters: { "06": A_TEST, "28": 1_000_000_000.0 }, haulMoved: 1_000_000_000.0 }),
      w,
    );
    expect(b.error).toBeFalsy();
    expect(w.some((x) => x.item === "clause5_haul")).toBe(true);
  });
});

// ═════════ §۳.۶ — جانشانیِ خودکارِ موقت→قطعی ═════════

describe("T119 §۳.۶ — جانشانیِ خودکارِ موقت→قطعی", () => {
  it("precond: بدونِ دادهٔ قطعی، مسیرِ موقت برقرار است", () => {
    // announced=false در config واقعی
    expect(quarterIndex("06", "1405Q1", PROV_COEF)).toEqual([
      CH06[1] * PROV_COEF,
      "موقت",
    ]);
    expect(quarterDiscipline("1405Q1", PROV_COEF)[1]).toBe("موقت");
  });

  it("announced=true ولی بدونِ ردیفِ مقدار ⇒ هنوز موقت (قاعدهٔ طلایی)", async () => {
    const m = await importWithDefinitive({ "1405Q1": { announced: true } });
    expect(m.quarterHasDefinitive("1405Q1")).toBe(false);
    expect(m.quarterIndex("06", "1405Q1", PROV_COEF)).toEqual([
      CH06[1] * PROV_COEF,
      "موقت",
    ]);
  });

  it("announced=false با ردیفِ مقدار ⇒ هنوز موقت", async () => {
    const m = await importWithDefinitive(
      { "1405Q1": { announced: false } },
      [{ name: "ابنیه", q1_1405: 16000.0 }],
      [{ chapter: "06", q1_1405: 12000.0 }],
    );
    expect(m.quarterHasDefinitive("1405Q1")).toBe(false);
    expect(m.quarterIndex("06", "1405Q1", PROV_COEF)[1]).toBe("موقت");
  });

  it("شاخصِ قطعیِ واردشده جایگزینِ ضریبِ موقت می‌شود", async () => {
    const m = await importWithDefinitive(
      { "1405Q1": { announced: true } },
      [{ name: "ابنیه", q1_1405: 16000.0, page: 9 }],
      [{ chapter: "06", q1_1405: 12000.0, page: 9 }],
    );
    expect(m.quarterHasDefinitive("1405Q1")).toBe(true);
    // فصل
    expect(m.quarterIndex("06", "1405Q1", PROV_COEF)).toEqual([12000.0, "قطعی"]);
    // رشته
    expect(m.quarterDiscipline("1405Q1", PROV_COEF)).toEqual([16000.0, "قطعی"]);
    // سه‌ماههٔ بعدتر هنوز اعلام نشده ⇒ موقت
    expect(m.quarterIndex("06", "1405Q2", PROV_COEF)).toEqual([
      CH06[1] * PROV_COEF,
      "موقت",
    ]);
    // ۱۴۰۴Q4 (قطعیِ پیوست ۳) دست‌نخورده
    expect(m.quarterIndex("06", "1404Q4", PROV_COEF)).toEqual([CH06[1], "قطعی"]);
  });

  it("فقدانِ شاخصِ قطعیِ یک فصل ⇒ بازگشت به مسیرِ موقت", async () => {
    const m = await importWithDefinitive(
      { "1405Q1": { announced: true } },
      [],
      [{ chapter: "08", q1_1405: 15000.0 }],
    );
    expect(m.quarterIndex("06", "1405Q1", PROV_COEF)).toEqual([
      CH06[1] * PROV_COEF,
      "موقت",
    ]);
  });

  it("شاخصِ قطعی در خروجیِ کاملِ موتور تعدیل ظاهر می‌شود", async () => {
    const m = await importWithDefinitive(
      { "1405Q1": { announced: true } },
      [],
      [{ chapter: "06", q1_1405: 12000.0 }],
    );
    const w: Warning[] = [];
    const t = m.tadilEngine(
      on({ workPeriodStart: "۱۴۰۴/۰۱/۰۱", workPeriodEnd: "۱۴۰۵/۰۲/۱۵" } as never),
      ctx({ chapters: { "06": A_TEST } }),
      w,
    );
    expect(t.error).toBeFalsy();
    const rows = (t.chapters ?? []) as any[];
    const r06 = rows.find((r) => r.chapter === "06");
    expect(r06).toBeTruthy();
    const q1 = (r06.quarters ?? []).find(
      (qq: [string, number, string]) => qq[0] === "1405Q1",
    );
    expect(q1).toBeTruthy();
    expect(q1[1]).toBe(12000.0);
    expect(q1[2]).toBe("قطعی");
  });
});
