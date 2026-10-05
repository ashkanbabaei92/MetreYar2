// ─────────────────────────────────────────────────────────────
// T104 — فاز E-6 Part C گام ۶ (حرف b): مسیر شاخص — بندهای ۲-۱/۲-۲
//
// بند ۲-۱: پیمان‌های با مبلغ اولیهٔ کمتر از آستانه با شاخص رشته‌ای تعدیل
// می‌شوند. بند ۲-۲: آستانه و بیشتر با شاخص‌های گروهی (هر فصل).
// آستانه از config/index_bulletins.json → bulletin_2080.threshold_rail.
// آینهٔ tests/char_python/test_T104_e6_index_chain.py — اعداد از همان
// جدولی محاسبه می‌شوند که موتور می‌خواند (indexValue/quarterDiscipline).
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import {
  baravordEngine,
  indexValue,
  quarterDiscipline,
  tadilEngine,
  workSplit,
} from "../../src/lib/adjustment";
import { copyProject } from "../../src/lib/manualEntries";
import { defaultSettings } from "../../src/lib/engine";
import type {
  AdjustmentCtx,
  ProjectMeta,
  ProjectSettings,
  Warning,
} from "../../src/lib/types";

const BASE = 10_000_000_000.0;
// ΔP مرجعِ این تنظیمات (گروهی، setup=۰) — از موتور استخراج شده تا
// تغییرِ ناخواستهٔ مسیرِ گروهی فوراً خودش را نشان دهد.
const REF_DELTA_P_GROUP = 4273060821.9178085;

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
    floors_info: { value: 1.0, status: "کامل", eligible_total: BASE, excluded_total: 0 },
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

function tadil(s: ProjectSettings, c?: AdjustmentCtx) {
  const w: Warning[] = [];
  return { t: tadilEngine(s, c ?? ctx(), w), w };
}

function ch0(t: ReturnType<typeof tadilEngine>) {
  return t.chapters[0];
}

function warnItem(w: Warning[], item: string) {
  return w.filter((x) => x.item === item);
}

