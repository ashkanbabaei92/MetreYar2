// T124 — فاز E-10 §۰ — دامنهٔ دستورالعمل ۱۴۰۳/۷۴۴۳۱۷ (۱۴۰۳/۱۲/۲۹).
//
// [SRC: بخشنامهٔ ۷۴۴۳۱۷/۱۴۰۳، صفحه ۱، بند ۲]:
//   «این بخشنامه صرفاً به رشته‌های مشخص شده در جدول زیر اعمال می‌شود.»
// موضوعِ دستورالعمل «رشته‌های بهره‌برداری، نگهداری و خدماتی» است و «ابنیه»
// و سایر رشته‌های ساختمانی در جدول نیستند. پس قاعدهٔ ماکزیمم
// [SRC: بخشنامهٔ ۶۶۶۳۱۲/۱۴۰۴، صفحه ۲، بند ۵] برای پروژهٔ ابنیه‌محور N/A است.
//
// همتایِ Python این آزمون: tests/char_python/test_T124_i744317_scope.py
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import type { AdjustmentCtx, ProjectSettings, Warning } from "../../src/lib/types";
import { defaultSettings } from "../../src/lib/engine";
import {
  projectDiscipline,
  runAdjustment,
  tadilEngine,
} from "../../src/lib/adjustment";

const ROOT = path.join(__dirname, "..", "..");
const REAL_CFG = JSON.parse(
  fs.readFileSync(path.join(ROOT, "config", "index_bulletins.json"), "utf-8"),
) as Record<string, any>;

const CH06: [number, number] = [7273.8, 10632.1]; // فصل ۶ قالب‌بندی — صفحهٔ ۶
const A_TEST = 10_000_000_000.0;
const OH = 1.3;
const REG = 1.04;
const PROP = 1.0;
const PRICE_MULT = OH * REG * PROP; // ۱٫۳۵۲
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"; // ⇒ Io = اسفند ۱۴۰۳ (مبنا)

function ctx(): AdjustmentCtx {
  return {
    chapter_amounts: { "06": A_TEST },
    haul_moved_amount: 0,
    floors_amount: A_TEST,
    base_total: A_TEST,
    site_setup: 0,
    advance_payment: 0,
    overhead_coef: OH,
    regional_coef: REG,
    grand_total: A_TEST * PRICE_MULT,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: A_TEST,
      excluded_total: 0.0,
    },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    tadilApproved: true,
    proposalDate: PROPOSAL_DATE,
    workPeriodStart: "۱۴۰۴/۱۰/۰۱",
    workPeriodEnd: "۱۴۰۴/۱۲/۳۰",
    ...extra,
  };
}

/** بارگذاریِ دوبارهٔ adjustment با config ای که ۷۴۴۳۱۷ آن جایگزین شده.
 * قاعدهٔ طلاییِ vitest: doMock باید قبل از importِ ماژولِ تازه اجرا شود. */
async function importWith744(patch: Record<string, any>) {
  vi.resetModules();
  vi.doMock("../../config/index_bulletins.json", () => ({
    default: {
      ...REAL_CFG,
      instructions_744317: {
        ...REAL_CFG["instructions_744317"],
        ...patch,
      },
    },
  }));
  return await import("../../src/lib/adjustment");
}

// ═════ §۰.۱ — رشتهٔ پروژه ═════

describe("T124 §۰.۱ — projectDiscipline", () => {
  it("پیش‌فرض «ابنیه» است", () => {
    expect(projectDiscipline(defaultSettings())).toBe("ابنیه");
  });
  it("تنظیمات regionalSelection خوانده می‌شود و رشتهٔ خالی ⇒ پیش‌فرض", () => {
    const s = defaultSettings();
    s.regionalSelection.discipline = "راهداری";
    expect(projectDiscipline(s)).toBe("راهداری");
    s.regionalSelection.discipline = "   ";
    expect(projectDiscipline(s)).toBe("ابنیه");
  });
});

// ═════ §۰.۲ — N/A برای ابنیه ═════

