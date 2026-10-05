// ─────────────────────────────────────────────────────────────
// T100 — فاز E-6 Part C (گام ۲): روش شاخص مبنا (بندهای ۱-۶-۱/۱-۶-۲)،
// پیشنهاد نهاییِ ترک تشریفات (finalOfferDate)، و هشدارِ Io بعد از It.
// (آینهٔ test_T100_e6_base_index.py — پاریتی کامل).
//
// منبع: بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳) — docs/sources/2080_summary.md
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import * as path from "node:path";
import { defaultSettings } from "../../src/lib/engine";
import { dateQuarter, tadilEngine } from "../../src/lib/adjustment";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";
import indexBulletins from "../../config/index_bulletins.json";

const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"; // ⇒ Io = ۱۴۰۳Q4 (مبنا)

function ctx(): AdjustmentCtx {
  const base = 10_000_000_000.0;
  return {
    chapter_amounts: { "06": base },
    floors_amount: base,
    base_total: base,
    site_setup: 0,
    advance_payment: 0,
    overhead_coef: 1.3,
    regional_coef: 1.04,
    grand_total: base * 1.352,
    floors_info: { value: 1.0, status: "کامل", eligible_total: base, excluded_total: 0.0 },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return { ...defaultSettings(), tadilEnabled: true, proposalDate: PROPOSAL_DATE, ...extra };
}

function tadil(settings: ProjectSettings): { t: ReturnType<typeof tadilEngine>; w: Warning[] } {
  const w: Warning[] = [];
  return { t: tadilEngine(settings, ctx(), w), w };
}

// changeConfig: جایگزینی موقتی fehrest_base_periods (همان شیءِ CFG موتور)
function changeConfig(v: Record<string, unknown>): () => void {
  const cfg = indexBulletins as unknown as Record<string, any>;
  const orig = cfg["fehrest_base_periods"];
  cfg["fehrest_base_periods"] = v;
  return () => {
    cfg["fehrest_base_periods"] = orig;
  };
}

describe("T100 فاز E-6 Part C — روش شاخص مبنا", () => {
  // ── ۱-۶-۱ دوم: ترک تشریفات ⇒ ملاک پیشنهاد نهایی کتبی ──
  it("finalOfferDate مقدم بر deadline و proposalDate است", () => {
    const { t } = tadil(
      on({ proposalDate: "۱۴۰۳/۱۲/۲۹", proposalDeadline: "۱۴۰۴/۰۶/۰۱", finalOfferDate: "۱۴۰۴/۰۹/۰۱" }),
    );
    expect(t.error).toBeUndefined();
    expect(t.io_q).toBe("1404Q3");
  });

  it("بدون پیشنهاد نهایی: مهلت تسلیم مقدم بر تاریخ تسلیم است", () => {
    const { t } = tadil(
      on({ proposalDate: "۱۴۰۳/۱۲/۲۹", proposalDeadline: "۱۴۰۴/۰۳/۰۱", finalOfferDate: "" }),
    );
    expect(t.error).toBeUndefined();
    expect(t.io_q).toBe("1404Q1");
  });

  it("finalOfferDate نامعتبر ⇒ توقف موتور", () => {
    const { t, w } = tadil(on({ finalOfferDate: "بد" }));
    expect(t.error).toBeDefined();
    expect(w.some((x) => x.level === "خطا")).toBe(true);
  });

  // ── ۱-۶-۲: پیمان بدون فهرست‌بها ──
  it("no_base_list: دورهٔ تسلیم پیشنهاد ملاک است", () => {
    const { t } = tadil(on({ baseIndexMethod: "no_base_list", proposalDate: "۱۴۰۴/۰۳/۱۵" }));
    expect(t.error).toBeUndefined();
    expect(t.io_q).toBe("1404Q1");
  });

  // ── ۱-۶-۱ یکم: دورهٔ تهیهٔ فهرست‌بها ──
  it("fehrest_period: دوره در config نیست ⇒ توقف + نیازمند ورود", () => {
    const restore = changeConfig({ "۱۴۰۴": null });
    try {
      const { t, w } = tadil(on({ baseIndexMethod: "fehrest_period", fehrestYear: "۱۴۰۴" }));
      expect(t.error).toBeDefined();
      expect(t.incomplete).toBe(true);
      expect(w.some((x) => x.level === "خطا" && x.item === "proposal_date")).toBe(true);
      expect(t.error ?? "").toContain("۱۴۰۴");
    } finally {
      restore();
    }
  });

  it("fehrest_period: سال در جدول نیست ⇒ توقف", () => {
    const restore = changeConfig({});
    try {
      const { t } = tadil(on({ baseIndexMethod: "fehrest_period", fehrestYear: "۱۴۰۴" }));
      expect(t.error).toBeDefined();
    } finally {
      restore();
    }
  });

  it("fehrest_period: وقتی دوره در config است، Io = همان دوره", () => {
    const restore = changeConfig({ "۱۴۰۴": "1403Q4" });
    try {
      const { t } = tadil(on({ baseIndexMethod: "fehrest_period", fehrestYear: "۱۴۰۴" }));
      expect(t.error).toBeUndefined();
      expect(t.io_q).toBe("1403Q4");
      // تاریخ‌های تسلیم دیگر ملاک نیستند
      const { t: t2 } = tadil(
        on({
          baseIndexMethod: "fehrest_period",
          fehrestYear: "۱۴۰۴",
          proposalDate: "۱۴۰۴/۰۹/۰۱",
          proposalDeadline: "۱۴۰۴/۰۹/۰۱",
        }),
      );
      expect(t2.io_q).toBe("1403Q4");
      // و حتی خالی بودن همهٔ تاریخ‌ها
      const { t: t3 } = tadil(
        on({
          baseIndexMethod: "fehrest_period",
          fehrestYear: "۱۴۰۴",
          proposalDate: "",
          proposalDeadline: "",
          finalOfferDate: "",
        }),
      );
      expect(t3.error).toBeUndefined();
      expect(t3.io_q).toBe("1403Q4");
    } finally {
      restore();
    }
  });

  it("fehrest_period: مقدار غیرمجاز در config ⇒ توقف", () => {
    const restore = changeConfig({ "۱۴۰۴": "1399Q2" });
    try {
      const { t } = tadil(on({ baseIndexMethod: "fehrest_period", fehrestYear: "۱۴۰۴" }));
      expect(t.error).toBeDefined();
    } finally {
      restore();
    }
  });

  // ── بند ۱-۷: هشدار Io بعد از It ──
  it("هشدار وقتی Io بعد از It است (بند ۱-۷)", () => {
    const { w } = tadil(on({ proposalDate: "۱۴۰۴/۰۹/۰۱", tadilItPeriod: "q2" }));
    const ioWarns = w.filter((x) => x.item === "io_after_it");
    expect(ioWarns.length).toBe(1);
    expect(ioWarns[0].message).toContain("1404Q3");
    expect(ioWarns[0].message).toContain("1404Q2");
    expect(ioWarns[0].ref ?? "").toContain("۱-۷");
  });

  it("هیچ هشداری وقتی Io قبل از It است", () => {
    const { w } = tadil(on({ proposalDate: "۱۴۰۳/۱۲/۲۹", tadilItPeriod: "q2" }));
    expect(w.some((x) => x.item === "io_after_it")).toBe(false);
  });

  it("تنظیمات پیش‌فرض: هیچ هشدارِ io_after_it", () => {
    const { w } = tadil(on());
    expect(w.some((x) => x.item === "io_after_it")).toBe(false);
  });

  // ── مرزهای فصل‌ها (بند ۱-۵) ──
  it.each([
    ["۱۴۰۴/۰۱/۰۱", "1404Q1"],
    ["۱۴۰۴/۰۳/۳۱", "1404Q1"],
    ["۱۴۰۴/۰۴/۰۱", "1404Q2"],
    ["۱۴۰۴/۰۶/۳۱", "1404Q2"],
    ["۱۴۰۴/۰۷/۰۱", "1404Q3"],
    ["۱۴۰۴/۰۹/۳۰", "1404Q3"],
    ["۱۴۰۴/۱۰/۰۱", "1404Q4"],
    ["۱۴۰۴/۱۲/۲۹", "1404Q4"],
    ["۱۴۰۳/۱۲/۲۹", "1403Q4"],
  ])("مرز سه‌ماهه: %s ⇒ %s", (d, expected) => {
    expect(dateQuarter(d)).toBe(expected);
  });

  it.each(["۱۴۰۴/۱۳/۰۱", "بد", ""])("تاریخ نامعتبر رد می‌شود: %s", (bad) => {
    expect(dateQuarter(bad)).toBeNull();
  });

  it("طولِ ماه بررسی نمی‌شود ولی انتسابِ سه‌ماهه درست است", () => {
    // یادداشت: تجزیه‌کنندهٔ تاریخ درست‌بودنِ طولِ ماه را بررسی نمی‌کند
    // (۱۴۰۳ کبیسه نیست ولی ۳۰ اسفند را می‌پذیرد). رفتارِ ازپیش‌وجودداشته.
    expect(dateQuarter("۱۴۰۳/۱۲/۳۰")).toBe("1403Q4");
    expect(dateQuarter("۱۴۰۴/۱۲/۳۰")).toBe("1404Q4");
    expect(dateQuarter("۱۴۰۴/۰۱/۳۲")).toBeNull();
  });
});
