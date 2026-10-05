// T122 — فاز E-9 §۵: پیش‌فرضِ هدف‌محورِ It (تعدیل صورت‌وضعیت vs برآورد به‌هنگام).
//
// موتورِ تعدیلِ صورت‌وضعیت باید شاخص را از دورهٔ واقعیِ انجامِ کار بخواند.
// وقتی دوره خالی است، تمامِ کارکرد به آخرین شاخصِ قطعی (۱۴۰۴Q4) منتسب
// می‌شود و ΔP متفاوتی می‌دهد. موتور باید هشدار دهد و کاربر را به فیلد
// مربوطه هدایت کند (قاعدهٔ طلایی).
//
// همتایِ Python این آزمون: tests/char_python/test_T122_purpose_based_it.py
import { describe, expect, it } from "vitest";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";
import { defaultSettings } from "../../src/lib/engine";
import { tadilEngine } from "../../src/lib/adjustment";

const A_TEST = 10_000_000_000.0;
const OH = 1.3;
const REG = 1.04;
const PRICE_MULT = OH * REG;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹";

function ctx(): AdjustmentCtx {
  return {
    chapter_amounts: { "06": A_TEST },
    floors_amount: A_TEST,
    base_total: A_TEST,
    site_setup: 0,
    advance_payment: 0,
    overhead_coef: OH,
    regional_coef: REG,
    grand_total: A_TEST * PRICE_MULT,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: A_TEST,
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

describe("T122 §۵ — پیش‌فرضِ هدف‌محورِ It", () => {
  it("دورهٔ خالی ⇒ هشدارِ work_period_missing_for_it", () => {
    const w: Warning[] = [];
    const t = tadilEngine(on(), ctx(), w); // پیش‌فرض: دوره خالی
    expect(t.error).toBeFalsy();
    const notes = w.filter((x) => x.item === "work_period_missing_for_it");
    expect(notes).toHaveLength(1);
    expect(notes[0].level).toBe("هشدار");
    expect(notes[0].category).toBe("موتور تعدیل");
    expect(notes[0].message).toContain("1404Q4");
    expect(notes[0].ref).toBe("فاز E-9 §۵ — بند ۱-۷ بخشنامهٔ ۲۰۸۰");
  });

  it("دورهٔ تنظیم‌شده ⇒ بدون هشدار + شاخصِ هر سه‌ماهه", () => {
    const w: Warning[] = [];
    const t = tadilEngine(
      on({ workPeriodStart: "۱۴۰۴/۰۱/۰۱", workPeriodEnd: "۱۴۰۵/۰۲/۱۵" }),
      ctx(),
      w,
    );
    expect(t.error).toBeFalsy();
    expect(w.some((x) => x.item === "work_period_missing_for_it")).toBe(false);
    const qs = new Set<string>();
    for (const row of t.chapters ?? []) {
      for (const [q] of row.quarters ?? []) qs.add(q);
    }
    expect(qs).toEqual(
      new Set(["1404Q1", "1404Q2", "1404Q3", "1404Q4", "1405Q1"]),
    );
  });

  it("بدونِ دوره، ΔP متفاوت است", () => {
    const tFb = tadilEngine(on(), ctx(), []);
    const tSp = tadilEngine(
      on({ workPeriodStart: "۱۴۰۴/۰۱/۰۱", workPeriodEnd: "۱۴۰۵/۰۲/۱۵" }),
      ctx(),
      [],
    );
    expect(Math.abs(tFb.delta_p - tSp.delta_p)).toBeGreaterThan(1_000_000);
  });

  it("tadil_it_period صریح در fallback استفاده می‌شود", () => {
    const w: Warning[] = [];
    const t = tadilEngine(on({ tadilItPeriod: "q2" }), ctx(), w);
    expect(t.error).toBeFalsy();
    const notes = w.filter((x) => x.item === "work_period_missing_for_it");
    expect(notes).toHaveLength(1);
    expect(notes[0].message).toContain("1404Q2");
  });
});
