// ─────────────────────────────────────────────────────────────
// T107 — دودویِ مسیرهای پولیِ پوشش‌نیافته (فاز E-6)
//
// هدف: هر شاخهٔ محاسبهٔ پولیِ موتورها که در پوششِ آزمون‌ها نبود، حداقل
// یک بار اجرا شود تا هیچ NameError/TypeError نهفته‌ای نمانَد. شاخه‌ها:
//   ۱) ردیفِ تجهیز در موتورِ برآورد (setup > 0)
//   ۲) ترکیبِ تجهیز + کار جدید در برآورد
//   ۳) هشدارِ «دورهٔ مبنا ناموجود» در موتورِ برآورد
//   ۴) تأخیرِ تعیین‌نشده (۲-۵-۳) روی ردیفِ تجهیز
//   ۵) تأخیرِ تعیین‌نشده (۲-۵-۳) روی ردیفِ کار جدید
//   ۶) شاخص دستیِ It فصل + تأخیر
//   ۷) ماتریسِ دودویی: هر دو موتور روی ترکیب‌های متنوع بدون خطا + invariant
// آینهٔ tests/char_python/test_T107_money_path_smoke.py
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import { tadilEngine, baravordEngine } from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";

const BASE = 10_000_000_000.0;
const SETUP = 100_000_000.0;
// شاخصِ گروهیِ فصل ۰۶ و شاخصِ رشتهٔ ابنیه (config)
const IO_CH06 = 7273.8;
const IO_DISC = 9744.7;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹";

function ctx(setup = 0.0): AdjustmentCtx {
  return {
    chapter_amounts: { "06": BASE },
    floors_amount: BASE,
    base_total: BASE,
    site_setup: setup,
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
    baravordEnabled: true,
    proposalDate: PROPOSAL_DATE,
    workPeriodStart: "۱۴۰۴/۰۱/۰۱",
    workPeriodEnd: "۱۴۰۴/۱۲/۲۹",
    ...extra,
  };
}

function tadil(
  settings: ProjectSettings,
  c?: AdjustmentCtx,
): { t: ReturnType<typeof tadilEngine>; w: Warning[] } {
  const w: Warning[] = [];
  return { t: tadilEngine(settings, c ?? ctx(), w), w };
}

function baravord(
  settings: ProjectSettings,
  c?: AdjustmentCtx,
): { b: ReturnType<typeof baravordEngine>; w: Warning[] } {
  const w: Warning[] = [];
  return { b: baravordEngine(settings, c ?? ctx(), w), w };
}

const EXT_UNDEF = [
  { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "تعیین‌نشده" as const, docNo: "ن۳" },
];

