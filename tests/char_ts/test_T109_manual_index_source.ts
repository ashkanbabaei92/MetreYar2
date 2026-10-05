// ─────────────────────────────────────────────────────────────
// T109 — شاخص‌های دستی با منبعِ اجباری + هشدار اختلاف (گام ۸)
//
// گام ۸ (حرف e):
//   - فیلد src برای شاخص دستی (فصل و رشته) اجباری است؛ اگر نباشد
//     هشدارِ خطای manual_index_source_required داده می‌شود.
//   - اگر شاخص دستی بیش از ۲۰٪ با شاخص config اختلاف داشته باشد
//     هشدارِ manual_index_deviation_20 داده می‌شود (آستانه در config).
//   - برچسبِ src شاملِ منبع می‌شود: «دستی (پیوست ۳)».
// آینهٔ tests/char_python/test_T109_manual_index_source.py
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import { baravordEngine, tadilEngine } from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";

const BASE = 10_000_000_000.0;
const IO_CH06 = 7273.8; // شاخصِ گروهیِ فصل ۰۶ در config

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
    ...extra,
  };
}

function tadil(settings: ProjectSettings): { t: any; w: Warning[] } {
  const w: Warning[] = [];
  const t = tadilEngine(settings, ctx(), w);
  return { t, w };
}

describe("T109 — شاخص دستی با منبعِ اجباری (گام ۸)", () => {
  // ── ۱) شاخص دستیِ فصل بدون src ⇒ خطای manual_index_source_required ──
  it("chapter manual without src warns", () => {
    const { t, w } = tadil(
      on({
        chapterIndexManual: { "06": { io: 7000.0, it: 12000.0 } },
      }),
    );
    const req = w.filter((x) => x.item === "manual_index_source_required");
    expect(req).toHaveLength(1);
    expect(req[0].level).toBe("خطا");
    expect(req[0].category).toBe("موتور تعدیل");
    expect(req[0].message).toContain("فصل 06");
    expect(req[0].ref).toBe("بخشنامهٔ ۲۰۸۰ — گام ۸");
    // موتور همچنان اجرا می‌شود
    expect(t.chapters).toHaveLength(1);
  });

  // ─ـ ۲) شاخص دستیِ فصل با src ⇒ بدون هشدار ─ـ
  it("chapter manual with src no warn", () => {
    const { w } = tadil(
      on({
        chapterIndexManual: {
          "06": { io: 7000.0, it: 12000.0, src: "پیوست ۳" },
        },
      }),
    );
    expect(
      w.some((x) => x.item === "manual_index_source_required"),
    ).toBe(false);
  });

  // ─ـ ۳) برچسب src شاملِ منبع می‌شود ──
  it("chapter src label includes source", () => {
    const { t } = tadil(
      on({
        chapterIndexManual: {
          "06": { io: 7000.0, it: 12000.0, src: "نامهٔ کارفرما" },
        },
      }),
    );
    expect(t.chapters[0].src).toBe("دستی (نامهٔ کارفرما)");
  });

  // ─ـ ۴) شاخص دستیِ رشته بدون src ⇒ خطا ──
  it("discipline manual without src warns", () => {
    const { w } = tadil(
      on({
        disciplineIndexManual: { io: 9500.0, it: 15000.0 },
      }),
    );
    const req = w.filter((x) => x.item === "manual_index_source_required");
    expect(req).toHaveLength(1);
    expect(req[0].message).toContain("رشتهٔ ابنیه");
  });

  // ─ـ ۵) شاخص دستیِ رشته با src ⇒ بدون هشدار ──
  it("discipline manual with src no warn", () => {
    const { w } = tadil(
      on({
        disciplineIndexManual: {
          io: 9500.0,
          it: 15000.0,
          src: "پیوست ۳",
        },
      }),
    );
    expect(
      w.some((x) => x.item === "manual_index_source_required"),
    ).toBe(false);
  });

  // ─ـ ۶) اختلاف > ۲۰٪ با config ⇒ هشدارِ manual_index_deviation_20 ──
  it("deviation over threshold warns", () => {
    // شاخص config فصل ۰۶ = ۷۲۷۳٫۸؛ ۱۲۰۰۰ ⇒ اختلاف ~۶۵٪
    const { w } = tadil(
      on({
        chapterIndexManual: { "06": { io: 12000.0, src: "پیوست ۳" } },
      }),
    );
    const dev = w.filter((x) => x.item === "manual_index_deviation_20");
    expect(dev).toHaveLength(1);
    expect(dev[0].level).toBe("هشدار");
    expect(dev[0].message).toContain("فصل 06");
    expect(dev[0].message).toContain("۲۰٪");
  });

  // ─ـ ۷) اختلاف < ۲۰٪ ⇒ بدون هشدار ──
  it("deviation under threshold no warn", () => {
    // ۷۰۰۰ ÷ ۷۲۷۳٫۸ ≈ ۰٫۹۶ ⇒ اختلاف ~۳٫۸٪
    const { w } = tadil(
      on({
        chapterIndexManual: { "06": { io: 7000.0, src: "پیوست ۳" } },
      }),
    );
    expect(w.some((x) => x.item === "manual_index_deviation_20")).toBe(false);
  });

  // ─ـ ۸) dedup: فصلِ ناموجود فقط یک هشدار می‌دهد ──
  it("dedup across chapters", () => {
    const { w } = tadil(
      on({
        chapterIndexManual: {
          "06": { io: 12000.0, src: "پیوست ۳" },
          "07": { io: 13000.0, src: "پیوست ۳" },
        },
      }),
    );
    const dev = w.filter((x) => x.item === "manual_index_deviation_20");
    // فقط فصل‌های فعال (موجود در ctx) بررسی می‌شوند ⇒ ۰۷ نادیده
    expect(dev).toHaveLength(1);
    expect((dev[0] as any)._code).toBe("06");
  });

  // ─ـ ۹) فصل بدون شاخص دستی ⇒ هیچ‌کدام از هشدارها ─ـ
  it("no manual no warns", () => {
    const { w } = tadil(on());
    expect(w.some((x) => x.item === "manual_index_source_required")).toBe(
      false,
    );
    expect(w.some((x) => x.item === "manual_index_deviation_20")).toBe(false);
  });

  // ── ۱۰) موتور برآورد هم همین بررسی‌ها را دارد ──
  it("baravord chapter manual without src warns", () => {
    const w: Warning[] = [];
    baravordEngine(
      on({
        baravordEnabled: true,
        chapterIndexManual: { "06": { io: 7000.0, it: 12000.0 } },
      }),
      ctx(),
      w,
    );
    expect(w.some((x) => x.item === "manual_index_source_required")).toBe(true);
  });
});
