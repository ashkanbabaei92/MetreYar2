// ─────────────────────────────────────────────────────────────
// T97 — فاز E-6: ضریب مشتق‌شدهٔ k (بخشنامهٔ ۲۰۸۰، بند ۱-۸ و تبصرهٔ ۲)
// و گردکردن ضریب طبق بند ۸-۲ (آینهٔ test_T97_e6_k_and_rounding.py).
//
// منبع: docs/sources/2080.pdf — بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳)،
// پس فقط نامی که کاربر معرفی کرده استفاده می‌شود: «بخشنامهٔ ۲۰۸۰»).
// k ورودی کاربر نیست:
//   completedWithinTerm = true  => k = ۱    (تبصرهٔ ۲ بند ۱-۸)
//   completedWithinTerm = false => k = ۰٫۹۵ (بند ۱-۸)
//   completedWithinTerm = null  => k = ۰٫۹۵ (علی‌الحساب، تکلیف نامشخص)
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import { tadilEngine, tadilK, roundCoef2080, TADIL_K_2080 } from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹";
const A_TEST = 10_000_000_000.0;

function ctx(opts?: { chapters?: Record<string, number>; setup?: number }): AdjustmentCtx {
  const base = A_TEST;
  return {
    chapter_amounts: opts?.chapters ?? { "06": base },
    floors_amount: base,
    base_total: base,
    site_setup: opts?.setup ?? 0,
    advance_payment: 0,
    overhead_coef: 1.3,
    regional_coef: 1.04,
    grand_total: base * 1.352,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: base,
      excluded_total: 0.0,
    },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return { ...defaultSettings(), tadilEnabled: true, proposalDate: PROPOSAL_DATE, ...extra };
}

function tadil(settings: ProjectSettings, c?: AdjustmentCtx) {
  const w: Warning[] = [];
  return { t: tadilEngine(settings, c ?? ctx(), w), w };
}

// ═══ گردکردن ضریب (بند ۸-۲) ═══

describe("T97 گردکردن ضریب طبق بند ۸-۲", () => {
  it("جدول بازبینی فاز E-6 (تفسیر الف)", () => {
    const cases: [number, number][] = [
      [0.1234, 0.12], [0.1235, 0.12], [0.1249, 0.13], [0.125, 0.13],
      [0.0049, 0.01], [0.005, 0.01], [0.0, 0.0], [0.9995, 1.0], [0.4473, 0.45],
    ];
    for (const [x, exp] of cases) {
      expect(roundCoef2080(x)).toBeCloseTo(exp, 9);
    }
  });

  it("ضرایب منفی روی قدر مطلق عمل می‌کنند", () => {
    // بخشنامه دربارهٔ ضرایب منفی ساکتی است (در ACCEPTANCE §۱۸ ثبت شده)
    const cases: [number, number][] = [
      [-0.125, -0.13], [-0.1249, -0.13], [-0.1235, -0.12],
      [-0.1234, -0.12], [-0.0049, -0.01], [-0.4473, -0.45],
    ];
    for (const [x, exp] of cases) {
      expect(roundCoef2080(x)).toBeCloseTo(exp, 9);
    }
  });

  it("null ورودی ⇒ null خروجی", () => {
    expect(roundCoef2080(null)).toBeNull();
    expect(roundCoef2080(undefined)).toBeNull();
  });
});

// ═══ مشتق‌شدن k (بند ۱-۸ و تبصرهٔ ۲) ═══

describe("T97 مشتق‌شدن ضریب قانونی k", () => {
  it("پیش‌فرض: completedWithinTerm = null ⇒ k = ۰٫۹۵", () => {
    const s = defaultSettings();
    expect(s.completedWithinTerm).toBeNull();
    expect(tadilK(s)[0]).toBe(0.95);
  });

  it("سه حالت completedWithinTerm", () => {
    const s = defaultSettings();
    s.completedWithinTerm = true;
    const [kt, lt, st] = tadilK(s);
    expect(kt).toBe(1.0);
    expect(lt).toContain("تبصرهٔ ۲");
    expect(st).toContain("تبصرهٔ ۲");
    s.completedWithinTerm = false;
    const [kf, lf] = tadilK(s);
    expect(kf).toBe(0.95);
    expect(lf).toContain("تمام نشد");
    s.completedWithinTerm = null;
    const [kn, ln] = tadilK(s);
    expect(kn).toBe(0.95);
    expect(ln).toContain("نامشخص");
  });

  it("منبع، شماره و تاریخ سند را دارد (صفحهٔ ۴)", () => {
    const src = tadilK(defaultSettings())[2];
    expect(src).toContain("۲۰۸۰");
    expect(src).toContain("۹۷۰۶");
    expect(src).toContain("۱۳۷۰");
  });

  it("موتور، tadilCoef قدیمی را نادیده می‌گیرد", () => {
    const { t, w } = tadil(on({ tadilCoef: 1.5 }));
    expect(t.coef).toBe(0.95);
    expect(t.completed_within_term).toBe(false);
    expect(w.some((x) => x.item === "tadil_coef")).toBe(false);
  });

  it("وضعیت k در رجیستری، وضعیت اتمام کار را نشان می‌دهد", () => {
    const kNone = tadil(on()).t.pending.filter((p) => p.item.includes("ضریب قانونی"))[0];
    expect(kNone.value).toBe(0.95);
    expect(kNone.status).toContain("نامشخص");
    const kTrue = tadil(on({ completedWithinTerm: true })).t.pending.filter(
      (p) => p.item.includes("ضریب قانونی"),
    )[0];
    expect(kTrue.value).toBe(1.0);
    expect(kTrue.page).toContain("تبصرهٔ ۲");
  });

  it("ثابت پایه با پایتون برابر است", () => {
    expect(TADIL_K_2080).toBe(0.95);
  });

  it("config به اسکن بخشنامهٔ ۲۰۸۰ ارجاع می‌دهد و فایل موجود است", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const cfg = require("../../config/index_bulletins.json");
    const b = cfg.bulletin_2080;
    expect(b.source_file).toBe("docs/sources/2080.pdf");
    expect(fs.existsSync(path.join(ROOT, b.source_file))).toBe(true);
    const clauses = b.rules.map((r: { clause: string }) => r.clause);
    expect(clauses).toContain("۱-۸");
    expect(clauses).toContain("۱-۸ تبصرهٔ ۲");
    expect(clauses).toContain("۸-۲");
    expect(clauses).toContain("۸-۴");
  });
});
