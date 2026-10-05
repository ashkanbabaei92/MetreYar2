// ─────────────────────────────────────────────────────────────
// T107-ب — مسیرِ توقفِ موتورها وقتی شاخصِ موقت قابل محاسبه نیست
//
// وقتی دورهٔ کاری به ۱۴۰۵Q1 می‌رسد و دادهٔ CPI در config/cpi_monthly.json
// ناقص است، موتورها باید متوقف شوند و هشدارِ خطا بدهند (delta_p = ۰).
// این مسیر در Python توسط T91 پوشش داده شده بود ولی در TS پوشش نداشت.
// JSON با vi.mock خالی می‌شود چون CPI_MONTHLY در زمان import خوانده می‌شود.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";

vi.mock("../../config/cpi_monthly.json", () => ({ default: { months: {} } }));

const { tadilEngine, baravordEngine } = await import(
  "../../src/lib/adjustment"
);
const { defaultSettings } = await import("../../src/lib/engine");

const BASE = 10_000_000_000.0;

function ctx() {
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

function on(extra = {}) {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    baravordEnabled: true,
    proposalDate: "۱۴۰۳/۱۲/۲۹",
    workPeriodStart: "۱۴۰۴/۰۱/۰۱",
    workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
    ...extra,
  };
}

describe("T107-b — توقف موتورها بدون CPI", () => {
  it("tadil stops and errors when CPI missing", () => {
    const w = [];
    const t = tadilEngine(on(), ctx(), w);
    expect(t.error).toBeTruthy();
    expect(t.chapters).toHaveLength(0);
    expect(t.delta_p).toBeCloseTo(0, 6);
    expect(
      w.some(
        (x) => x.level === "خطا" && x.item === "provisional_coef_1405q1",
      ),
    ).toBe(true);
  });

  it("baravord stops and errors when CPI missing", () => {
    const w = [];
    const b = baravordEngine(
      on({ baravordItPeriod: "1405Q1" }),
      ctx(),
      w,
    );
    expect(b.error).toBeTruthy();
    expect(b.chapters).toHaveLength(0);
    expect(
      w.some(
        (x) => x.level === "خطا" && x.item === "provisional_coef_1405q1",
      ),
    ).toBe(true);
  });

  it("manual chapter indices bypass the CPI requirement (tadil)", () => {
    const w = [];
    const t = tadilEngine(
      on({ chapterIndexManual: { "06": { io: 7273.8, it: 11900.0, src: "پیوست ۳" } } }),
      ctx(),
      w,
    );
    expect(t.error).toBeFalsy();
    expect(t.chapters.length).toBeGreaterThan(0);
    expect(t.chapters[0].it).toBeCloseTo(11900.0, 4);
    expect(t.delta_p).toBeGreaterThan(0);
  });
});
