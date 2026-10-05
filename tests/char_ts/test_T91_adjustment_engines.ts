// ─────────────────────────────────────────────────────────────
// T91 — موتورهای مستقل تعدیل فاز B (آینهٔ test_T91_adjustment_engines.py)
//
// دو موتور مجزا (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند):
//   ۱) تعدیل پیمان    : ΔP = k × Σ_c (It_c/Io_c − 1) × A_c
//   ۲) برآورد به‌هنگام : A_new = Σ_c A_c × It_c/Io_c
// هر آزمون باید خروجیِ bit-identical با موتور پایتون تولید کند.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { exportWorkbook } from "../../src/lib/exporters";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import {
  baravordEngine,
  chapterIndex,
  dateQuarter,
  jalaliLeap,
  provisionalCoef1405q1,
  quarterDiscipline,
  quarterIndex,
  quarterIsProvisional,
  roundTo,
  runAdjustment,
  splitRounded,
  tadilEngine,
  workSplit,
} from "../../src/lib/adjustment";
import type {
  AdjustmentCtx,
  ProjectSettings,
  ProjectResult,
  Warning,
} from "../../src/lib/types";
import indexBulletins from "../../config/index_bulletins.json";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

// شاخص‌های قطعی استخراج‌شده از پیوست ۳ (بخشنامهٔ ۱۴۰۵/۱۵۵۲۳۳)
const IO_BASE = 9744.7; // ردیف ۱ (شاخص رشته ابنیه) — صفحهٔ ۴
const IT_Q4 = 14333.1;
const CH06: [number, number] = [7273.8, 10632.1]; // فصل ۶ قالب‌بندی — صفحهٔ ۶
const CH08: [number, number] = [9787.4, 14154.7]; // فصل ۸ بتن درجا — صفحهٔ ۶
const CH28: [number, number] = [13243.1, 18897.9]; // فصل ۲۸ حمل‌ونقل — صفحهٔ ۷
const A_TEST = 10_000_000_000.0;
// ضرایب قیمت پیمان در ctx آزمون‌ها
const OH = 1.3;
const REG = 1.04;
const PROP = 1.0;
// ضریب موقت ۱۴۰۵Q1 محاسبه‌شده از CPI + m برای ابنیه (m=۰٫۷):
//   ۱ + ۰٫۷ × (۶۱۹٫۶ ÷ میانگین(۴۶۹٫۴، ۵۱۳٫۶، ۵۴۲٫۳) − ۱) = ۱٫۱۵۳۰۵۱۹…
const PROV_COEF = 1.1530518586507572;
const PRICE_MULT = OH * REG * PROP; // ۱٫۳۵۲

// تاریخ تسلیم پیشنهاد پیش‌فرض برای آزمون‌های موتور تعدیل (الزامی)
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹"; // ⇒ Io = اسفند ۱۴۰۳ (مبنا)

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