describe("T104 — فاز E-6 Part C گام ۶: مسیر شاخص (۲-۱/۲-۲)", () => {
  // ── ۱) پیش‌فرض: مسیر گروهی، بدون تغییر، بدون هشدار ──
  it("default = group, no warnings", () => {
    const { t, w } = tadil(on());
    expect(t.index_method_resolved).toEqual({ method: "گروهی", source: "دستی" });
    expect(t.delta_p).toBeCloseTo(REF_DELTA_P_GROUP, 4);
    expect(warnItem(w, "index_method_threshold_1370")).toHaveLength(0);
    expect(warnItem(w, "index_method_no_amount")).toHaveLength(0);
  });

  // ── ۲) خودکار + مبلغِ کمتر از آستانه ⇒ رشته‌ای + هشدارِ آستانه ──
  it("auto below threshold = reshteh + threshold warning", () => {
    const { t, w } = tadil(
      on({ indexMethod: "خودکار", contractInitialAmount: 200_000_000 }),
    );
    expect(t.index_method_resolved.method).toBe("رشته‌ای");
    expect(t.index_method_resolved.source).toBe(
      "خودکار: مبلغ اولیه < آستانه (بند ۲-۱)",
    );
    const f = warnItem(w, "index_method_threshold_1370");
    expect(f).toHaveLength(1);
    expect(f[0].level).toBe("اطلاع");
    expect(f[0].category).toBe("موتور تعدیل");
    expect(f[0].message.startsWith("آستانهٔ ۳۰۰,۰۰۰,۰۰۰ ریال")).toBe(true);
    expect(f[0].action).toBe("آستانه و مبلغ اولیهٔ پیمان را بررسی کنید.");
    expect(f[0].ref).toBe("بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲");
  });

  // ── ۳) خودکار + مبلغِ آستانه و بیشتر ⇒ گروهی، مثلِ پیش‌فرض ──
  it("auto at/above threshold = group, same delta_p", () => {
    const a = tadil(on());
    const { t } = tadil(
      on({ indexMethod: "خودکار", contractInitialAmount: 400_000_000 }),
    );
    expect(t.index_method_resolved.method).toBe("گروهی");
    expect(t.delta_p).toBeCloseTo(a.t.delta_p, 4);
  });

  // ── ۴) خودکار بدون مبلغ ⇒ گروهی + هشدار ──
  it("auto without amount = group + warning", () => {
    const { t, w } = tadil(
      on({ indexMethod: "خودکار", contractInitialAmount: null }),
    );
    expect(t.index_method_resolved.method).toBe("گروهی");
    const f = warnItem(w, "index_method_no_amount");
    expect(f).toHaveLength(1);
    expect(f[0].level).toBe("هشدار");
    expect(f[0].category).toBe("موتور تعدیل");
    expect(f[0].message).toBe(
      "مسیر شاخص «خودکار» است ولی مبلغ اولیهٔ پیمان وارد نشده؛ مسیر گروهی (۲-۲) فرض می‌شود.",
    );
    expect(f[0].action).toBe(
      "مبلغ اولیهٔ پیمان را در بخش «ورودی‌های قرارداد» وارد کنید.",
    );
    expect(f[0].ref).toBe("بخشنامهٔ ۲۰۸۰، بندهای ۲-۱ و ۲-۲");
  });

  // ── ۵) مرزِ دقیقِ آستانه ⇒ گروهی (آستانه مشمولِ ۲-۲ است) ──
  it("boundary at exact threshold = group", () => {
    const { t } = tadil(
      on({ indexMethod: "خودکار", contractInitialAmount: 300_000_000 }),
    );
    expect(t.index_method_resolved.method).toBe("گروهی");
  });

  // ── ۶) رشته‌ایِ دستی: شاخصِ رشته برای Io و Itِ هر سه‌ماهه ──
  it("manual reshteh uses discipline index", () => {
    const { t } = tadil(on({ indexMethod: "رشته‌ای" }));
    const ch = ch0(t);
    const [dIo] = indexValue("base", "ابنیه");
    expect(ch.io).toBe(dIo);
    expect(ch.src).toBe("شاخص رشته (مسیر ۲-۱)");
    for (const [q, v] of ch.quarters) {
      const [dv] = quarterDiscipline(q, 1, "ابنیه");
      expect(v).toBe(dv);
    }
    // نسبتِ وزن‌دار: Σ f_q × it_q ÷ io
    let exp = 0;
    for (const [q, f] of workSplit("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۱۲/۲۹")) {
      const [dv] = quarterDiscipline(q, 1, "ابنیه");
      exp += f * (dv as number);
    }
    expect(ch.ratio).toBeCloseTo(exp / (dIo as number), 9);
  });

  // ── ۷) رشته‌ای + ۲-۶: میانگینِ شاخص‌های رشته تا آخرین موقت ──
  it("reshteh + 2-6 average uses discipline", () => {
    const { t } = tadil(
      on({
        indexMethod: "رشته‌ای",
        contractDate: "۱۴۰۴/۰۱/۰۱",
        contractDurationMonths: 12,
        lastProvisionalDate: "۱۴۰۴/۰۶/۳۰",
      }),
    );
    const ch = ch0(t);
    const span = workSplit("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۰۶/۳۰").map(([q]) => q);
    const vals = span.map((q) => quarterDiscipline(q, 1, "ابنیه")[0] as number);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    const notes = new Map((ch.delay_notes ?? []).map((n) => [n.q, n]));
    let checked = 0;
    for (const [q, v] of ch.quarters) {
      const n = notes.get(q);
      if (n && n.rule === "۲-۶") {
        expect(v).toBeCloseTo(avg, 9);
        checked++;
      }
    }
    expect(checked).toBeGreaterThan(0);
  });

  // ── ۸) هشدارها وقتی هر دو موتور روشن‌اند یکبار ساطع می‌شوند ──
  it("warnings deduped across both engines", () => {
    const s = on({ indexMethod: "خودکار", baravordEnabled: true });
    const w: Warning[] = [];
    tadilEngine(s, ctx(), w);
    baravordEngine(s, ctx(), w);
    expect(warnItem(w, "index_method_threshold_1370")).toHaveLength(1);
    expect(warnItem(w, "index_method_no_amount")).toHaveLength(1);
  });

  // ── ۹) هر دو موتور مسیرِ حل‌شده را برمی‌گردانند ──
  it("resolved method present in both engines", () => {
    const s = on({
      indexMethod: "خودکار",
      contractInitialAmount: 200_000_000,
      baravordEnabled: true,
    });
    const w: Warning[] = [];
    const t = tadilEngine(s, ctx(), w);
    const b = baravordEngine(s, ctx(), w);
    expect(t.index_method_resolved.method).toBe("رشته‌ای");
    expect(b.index_method_resolved.method).toBe("رشته‌ای");
    expect(t.index_method_resolved.source).toBe(b.index_method_resolved.source);
  });

  // ── ۱۰) copyProject مسیر و مبلغ اولیه را نگه می‌دارد ──
  it("copyProject keeps indexMethod + amount", () => {
    const s = on({ indexMethod: "خودکار", contractInitialAmount: 200_000_000 });
    const meta: ProjectMeta = {
      projectName: "پروژهٔ آزمایشی", employer: "", contractor: "",
      consultant: "", contractNo: "۹۹", contractDate: "۱۴۰۴/۰۱/۰۱",
      location: "", reportNo: "۳", reportType: "موقت",
      periodStart: "۱۴۰۴/۰۱", periodEnd: "۱۴۰۴/۰۶",
    };
    const cp = copyProject(s, meta);
    expect(cp.settings.indexMethod).toBe("خودکار");
    expect(cp.settings.contractInitialAmount).toBe(200_000_000);
  });
});