describe("T124 §۰.۲ — قاعدهٔ ماکزیمم برای ابنیه N/A است", () => {
  it("هشدارِ اطلاعِ N/A برای رشتهٔ ابنیه", async () => {
    const adj = await importWith744({});
    const w: Warning[] = [];
    adj.runAdjustment(on(), ctx(), w);
    const na = w.filter((x) => x.item === "instructions_744317_na");
    expect(na).toHaveLength(1);
    expect(na[0].level).toBe("اطلاع");
    expect(na[0].message).toContain("ابنیه");
    expect(na[0].message).toContain("N/A");
    expect(w.some((x) => x.item === "instructions_744317")).toBe(false);
  });

  it("حتی با جدولِ ۷۴۴۳۱۷ِ پر، شاخصِ فصل ۶ تغییر نمی‌کند", async () => {
    const adj = await importWith744({
      chapters_abnieh: [{ chapter: 6, q4: 99999.0, page: 1 }],
    });
    const w: Warning[] = [];
    const t = adj.tadilEngine(on(), ctx(), w);
    expect(t.chapters[0].it).toBeCloseTo(CH06[1], 12);
  });
});

// ═════ §۰.۳ — رشتهٔ مشمول ⇒ pending_d ═════

describe("T124 §۰.۳ — رشتهٔ مشمول: هشدارِ pending_d", () => {
  it("رشتهٔ مشمول ⇒ هشدارِ نیازمندیِ عددِ d، بدون اعمالِ ماکزیمم", async () => {
    const adj = await importWith744({
      disciplines: [{ name: "ابنیه", rows: [{ chapters: [6], m: 0.99 }] }],
      chapters_abnieh: [{ chapter: 6, q4: 99999.0, page: 1 }],
    });
    const w: Warning[] = [];
    adj.runAdjustment(on(), ctx(), w);
    const pd = w.filter((x) => x.item === "instructions_744317_pending_d");
    expect(pd).toHaveLength(1);
    expect(pd[0].level).toBe("اطلاع");
    expect(pd[0].message).toContain("ابنیه");
    expect(pd[0].message).toContain("d");
    expect(w.some((x) => x.item === "instructions_744317_na")).toBe(false);
    // و باز هم قاعدهٔ ماکزیمم اعمال نمی‌شود
    const t = adj.tadilEngine(on(), ctx(), []);
    expect(t.chapters[0].it).toBeCloseTo(CH06[1], 12);
  });
});

// ═════ §۰.۴ — یکسان بودنِ جدولِ config با PDF ═════

describe("T124 §۰.۴ — جدولِ ۷۴۴۳۱۷ در config با PDF یکی است", () => {
  const b = REAL_CFG["instructions_744317"];
  const expected: Record<string, Array<[any, number]>> = {
    "بهره‌برداری و نگهداری تأسیسات آب شرب": [
      [[1, 2, 3, 9], 0.35],
      [[4], 0.65],
      [[8], 0.70],
    ],
    "بهره‌برداری و نگهداشت تجهیزات برقی، کنترلی و ابزار دقیق تأسیسات آب و فاضلاب":
      [
        [[1], 0.7],
        [[2, 3], 0.45],
      ],
    "بهره‌برداری و نگهداری از شبکه جمع‌آوری و خطوط انتقال فاضلاب": [
      [[1, 2, 3, 4], 0.35],
    ],
    "نگهداری و تعمیرات شبکه انتقال و فوق توزیع نیروی برق": [
      ["همه فصل‌ها", 0.5],
    ],
    راهداری: [[[24], 0.45]],
    "نگهداری، تعمیر روسازی و ابنیه خطوط راه‌آهن": [
      [[1], 0.55],
      [[4], 0.7],
    ],
    پسماند: [
      [[1, 9], 0.65],
      [[6, 11], 0.35],
      [[10], 0.4],
    ],
    "فضای سبز": [
      [[2, 5, 7, 9, 10, 12, 17], 0.55],
      [[1, 13], 0.4],
    ],
  };

  it("scope_clause و max_rule با [SRC] بندها یکی است", () => {
    expect(b["scope_clause"]).toContain("صرفاً به رشته‌های مشخص شده");
    expect(b["max_rule"]).toContain("بزرگ‌تر است، ملاک عمل");
    expect(b["max_rule"]).toContain("۶۶۶۳۱۲");
  });

  it("۸ رشتهٔ مشمول؛ ابنیه در میانِ آن‌ها نیست", () => {
    const cov = new Set<string>(b["covered_disciplines"]);
    expect(cov.size).toBe(8);
    expect(new Set(b["disciplines"].map((d: any) => d.name))).toEqual(cov);
    expect(cov.has("ابنیه")).toBe(false);
  });

  it("ضرایبِ m و فصولِ هر رشته با جدولِ PDF یکی است", () => {
    const byName: Record<string, any> = {};
    for (const d of b["disciplines"]) byName[d.name] = d;
    for (const [name, rows] of Object.entries(expected)) {
      const got = byName[name].rows.map((r: any) => [r.chapters, r.m]);
      expect(got).toEqual(rows);
    }
  });
});
