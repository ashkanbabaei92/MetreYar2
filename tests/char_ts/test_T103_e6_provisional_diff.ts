// ─────────────────────────────────────────────────────────────
// T103 — فاز E-6 Part C گام ۹ (حرف a): بند ۲-۶ — مابه‌التفاوتِ آخرین
// صورت‌وضعیتِ موقت و صورت‌وضعیتِ قطعی.
//
// بند ۲-۶ بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (docs/sources/2080_summary.md):
//   مابه‌التفاوت آخرین صورت‌وضعیت موقت و صورت‌وضعیت قطعی: اگر در مدت پیمان
//   انجام شده، با میانگین شاخص‌های دوره‌های سه‌ماههٔ بین تاریخ شروع پیمان و
//   تاریخ آخرین صورت‌وضعیت موقت.
//   تبصرهٔ ۱: اگر دورهٔ انجام بخشی از آن قابل تشخیص است، با شاخص همان دوره.
//   تبصرهٔ ۲: اگر تمام یا بخشی از آن در تأخیر غیرمجاز انجام شده، طبق ۲-۵-۲.
//
// آینهٔ test_T103_e6_provisional_diff.py — مقدارِ «منتظر» از همان جدولی
// محاسبه می‌شود که موتور می‌خواند (quarterIndex/quarterDiscipline) — هیچ
// عددی حدس زده نمی‌شود.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import {
  quarterDiscipline,
  quarterIndex,
  tadilEngine,
  workSplit,
} from "../../src/lib/adjustment";
import { defaultSettings } from "../../src/lib/engine";
import type {
  AdjustmentCtx,
  ContractExtension,
  ProjectSettings,
  Warning,
} from "../../src/lib/types";

const BASE = 10_000_000_000.0;