/** خط لولهٔ مرجع: ۱۰ جدول Revit + نگاشت Dynamo + فهرست‌بهای رسمی ۱۴۰۴. */
function pipeline(settings: ProjectSettings): ProjectResult {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .filter((f) => f.endsWith(".txt"))
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows: ReturnType<typeof parseDynamoMapping["rows"] extends infer T ? T : never> = [] as never;
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const sd = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(sd).isDirectory()) continue;
    for (const fn of fs.readdirSync(sd).sort()) {
      if (!fn.endsWith(".txt")) continue;
      (rows as unknown[]).push(...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows);
    }
  }
  return computeProject(tables, OFFICIAL_1404_FEHREST, settings, {
    rows,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
}

function ctx(opts?: {
  chapters?: Record<string, number>;
  base?: number;
  setup?: number;
  advance?: number;
}): AdjustmentCtx {
  const base = opts?.base ?? A_TEST;
  return {
    chapter_amounts: opts?.chapters ?? { "06": base },
    floors_amount: base,
    base_total: base,
    site_setup: opts?.setup ?? 0,
    advance_payment: opts?.advance ?? 0,
    overhead_coef: OH,
    regional_coef: REG,
    grand_total: base * PRICE_MULT,
    floors_info: {
      value: 1.0,
      status: "کامل",
      eligible_total: base,
      excluded_total: 0.0,
    },
  };
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return { ...defaultSettings(), tadilEnabled: true, proposalDate: PROPOSAL_DATE, ...extra };
}

function tadil(
  settings: ProjectSettings,
  c?: AdjustmentCtx,
  warns?: Warning[],
): { t: ReturnType<typeof tadilEngine>; w: Warning[] } {
  const w = warns ?? [];
  return { t: tadilEngine(settings, c ?? ctx(), w), w };
}

function baravord(
  settings: ProjectSettings,
  c?: AdjustmentCtx,
  warns?: Warning[],
): { b: ReturnType<typeof baravordEngine>; w: Warning[] } {
  const w = warns ?? [];
  return { b: baravordEngine(settings, c ?? ctx(), w), w };
}

// ═══ فعال‌نبودن پیش‌فرض و استقلال موتورها ═══

describe("T91 موتورهای فاز B — فعال‌نبودن پیش‌فرض و استقلال", () => {
  it("پیش‌فرض: هر دو موتور خروجی null", () => {
    const res = pipeline(defaultSettings());
    expect(res.adjustment).toEqual({ tadil: null, baravord: null });
  }, 120000);

  it("هر دو موتور می‌توانند همزمان فعال باشند", () => {
    const res = pipeline(on({ baravordEnabled: true }));
    const adj = res.adjustment;
    expect(adj.tadil).not.toBeNull();
    expect(adj.baravord).not.toBeNull();
    expect(adj.tadil!.mode).toBe("تعدیل پیمان");
    expect(adj.baravord!.mode).toBe("برآورد به‌هنگام");
    // فرمول‌ها و خروجی‌ها مستقل‌اند
    expect(adj.tadil!.formula).toContain("Σ_c");
    expect(adj.baravord!.formula).toContain("It_c/Io_c");
  }, 120000);

  it("موتورها روی زنجیرهٔ مالی اثری ندارند", () => {
    const base = pipeline(defaultSettings());
    const on1 = pipeline(on({ baravordEnabled: true }));
    for (const key of ["baseTotal", "floorsAmount", "grossPayable", "grandTotal", "netPayable"] as const) {
      expect(on1[key]).toBe(base[key]);
    }
  }, 120000);
});

// ═══ شاخص فصل به فصل (پیوست ۳) ═══

describe("T91 شاخص‌های فصل (پیوست ۳)", () => {
  it("کد فصل عددی و رشته‌ای یکسان کار می‌کنند", () => {
    const vInt = chapterIndex(6, "base");
    const vStr = chapterIndex("06", "base");
    expect(vInt[0]).toBe(CH06[0]);
    expect(vStr[0]).toBe(CH06[0]);
    const v28 = chapterIndex("28", "q4");
    expect(v28[0]).toBe(CH28[1]);
  });

  it("شاخص هر فصل در خروجی موتور استفاده می‌شود", () => {
    const res = pipeline(on());
    const rows = new Map(res.adjustment.tadil!.chapters.map((r) => [r.chapter, r]));
    if (rows.has("06")) {
      expect(rows.get("06")!.io).toBe(CH06[0]);
      expect(rows.get("06")!.it).toBe(CH06[1]);
    }
    if (rows.has("08")) {
      expect(rows.get("08")!.io).toBe(CH08[0]);
      expect(rows.get("08")!.it).toBe(CH08[1]);
    }
    if (rows.has("28")) {
      expect(rows.get("28")!.io).toBe(CH28[0]);
      expect(rows.get("28")!.it).toBe(CH28[1]);
    }
  }, 120000);

  it("ریاضیات تعدیل با محاسبهٔ مستقل برابر است", () => {
    // فاز E-6: فرمول خام، با گردکردن بند ۸-۲ خاموش
    const res = pipeline(on({ coefRounding2080: false }));
    const t = res.adjustment.tadil!;
    let expect_ = 0.0;
    for (const r of t.chapters) {
      expect_ += t.coef * ((r.ratio as number) - 1.0) * r.amount;
    }
    const sr = t.setup_row;
    if (sr) expect_ += t.coef * ((sr.ratio as number) - 1.0) * sr.amount;
    expect(t.delta_p).toBeCloseTo(expect_, 9);
    expect(t.result_amount).toBeCloseTo(t.base_amount + t.delta_p, 9);
  }, 120000);

  it("مبالغ ریالی دقیق هستند، نه گردشده", () => {
    const res = pipeline(on());
    const t = res.adjustment.tadil!;
    expect(Math.abs(t.result_amount - Math.round(t.result_amount / 1000) * 1000)).toBeGreaterThan(1.0);
    expect(t.delta_p).not.toBe(Math.round(t.delta_p / 1000) * 1000);
  }, 120000);

  it("شاخص دستی فصل مقدم بر جدول پیوست ۳ است", () => {
    const { t } = tadil(
      on({ chapterIndexManual: { "06": { io: 7000.0, it: 14000.0, src: "پیوست ۳" } } }),
    );
    const r = t.chapters.find((x) => x.chapter === "06")!;
    expect(r.io).toBe(7000.0);
    expect(r.it).toBe(14000.0);
    expect(r.ratio).toBeCloseTo(2.0, 9);
    expect(r.src).toBe("دستی (پیوست ۳)");
  });

  it("فصل بدون شاخص به شاخص رشته‌ای برمی‌گردد (بند ۴)", () => {
    const { t } = tadil(on(), ctx({ chapters: { "15": 1_000_000.0 } }));
    const r = t.chapters.find((x) => x.chapter === "15")!;
    expect(r.io).toBe(IO_BASE); // شاخص رشته (بند ۴)
    expect(r.src).toContain("بدون شاخص فصل");
    expect(t.incomplete).toBe(false);
    expect(t.pending.some((p) => p.item.includes("شاخص فصل"))).toBe(true);
  });

  it("تجهیز از شاخص رشته‌ای استفاده می‌کند (بند ۴)", () => {
    // فاز E-6: فرمول خام با گردکردن بند ۸-۲ خاموش
    const { t } = tadil(on({ coefRounding2080: false }), ctx({ chapters: { "06": 5e9 }, setup: 1e9 }));
    const sr = t.setup_row!;
    expect(sr).not.toBeNull();
    expect(sr.io).toBe(IO_BASE);
    expect(sr.delta).toBeCloseTo(0.95 * (sr.it / IO_BASE - 1.0) * 1e9, 6);
  });
});

// ═══ A = مبلغ کارکرد به قیمت پیمان (A_basis) ═══

describe("T91 مبنای مبلغ A", () => {
  it("A_basis = «با ضرایب» ⇒ A = A۰ × بالاسری × منطقه‌ای × پیشنهادی", () => {
    const { t } = tadil(on());
    const labels = t.chain.map((x) => x[0]);
    expect(labels).toContain("× ضریب بالاسری");
    expect(labels).toContain("× ضریب منطقه‌ای");
    expect(labels).toContain("× ضریب پیشنهادی پیمانکار");
    expect(t.work_base).toBeCloseTo(A_TEST * PRICE_MULT, 6);
    // ضرایب روی مبالغ فصل‌ها هم اعمال شده‌اند تا Σ A_c = A
    expect(t.chapters.reduce((a, r) => a + r.amount, 0)).toBeCloseTo(t.work_base, 9);
  });

  it("A_basis = «بدون ضرایب» ⇒ A = A۰ (فهرست‌بها)", () => {
    const { t } = tadil(on({ aBasis: "بدون ضرایب" }));
    const labels = t.chain.map((x) => x[0]);
    expect(labels).not.toContain("× ضریب بالاسری");
    expect(t.work_base).toBeCloseTo(A_TEST, 6);
    expect(t.chapters.reduce((a, r) => a + r.amount, 0)).toBeCloseTo(t.work_base, 9);
  });

  it("ضریب پیشنهادی پیمانکار اعمال و در رجیستری ثبت می‌شود", () => {
    const { t } = tadil(on({ proposalCoef: 1.1 }));
    expect(t.work_base).toBeCloseTo(A_TEST * PRICE_MULT * 1.1, 6);
    expect(t.pending.some((p) => p.item.includes("ضریب پیشنهادی پیمانکار") && p.value === 1.1)).toBe(true);
  });
});

// ═══ Io از تاریخ تسلیم پیشنهاد (الزامی در موتور تعدیل) ═══

describe("T91 Io از تاریخ تسلیم پیشنهاد", () => {
  it("تاریخ تسلیم، سه‌ماههٔ Io را تعیین می‌کند", () => {
    expect(tadil(on({ proposalDate: "۱۴۰۴/۰۵/۱۰" })).t.io_q).toBe("1404Q2");
  });

  it("اسفند ۱۴۰۳ همان دورهٔ مبنا است", () => {
    expect(tadil(on({ proposalDate: "۱۴۰۳/۱۲/۲۹" })).t.io_q).toBe("1403Q4");
  });

  it("تاریخ تسلیم خالی ⇒ موتور متوقف می‌شود", () => {
    const res = pipeline(on({ proposalDate: "" }));
    const t = res.adjustment.tadil!;
    expect(t.error).toBeTruthy();
    expect(t.incomplete).toBe(true);
    expect(t.chapters).toEqual([]);
    expect(t.delta_p).toBe(0.0);
    expect(res.warnings.some((w) => w.level === "خطا" && w.item === "proposal_date")).toBe(true);
  }, 120000);

  it("تاریخ تسلیم نامعتبر ⇒ موتور متوقف می‌شود", () => {
    const { t, w } = tadil(on({ proposalDate: "نامعتبر" }));
    expect(t.error).toBeTruthy();
    expect(t.incomplete).toBe(true);
    expect(t.chapters).toEqual([]);
    expect(w.some((x) => x.level === "خطا" && x.item === "proposal_date")).toBe(true);
  });

  it("موتور برآورد به تاریخ تسلیم نیاز ندارد", () => {
    const { b, w } = baravord(on({ baravordEnabled: true, proposalDate: "" }));
    expect(b.io_q).toBe("1403Q4");
    expect(w.some((x) => x.item === "proposal_date")).toBe(false);
  });
});

// ═══ تقسیم کارکرد بین سه‌ماهه‌ها ═══

describe("T91 تقسیم کارکرد", () => {
  it("یک سه‌ماههٔ کامل", () => {
    expect(workSplit("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۰۳/۳۱")).toEqual([["1404Q1", 1.0]]);
  });

  it("چند سه‌ماهه‌ای که جمعش یک می‌شود", () => {
    const sp = workSplit("۱۴۰۴/۰۱/۰۱", "۱۴۰۵/۰۲/۱۵");
    expect(sp.length).toBeGreaterThanOrEqual(5);
    expect(sp.reduce((a, x) => a + x[1], 0)).toBeCloseTo(1.0, 9);
    expect(sp[0][0]).toBe("1404Q1");
    expect(sp[sp.length - 1][0]).toBe("1405Q1");
  });

  it("استثنی کردن دورهٔ تأخیر", () => {
    const sp = workSplit("۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۰۶/۳۰", "۱۴۰۴/۰۴/۰۱");
    const qs = sp.map((x) => x[0]);
    expect(qs).not.toContain("1404Q1");
    expect(qs).toContain("1404Q2");
  });

  it("تقسیم از دورهٔ انجام کار استفاده می‌کند", () => {
    const res = pipeline(
      on({ workPeriodStart: "۱۴۰۴/۰۱/۰۱", workPeriodEnd: "۱۴۰۴/۰۶/۳۰" }),
    );
    expect(res.adjustment.tadil!.split.map((x) => x[0])).toEqual(["1404Q1", "1404Q2"]);
  }, 120000);
});

// ═══ جدول فصل × سه‌ماهه ═══

describe("T91 جدول فصل × سه‌ماهه", () => {
  it("هر فصل یک ردیف برای هر سه‌ماههٔ کارکرد دارد", () => {
    const { t } = tadil(
      on({
        provisionalCoef1405q1: PROV_COEF,
        workPeriodStart: "۱۴۰۴/۰۱/۰۱",
        workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
      }),
    );
    expect(t.split.length).toBe(5);
    for (const r of t.chapters) {
      const qs = r.quarters ?? [];
      expect(qs.length).toBe(5);
      expect(qs.map((x) => x[0])).toEqual(t.split.map((x) => x[0]));
      // آخرین سه‌ماهه (۱۴۰۵Q1) موقت است
      expect(qs[qs.length - 1][0]).toBe("1405Q1");
      expect(qs[qs.length - 1][2]).toBe("موقت");
      // بقیه قطعی
      expect(qs.slice(0, -1).every((x) => x[2] === "قطعی")).toBe(true);
    }
  });

  it("در یک سه‌ماهه فقط یک ردیف در جدول هست", () => {
    const { t } = tadil(on());
    for (const r of t.chapters) {
      const qs = r.quarters ?? [];
      expect(qs.length).toBe(1);
      expect(qs[0][0]).toBe(t.split[0][0]);
    }
  });
});

// ═══ شاخص موقت ۱۴۰۵Q1 = ضریب × آخرین قطعی ═══

describe("T91 شاخص موقت ۱۴۰۵Q1", () => {
  it("شاخص موقت روی سه‌ماههٔ اول ۱۴۰۵ اعمال می‌شود", () => {
    const { t } = tadil(
      on({
        provisionalCoef1405q1: PROV_COEF,
        workPeriodStart: "۱۴۰۵/۰۱/۰۱",
        workPeriodEnd: "۱۴۰۵/۰۳/۳۱",
      }),
    );
    const r = t.chapters[0];
    expect(t.split[0][0]).toBe("1405Q1");
    expect(r.it).toBeCloseTo(CH06[1] * PROV_COEF, 6);
    expect(r.status).toBe("موقت");
    expect(t.delta_p).toBeGreaterThan(t.delta_p_definitive);
  });

  it("در رجیستری «مقادیر منتظر تأیید» ثبت می‌شود", () => {
    const { t } = tadil(on({ provisionalCoef1405q1: PROV_COEF }));
    expect(t.pending.some((p) => p.item.includes("موقت") && p.value === PROV_COEF)).toBe(true);
  });
});

// ═══ فاز E: ضریب موقت ۱۴۰۵Q1 از CPI + m (محاسبهٔ خودکار) ═══

describe("T91 فاز E — ضریب موقت از CPI + m", () => {
  it("ضریب از CPI و m محاسبه می‌شود (ابنیه m=۰٫۷)", () => {
    const [coef, st, tr] = provisionalCoef1405q1("ابنیه");
    expect(st).toBe("محاسبه‌شده");
    expect(tr.m as number).toBeCloseTo(0.7, 9);
    expect(tr.numerator as number).toBeCloseTo(619.6, 9);
    expect(tr.denominator_mean as number).toBeCloseTo(508.43333333333334, 9);
    expect(coef).toBeCloseTo(1.1530518586507572, 12);
  });

  it("m=۱٫۱ برای چهار رشتهٔ انتقال/توزیع برق", () => {
    const [coef] = provisionalCoef1405q1("توزیع نیروی برق");
    expect(coef).toBeCloseTo(1.2405100635940471, 12);
  });

  it("m=۱٫۰ برای جدول دوم پیوست", () => {
    const [coef] = provisionalCoef1405q1("فضای سبز");
    expect(coef).toBeCloseTo(1.2186455123582247, 12);
  });

  it("رشتهٔ ناشناخته ⇒ null (حدس زده نمی‌شود)", () => {
    const [coef, st] = provisionalCoef1405q1("رشتهٔ ناشناخته");
    expect(coef).toBeNull();
    expect(st).toBe("ناموجود");
  });

  it("بدون ورودی دستی، ۱۴۰۵Q1 با ضریب محاسبه‌شده اجرا می‌شود", () => {
    const { t } = tadil(
      on({ workPeriodStart: "۱۴۰۴/۰۱/۰۱", workPeriodEnd: "۱۴۰۵/۰۲/۱۵" }),
    );
    expect(t.error).toBeUndefined();
    expect(t.chapters.length).toBeGreaterThan(0);
    expect(t.delta_p).toBeGreaterThan(0);
    const r = t.chapters[0];
    const qs = r.quarters ?? [];
    expect(qs[qs.length - 1][0]).toBe("1405Q1");
    expect(qs[qs.length - 1][2]).toBe("موقت");
    expect(qs[qs.length - 1][1]).toBeCloseTo(CH06[1] * PROV_COEF, 6);
  });

  it("برآورد به‌هنگام: It موقت ۱۴۰۵Q1 بدون ورودی دستی", () => {
    const { b } = baravord(
      on({ baravordEnabled: true, baravordItPeriod: "1405Q1" }),
      ctx({ chapters: { "06": 6e9 } }),
    );
    expect(b.it_q).toBe("1405Q1");
    expect(b.error).toBeUndefined();
    const r = b.chapters[0];
    expect(r.status).toBe("موقت");
    expect(r.it).toBeCloseTo(CH06[1] * PROV_COEF, 6);
  });
});

// ═══ فاز E (بندهای ۲ و ۳): تعمیم ضریب موقت به همهٔ سه‌ماهه‌های ۱۴۰۵+ ═══

describe("T91 فاز E — بندهای ۲ و ۳: سه‌ماهه‌های بعدتر", () => {
  it("quarterIsProvisional: ۱۴۰۵+ موقت، ۱۴۰۴ و نامعتبر غیرموقت", () => {
    expect(quarterIsProvisional("1404Q4")).toBe(false);
    expect(quarterIsProvisional("1405Q1")).toBe(true);
    expect(quarterIsProvisional("1405Q2")).toBe(true);
    expect(quarterIsProvisional("1405Q4")).toBe(true);
    expect(quarterIsProvisional("1406Q2")).toBe(true);
    expect(quarterIsProvisional(null)).toBe(false);
    expect(quarterIsProvisional("x")).toBe(false);
  });

  it("quarterIndex/quarterDiscipline برای ۱۴۰۵Q2..Q4 = ضریب × قطعی ۱۴۰۴Q4", () => {
    for (const q of ["1405Q2", "1405Q3", "1405Q4", "1406Q1"]) {
      const [v, st] = quarterIndex("06", q, PROV_COEF);
      expect(v).not.toBeNull();
      expect(st).toBe("موقت");
      expect(v as number).toBeCloseTo(CH06[1] * PROV_COEF, 9);
      const [vd, std] = quarterDiscipline(q, PROV_COEF);
      expect(vd).not.toBeNull();
      expect(std).toBe("موقت");
      expect(vd as number).toBeCloseTo(IT_Q4 * PROV_COEF, 9);
    }
    const [v2, st2] = quarterIndex("06", "1405Q2", null);
    expect(v2).toBeNull();
    expect(st2).toBe("ناموجود");
  });

  it("تعدیل: کارکرد تا مرداد ۱۴۰۵ ⇒ ۱۴۰۵Q1 و ۱۴۰۵Q2 موقت (بند ۳)", () => {
    const { t } = tadil(
      on({ workPeriodStart: "۱۴۰۴/۰۱/۰۱", workPeriodEnd: "۱۴۰۵/۰۵/۱۵" }),
    );
    expect(t.error).toBeUndefined();
    const qs = (t.split ?? []).map(([q]) => q);
    expect(qs).toContain("1405Q1");
    expect(qs).toContain("1405Q2");
    for (const r of t.chapters) {
      for (const [q, _iv, st] of r.quarters ?? []) {
        if (q.startsWith("1405")) expect(st).toBe("موقت");
      }
      const prov = Object.fromEntries(
        (r.quarters ?? [])
          .filter(([q]) => q.startsWith("1405"))
          .map(([q, iv]) => [q, iv]),
      );
      expect(prov["1405Q1"]).toBeCloseTo(prov["1405Q2"], 9);
    }
    expect(t.delta_p_provisional).toBeGreaterThan(0);
  });

  it("برآورد به‌هنگام: It موقت ۱۴۰۵Q2 بدون ورودی دستی", () => {
    const { b } = baravord(
      on({ baravordEnabled: true, baravordItPeriod: "1405Q2" }),
      ctx({ chapters: { "06": 6e9 } }),
    );
    expect(b.it_q).toBe("1405Q2");
    expect(b.error).toBeUndefined();
    const r = b.chapters[0];
    expect(r.status).toBe("موقت");
    expect(r.it).toBeCloseTo(CH06[1] * PROV_COEF, 6);
  });
});

// ═══ فاز E (E3 — بخشنامهٔ ۱۴۴۳۷۴): Io ماهانهٔ خرداد ۱۴۰۵ ═══
// اگر مهلت تسلیم پیشنهاد در تابستان ۱۴۰۵ باشد، Io شاخص ماهانهٔ خرداد
// ۱۴۰۵ (آحادبها) است، نه سه‌ماهه‌ای. تا این شاخص وارد نشده باشد، موتورها
// با خطا متوقف می‌شوند. ۱۴۴۳۷۴ ضریب تبدیل مبنا ندارد.

describe("T91 فاز E — E3: Io ماهانهٔ خرداد ۱۴۰۵ (۱۴۴۳۷۴)", () => {
  it("مهلت تسلیم مقدم بر تاریخ تسلیم است", () => {
    const { t } = tadil(
      on({ proposalDate: "۱۴۰۴/۰۵/۱۰", proposalDeadline: "۱۴۰۴/۰۸/۲۰" }),
    );
    expect(t.io_q).toBe("1404Q3");
    expect(t.io_month).toBeNull();
  });

  it("مهلت تسلیم در تابستان ۱۴۰۵ ⇒ توقف موتور تا وارد شدن شاخص ماهانه", () => {
    const { t, w } = tadil(
      on({ proposalDate: "۱۴۰۵/۰۲/۱۵", proposalDeadline: "۱۴۰۵/۰۵/۱۰" }),
    );
    expect(t.error).toBeDefined();
    expect(t.chapters).toEqual([]);
    expect(t.io_month).toBe("khordad_1405");
    expect(
      w.some((x) => x.level === "خطا" && x.item === "monthly_index_1405"),
    ).toBe(true);
  });

  it("برآورد به‌هنگام: توقف در نبود شاخص ماهانه", () => {
    const { b, w } = baravord(
      on({
        baravordEnabled: true,
        proposalDate: "۱۴۰۵/۰۲/۱۵",
        proposalDeadline: "۱۴۰۵/۰۶/۰۵",
      }),
    );
    expect(b.error).toBeDefined();
    expect(b.chapters).toEqual([]);
    expect(b.io_month).toBe("khordad_1405");
    expect(
      w.some((x) => x.level === "خطا" && x.item === "monthly_index_1405"),
    ).toBe(true);
  });

  it("با شاخص ماهانهٔ واردشده، Io فصل از جدول ماهانه خوانده می‌شود", () => {
    const m = (indexBulletins as any).monthly;
    const ch0 = m.chapters_abnieh;
    const di0 = m.disciplines;
    m.chapters_abnieh = [{ chapter: 6, khordad_1405: 12000.0, page: 1 }];
    m.disciplines = [{ name: "ابنیه", khordad_1405: 15000.0, page: 1 }];
    try {
      const { t } = tadil(
        on({
          proposalDate: "۱۴۰۵/۰۲/۱۵",
          proposalDeadline: "۱۴۰۵/۰۵/۱۰",
          workPeriodStart: "۱۴۰۵/۰۴/۰۱",
          workPeriodEnd: "۱۴۰۵/۰۶/۳۰",
          provisionalCoef1405q1: PROV_COEF,
        }),
      );
      expect(t.error).toBeUndefined();
      expect(t.io_month).toBe("khordad_1405");
      const r = t.chapters[0];
      expect(r.io).toBeCloseTo(12000.0, 6);
      const it = (r.quarters ?? []).find(([q]) => q === "1405Q2");
      expect(it?.[1]).toBeCloseTo(CH06[1] * PROV_COEF, 6);
    } finally {
      m.chapters_abnieh = ch0;
      m.disciplines = di0;
    }
  });

  it("ضریب تبدیل مبنا نادیده گرفته می‌شود (۱۴۴۳۷۴ ندارد)", () => {
    const { t } = tadil(on({ baseConversionCoef: 1.05 } as any));
    expect(t.work_base).toBeCloseTo(A_TEST * PRICE_MULT, 6);
    expect(t.chain.some((x) => x[0].includes("ضریب تبدیل مبنا"))).toBe(false);
  });
});

// ═══ فاز E — بندهای ۴ و ۵: هشدارهای شیت هشدارها ═══

describe("T91 فاز E — بندهای ۴ و ۵: هشدارها", () => {
  it("بند ۴: کارکرد موقت در موتور تعدیل ⇒ هشدار اطلاع", () => {
    const w: Warning[] = [];
    const out = runAdjustment(
      on({
        proposalDate: "۱۴۰۴/۰۱/۰۱",
        workPeriodStart: "۱۴۰۵/۰۱/۰۱",
        workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
        provisionalCoef1405q1: PROV_COEF,
      }),
      ctx(),
      w,
    );
    expect(out.tadil?.chapters.length).toBeGreaterThan(0);
    expect(
      w.some((x) => x.item === "definitive_1405" && x.level === "اطلاع"),
    ).toBe(true);
  });

  it("بند ۴: کارکرد کاملاً قطعی ⇒ بدون هشدار", () => {
    const w: Warning[] = [];
    runAdjustment(on({ proposalDate: "۱۴۰۴/۰۱/۰۱" }), ctx(), w);
    expect(w.some((x) => x.item === "definitive_1405")).toBe(false);
  });

  it("بند ۴: موتور برآورد با It موقت ⇒ هشدار اطلاع", () => {
    const w: Warning[] = [];
    const out = runAdjustment(
      on({
        baravordEnabled: true,
        baravordItPeriod: "1405Q1",
        provisionalCoef1405q1: PROV_COEF,
      }),
      ctx({ chapters: { "06": 6e9 } }),
      w,
    );
    expect(
      out.baravord?.chapters.some((r) => r.status === "موقت"),
    ).toBe(true);
    expect(
      w.some((x) => x.item === "definitive_1405" && x.level === "اطلاع"),
    ).toBe(true);
  });

  it("بند ۵: موتور روشن ⇒ هشدار اطلاع", () => {
    const w: Warning[] = [];
    runAdjustment(on({}), ctx(), w);
    expect(
      w.some((x) => x.item === "instructions_744317" && x.level === "اطلاع"),
    ).toBe(true);
  });
});

// ═══ کسورات ═══

describe("T91 کسورات و پیش‌پرداخت", () => {
  it("کسر پیش‌پرداخت از مبلغ پایه", () => {
    const { t } = tadil(
      on({ tadilAdvanceMode: "کسر پیش‌پرداخت" }),
      ctx({ advance: 2e9 }),
    );
    // کسر پیش‌پرداخت پس از اعمال ضرایب قیمت پیمان
    expect(t.work_base).toBeCloseTo(A_TEST * PRICE_MULT - 2e9, 6);
    expect(t.chain.some((x) => x[0].includes("پیش‌پرداخت"))).toBe(true);
  });

  it("کسر پیش‌پرداخت در موتور برآورد اعمال نمی‌شود", () => {
    const { b } = baravord(
      on({ tadilAdvanceMode: "کسر پیش‌پرداخت" }),
      ctx({ advance: 2e9 }),
    );
    expect(b.work_base).toBeCloseTo(A_TEST * PRICE_MULT, 6);
  });
});

// ═══ تعدیل منفی ═══

describe("T91 تعدیل منفی", () => {
  it("تعدیل منفی در حالت غیرمجاز صفر می‌شود", () => {
    // Io = شاخص q4 (بالا) و It = base (پایین) ⇒ تعدیل منفی
    const { t, w } = tadil(
      on({
        proposalDate: "۱۴۰۴/۱۲/۲۹",
        tadilItPeriod: "base",
        tadilAllowNegative: false,
      }),
    );
    expect(t.delta_p).toBe(0.0);
    expect(w.some((x) => x.level === "هشدار")).toBe(true);
  });

  it("تعدیل منفی در حالت مجاز اعمال می‌شود", () => {
    const { t } = tadil(
      on({
        proposalDate: "۱۴۰۴/۱۲/۲۹",
        tadilItPeriod: "base",
        tadilAllowNegative: true,
      }),
    );
    expect(t.delta_p).toBeLessThan(0);
  });
});

// ═══ موتور ۲: برآورد به‌هنگام ═══

describe("T91 موتور برآورد به‌هنگام", () => {
  it("ریاضیات برآورد (بدون k)", () => {
    const { b } = baravord(
      on({ baravordEnabled: true }),
      ctx({ chapters: { "06": 6e9, "28": 4e9 } }),
    );
    let expect_ = 0.0;
    for (const r of b.chapters) expect_ += r.amount * (r.ratio as number);
    expect(b.result_amount).toBeCloseTo(expect_, 9);
  });

  it("خروجی گرد نمی‌شود", () => {
    const { b } = baravord(on({ baravordEnabled: true }));
    expect(Math.abs(b.result_amount - Math.round(b.result_amount))).toBeGreaterThan(0);
  });

  it("grand به‌هنگام‌شده با ضرایب (A_basis = با ضرایب)", () => {
    const { b } = baravord(
      on({ baravordEnabled: true }),
      ctx({ chapters: { "06": 6e9, "28": 4e9 } }),
    );
    // A_basis = با ضرایب ⇒ ضرایب داخل A_c هستند ⇒ grand_updated = result
    expect(b.grand_updated).toBeCloseTo(b.result_amount, 9);
    expect(b.grand_current).toBeCloseTo(A_TEST * PRICE_MULT, 9);
    expect(b.applied_mult).toBeCloseTo(PRICE_MULT, 9);
  });

  it("grand به‌هنگام‌شده بدون ضرایب (ضرایب پس از It/Io)", () => {
    const { b } = baravord(
      on({ baravordEnabled: true, aBasis: "بدون ضرایب" }),
      ctx({ chapters: { "06": 6e9, "28": 4e9 } }),
    );
    // ضرایب پس از It/Io اعمال می‌شوند تا grand به قیمت پیمان به‌دست آید
    expect(b.applied_mult).toBe(1.0);
    expect(b.grand_updated).toBeCloseTo(b.result_amount * PRICE_MULT, 9);
  });

  it("grand به‌هنگام‌شده با خط لولهٔ مرجع", () => {
    const res = pipeline(on({ baravordEnabled: true }));
    const b = res.adjustment.baravord!;
    expect(b.grand_current).toBeCloseTo(res.grandTotal, 9);
    // روی پروژهٔ مرجع، grand به‌هنگام‌شده باید از grand فعلی بیشتر باشد
    expect(b.grand_updated).toBeGreaterThan(res.grandTotal);
  }, 120000);
});

// ═══ fallback شاخص رشته‌ای در رجیستری هر دو موتور ═══

describe("T91 رجیستری مقادیر منتظر تأیید", () => {
  it("fallback فصل ۱۵ در رجیستری هر دو موتور", () => {
    const c = ctx({ chapters: { "15": 1_000_000.0, "06": 5e9 } });
    const { t } = tadil(on(), c);
    const { b } = baravord(on({ baravordEnabled: true }), c);
    expect(t.pending.some((p) => p.item === "شاخص فصل 15 — Io")).toBe(true);
    expect(b.pending.some((p) => p.item === "شاخص فصل 15 — Io")).toBe(true);
  });

  it("خروجی تا تأیید، «پیش‌نویس» است", () => {
    expect(tadil(on()).t.draft).toBe(true);
    expect(tadil(on({ tadilApproved: true })).t.draft).toBe(false);
  });

  it("k = ۰٫۹۵ با منبع بخشنامه ۲۰۸۰ در رجیستری است", () => {
    const { t } = tadil(on());
    const kRow = t.pending.filter((p) => p.item.includes("ضریب قانونی"));
    expect(kRow.length).toBeGreaterThan(0);
    expect(kRow[0].value).toBe(0.95);
    expect(kRow[0].source).toContain("۲۰۸۰");
    expect(kRow[0].page).toContain("بند ۱-۸");
  });

  it("k از completedWithinTerm مشتق می‌شود، نه ورودی کاربر (فاز E-6)", () => {
    const tNone = tadil(on()).t;
    expect(tNone.coef).toBe(0.95);
    expect(tNone.completed_within_term).toBe(false);
    const tTrue = tadil(on({ completedWithinTerm: true })).t;
    expect(tTrue.coef).toBe(1.0);
    expect(tTrue.completed_within_term).toBe(true);
    const tFalse = tadil(on({ completedWithinTerm: false })).t;
    expect(tFalse.coef).toBe(0.95);
    // tadilCoef قدیمی دیگر در موتور اثری ندارد
    const { t, w } = tadil(on({ tadilCoef: 5.0 }));
    expect(t.coef).toBe(0.95);
    expect(w.some((x) => x.item === "tadil_coef")).toBe(false);
  });
});

// ═══ کمکّی‌های تاریخ شمسی ═══

describe("T91 کمکّی‌های تاریخ شمسی", () => {
  it("سه‌ماههٔ یک تاریخ", () => {
    expect(dateQuarter("۱۴۰۴/۰۱/۰۵")).toBe("1404Q1");
    expect(dateQuarter("۱۴۰۴/۱۲/۲۹")).toBe("1404Q4");
    expect(dateQuarter("۱۴۰۳/۱۰/۰۱")).toBe("1403Q4");
    expect(dateQuarter("بد")).toBeNull();
  });

  it("سال کبیسهٔ شمسی", () => {
    expect(jalaliLeap(1404)).toBe(true);
    expect(jalaliLeap(1403)).toBe(false);
  });
});

// ═══§۱۴-۶ برابری اعداد مرجع پذیرش ═══

describe("T91 §۱۴-۶ برابری با اعداد مرجع پذیرش", () => {
  // سناریوی کامل: دو موتور + دورهٔ کارکرد ۱۴۰۴/۰۱/۰۱ تا ۱۴۰۵/۰۲/۱۵
  // + شاخص موقت ۱۴۰۵Q1 (CPI + m، ابنیه = ۱٫۱۵۳۰۵۱۹) + تاریخ تسلیم اسفند ۱۴۰۳.
  // فاز E-6: مقدارهای مرجع پیش از E-6 (گردکردن بند ۸-۲ خاموش) — میراث
  const ref = () =>
    pipeline(
      on({
        coefRounding2080: false,
        baravordEnabled: true,
        workPeriodStart: "۱۴۰۴/۰۱/۰۱",
        workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
        provisionalCoef1405q1: PROV_COEF,
      }),
    );

  it("زنجیرهٔ مالی اصلی (بدون موتورها) تغییر نمی‌کند", () => {
    const res = ref();
    expect(res.baseTotal).toBeCloseTo(23_218_381_337.01, 2);
    expect(res.grandTotal).toBeCloseTo(31_391_251_567.64, 2);
  }, 120000);

  it("ΔP = ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴ = قطعی ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰ + علی‌الحساب ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴", () => {
    const t = ref().adjustment.tadil!;
    expect(t.delta_p).toBeCloseTo(9_937_407_877.64, 2);
    expect(t.delta_p_definitive).toBeCloseTo(7_709_893_479.4, 1);
    expect(t.delta_p_provisional).toBeCloseTo(2_227_514_398.23, 1);
    expect(t.delta_p - t.delta_p_definitive).toBe(t.delta_p_provisional);
  }, 120000);

  it("A + ΔP = ۴۱٬۳۲۸٬۶۵۹٬۴۴۵٫۲۸", () => {
    const t = ref().adjustment.tadil!;
    expect(t.base_amount).toBeCloseTo(31_391_251_567.64, 2);
    expect(t.result_amount).toBeCloseTo(41_328_659_445.28, 2);
  }, 120000);

  it("برآورد به‌هنگام (It = ۱۴۰۴Q4) = ۴۵٬۴۳۷٬۷۴۲٬۸۲۰٫۳۲", () => {
    const b = ref().adjustment.baravord!;
    expect(b.it_q).toBe("1404Q4");
    expect(b.result_amount).toBeCloseTo(45_437_742_820.32, 2);
    expect(b.grand_updated).toBeCloseTo(45_437_742_820.32, 2);
  }, 120000);

  it("برآورد به‌هنگام (It = ۱۴۰۵Q1 موقت) = ۵۲٬۳۹۲٬۰۷۳٬۸۱۱٫۸۷", () => {
    const res = pipeline(
      on({
        baravordEnabled: true,
        baravordItPeriod: "1405Q1",
        provisionalCoef1405q1: PROV_COEF,
      }),
    );
    const b = res.adjustment.baravord!;
    expect(b.it_q).toBe("1405Q1");
    expect(b.result_amount).toBeCloseTo(52_392_073_811.87, 2);
  }, 120000);

  it("تقسیم کارکرد: ۲۲٫۵۷ / ۲۲٫۵۷ / ۲۱٫۸۴ / ۲۱٫۸۴ / ۱۱٫۱۷ درصد", () => {
    const t = ref().adjustment.tadil!;
    expect(t.split.map((x) => x[0])).toEqual([
      "1404Q1",
      "1404Q2",
      "1404Q3",
      "1404Q4",
      "1405Q1",
    ]);
    // جمع کسرها = ۱
    expect(t.split.reduce((a, x) => a + x[1], 0)).toBeCloseTo(1.0, 9);
    for (const f of t.split.map((x) => x[1])) expect(f).toBeGreaterThan(0.1);
    expect(t.split[0][1]).toBeCloseTo(0.2257, 3);
    expect(t.split[4][1]).toBeCloseTo(0.1117, 3);
  }, 120000);

  it("k = ۰٫۹۵ و خروجی پیش‌نویس است", () => {
    const t = ref().adjustment.tadil!;
    expect(t.coef).toBe(0.95);
    expect(t.draft).toBe(true);
  }, 120000);

  it("runAdjustment هرگز زنجیرهٔ مالی را تغییر نمی‌دهد", () => {
    const off = pipeline(defaultSettings());
    const on1 = ref();
    expect(on1.baseTotal).toBe(off.baseTotal);
    expect(on1.grandTotal).toBe(off.grandTotal);
    expect(on1.netPayable).toBe(off.netPayable);
  }, 120000);

  it("بخش قطعی + بخش علی‌الحساب ≡ ΔP (باقی‌ماندهٔ گردسازی به بخش آخر)", () => {
    const t = ref().adjustment.tadil!;
    // مقادیر دقیق موتور
    expect(t.delta_p_definitive + t.delta_p_provisional).toBe(t.delta_p);
    // تفکیک گردشده: جمع دو بخش برابر ΔP گردشده
    const [dp, df, dprov] = splitRounded(t.delta_p, t.delta_p_definitive, 2);
    expect(dp).toBeCloseTo(9_937_407_877.64, 2);
    expect(df).toBeCloseTo(7_709_893_479.4, 2);
    expect(df + dprov).toBe(dp);
    // عدد مرجع ACCEPTANCE §۱۴-۶: ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴ (باقی‌مانده به علی‌الحساب)
    expect(dprov).toBeCloseTo(2_227_514_398.24, 2);
  }, 120000);
});

// ═══ تفکیک گردشدهٔ ΔP ═══

describe("T91 تفکیک گردشده (splitRounded)", () => {
  it("باقی‌ماندهٔ گردسازی به بخش دوم می‌رسد", () => {
    // اعداد دقیق سناریوی مرجع §۱۴-۶
    const [r, a, b] = splitRounded(9_937_407_877.639_488_220, 7_709_893_479.404_506, 2);
    expect(r).toBeCloseTo(9_937_407_877.64, 2);
    expect(a).toBeCloseTo(7_709_893_479.4, 2);
    // نامساویِ کلیدی: قطعی + علی‌الحساب ≡ ΔP (دقیق)
    expect(a + b).toBe(r);
    expect(b).toBeCloseTo(2_227_514_398.24, 2);
  });

  it("بدون رقم اعشار: جمع دقیق", () => {
    const [r, a, b] = splitRounded(9_937_407_877.639_488_220, 7_709_893_479.404_506);
    expect(r).toBe(9_937_407_878);
    expect(a).toBe(7_709_893_479);
    expect(a + b).toBe(r);
    expect(b).toBe(2_227_514_399);
  });

  it("مقادیر منفی و صفر", () => {
    const [r, a, b] = splitRounded(-1_000_000.006, -600_000.004, 2);
    expect(r).toBe(-1_000_000.01);
    expect(a).toBe(-600_000.0);
    expect(a + b).toBe(r);
    expect(splitRounded(0, 0, 2)).toEqual([0, 0, 0]);
  });

  it("roundTo رفتار نصف-به-بالا دارد", () => {
    expect(roundTo(0.125, 2)).toBe(0.13);
    expect(roundTo(0.5)).toBe(1);
    expect(roundTo(1.2345, 3)).toBe(1.235);
  });
});

// ═══ خروجی Excel موتورها (فاز D — آینهٔ تست‌های Python) ═══

const XLS_EXTRA: Partial<ProjectSettings> = {
  baravordEnabled: true,
  proposalDate: PROPOSAL_DATE,
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
  provisionalCoef1405q1: PROV_COEF,
};

/** صادر کردن کتاب‌کار با ضبطِ workbook (mock روی writeFile). */
function exportWb(result: ProjectResult, settings: ProjectSettings): XLSX.WorkBook {
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook(
      { projectName: "T91", reportNo: "1" } as never,
      result,
      settings,
      [] as never,
    );
  } finally {
    mock.mockRestore();
  }
  return wb as XLSX.WorkBook;
}

