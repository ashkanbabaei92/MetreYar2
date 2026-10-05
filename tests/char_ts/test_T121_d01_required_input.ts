// T121 — فاز E-9 §۴: D-01 به‌عنوانِ «دادهٔ ورودیِ الزامی».
//
// قاعدهٔ k (بخشنامهٔ ۲۰۸۰ — بند ۱-۸، تبصرهٔ ۲ و بند ۸-۴) با ورودیِ کاربر
// کاملاً تعیین می‌شود؛ گزینه‌ای برای تصمیم باقی نمانده. تا وقتی کاربر
// وضعیتِ اتمام را مشخص نکرده، خروجی علی‌الحساب است و یک هشدارِ مرکزی او را
// به فیلد هدایت می‌کند.
//
// همتایِ Python این آزمون: tests/char_python/test_T121_d01_required_input.py
import { describe, expect, it } from "vitest";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";
import { defaultSettings } from "../../src/lib/engine";
import { TADIL_K_2080, TADIL_K_COMPLETED, tadilEngine, tadilK } from "../../src/lib/adjustment";

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

// ═════════ مشتق‌شدنِ k از ورودی ═════════

describe("T121 §۴ — D-01: دادهٔ ورودیِ الزامی", () => {
  it("tadilK: k از completedWithinTerm مشتق می‌شود", () => {
    expect(tadilK({ ...on(), completedWithinTerm: true })[0]).toBe(TADIL_K_COMPLETED);
    expect(tadilK({ ...on(), completedWithinTerm: false })[0]).toBe(TADIL_K_2080);
    const [k, st] = tadilK({ ...on(), completedWithinTerm: null });
    expect(k).toBe(TADIL_K_2080);
    expect(st).toContain("علی‌الحساب");
  });

  it("نامشخص ⇒ هشدارِ completed_within_term_required + خروجی علی‌الحساب", () => {
    const w: Warning[] = [];
    const t = tadilEngine(on(), ctx(), w); // پیش‌فرض = نامشخص
    expect(t.error).toBeFalsy();
    const notes = w.filter((x) => x.item === "completed_within_term_required");
    expect(notes).toHaveLength(1);
    expect(notes[0].level).toBe("اطلاع");
    expect(notes[0].message).toContain("۰٫۹۵");
    expect(notes[0].ref).toBe("بخشنامهٔ ۲۰۸۰ — بند ۱-۸، تبصرهٔ ۲ و بند ۸-۴");
    expect(t.coef).toBe(TADIL_K_2080);
    expect(t.k_diff).toBe(0);
  });

  it("«بله» ⇒ بدون هشدار + k=۱ + k_diff جداگانه", () => {
    const w: Warning[] = [];
    const t = tadilEngine(on({ completedWithinTerm: true }), ctx(), w);
    expect(t.error).toBeFalsy();
    expect(w.some((x) => x.item === "completed_within_term_required")).toBe(false);
    expect(t.coef).toBe(TADIL_K_COMPLETED);
    expect(t.k_diff).toBeGreaterThan(0);
    expect(t.completed_within_term).toBe(true);
  });

  it("«خیر» ⇒ بدون هشدار + k=۰٫۹۵", () => {
    const w: Warning[] = [];
    const t = tadilEngine(on({ completedWithinTerm: false }), ctx(), w);
    expect(t.error).toBeFalsy();
    expect(w.some((x) => x.item === "completed_within_term_required")).toBe(false);
    expect(t.coef).toBe(TADIL_K_2080);
    expect(t.completed_within_term).toBe(false);
  });

  it("اختلافِ نامشخص و «بله» دقیقاً k_diff است", () => {
    const tNull = tadilEngine(on(), ctx(), []);
    const tTrue = tadilEngine(on({ completedWithinTerm: true }), ctx(), []);
    expect(
      Math.abs(tTrue.result_amount - tNull.result_amount - tTrue.k_diff),
    ).toBeLessThan(1e-6);
  });
});