function ctx(setup = 0.0): AdjustmentCtx {
  return {
    chapter_amounts: { "06": BASE },
    floors_amount: BASE,
    base_total: BASE,
    site_setup: setup,
    advance_payment: 0,
    overhead_coef: 1.3,
    regional_coef: 1.04,
    grand_total: BASE * 1.352,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: BASE,
      excluded_total: 0,
    },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    proposalDate: "۱۴۰۳/۱۲/۲۹", // ⇒ Io = ۱۴۰۳Q4 (مبنا)
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

function notes(t: ReturnType<typeof tadilEngine>) {
  return (t.chapters ?? [])[0]?.delay_notes ?? [];
}

function lpdWarns(w: Warning[]) {
  return w.filter((x) => x.item === "last_provisional_date");
}

describe("T103 فاز E-6 Part C گام ۹ — بند ۲-۶ (موقت ↔ قطعی)", () => {
  // ── بدونِ آخرین موقت: هیچ بازنویسی‌ای نیست (اعداد مرجع ثابت) ──
  it("بدون lpd: بازنویسی نیست", () => {
    const { t, w } = tadil(
      on({ contractDate: "۱۴۰۴/۰۱/۰۱", contractDurationMonths: 12 }),
    );
    expect(notes(t)).toEqual([]);
    expect(lpdWarns(w)).toEqual([]);
    const t0 = tadil(on()).t;
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
  });

  // ── متنِ اصلیِ بند: میانگین شاخص‌های شروع تا آخرین موقت ──
  it("lpd میانی: Q3 و Q4 میانگینِ Q1+Q2 را می‌گیرند", () => {
    const { t, w } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
      }),
    );
    expect(lpdWarns(w)).toEqual([]);
    const span = ["1404Q1", "1404Q2"]; // workSplit(شروع، lpd)
    const vals = span.map((q) => quarterIndex("06", q, 1)[0]!);
    const exp = (vals[0] + vals[1]) / 2;
    const m = qmap(t);
    // Q1 و Q2 شاخصِ خودشان را نگه می‌دارند
    for (const q of ["1404Q1", "1404Q2"] as const) {
      expect(m[q][0]).toBeCloseTo(quarterIndex("06", q, 1)[0]!, 6);
      expect(m[q][1]).not.toContain("۲-۶");
    }
    // Q3 و Q4 میانگینِ ۲-۶ را می‌گیرند
    for (const q of ["1404Q3", "1404Q4"] as const) {
      expect(m[q][0]).toBeCloseTo(exp, 6);
      expect(m[q][1]).toContain("۲-۶");
    }
    const ns = notes(t);
    expect(ns.map((n) => n.q)).toEqual(["1404Q3", "1404Q4"]);
    expect(ns.every((n) => n.rule === "۲-۶")).toBe(true);
  });

  // ── تبصرهٔ ۱: شاخصِ همان دوره (بدونِ بازنویسی) ──
  it("own_period (تبصرهٔ ۱): شاخصِ همان سه‌ماهه", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
        provisionalDiffMethod: "own_period",
      }),
    );
    const t0 = tadil(on()).t;
    expect(qmap(t)).toEqual(qmap(t0));
    expect(notes(t)).toEqual([]);
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
  });

  // ── lpd قبل از شروعِ پیمان: هشدار + بدونِ بازنویسی ──
  it("lpd قبل از شروع: هشدار و بدون بازنویسی", () => {
    const { t, w } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۶/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۱/۰۱",
      }),
    );
    const f = lpdWarns(w);
    expect(f.length).toBe(1);
    expect(f[0].message).toContain("قبل از شروع");
    expect(f[0].ref).toContain("۲-۶");
    expect(notes(t)).toEqual([]);
    const t0 = tadil(on()).t;
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
  });

  // ── بدونِ تاریخِ شروع: هشدار + بدونِ بازنویسی ──
  it("بدونِ تاریخ شروع: هشدار و بدون بازنویسی", () => {
    const { t, w } = tadil(
      on({
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
      }),
    );
    const f = lpdWarns(w);
    expect(f.length).toBe(1);
    expect(f[0].message).toContain("شروع پیمان");
    expect(notes(t)).toEqual([]);
    const t0 = tadil(on()).t;
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
  });

  // ── lpd نامعتبر: هشدار ──
  it("lpd نامعتبر: هشدار", () => {
    const { t, w } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "نامعتبر",
      }),
    );
    const f = lpdWarns(w);
    expect(f.length).toBe(1);
    expect(f[0].message).toContain("نامعتبر");
    expect(notes(t)).toEqual([]);
  });

  // ── lpd بعد از پایانِ کار: بدونِ بازنویسی ──
  it("lpd بعد از پایان کار: بدون بازنویسی", () => {
    const { t, w } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۵/۰۶/۳۰",
      }),
    );
    expect(lpdWarns(w)).toEqual([]);
    expect(notes(t)).toEqual([]);
    const t0 = tadil(on()).t;
    expect(t.delta_p).toBeCloseTo(t0.delta_p, 6);
  });

  // ── تبصرهٔ ۲: تأخیر غیرمجاز → ۲-۵-۲ (اولویت) ──
  it("غیرمجاز: ۲-۵-۲ اولویت دارد (تبصرهٔ ۲)", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "غیرمجاز", docNo: "ن۲" },
    ];
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: ext,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
      }),
    );
    const ns = notes(t);
    expect(ns.length).toBeGreaterThan(0);
    expect(ns.every((n) => n.rule === "غیرمجاز")).toBe(true);
    expect(ns.some((n) => n.rule === "۲-۶")).toBe(false);
    const m = qmap(t);
    expect(Object.values(m).every(([, st]) => !st.includes("۲-۶"))).toBe(true);
  });

  // ── تمدیدِ مجاز: کارِ پوشش‌شده جزوِ مدت است ⇒ ۲-۶ (تفسیر — §۱۸-۳) ──
  it("مجاز: کارِ بین contract_end و term_end بعد از lpd ⇒ ۲-۶", () => {
    const ext: ContractExtension[] = [
      { date: "۱۴۰۴/۰۴/۰۱", months: 6, kind: "مجاز", docNo: "ن۱" },
    ];
    const { t, w } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 3,
        contractExtensions: ext,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
      }),
    );
    expect(t.delay_info.term_end).toBe("1404/10/01");
    expect(t.delay_info.override).toEqual({});
    const span = ["1404Q1", "1404Q2"];
    const vals = span.map((q) => quarterIndex("06", q, 1)[0]!);
    const exp = (vals[0] + vals[1]) / 2;
    const m = qmap(t);
    // Q3 (شروع ۱۴۰۴/۰۷/۰۱): بعد از lpd، قبل از term_end، بدون override
    expect(m["1404Q3"][0]).toBeCloseTo(exp, 6);
    expect(m["1404Q3"][1]).toContain("۲-۶");
    // Q4 (شروع ۱۴۰۴/۱۰/۰۱ = term_end): بعد از مدت ⇒ شاخصِ خودش (۲-۵-۱)
    expect(m["1404Q4"][0]).toBeCloseTo(quarterIndex("06", "1404Q4", 1)[0]!, 6);
    expect(m["1404Q4"][1]).not.toContain("۲-۶");
    const ns = notes(t);
    expect(ns.map((n) => n.q)).toEqual(["1404Q3"]);
    expect(ns[0].rule).toBe("۲-۶");
    expect(lpdWarns(w)).toEqual([]);
  });

  // ── تجهیز و برچیدن: همان منطق (شاخص رشته‌ای) ──
  it("تجهیز: میانگین شاخص رشتهٔ شروع تا lpd", () => {
    const { t } = tadil(
      on({
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
      }),
      ctx(BASE),
    );
    const span = ["1404Q1", "1404Q2"];
    const vals = span.map((q) => quarterDiscipline(q, 1)[0]!);
    const avg26 = (vals[0] + vals[1]) / 2;
    // it تجهیز = Σ(f_q × it_q) — Q3 و Q4 میانگینِ ۲-۶ را می‌گیرند
    let expIt = 0;
    for (const [q, f] of workSplit("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۱۲/۲۹")) {
      const iv = ["1404Q3", "1404Q4"].includes(q)
        ? avg26
        : quarterDiscipline(q, 1)[0]!;
      expIt += f * iv;
    }
    const row = t.setup_row;
    expect(row).not.toBeNull();
    expect(row!.it).toBeCloseTo(expIt, 6);
    const sn = row!.delay_notes ?? [];
    expect(sn.map((n) => n.q)).toEqual(["1404Q3", "1404Q4"]);
    expect(sn.every((n) => n.rule === "۲-۶")).toBe(true);
  });
});
