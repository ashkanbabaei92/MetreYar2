// ─────────────────────────────────────────────────────────────
// T102 — فاز E-6 Part C گام ۴: وضعیت خاتمهٔ پیمان (بندهای ۶ و ۷).
//
// بند ۶: پیمان‌هایی که بدون قصور پیمانکار خاتمه داده شوند — طبق همین
// دستورالعمل (بدون تغییر).
// بند ۷: پیمان‌هایی که به علت قصور پیمانکار فسخ شوند — ۵٪ از مبلغ تعدیل
// کسر می‌شود (ردیفِ جداگانه در خروجی و Excel).
// آینهٔ test_T102_e6_contract_status.py
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import { tadilEngine } from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type { AdjustmentCtx, ProjectMeta, ProjectSettings, Warning } from "../../src/lib/types";
import { copyProject } from "../../src/lib/manualEntries";

const BASE = 10_000_000_000.0;

function ctx(): AdjustmentCtx {
  return {
    chapter_amounts: { "06": BASE },
    floors_amount: BASE,
    base_total: BASE,
    site_setup: 0,
    advance_payment: 0,
    overhead_coef: 1.3,
    regional_coef: 1.04,
    grand_total: BASE * 1.352,
    floors_info: { value: 1.0, status: "کامل", eligible_total: BASE, excluded_total: 0 },
  };
}

function tadil(extra: Partial<ProjectSettings> = {}): {
  t: ReturnType<typeof tadilEngine>;
  w: Warning[];
} {
  const s: ProjectSettings = {
    ...defaultSettings(),
    tadilEnabled: true,
    proposalDate: "۱۴۰۳/۱۲/۲۹", // ⇒ Io = ۱۴۰۳Q4 (مبنا)
    ...extra,
  };
  const w: Warning[] = [];
  return { t: tadilEngine(s, ctx(), w), w };
}

