// ─────────────────────────────────────────────────────────────
// T101 — فاز E-6 Part C گام ۳: تأخیرهای مجاز/غیرمجاز/تعیین‌نشده.
//
// بندهای ۲-۵-۱..۲-۵-۳ بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (docs/sources/2080_summary.md):
//   ۲-۵-۱ مجاز       : شاخص همان دورهٔ انجام کار.
//   ۲-۵-۲ غیرمجاز    : میانگین شاخص‌های سه‌ماهه‌های داخل مدت پیمان
//                      (مدت اولیه + تمدیدها).
//   ۲-۵-۳ تعیین‌نشده  : علی‌الحساب با شاخص دورهٔ منتهی به تاریخ خاتمهٔ مدت
//                      (یا هر تمدید).
//
// آینهٔ test_T101_e6_delays.py — مقدارِ «منتظر» از همان جدولی محاسبه می‌شود
// که موتور می‌خواند (quarterIndex/quarterDiscipline) — هیچ عددی حدس زده نمی‌شود.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import {
  addMonthsJalali,
  delayClassification,
  quarterDiscipline,
  quarterIndex,
  tadilEngine,
} from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type {
  AdjustmentCtx,
  ContractExtension,
  ProjectSettings,
  Warning,
} from "../../src/lib/types";

// شاخص قطعیِ فصل ۶ در ۱۴۰۴Q4 (پیوست ۳، صفحهٔ ۶) — ثابتِ مرجعٔ آزمون‌ها
const CH06_Q4 = 10632.1;
const BASE = 10_000_000_000.0;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"; // ⇒ Io = ۱۴۰۳Q4 (مبنا)

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

function qmap(t: ReturnType<typeof tadilEngine>): Record<string, [number, string]> {
  const ch = (t.chapters ?? [])[0];
  const out: Record<string, [number, string]> = {};
  for (const [q, v, st] of ch?.quarters ?? []) out[q] = [v, st];
  return out;
}

const ON3 = {
  contractDate: "۱۴۰۴/۰۱/۰۱",
  contractDurationMonths: 3,
};