describe("T107 — دودویِ مسیرهای پولی", () => {
  // ── ۱) برآورد: ردیف تجهیز ──
  it("baravord setup row", () => {
    const { b } = baravord(on(), ctx(SETUP));
    const sr = b.setup_row;
    expect(sr).not.toBeNull();
    expect(sr!.amount).toBeCloseTo(SETUP, 4);
    expect(sr!.io).toBeCloseTo(IO_DISC, 4);
    expect(sr!.it).toBeCloseTo(14333.1, 4);
    expect(sr!.ratio).toBeCloseTo(1.470861083460753, 8);
    expect(sr!.value).toBeCloseTo(147086108.3460753, 4);
    expect(b.result_amount).toBeCloseTo(19909245089.896297, 2);
    expect(b.base_amount).toBeCloseTo(13620000000.0, 2);
    expect(b.grand_updated).toBeCloseTo(b.result_amount, 2);
  });

  // ── ۲) برآورد: تجهیز + کار جدید ۳-۱ ──
  it("baravord setup + new work", () => {
    const { b } = baravord(
      on({ newItemMethod: "فهرست پیمان", newItemAmount: 1_000_000_000 }),
      ctx(SETUP),
    );
    expect(b.setup_row!.value).toBeCloseTo(147086108.3460753, 4);
    expect(b.new_work_row!.value).toBeCloseTo(1470861083.460753, 2);
    expect(b.result_amount).toBeCloseTo(21380106173.35705, 2);
  });

  // ── ۳) برآورد: کار جدید بدونِ دورهٔ مبنا ⇒ هشدار ──
  it("baravord new work missing base period warns", () => {
    const { b, w } = baravord(
      on({ newItemMethod: "فهرست پایه", newItemAmount: 1_000_000_000 }),
      ctx(),
    );
    expect(b.new_work_row).toBeNull();
    const f = w.filter((x) => x.item === "new_item_base_period_missing");
    expect(f).toHaveLength(1);
    expect(f[0].level).toBe("خطا");
    expect(f[0].category).toBe("موتور برآورد");
    expect(f[0].ref).toBe("بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳");
  });

  // ── ۴) تعدیل: تأخیرِ تعیین‌نشده روی ردیفِ تجهیز (۲-۵-۳) ──
  it("tadil setup row with undefined delay (۲-۵-۳)", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: EXT_UNDEF,
      }),
      ctx(SETUP),
    );
    const sr = t.setup_row;
    expect(sr).not.toBeNull();
    // هر سه سه‌ماههٔ پس از مدت ⇒ علی‌الحساب با شاخصِ دورهٔ خاتمه
    expect(sr!.delay_notes?.map((n) => n.rule)).toEqual([
      "تعیین‌نشده",
      "تعیین‌نشده",
      "تعیین‌نشده",
    ]);
    expect(sr!.delay_notes?.every((n) => n.note.includes("۲-۵-۳"))).toBe(true);
    expect(sr!.it).toBeCloseTo(13563.977260273972, 4);
    expect(sr!.delta).toBeCloseTo(37356164.38356164, 2);
    // Q1 ضریبِ خودش، بقیه ضریبِ دورهٔ خاتمه
    expect(sr!.coef_rows?.map((x) => x[2])).toEqual([
      expect.closeTo(0.15, 6),
      expect.closeTo(0.45, 6),
      expect.closeTo(0.45, 6),
      expect.closeTo(0.45, 6),
    ]);
    // invariant
    expect(t.delta_p).toBeCloseTo(
      t.delta_p_definitive + t.delta_p_provisional,
      2,
    );
  });

  // ── ۵) تعدیل: تأخیرِ تعیین‌نشده روی ردیفِ کار جدید ──
  it("tadil new work row with undefined delay (۲-۵-۳)", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: EXT_UNDEF,
        newItemMethod: "فهرست پیمان",
        newItemAmount: 1_000_000_000,
      }),
      ctx(SETUP),
    );
    const nr = t.new_work_row;
    expect(nr).not.toBeNull();
    expect(nr!.delay_notes?.map((n) => n.rule)).toEqual([
      "تعیین‌نشده",
      "تعیین‌نشده",
      "تعیین‌نشده",
    ]);
    expect(nr!.it).toBeCloseTo(13563.977260273972, 4);
    expect(nr!.delta).toBeCloseTo(373561643.83561647, 2);
    expect(t.delta_p).toBeCloseTo(5636305205.479452, 2);
    expect(t.delta_p).toBeCloseTo(
      t.delta_p_definitive + t.delta_p_provisional,
      2,
    );
  });

  // ── ۶) شاخص دستیِ It فصل + تأخیر ──
  it("manual chapter It with delay", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: EXT_UNDEF,
        chapterIndexManual: { "06": { it: 13000.0, src: "پیوست ۳" } },
      }),
      ctx(),
    );
    const c0 = t.chapters[0];
    expect(c0.io).toBeCloseTo(IO_CH06, 4);
    expect(c0.it).toBeCloseTo(13000.0, 4);
    expect(c0.status).toContain("دستی");
    expect(c0.status).toContain("۲-۵-۳");
    // ۰٫۹۵ × (13000/7273.8 − 1) = ۰٫۷۴۷۸۷… ⇒ گردشده ۰٫۷۵
    expect(c0.coef_rows?.map((x) => x[2])).toEqual([
      expect.closeTo(0.75, 6),
      expect.closeTo(0.75, 6),
      expect.closeTo(0.75, 6),
      expect.closeTo(0.75, 6),
    ]);
    expect(t.delta_p).toBeCloseTo(10140000000.0, 2);
    // علی‌الحساب ⇒ همهٔ ΔP موقت
    expect(t.delta_p_definitive).toBeCloseTo(0, 4);
    expect(t.delta_p_provisional).toBeCloseTo(t.delta_p, 2);
  });

  // ── ۸) شاخص دستیِ رشته (Io) روی ردیفِ تجهیز ──
  it("manual discipline Io on setup row", () => {
    const { t } = tadil(
      on({ disciplineIndexManual: { io: 9500.0 } }),
      ctx(SETUP),
    );
    const sr = t.setup_row;
    expect(sr).not.toBeNull();
    expect(sr!.io).toBeCloseTo(9500.0, 4);
    expect(sr!.src).toContain("دستی");
    expect(sr!.value).toBeCloseTo(29531506.84931507, 2);
    // فصلی که شاخصِ گروهی دارد همچنان از شاخصِ گروهی استفاده می‌کند
    expect(t.chapters[0].io).toBeCloseTo(IO_CH06, 4);
    expect(t.delta_p).toBeCloseTo(4302592328.767123, 2);
  });

  // ─ـ ۹) فصلِ صغیر نادیده گرفته می‌شود ──
  it("tiny chapter is skipped", () => {
    const { t } = tadil(on(), { ...ctx(), chapter_amounts: { "06": BASE, "07": 0.001 } });
    expect(t.chapters.map((c) => c.chapter)).toEqual(["06"]);
    expect(t.chapters[0].amount).toBeCloseTo(13520000000.0, 2);
  });

  // ── ۱۰) برآورد: شاخص دستیِ رشته (Io/It) روی تجهیز و کار جدید ──
  it("baravord manual discipline Io/It on setup + new work", () => {
    const { b } = baravord(
      on({
        disciplineIndexManual: { io: 9500.0, it: 15000.0 },
        newItemMethod: "فهرست پیمان",
        newItemAmount: 1_000_000_000,
      }),
      ctx(SETUP),
    );
    expect(b.setup_row!.io).toBeCloseTo(9500.0, 4);
    expect(b.setup_row!.it).toBeCloseTo(15000.0, 4);
    expect(b.new_work_row!.io).toBeCloseTo(9500.0, 4);
    expect(b.new_work_row!.it).toBeCloseTo(15000.0, 4);
    expect(b.new_work_row!.value).toBeCloseTo(1578947368.4210527, 2);
    expect(b.result_amount).toBeCloseTo(21499001086.813377, 2);
  });

  // ─ـ ۱۱) برآورد: شاخص دستیِ فصل ──
  it("baravord manual chapter indices", () => {
    const { b } = baravord(
      on({ chapterIndexManual: { "06": { io: 7000.0, it: 12000.0, src: "پیوست ۳" } } }),
      ctx(),
    );
    const c0 = b.chapters[0];
    expect(c0.io).toBeCloseTo(7000.0, 4);
    expect(c0.it).toBeCloseTo(12000.0, 4);
    expect(c0.src).toBe("دستی (پیوست ۳)");
    expect(c0.status).toBe("دستی");
    expect(c0.value).toBeCloseTo(23177142857.142857, 2);
    expect(b.result_amount).toBeCloseTo(23177142857.142857, 2);
  });

  // ── ۱۲) برآورد: فصلِ صغیر نادیده گرفته می‌شود ──
  it("baravord tiny chapter is skipped", () => {
    const { b } = baravord(
      on(),
      { ...ctx(), chapter_amounts: { "06": BASE, "07": 0.001 } },
    );
    expect(b.chapters.map((c) => c.chapter)).toEqual(["06"]);
    expect(b.chapters[0].amount).toBeCloseTo(13520000000.0, 2);
  });

  // ─ـ ۱۳) تعدیل: مسیر رشته‌ای + تأخیرِ تعیین‌نشده (useDisc در ۲-۵-۳) ──
  it("tadil rail method with undefined delay", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: EXT_UNDEF,
        indexMethod: "رشته‌ای",
      }),
      ctx(),
    );
    const c0 = t.chapters[0];
    // مسیر رشته‌ای ⇒ شاخص رشتهٔ ابنیه
    expect(c0.io).toBeCloseTo(IO_DISC, 4);
    expect(c0.it).toBeCloseTo(13563.977260273972, 4);
    expect(c0.status).toContain("۲-۵-۳");
    expect(c0.delay_notes?.map((n) => n.rule)).toEqual([
      "تعیین‌نشده",
      "تعیین‌نشده",
      "تعیین‌نشده",
    ]);
    expect(t.delta_p).toBeCloseTo(5050553424.657535, 2);
    expect(t.delta_p).toBeCloseTo(
      t.delta_p_definitive + t.delta_p_provisional,
      2,
    );
  });

  // ─ـ ۱۴) تعدیل: ۲-۵-۲ (غیرمجاز) + شاخص دستیِ It فصل ──
  it("tadil unauthorized delay with manual chapter It", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: [
          { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "غیرمجاز", docNo: "ن۲" },
        ],
        chapterIndexManual: { "06": { io: 7273.8, it: 11900.0, src: "پیوست ۳" } },
      }),
      ctx(),
    );
    const c0 = t.chapters[0];
    expect(c0.io).toBeCloseTo(7273.8, 4);
    expect(c0.it).toBeCloseTo(11900.0, 4);
    expect(c0.status).toContain("۲-۵-۲");
    // شاخص دستی ⇒ میانگین مدت همان مقدار دستی است
    expect(c0.delay_notes?.map((n) => n.rule)).toEqual([
      "غیرمجاز",
      "غیرمجاز",
      "غیرمجاز",
    ]);
    expect(c0.coef_rows?.map((x) => x[2])).toEqual([
      expect.closeTo(0.6, 6),
      expect.closeTo(0.6, 6),
      expect.closeTo(0.6, 6),
      expect.closeTo(0.6, 6),
    ]);
    expect(t.delta_p).toBeCloseTo(8112000000.0, 2);
    expect(t.delta_p_definitive).toBeCloseTo(0, 4);
    expect(t.delta_p_provisional).toBeCloseTo(t.delta_p, 2);
  });

  // ─ـ ۱۵) تعدیل: ۲-۶ (آخرین موقت) + شاخص دستیِ It فصل ──
  it("tadil 2-6 average with manual chapter It", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
        chapterIndexManual: { "06": { io: 7273.8, it: 11900.0, src: "پیوست ۳" } },
      }),
      ctx(),
    );
    const c0 = t.chapters[0];
    expect(c0.io).toBeCloseTo(7273.8, 4);
    expect(c0.it).toBeCloseTo(11900.0, 4);
    expect(c0.status).toContain("۲-۶");
    // فقط فصل‌های پس از آخرین موقت درونِ مدت
    expect(c0.delay_notes?.map((n) => n.q)).toEqual(["1404Q3", "1404Q4"]);
    expect(c0.delay_notes?.every((n) => n.rule === "۲-۶")).toBe(true);
    expect(c0.coef_rows?.map((x) => x[2])).toEqual([
      expect.closeTo(0.6, 6),
      expect.closeTo(0.6, 6),
      expect.closeTo(0.6, 6),
      expect.closeTo(0.6, 6),
    ]);
    expect(t.delta_p).toBeCloseTo(8112000000.0, 2);
    expect(t.delta_p_provisional).toBeCloseTo(t.delta_p, 2);
  });

  // ── ۷) ماتریسِ دودویی: هیچ خطایی نهفته نیست + invariant ──
  const COMBOS: [string, boolean | null, boolean, number, string, string, string][] =
    [];
  for (const im of ["گروهی", "رشته‌ای"]) {
    for (const cwt of [null, true] as const) {
      for (const rnd of [true, false] as const) {
        for (const setup of [0.0, SETUP] as const) {
          for (const method of ["فهرست پیمان", "فهرست پایه", "ترکیب"] as const) {
            for (const status of ["عادی", "فسخ با قصور"] as const) {
              for (const pdm of ["average", "last"] as const) {
                COMBOS.push([im, cwt, rnd, setup, method, status, pdm]);
              }
            }
          }
        }
      }
    }
  }

  it.each(COMBOS)(
    "smoke matrix: im=%s cwt=%s rnd=%s setup=%s method=%s status=%s pdm=%s",
    (im, cwt, rnd, setup, method, status, pdm) => {
      const extra: Partial<ProjectSettings> = {
        indexMethod: im as ProjectSettings["indexMethod"],
        completedWithinTerm: cwt as boolean | null,
        coefRounding2080: rnd,
        contractStatus: status as ProjectSettings["contractStatus"],
        provisionalDiffMethod: pdm as ProjectSettings["provisionalDiffMethod"],
        newItemMethod: method as ProjectSettings["newItemMethod"],
        newItemAmount: 500_000_000,
      };
      if (method === "فهرست پایه" || method === "ترکیب") {
        extra.newItemBasePeriod = "1404Q2";
        if (method === "ترکیب") {
          extra.newItemAmountAttached = 300_000_000;
        }
      }
      const { t } = tadil(on(extra), ctx(setup));
      // invariantِ همیشگی
      expect(t.delta_p).toBeCloseTo(
        t.delta_p_definitive + t.delta_p_provisional,
        0,
      );
      // ردیفِ تجهیز فقط وقتی setup > 0 است
      expect((t.setup_row === null) === (setup <= 0)).toBe(true);
      // کار جدید همیشه ردیف دارد (روش و دوره معتبرند)
      expect(t.new_work_row).not.toBeNull();

      const { b } = baravord(on(extra), ctx(setup));
      expect((b.setup_row === null) === (setup <= 0)).toBe(true);
      expect(b.new_work_row).not.toBeNull();
      expect(b.result_amount).toBeGreaterThan(0);
    },
  );
});