describe("T102 فاز E-6 Part C گام ۴ — وضعیت خاتمهٔ پیمان", () => {
  // ── پیش‌فرض: فعال ⇒ هیچ کسری نیست (اعداد مرجع ثابت) ──
  it("فعال: بدون کسر و بدون هشدار", () => {
    const { t, w } = tadil();
    expect(t.contract_status).toBe("فعال");
    expect(t.deduction_fault).toBe(0);
    expect(
      w.some(
        (x) => x.category === "موتور تعدیل" && (x.ref ?? "").includes("بند ۷"),
      ),
    ).toBe(false);
  });

  // ── بند ۶: خاتمهٔ بدون قصور ⇒ مثلِ حالتِ عادی ──
  it("خاتمهٔ بدون قصور: مثلِ حالتِ عادی (بند ۶)", () => {
    const { t } = tadil({ contractStatus: "خاتمه بدون قصور" });
    const { t: t0 } = tadil();
    expect(t.contract_status).toBe("خاتمه بدون قصور");
    expect(t.deduction_fault).toBe(0);
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
    expect(t.result_amount).toBeCloseTo(t0.result_amount, 6);
  });

  // ── بند ۷: فسخ با قصور ⇒ ۵٪ از مبلغ تعدیل کسر می‌شود ──
  it("فسخ با قصور: ۵٪ کسر از مبلغ نهایی (بند ۷)", () => {
    const { t } = tadil({ contractStatus: "فسخ با قصور" });
    const { t: t0 } = tadil();
    expect(t.contract_status).toBe("فسخ با قصور");
    // کسر = ۵٪ از مبلغ تعدیل (عددِ منفی)
    expect(t.deduction_fault).toBeCloseTo(-0.05 * t.delta_p, 6);
    // مبلغ نهایی شامل کسر است
    expect(t.result_amount).toBeCloseTo(
      t.base_amount + t.delta_p + t.deduction_fault,
      6,
    );
    // خودِ مبلغ تعدیل تغییر نمی‌کند — فقط پرداختِ نهایی
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
    expect(t.delta_p_definitive).toBeCloseTo(t0.delta_p_definitive, 6);
  });

  it("فسخ با قصور: یک هشدار با ارجاعِ بند ۷", () => {
    const { t, w } = tadil({ contractStatus: "فسخ با قصور" });
    const f = w.filter(
      (x) => x.category === "موتور تعدیل" && (x.ref ?? "").includes("بند ۷"),
    );
    expect(f.length).toBe(1);
    expect(f[0].level).toBe("هشدار");
    expect(f[0].message).toContain("فسخ با قصور");
    // فیلدهای جدید در خروجی موجودند
    expect(typeof t.contract_status).toBe("string");
    expect(typeof t.deduction_fault).toBe("number");
  });

  it("فسخ با قصور: مبلغ نهایی کمتر از A + ΔP است", () => {
    const { t } = tadil({ contractStatus: "فسخ با قصور" });
    expect(t.result_amount).toBeLessThan(t.base_amount + t.delta_p);
  });

  // ── ΔP منفی: کسر فقط با فلگ اعمال می‌شود (تفسیر — §۱۸-۳) ──
  it("ΔP منفی بدون فلگ: کسر نیست، هشدارِ «اعمال نشد»", () => {
    const { t, w } = tadil({
      contractStatus: "فسخ با قصور",
      proposalDate: "۱۴۰۴/۱۲/۲۹",
      tadilItPeriod: "base",
      tadilAllowNegative: true,
    });
    expect(t.delta_p).toBeLessThan(0);
    expect(t.deduction_fault).toBe(0);
    expect(t.result_amount).toBeCloseTo(t.base_amount + t.delta_p, 6);
    const f = w.filter(
      (x) => x.category === "موتور تعدیل" && (x.ref ?? "").includes("بند ۷"),
    );
    expect(f.length).toBe(1);
    expect(f[0].message).toContain("اعمال نشد");
  });

  it("ΔP منفی با فلگ: کسر اعمال می‌شود (عددِ مثبت)", () => {
    const { t, w } = tadil({
      contractStatus: "فسخ با قصور",
      proposalDate: "۱۴۰۴/۱۲/۲۹",
      tadilItPeriod: "base",
      tadilAllowNegative: true,
      faultDeductionOnNegative: true,
    });
    expect(t.delta_p).toBeLessThan(0);
    expect(t.deduction_fault).toBeCloseTo(-0.05 * t.delta_p, 6);
    // کسرِ تعدیلِ منفی ⇒ عددِ مثبت (افزایشِ مبلغ نهایی)
    expect(t.deduction_fault).toBeGreaterThan(0);
    expect(t.result_amount).toBeCloseTo(
      t.base_amount + t.delta_p + t.deduction_fault,
      6,
    );
    const f = w.filter(
      (x) => x.category === "موتور تعدیل" && (x.ref ?? "").includes("بند ۷"),
    );
    expect(f.length).toBe(1);
    expect(f[0].message).toContain("فسخ با قصور");
  });

  it("ΔP صفر: کسر صفر ولی هشدارِ بند ۷ هست", () => {
    // Io = It = ۱۴۰۳Q4 ⇒ ΔP = 0
    const { t, w } = tadil({
      contractStatus: "فسخ با قصور",
      tadilItPeriod: "base",
    });
    expect(t.delta_p).toBe(0);
    expect(t.deduction_fault).toBeCloseTo(0, 6);
    expect(t.result_amount).toBeCloseTo(t.base_amount, 6);
    const f = w.filter(
      (x) => x.category === "موتور تعدیل" && (x.ref ?? "").includes("بند ۷"),
    );
    expect(f.length).toBe(1);
  });

  it("فسخ با قصور + completed_within_term: k = ۱ و کسر ۵٪ با هم", () => {
    const { t } = tadil({
      contractStatus: "فسخ با قصور",
      completedWithinTerm: true,
    });
    const { t: t0 } = tadil({ completedWithinTerm: true });
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
    expect(t.delta_p_definitive).toBeCloseTo(t0.delta_p_definitive, 6);
    expect(t.deduction_fault).toBeCloseTo(-0.05 * t0.delta_p, 6);
    expect(t.result_amount).toBeCloseTo(
      t0.result_amount + t.deduction_fault,
      6,
    );
  });

  it("copyProject: وضعیت خاتمه پاک می‌شود، فلگ نگه داشته می‌شود", () => {
    const s = { ...defaultSettings() };
    s.contractStatus = "فسخ با قصور";
    s.faultDeductionOnNegative = true;
    const { settings: ns } = copyProject(s, {
      projectName: "P",
    } as ProjectMeta);
    expect(ns.contractStatus).toBe("فعال");
    expect(ns.faultDeductionOnNegative).toBe(true);
  });
});
