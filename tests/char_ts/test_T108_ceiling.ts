// ─────────────────────────────────────────────────────────────
// T108 — سقفِ قیمت قابل قبول ۱۰٪ (فاز E-6 Part C گام ۷ — نامه-۶)
//
// «در کارهایی که شاخص مبنایشان طبق ۱-۶-۱ یکم است، سقف قیمت قابل قبول
//  حداکثر ۱۰٪ بالاتر از مبلغ برآورد بر اساس قیمت‌های پایه است و انعقاد
//  قرارداد بیش از آن مجاز نیست.»
// بررسی فقط وقتی روش ۱-۶-۱ یکم (fehrest_period) انتخاب شده باشد.
// مبلغ برآورد بر اساس قیمت‌های پایه = ctx.base_total (تفسیر ۱۸).
// آینهٔ tests/char_python/test_T108_ceiling.py
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import { tadilEngine } from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";

const BASE = 10_000_000_000.0;

function ctx(): AdjustmentCtx {
  return {
    chapter_amounts: { "06": BASE },
    floors_amount: BASE,
    base_total: BASE,
    site_setup: 0.0,
    advance_payment: 0.0,
    overhead_coef: 1.3,
    regional_coef: 1.04,
    grand_total: BASE * 1.352,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: BASE,
      excluded_total: 0.0,
    },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    proposalDate: "۱۴۰۳/۱۲/۲۹",
    workPeriodStart: "۱۴۰۴/۰۱/۰۱",
    workPeriodEnd: "۱۴۰۴/۱۲/۲۹",
    fehrestYear: "1403",
    ...extra,
  };
}

function ceilingWarns(settings: ProjectSettings): Warning[] {
  const w: Warning[] = [];
  tadilEngine(settings, ctx(), w);
  return w.filter((x) => x.item === "contract_price_ceiling_110");
}

describe("T108 — سقف ۱۰٪ قیمت قابل قبول (نامه-۶)", () => {
  // ── ۱) قیمت ۱۲۰٪ ⇒ هشدار ──
  it("price 120% warns", () => {
    const ws = ceilingWarns(
      on({
        baseIndexMethod: "fehrest_period",
        contractInitialAmount: 1.2e10,
      }),
    );
    expect(ws).toHaveLength(1);
    expect(ws[0].level).toBe("هشدار");
    expect(ws[0].category).toBe("موتور تعدیل");
    expect(ws[0].ref).toBe("نامه-۶");
  });

  // ── ۲) قیمت ۱۰۵٪ ⇒ بدون هشدار ──
  it("price 105% no warn", () => {
    expect(
      ceilingWarns(
        on({
          baseIndexMethod: "fehrest_period",
          contractInitialAmount: 1.05e10,
        }),
      ),
    ).toHaveLength(0);
  });

  // ── ۳) دقیقاً ۱۱۰٪ ⇒ بدون هشدار (مرزِ باز) ──
  it("exactly 110% no warn", () => {
    expect(
      ceilingWarns(
        on({
          baseIndexMethod: "fehrest_period",
          contractInitialAmount: 1.10e10,
        }),
      ),
    ).toHaveLength(0);
  });

  // ─ـ ۴) کمی بالاتر از ۱۱۰٪ ⇒ هشدار ──
  it("just over 110% warns", () => {
    expect(
      ceilingWarns(
        on({
          baseIndexMethod: "fehrest_period",
          contractInitialAmount: 1.1000001e10,
        }),
      ),
    ).toHaveLength(1);
  });

  // ─ـ ۵) روش proposal_period ⇒ بدون بررسی حتی با قیمت ۱۵۰٪ ──
  it("proposal_period no check", () => {
    expect(
      ceilingWarns(
        on({
          baseIndexMethod: "proposal_period",
          contractInitialAmount: 1.5e10,
        }),
      ),
    ).toHaveLength(0);
  });

  // ── ۶) قیمت خالی ⇒ بدون هشدار ──
  it("no amount no warn", () => {
    expect(
      ceilingWarns(
        on({ baseIndexMethod: "fehrest_period" }),
      ),
    ).toHaveLength(0);
  });

  // ─ـ ۷) پیامِ هشدار اعداد را درست نمایش می‌دهد ──
  it("warning message shows amounts", () => {
    const ws = ceilingWarns(
      on({
        baseIndexMethod: "fehrest_period",
        contractInitialAmount: 1.2e10,
      }),
    );
    const msg = ws[0].message;
    // faFloat ارقامِ فارسی با جداکنندهٔ هزارگان (کاما) می‌نویسد
    expect(msg).toContain("۱۲,۰۰۰,۰۰۰,۰۰۰");
    expect(msg).toContain("۱۱,۰۰۰,۰۰۰,۰۰۰");
    expect(msg).toContain("۱۰,۰۰۰,۰۰۰,۰۰۰");
    expect(msg).toContain("۱۰%");
  });
});
