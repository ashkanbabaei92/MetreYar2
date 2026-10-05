// ─────────────────────────────────────────────────────────────
// T105 — فاز E-6 Part C گام ۵ (حرف c): کارهای جدید — بندهای ۳-۱..۳-۵
//
// ۳-۱: قیمت از فهرستِ ضمیمهٔ پیمان (شاخص مبنا = مبنای پیمان).
// ۳-۲: فهرستِ پایه / ۳-۳: قیمت روز (شاخص مبنا = دورهٔ آن قیمت‌ها).
// ۳-۴: ترکیب — هر بخش طبق روشِ همان بخش.
// ۳-۵: قیمت بر ۰٫۹۵ تقسیم، سپس × (Io پیمان ÷ Io کار جدید).
// آینهٔ tests/char_python/test_T105_e6_new_work.py — اعداد از همان
// جدولی محاسبه می‌شوند که موتور می‌خواند (quarterDiscipline).
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import {
  baravordEngine,
  tadilEngine,
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
// ΔP و base_amount مرجعِ این تنظیمات (گروهی، setup=۰، بدون کار جدید)
const REF_DELTA_P = 4273060821.9178085;
const REF_BASE_AMT = 13520000000.0;
// شاخص‌های رشتهٔ ابنیه (config/index_bulletins.json)
const IO_BASE = 9744.7; // اسفند ۱۴۰۳
const IO_Q2 = 11608.0; // سه‌ماههٔ دوم ۱۴۰۴

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
    baravordEnabled: true,
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

function baravord(s: ProjectSettings, c?: AdjustmentCtx) {
  const w: Warning[] = [];
  return { b: baravordEngine(s, c ?? ctx(), w), w };
}

function warnItem(w: Warning[], item: string) {
  return w.filter((x) => x.item === item);
}

describe("T105 — فاز E-6 Part C گام ۵: کارهای جدید (۳-۱..۳-۵)", () => {
  // ── ۱) پیش‌فرض: کار جدیدی نیست، ردیفی هم نیست ──
  it("default = no-op", () => {
    const { t, w } = tadil(on());
    expect(t.new_work_row).toBeNull();
    expect(t.delta_p).toBeCloseTo(REF_DELTA_P, 4);
    expect(t.base_amount).toBeCloseTo(REF_BASE_AMT, 4);
    expect(warnItem(w, "new_item_base_period_missing")).toHaveLength(0);
    expect(warnItem(w, "new_item_095_conversion")).toHaveLength(0);
  });

  // ── ۲) ۳-۱ فهرست پیمان: شاخص مبنا همان مبنای پیمان ──
  it("۳-۱ fehrest peman uses contract base index", () => {
    const { t, w } = tadil(
      on({ newItemMethod: "فهرست پیمان", newItemAmount: 1_000_000_000 }),
    );
    const r = t.new_work_row!;
    expect(r).not.toBeNull();
    expect(r.method).toBe("فهرست پیمان");
    expect(r.amount).toBeCloseTo(1_000_000_000, 4);
    expect(r.io).toBeCloseTo(IO_BASE, 4);
    expect(r.io_new).toBeCloseTo(IO_BASE, 4); // ۳-۱ ⇒ همان Io
    expect(r.conv).toBeCloseTo(1.0, 6);
    expect(r.ratio).toBeCloseTo(1.2786616005244016, 6);
    expect(r.it).toBeCloseTo(12460.173698630137, 4);
    expect(r.delta).toBeCloseTo(265315068.49315068, 4);
    expect(r.delta).toBeCloseTo(r.value, 4);
    expect(r.deltaDefinitive).toBeCloseTo(r.delta, 4);
    expect(r.delta_k095).toBeCloseTo(r.delta, 4);
    // جمع‌ها
    expect(t.delta_p).toBeCloseTo(4538375890.410959, 4);
    expect(t.delta_p_definitive).toBeCloseTo(4538375890.410959, 4);
    expect(t.delta_p_provisional).toBeCloseTo(0, 5);
    // مبلغ پایه به اندازهٔ کار جدید زیاد می‌شود
    expect(t.base_amount).toBeCloseTo(REF_BASE_AMT + 1_000_000_000, 4);
    // ضریبِ هر سه‌ماهه گرد شده (بند ۸-۲)
    expect((r.coef_rows ?? []).map((x) => x[2])).toEqual([
      0.15, 0.18, 0.29, 0.45,
    ]);
    expect(warnItem(w, "new_item_base_period_missing")).toHaveLength(0);
  });

  // ── ۳) ۳-۲ فهرست پایه: شاخص مبنا = دورهٔ فهرست پایه ──
  it("۳-۲ fehrest payeh converts via ۳-۵", () => {
    const { t, w } = tadil(
      on({
        newItemMethod: "فهرست پایه",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
      }),
    );
    const r = t.new_work_row!;
    expect(r.method).toBe("فهرست پایه");
    expect(r.io_new).toBeCloseTo(IO_Q2, 4);
    // ۳-۵: تبدیل = (Io پیمان ÷ Io کار جدید) / ۰٫۹۵
    expect(r.conv).toBeCloseTo((IO_BASE / IO_Q2) / 0.95, 8);
    expect(r.conv).toBeCloseTo(0.883664623308789, 8);
    expect(r.amount).toBeCloseTo(883664623.308789, 4);
    expect(r.delta).toBeCloseTo(234449540.05814552, 4);
    expect(t.delta_p).toBeCloseTo(4507510361.975954, 4);
    // هشدارِ اطلاعاتیِ ۳-۵
    const f = warnItem(w, "new_item_095_conversion");
    expect(f).toHaveLength(1);
    expect(f[0].level).toBe("اطلاع");
    expect(f[0].ref).toBe("بخشنامهٔ ۲۰۸۰، بند ۳-۵");
  });

  // ── ۴) ۳-۳ قیمت روز: همان مسیرِ ۳-۲ ──
  it("۳-۳ gheymat rooz = same path as ۳-۲", () => {
    const { t } = tadil(
      on({
        newItemMethod: "قیمت روز",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
      }),
    );
    const r = t.new_work_row!;
    expect(r.method).toBe("قیمت روز");
    expect(r.conv).toBeCloseTo(0.883664623308789, 8);
    expect(r.amount).toBeCloseTo(883664623.308789, 4);
    expect(r.delta).toBeCloseTo(234449540.05814552, 4);
  });

  // ── ۵) ۳-۴ ترکیب: هر بخش طبق روشِ خودش ──
  it("۳-۴ tarkib splits by method", () => {
    const { t } = tadil(
      on({
        newItemMethod: "ترکیب",
        newItemAmount: 600_000_000,
        newItemAmountAttached: 400_000_000,
        newItemBasePeriod: "1404Q2",
      }),
    );
    const r = t.new_work_row!;
    expect(r.method).toBe("ترکیب");
    expect(r.amount_own).toBeCloseTo(400_000_000, 4);
    expect(r.amount_new).toBeCloseTo(600_000_000, 4);
    // ۴e8 + ۶e8 × conv
    expect(r.amount).toBeCloseTo(
      400_000_000 + 600_000_000 * 0.883664623308789,
      4,
    );
    expect(r.amount).toBeCloseTo(930198773.9852734, 4);
    expect(r.delta).toBeCloseTo(246795751.4321476, 4);
  });

  // ── ۶) دورهٔ مبنا ناموجود ⇒ خطا و بدونِ ردیف ──
  it("missing base period = error, no row", () => {
    const { t, w } = tadil(
      on({ newItemMethod: "فهرست پایه", newItemAmount: 1_000_000_000 }),
    );
    expect(t.new_work_row).toBeNull();
    expect(t.delta_p).toBeCloseTo(REF_DELTA_P, 4); // بدون تغییر
    const f = warnItem(w, "new_item_base_period_missing");
    expect(f).toHaveLength(1);
    expect(f[0].level).toBe("خطا");
    expect(f[0].ref).toBe("بخشنامهٔ ۲۰۸۰، بندهای ۳-۲ و ۳-۳");
  });

  // ── ۷) روشِ نامعتبر ⇒ برگشت به فهرست پیمان ──
  it("invalid method falls back to fehrest peman", () => {
    const { t } = tadil(
      on({ newItemMethod: "نامعتبر", newItemAmount: 1_000_000_000 }),
    );
    const r = t.new_work_row!;
    expect(r.method).toBe("فهرست پیمان");
    expect(r.amount_own).toBeCloseTo(1_000_000_000, 4);
    expect(r.amount_new).toBeCloseTo(0, 6);
    expect(r.delta).toBeCloseTo(265315068.49315068, 4);
  });

  // ── ۸) برآورد به‌هنگام: ۳-۲ در result_amount / base_amount ──
  it("baravord ۳-۲ updates totals", () => {
    const { b } = baravord(
      on({
        newItemMethod: "فهرست پایه",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
      }),
    );
    const r = b.new_work_row!;
    expect(r).not.toBeNull();
    expect(r.value).toBeCloseTo(1299747905.2559035, 4);
    expect(b.result_amount).toBeCloseTo(21061906886.806126, 4);
    expect(b.grand_updated).toBeCloseTo(21061906886.806126, 4);
    expect(b.base_amount).toBeCloseTo(14403664623.308788, 4);
  });

  // ── ۹) برآورد به‌هنگام: ۳-۱ ──
  it("baravord ۳-۱", () => {
    const { b } = baravord(
      on({ newItemMethod: "فهرست پیمان", newItemAmount: 1_000_000_000 }),
    );
    const r = b.new_work_row!;
    expect(r.value).toBeCloseTo(1470861083.460753, 4);
    expect(r.io).toBeCloseTo(IO_BASE, 4);
    expect(r.it).toBeCloseTo(14333.1, 4);
    expect(r.ratio).toBeCloseTo(1.470861083460753, 6);
    expect(b.result_amount).toBeCloseTo(21233020065.010975, 4);
    expect(b.base_amount).toBeCloseTo(REF_BASE_AMT + 1_000_000_000, 4);
  });

  // ── ۱۰) گردکردنِ بند ۸-۲: روشن/خاموش ──
  it("coef rounding changes delta", () => {
    const onR = tadil(
      on({
        newItemMethod: "فهرست پایه",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
      }),
    );
    const offR = tadil(
      on({
        newItemMethod: "فهرست پایه",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
        coefRounding2080: false,
      }),
    );
    const rOn = onR.t.new_work_row!;
    const rOff = offR.t.new_work_row!;
    // ضرایبِ خام یکسان هستند
    expect((rOn.coef_rows ?? []).map((x) => x[1])).toEqual(
      (rOff.coef_rows ?? []).map((x) => x[1]),
    );
    // گردکردن مقدارِ delta را عوض می‌کند
    expect(rOn.delta).toBeCloseTo(234449540.05814552, 4);
    expect(rOff.delta).toBeCloseTo(233931228.34511858, 4);
    expect(rOn.delta).not.toBeCloseTo(rOff.delta, 6);
    expect(offR.t.delta_p).toBeCloseTo(4467042058.620941, 4);
  });

  // ── ۱۱) تبصرهٔ ۲: k_diff شاملِ بخشِ ۰٫۹۵ِ کار جدید است ──
  it("cwt k_diff includes new work", () => {
    const tNew = tadil(
      on({
        newItemMethod: "فهرست پایه",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
        completedWithinTerm: true,
      }),
    ).t;
    const tNo = tadil(on({ completedWithinTerm: true })).t;
    expect(tNew.k_diff).toBeCloseTo(179157910.65704632, 4);
    expect(tNo.k_diff).toBeCloseTo(168166575.3424654, 4);
    // کار جدید k_diff را بیشتر می‌کند (dpNew(k) > dpNew095)
    expect(tNew.k_diff).toBeGreaterThan(tNo.k_diff);
    // نامتغیرِ همیشگی
    expect(tNew.delta_p).toBeCloseTo(
      tNew.delta_p_definitive + tNew.delta_p_provisional,
      6,
    );
    // بدونِ تکمیل، k_diff صفر است
    const tNc = tadil(
      on({
        newItemMethod: "فهرست پایه",
        newItemAmount: 1_000_000_000,
        newItemBasePeriod: "1404Q2",
      }),
    ).t;
    expect(tNc.k_diff).toBeCloseTo(0, 6);
  });

  // ── ۱۲) copyProject فیلدها را نگه می‌دارد + ددآپِ هشدار ──
  it("copyProject keeps fields + warning dedup", () => {
    const s = on({
      newItemMethod: "ترکیب",
      newItemAmount: 600_000_000,
      newItemAmountAttached: 400_000_000,
      newItemBasePeriod: "1404Q2",
    });
    const cp = copyProject(s, { projectName: "کپی" } as ProjectMeta);
    expect(cp.settings.newItemMethod).toBe("ترکیب");
    expect(cp.settings.newItemAmount).toBeCloseTo(6e8, 6);
    expect(cp.settings.newItemAmountAttached).toBeCloseTo(4e8, 6);
    expect(cp.settings.newItemBasePeriod).toBe("1404Q2");

    // هشدارِ «دورهٔ مبنا ناموجود» بین دو موتور ددآپ می‌شود
    const w: Warning[] = [];
    const eng = on({ newItemMethod: "فهرست پایه", newItemAmount: 1_000_000_000 });
    tadilEngine(eng, ctx(), w);
    baravordEngine(eng, ctx(), w);
    const miss = warnItem(w, "new_item_base_period_missing");
    expect(miss).toHaveLength(1);
    expect(miss[0].level).toBe("خطا");
  });
});