describe("T101 فاز E-6 Part C گام ۳ — تأخیرها و تمدیدها", () => {
  // ── بدونِ مدتِ پیمان، هیچ بازنویسی‌ای نیست (اعداد مرجع ثابت) ──
  it("بدون مدت: بازنویسی نیست و خروجی با حالتِ بدونِ تاریخ یکسان است", () => {
    const a = tadil(on({ contractDate: "۱۴۰۴/۰۱/۰۱" }));
    const b = tadil(on());
    expect(a.t.delay_info.override).toEqual({});
    expect((a.t.chapters[0].delay_notes ?? [])).toEqual([]);
    expect(a.t.delta_p).toBeCloseTo(b.t.delta_p, 6);
    expect(a.t.delta_p_definitive).toBeCloseTo(b.t.delta_p_definitive, 6);
  });

  it("کارکردِ درونِ مدت: بدونِ بازنویسی", () => {
    const { t, w } = tadil(
      on({ contractDate: "۱۴۰۴/۰۱/۰۱", contractDurationMonths: 12 }),
    );
    expect(t.delay_info.contract_end).toBe("1405/01/01");
    expect(t.delay_info.override).toEqual({});
    expect(t.chapters[0].delay_notes ?? []).toEqual([]);
    expect(w.some((x) => x.category === "تأخیر پیمان")).toBe(false);
  });

  // ── ۲-۵-۱ تأخیر مجاز: شاخص همان دوره ──
  it("مجاز: شاخص همان سه‌ماهه (هیچ تفاوتی با حالتِ بدونِ طبقه‌بندی)", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "مجاز", docNo: "ن۱" },
    ];
    const { t, w } = tadil(on({ ...ON3, contractExtensions: ext }));
    expect(t.delay_info.override).toEqual({});
    const t0 = tadil(on()).t;
    expect(qmap(t)).toEqual(qmap(t0));
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
    expect(t.chapters[0].delay_notes ?? []).toEqual([]);
    expect(w.some((x) => x.item === "delay_uncovered")).toBe(false);
  });

  // ── ۲-۵-۲ تأخیر غیرمجاز: میانگین شاخص‌های داخل مدت ──
  it("غیرمجاز: میانگین شاخص‌های داخل مدت (همگی قطعی)", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "غیرمجاز", docNo: "ن۲" },
    ];
    const { t } = tadil(on({ ...ON3, contractExtensions: ext }));
    const di = t.delay_info;
    expect(di.contract_end).toBe("1404/04/01");
    expect(di.term_end).toBe("1404/10/01");
    expect(di.term_quarters).toEqual(["1404Q1", "1404Q2", "1404Q3", "1404Q4"]);
    // سه‌ماهه‌های پس از مدت: Q2, Q3, Q4 (Q1 درونِ مدت است)
    expect(Object.keys(di.override).sort()).toEqual(["1404Q2", "1404Q3", "1404Q4"]);
    const vals = di.term_quarters.map((q) => quarterIndex("06", q, 1)[0]);
    const exp = (vals.reduce((a, b) => a + (b ?? 0), 0) ?? 0) / vals.length;
    for (const q of ["1404Q2", "1404Q3", "1404Q4"] as const) {
      const [v, st] = qmap(t)[q];
      expect(v).toBeCloseTo(exp, 6);
      expect(st).toContain("۲-۵-۲");
    }
    // همگی قطعی ⇒ همه‌چیز در سبدِ قطعی
    expect(t.delta_p_definitive).toBeCloseTo(t.delta_p, 6);
    expect(t.delta_p_provisional).toBeCloseTo(0, 6);
    const notes = t.chapters[0].delay_notes ?? [];
    expect(notes.map((n) => n.q)).toEqual(["1404Q2", "1404Q3", "1404Q4"]);
    expect(notes.every((n) => n.rule === "غیرمجاز")).toBe(true);
  });

  // ── ۲-۵-۳ تأخیر تعیین‌نشده: علی‌الحساب ──
  it("تعیین‌نشده: علی‌الحساب با شاخص دورهٔ خاتمه + هشدار", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "تعیین‌نشده", docNo: "ن۳" },
    ];
    const { t, w } = tadil(on({ ...ON3, contractExtensions: ext }));
    expect(t.delay_info.override["1404Q2"].basis_q).toBe("1404Q4");
    for (const q of ["1404Q2", "1404Q3", "1404Q4"] as const) {
      const [v, st] = qmap(t)[q];
      expect(v).toBeCloseTo(CH06_Q4, 6);
      expect(st).toContain("علی‌الحساب");
      expect(st).toContain("۲-۵-۳");
    }
    // علی‌الحساب ⇒ در سبدِ موقت، حتی اگر شاخص قطعی است
    expect(t.delta_p_provisional).toBeGreaterThan(0);
    expect(t.delta_p_provisional).toBeCloseTo(
      t.delta_p - t.delta_p_definitive,
      6,
    );
    const inf = w.filter((x) => x.item === "delay_undefined");
    expect(inf.length).toBe(1);
    expect(inf[0].ref).toContain("۲-۵-۳");
  });

  // ── پس از مدت بدونِ تمدیدِ پوشش‌دهنده ⇒ علی‌الحساب + هشدار ──
  it("پس از مدتِ پوشش‌نشده: علی‌الحساب + هشدار برای هر سه‌ماهه", () => {
    const { t, w } = tadil(on({ ...ON3 }));
    const di = t.delay_info;
    expect(di.term_end).toBe("1404/04/01");
    expect(di.override["1404Q3"].basis_q).toBe("1404Q2");
    expect(qmap(t)["1404Q3"][1]).toContain("علی‌الحساب");
    const unc = w.filter((x) => x.item === "delay_uncovered");
    const covered = new Set<string>();
    for (const x of unc) {
      for (const q of ["1404Q2", "1404Q3", "1404Q4"]) {
        if (x.message.includes(`«${q}»`)) covered.add(q);
      }
    }
    expect(covered).toEqual(new Set(["1404Q2", "1404Q3", "1404Q4"]));
    expect(unc.every((x) => x.ref.includes("۲-۵-۳"))).toBe(true);
  });

  // ── تمدید نامعتبر نادیده گرفته می‌شود + خطا ──
  it("تمدید نامعتبر: نادیده + دو خطا", () => {
    const { t, w } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        contractExtensions: [
          { date: "bad", months: 3, kind: "مجاز", docNo: "" },
          { date: "۱۴۰۴/۰۶/۰۱", months: 0, kind: "مجاز", docNo: "" },
        ],
      }),
    );
    const errs = w.filter(
      (x) => x.item === "contract_extensions" && x.level === "خطا",
    );
    expect(errs.length).toBe(2);
    expect(t.delay_info.override).toEqual({});
    expect(w.some((x) => x.item === "delay_uncovered")).toBe(false);
  });

  // ── مرز: سه‌ماهه‌ای که روی تاریخ خاتمه شروع می‌شود، پس از مدت است ──
  it("مرز: سه‌ماههٔ آغازشده از تاریخ خاتمه، پس از مدت است", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۵/۰۱", months: 6, kind: "تعیین‌نشده", docNo: "ن۴" },
    ];
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 4,
        contractExtensions: ext,
      }),
    );
    expect(Object.keys(t.delay_info.override).sort()).toEqual(["1404Q3", "1404Q4"]);
    const t0 = tadil(on()).t;
    // Q2 درونِ مدت است ⇒ شاخصِ خودش
    expect(qmap(t)["1404Q2"]).toEqual(qmap(t0)["1404Q2"]);
  });

  // ── ساختارِ delay_info ──
  it("delay_info در خروجی.present", () => {
    const { t } = tadil(on({ contractDate: "۱۴۰۴/۰۱/۰۱", contractDurationMonths: 6 }));
    const di = t.delay_info;
    expect(Object.keys(di).sort()).toEqual(
      ["contract_end", "override", "term_end", "term_quarters"].sort(),
    );
    expect(di.contract_end).toBe("1404/07/01");
    expect(di.term_quarters).toEqual(["1404Q1", "1404Q2", "1404Q3"]);
  });

  // ── تجهیز/برچیدن: همان قاعده روی شاخصِ رشته (بند ۴) ──
  it("تجهیز: میانگینِ داخلِ مدت (مجموعِ وزن‌دار)", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "غیرمجاز", docNo: "ن۵" },
    ];
    const { t } = tadil(
      on({ ...ON3, contractExtensions: ext }),
      ctx(BASE),
    );
    const sr = t.setup_row;
    expect(sr).not.toBeNull();
    const term = t.delay_info.term_quarters;
    const avg =
      term.reduce((s, q) => s + (quarterDiscipline(q, 1)[0] ?? 0), 0) / term.length;
    const wmap = new Map(t.split);
    const expIt =
      (wmap.get("1404Q1") ?? 0) * (quarterDiscipline("1404Q1", 1)[0] ?? 0) +
      (["1404Q2", "1404Q3", "1404Q4"] as const).reduce(
        (s, q) => s + (wmap.get(q) ?? 0),
        0,
      ) *
        avg;
    expect(sr!.it).toBeCloseTo(expIt, 6);
    expect((sr!.delay_notes ?? []).map((n) => n.rule)).toEqual([
      "غیرمجاز",
      "غیرمجاز",
      "غیرمجاز",
    ]);
  });

  // ── کمک‌آینِ اضافه‌کردنِ ماه ──
  it.each([
    ["۱۴۰۴/۰۱/۰۱", 6, "1404/07/01"],
    ["۱۴۰۴/۰۶/۳۱", 1, "1404/07/30"],
    ["۱۴۰۴/۱۲/۲۹", 2, "1405/02/29"],
    ["۱۴۰۴/۰۶/۳۱", 12, "1405/06/31"],
    ["۱۴۰۳/۱۲/۳۰", 1, "1404/01/30"],
    ["۱۴۰۴/۰۱/۰۱", 0, null],
    ["bad", 3, null],
    ["", 3, null],
  ])("addMonthsJalali: %s + %s ماه ⇒ %s", (d, m, exp) => {
    expect(addMonthsJalali(d, m)).toBe(exp);
  });

  // ── delayClassification مستقل (بدونِ موتور) ──
  it("delayClassification:.kind مجاز هیچ بازنویسی نمی‌دهد", () => {
    const w: Warning[] = [];
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "مجاز", docNo: "" },
    ];
    const di = delayClassification(
      "۱۴۰۴/۰۱/۰۱",
      3,
      ext,
      [["1404Q2", 0.3], ["1404Q3", 0.7]],
      w,
    );
    expect(di.override).toEqual({});
    expect(di.term_quarters).toEqual(["1404Q1", "1404Q2", "1404Q3", "1404Q4"]);
    expect(w.length).toBe(0);
  });
});