/** همهٔ رشته‌های یک کتاب‌کار (معادل sharedStrings در Python). */
function allStrings(wb: XLSX.WorkBook): string[] {
  const out: string[] = [];
  for (const name of wb.SheetNames) {
    const ws = wb.Sheets[name] ?? {};
    for (const addr in ws) {
      if (addr.startsWith("!")) continue;
      const c = ws[addr as never] as { v?: unknown } | undefined;
      if (typeof c?.v === "string") out.push(c.v);
    }
  }
  return out;
}

describe("T91 شیت‌های Excel موتورها", () => {
  it("هر دو موتور روشن: شیت‌های موتور ساخته می‌شوند", () => {
    const res = pipeline(on(XLS_EXTRA));
    const wb = exportWb(res, on(XLS_EXTRA));
    expect(wb.SheetNames).toContain("تعدیل پیمان");
    expect(wb.SheetNames).toContain("برآورد به‌هنگام");
    expect(wb.SheetNames).toContain("بخش قطعی و علی‌الحساب");
    expect(wb.SheetNames).toContain("مقادیر منتظر تأیید");
    expect(wb.SheetNames).toContain("قیمت‌های دستی");
    expect(wb.SheetNames).toContain("سابقهٔ ویرایش");
    // ۷ شیت پایه + ۲ شیت فاز C + ۳ شیت موتور + ۲ شیت ضریب طبقات/هشدارها
    // + ۵ شیت فاز D (خلاصه و وضعیت، مشخصات پیمان، ضرایب، شاخص‌ها، منابع) = ۱۹
    expect(wb.SheetNames.length).toBe(19);
  }, 120000);

  it("موتورها خاموش: شیت موتور ساخته نمی‌شود ولی رجیستری هست", () => {
    const res = pipeline(defaultSettings());
    const wb = exportWb(res, defaultSettings());
    expect(wb.SheetNames).not.toContain("تعدیل پیمان");
    expect(wb.SheetNames).not.toContain("بخش قطعی و علی‌الحساب");
    expect(wb.SheetNames).not.toContain("برآورد به‌هنگام");
    expect(wb.SheetNames).toContain("مقادیر منتظر تأیید");
    // ۷ شیت پایه + ۲ شیت فاز C + ۲ شیت ضریب طبقات/هشدارها
    // + ۵ شیت فاز D (خلاصه و وضعیت، مشخصات پیمان، ضرایب، شاخص‌ها، منابع) = ۱۶
    expect(wb.SheetNames.length).toBe(16);
  }, 120000);

  it("شیت تعدیل: جدول فصل × سه‌ماهه و برچسب‌ها", () => {
    const res = pipeline(on(XLS_EXTRA));
    const wb = exportWb(res, on(XLS_EXTRA));
    const strs = allStrings(wb);
    expect(strs).toContain("شاخص It هر فصل در هر سه‌ماههٔ کارکرد (ستون زرد = موقت)");
    expect(strs.some((s) => s.includes("جمع تعدیل (شامل علی‌الحساب)"))).toBe(true);
    expect(strs.some((s) => s.includes("مبلغ نهایی (A + جمع تعدیل)"))).toBe(true);
  }, 120000);

  it("شیت برآورد: ردیف جمع کل به‌هنگام‌شده", () => {
    const res = pipeline(on(XLS_EXTRA));
    const wb = exportWb(res, on(XLS_EXTRA));
    const strs = allStrings(wb);
    expect(strs).toContain("جمع کل به‌هنگام‌شده (قیمت پیمان)");
  }, 120000);

  it("شیت بخش قطعی و علی‌الحساب: نام جدید، نه قدیمی", () => {
    const res = pipeline(on(XLS_EXTRA));
    const wb = exportWb(res, on(XLS_EXTRA));
    expect(wb.SheetNames).toContain("بخش قطعی و علی‌الحساب");
    const strs = allStrings(wb);
    expect(strs.some((s) => s.includes("مابه‌التفاوت موقت و قطعی"))).toBe(false);
    expect(strs.some((s) => s.includes("بخش قطعی (شاخص‌های قطعی ۱۴۰۴)"))).toBe(true);
    expect(strs.some((s) => s.includes("بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1)"))).toBe(true);
  }, 120000);

  it("رجیستری مقادیر منتظر تأیید: شاخص فصول ابنیه", () => {
    const res = pipeline(on());
    const wb = exportWb(res, on());
    const strs = allStrings(wb);
    expect(strs.some((s) => s.includes("شاخص فصول ابنیه"))).toBe(true);
    expect(strs.some((s) => s.includes("فصل ۶ — شاخص اسفند ۱۴۰۳ (مبنا)"))).toBe(true);
    // شاخص رشته ابنیه (ردیف ۱) — صفحهٔ ۴
    expect(strs.some((s) => s.includes("شاخص دورهٔ اسفند ۱۴۰۳ (مبنا)"))).toBe(true);
  }, 120000);

  it("تفکیک گردسازی در شیت تعدیل: قطعی + علی‌الحساب ≡ ΔP", () => {
    const res = pipeline(on(XLS_EXTRA));
    const t = res.adjustment?.tadil;
    expect(t).toBeTruthy();
    const [, dpDef, dpProv] = splitRounded(t!.delta_p, t!.delta_p_definitive, 0);
    expect(dpDef + dpProv).toBe(Math.round(t!.delta_p));
    const wb = exportWb(res, on(XLS_EXTRA));
    const ws = wb.Sheets["تعدیل پیمان"] ?? {};
    // مقادیر عددی سلول‌های بخش قطعی/علی‌الحساب
    const nums: number[] = [];
    for (const addr in ws) {
      if (addr.startsWith("!")) continue;
      const c = ws[addr as never] as { v?: unknown } | undefined;
      if (typeof c?.v === "number" && Math.abs(c.v) > 1e9) nums.push(c.v);
    }
    expect(nums).toContain(dpDef);
    expect(nums).toContain(dpProv);
  }, 120000);
});
