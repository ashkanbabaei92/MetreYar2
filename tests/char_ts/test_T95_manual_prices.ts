// ─────────────────────────────────────────────────────────────
// T95 — پنل قیمت دستی (فاز C، §۱۵-۴) — لایهٔ موتور + ماندگاری
// (آینهٔ test_T95_manual_prices.py)
//
// بررسی‌ها:
//   - مهاجرت ورودی‌های قدیمی (priceOverrides عددی / manualCodes رشته /
//     excluded رشته) به رکوردهای ردیخی‌پذیر، **بدون تغییر ارقام**
//     (درخواست صریح کاربر).
//   - اعمال قیمت دستی روی ردیف‌ها: appPrice / diffPct / priceStatus.
//   - اولویت: دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی.
//   - ردیف‌های ستاره‌دار: ورود کامل دستی، کد با پسوند *، حضور در صورت‌وضعیت.
//   - هشدار اختلاف > آستانه (پیش‌فرض ۳۰٪).
//   - ورود/خروج Excel: جابه‌جایی قیمت‌ها بین پروژه‌ها.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as path from "path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import {
  computeProject,
  defaultSettings,
  excludedIds,
  manualCodeOf,
  manualPriceOf,
  migrateManualEntries,
  priceStatusOf,
} from "../../src/lib/engine";
import { exportWorkbook } from "../../src/lib/exporters";
import type { FehrestRow, ProjectMeta, ProjectResult, ProjectSettings, RevitTable } from "../../src/lib/types";
import {
  applyManualEntries,
  manualEntriesPayload,
  MANUAL_ENTRIES_VERSION,
  parseManualEntriesXlsx,
} from "../../src/lib/manualEntries";
import { loadJson } from "./helper";

const fixture = loadJson(
  path.join(__dirname, "..", "char_shared", "fixtures", "revit", "T32_rebar_grand_total.json"),
);

function mkTable(): RevitTable {
  return {
    ...fixture.table,
    fileName: fixture.table.file_name,
    kindConfidence: fixture.table.kind_confidence,
    colMap: fixture.table.col_map,
    grandTotal: { weight: 310 },
    rows: fixture.table.rows.map((row: any) => ({ ...row, isSubtotal: row.is_subtotal })),
  } as RevitTable;
}

function settingsFrom(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  const s = {
    ...defaultSettings(),
    overheadCoef: fixture.settings.overhead_coef,
    regionalCoef: fixture.settings.regional_coef,
    floorsCoef: fixture.settings.floors_coef,
    siteSetupAmount: fixture.settings.site_setup_amount,
    insurancePct: fixture.settings.insurance_pct,
    taxPct: fixture.settings.tax_pct,
    goodJobPct: fixture.settings.good_job_pct,
    advancePayment: fixture.settings.advance_payment,
  };
  delete (s as { _manualMigrated?: boolean })._manualMigrated;
  return { ...s, ...extra };
}

function compute(extra: Partial<ProjectSettings> = {}): { result: ProjectResult; settings: ProjectSettings } {
  const settings = settingsFrom(extra);
  const result = computeProject([mkTable()], fixture.db as FehrestRow[], settings);
  return { result, settings };
}

function byId(result: ProjectResult): Record<string, ProjectResult["lines"][number]> {
  return Object.fromEntries(result.lines.map((l) => [l.id, l]));
}

function exportWb(result: ProjectResult, settings: ProjectSettings): XLSX.WorkBook {
  const writeFile = XLSX.writeFile as unknown as { mock: { calls: unknown[][] } };
  exportWorkbook(
    {
      reportType: "موقت", reportNo: "1", contractNo: "T95", projectName: "T95",
      employer: "", contractor: "", consultant: "", periodStart: "", periodEnd: "",
      location: "", contractDate: "",
    } as ProjectMeta,
    result,
    settings,
    [] as never,
  );
  const calls = writeFile.mock.calls;
  return calls[calls.length - 1][0] as XLSX.WorkBook;
}

// ── کمک‌توابع سطح ماژول ──

describe("T95 پنل قیمت دستی — کمک‌توابع", () => {
  it("مهاجرت ورودی‌های قدیمی به رکوردهای ردیخی‌پذیر (Idempotent)", () => {
    const s = {
      priceOverrides: { "rebar-070201": 999.0 },
      manualCodes: { "rebar-070203": "070201" },
      excluded: ["transport-rebar"],
    } as unknown as ProjectSettings;
    migrateManualEntries(s);
    const rec = s.manualPrices["rebar-070201"];
    expect(rec.price).toBe(999.0);
    expect(rec.source).toBe("ویرایش قدیمی (قبل از مرحلهٔ ۱۳)");
    expect(rec.status).toBe("نیازمند تأیید");
    expect(s.manualCodes["rebar-070203"]).toEqual({
      code: "070201", reason: "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)", user: "", at: "",
    });
    expect(s.excluded).toEqual([{ id: "transport-rebar", reason: "", user: "", at: "" }]);
    // Idempotent
    migrateManualEntries(s);
    expect(s.manualPrices["rebar-070201"].price).toBe(999.0);
  });

  it("کمک‌توابع manualPriceOf / manualCodeOf / excludedIds", () => {
    const s = {
      manualPrices: { a: { price: 12.5 } },
      manualCodes: { b: { code: "070201" }, c: "070203" },
    } as unknown as ProjectSettings;
    expect(manualPriceOf(s, "a")).toBe(12.5);
    expect(manualPriceOf(s, "z")).toBeNull();
    expect(manualCodeOf(s, "b")).toBe("070201");
    expect(manualCodeOf(s, "c")).toBe("070203");
    expect(manualCodeOf(s, "z")).toBe("");
    expect(excludedIds(s)).toEqual(new Set());
    expect(excludedIds({ excluded: ["x", { id: "y" }] } as never)).toEqual(new Set(["x", "y"]));
  });

  it("اولویت وضعیت قیمت: دستی > نیازمند ورود > موقت > پیش‌فرض اپ > قطعی", () => {
    expect(priceStatusOf({ manual: { price: 1 } })).toBe("دستی");
    expect(priceStatusOf({ needsReview: true })).toBe("نیازمند ورود");
    expect(priceStatusOf({ estimatedPrice: true })).toBe("موقت");
    expect(priceStatusOf({ matchMethod: "fuzzy", confidence: 0.4 })).toBe("پیش‌فرض اپ");
    expect(priceStatusOf({ matchMethod: "rule-exact", confidence: 0.99 })).toBe("قطعی");
    // دستی برنده است حتی اگر needsReview باشد
    expect(priceStatusOf({ manual: { price: 1 }, needsReview: true })).toBe("دستی");
  });
});

// ── مهاجرت: ارقام تغییر نمی‌کنند (درخواست صریح کاربر) ──

describe("T95 مهاجرت", () => {
  it("ویرایش قدیمیِ priceOverrides و رکورد جدیدِ manualPrices همان base/grand را می‌دهند", () => {
    const legacy = compute({ priceOverrides: { "rebar-070201": 999.0 } });
    const fresh = compute({
      manualPrices: {
        "rebar-070201": {
          price: 999.0, source: "استعلام", docNo: "Q-1", docDate: "۱۴۰۴/۰۵/۰۱",
          note: "", status: "دستی", chapter: "", user: "", at: "",
        },
      },
    });
    expect(fresh.result.baseTotal).toBeCloseTo(legacy.result.baseTotal, 6);
    expect(fresh.result.grandTotal).toBeCloseTo(legacy.result.grandTotal, 6);
    // و مهاجرت واقعاً رکورد قدیمی را برچسب می‌زند
    expect(legacy.settings.manualPrices["rebar-070201"].source).toBe(
      "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)",
    );
  });
});

// ── اعمال قیمت دستی ──

describe("T95 اعمال قیمت دستی", () => {
  it("قیمت دستی جایگزین می‌شود و appPrice/diffPct/priceStatus پر می‌شوند", () => {
    const base = compute();
    const origPrice = byId(base.result)["rebar-070201"].price;

    const r2 = compute({
      manualPrices: {
        "rebar-070201": {
          price: origPrice * 2, source: "بخشنامه", docNo: "۱۴۰۵/۱۵۵۲۳۳",
          docDate: "۱۴۰۵/۰۴/۱۲", note: "استعلام قیمت فولاد", status: "دستی",
          chapter: "07", user: "دفتر فنی", at: "۱۴۰۵/۰۷/۰۸",
        },
      },
    });
    const line = byId(r2.result)["rebar-070201"];
    expect(line.price).toBeCloseTo(origPrice * 2, 6);
    expect(line.total).toBeCloseTo(line.qty * origPrice * 2, 6);
    expect(line.appPrice).toBeCloseTo(origPrice, 6);
    expect(line.diffPct).toBeCloseTo(100.0, 6);
    expect(line.priceStatus).toBe("دستی");
    expect((line.manual as { docNo: string }).docNo).toBe("۱۴۰۵/۱۵۵۲۳۳");
    // رفتار قدیمی: قیمت دستی، ردیف را تأییدشده می‌کند
    expect(line.estimatedPrice).toBe(false);
    expect(line.needsReview).toBe(false);
    // ردیف‌های دیگر دست‌نخورده
    expect(byId(r2.result)["rebar-070203"].price).toBe(byId(base.result)["rebar-070203"].price);
    // زنجیرهٔ مالی با قیمت جدید محاسبه می‌شود
    expect(r2.result.baseTotal).toBeGreaterThan(base.result.baseTotal);
  });

  it("هشدار اختلاف فقط بالای آستانه داده می‌شود", () => {
    const orig = byId(compute().result)["rebar-070201"].price;
    const rec = {
      price: orig * 2, source: "استعلام", docNo: "", docDate: "", note: "",
      status: "دستی", chapter: "", user: "", at: "",
    };
    const loud = compute({ priceDiffWarnPct: 30.0, manualPrices: { "rebar-070201": rec } });
    const pw = loud.result.warnings.filter((w) => w.category === "قیمت دستی");
    expect(pw).toHaveLength(1);
    expect(pw[0].message).toContain("070201");
    expect(pw[0].action).toContain("بررسی");
    // زیر آستانه: هشدار نیست
    const quiet = compute({ priceDiffWarnPct: 300.0, manualPrices: { "rebar-070201": rec } });
    expect(quiet.result.warnings.filter((w) => w.category === "قیمت دستی")).toHaveLength(0);
  });

  it("خلاصهٔ وضعیت و شمارش «نیازمند ورود»", () => {
    const { result } = compute();
    expect(result.needsPriceEntry).toBeGreaterThan(0); // transport-rebar: needsReview
    expect(result.priceStatusSummary["قطعی"]).toBeDefined();
    expect(result.priceStatusSummary["نیازمند ورود"]).toBeGreaterThanOrEqual(1);
    // ستاره‌داری نیست
    expect(result.starredTotal).toBe(0);
  });
});

// ─ـ ردیف‌های ستاره‌دار ──

describe("T95 ردیف‌های ستاره‌دار", () => {
  it("ردیف ستاره‌دار در زنجیرهٔ مالی و شاخص تعدیل حاضر است", () => {
    const base = compute();
    const { result } = compute({
      starredRows: [{
        code: "990101", desc: "قفل‌سازی و یراق‌آلات درب‌ها", unit: "عدد",
        qty: 12, price: 2500000, source: "فاکتور", docNo: "F-77",
        docDate: "۱۴۰۴/۰۶/۰۱", note: "خرید محلی", chapter: "31",
        user: "دفتر فنی", at: "۱۴۰۵/۰۷/۰۸",
      }],
    });
    const star = result.lines.filter((l) => l.starred);
    expect(star).toHaveLength(1);
    expect(star[0].code).toBe("990101*");
    expect(star[0].chapter).toBe("31");
    expect(star[0].qty).toBe(12);
    expect(star[0].total).toBeCloseTo(12 * 2500000, 6);
    expect(star[0].priceStatus).toBe("دستی");
    expect(result.baseTotal - base.result.baseTotal).toBeCloseTo(12 * 2500000, 6);
    expect(result.starredTotal).toBeGreaterThan(0);
    expect(result.starredPct).toBeGreaterThan(0);
    // کد بدون ستاره خودکار ستاره می‌گیرد
    expect(result.lines.filter((l) => l.starred).every((l) => l.code.endsWith("*"))).toBe(true);
  });

  it("ردیف‌های ستاره‌دار نامعتبر (qty/price صفر) نادیده گرفته می‌شوند", () => {
    const { result } = compute({
      starredRows: [
        { code: "X1", qty: 0, price: 100, desc: "تست", unit: "عدد", chapter: "31",
          source: "توافق", docNo: "", docDate: "", note: "", user: "", at: "" },
        { code: "X2", qty: 5, price: 0, desc: "تست", unit: "عدد", chapter: "31",
          source: "توافق", docNo: "", docDate: "", note: "", user: "", at: "" },
        { code: "X3", qty: 5, price: 100, chapter: "31", desc: "تست", unit: "عدد",
          source: "توافق", docNo: "", docDate: "", note: "", user: "", at: "" },
      ],
    });
    expect(result.lines.filter((l) => l.starred)).toHaveLength(1);
  });
});

// ─ـ مستثنی‌ها ──

describe("T95 مستثنی‌ها", () => {
  it("ردیف مستثنی (رکورد یا رشته) از صورت‌وضعیت حذف می‌شود", () => {
    const withRec = compute({
      excluded: [{ id: "transport-rebar", reason: "حمل اختصاصی", user: "دفتر فنی", at: "۱۴۰۵/۰۷/۰۸" }],
    });
    expect(byId(withRec.result)["transport-rebar"]).toBeUndefined();
    expect(withRec.result.baseTotal).toBeLessThan(compute().result.baseTotal);
    // ساختار قدیمی رشته‌ای هم هنوز کار می‌کند
    const withStr = compute({ excluded: ["transport-rebar"] as never });
    expect(byId(withStr.result)["transport-rebar"]).toBeUndefined();
  });
});

// ── فایل کناری + ورود/خروج Excel ──

function fullSettings(): ProjectSettings {
  const base = compute();
  const orig = byId(base.result)["rebar-070201"].price;
  const s = base.settings;
  s.manualPrices = {
    "rebar-070201": {
      price: orig * 1.5, source: "استعلام", docNo: "Q-1", docDate: "۱۴۰۴/۰۵/۰۱",
      note: "استعلام فولاد", status: "دستی", chapter: "", user: "دفتر فنی",
      at: "۱۴۰۵/۰۷/۰۸ ۱۰:۰۰",
    },
  };
  s.starredRows = [{
    code: "990101", desc: "قفل‌سازی درب‌ها", unit: "عدد", qty: 4, price: 2500000,
    chapter: "31", source: "فاکتور", docNo: "F-77", docDate: "۱۴۰۴/۰۶/۰۱",
    note: "خرید محلی", user: "دفتر فنی", at: "۱۴۰۵/۰۷/۰۸ ۱۱:۰۰",
  }];
  s.priceAudit = [{
    at: "۱۴۰۵/۰۷/۰۸ ۱۰:۰۰", user: "دفتر فنی", item: "rebar-070201",
    field: "price", old: orig, new: orig * 1.5, source: "استعلام",
  }];
  s.priceUser = "دفتر فنی";
  return s;
}

describe("T95 ورود/خروج Excel و payload", () => {
  it("شیت صورت‌وضعیت ۱۷ ستون و شیت‌های قیمت دستی ساخته می‌شوند", () => {
    const s = fullSettings();
    const res = computeProject([mkTable()], fixture.db as FehrestRow[], s);
    const wb = exportWb(res, s);
    expect(wb.SheetNames).toContain("قیمت‌های دستی");
    expect(wb.SheetNames).toContain("سابقهٔ ویرایش");
    const header = XLSX.utils.sheet_to_json(wb.Sheets["صورت وضعیت"], { header: 1 }) as unknown[][];
    // سطر سرستون: ۱۷ ستون
    const headRow = header.find((r) => (r as unknown[])[0] === "ردیف") as unknown[];
    expect(headRow).toHaveLength(17);
  });

  it("خروجی Excel → ورود مجدد → محاسبه: ارقام عیناً یکسان (جابه‌جایی بین پروژه‌ها)", () => {
    const s = fullSettings();
    const res = computeProject([mkTable()], fixture.db as FehrestRow[], s);
    const wb = exportWb(res, s);
    const data = XLSX.write(wb, { type: "array", bookType: "xlsx" }) as Uint8Array;

    const payload = parseManualEntriesXlsx(data);
    expect(payload).not.toBeNull();
    expect(payload!.manualPrices["rebar-070201"]).toBeDefined();
    expect(payload!.manualPrices["rebar-070201"].price).toBe(s.manualPrices["rebar-070201"].price);
    expect(payload!.manualPrices["rebar-070201"].docNo).toBe("Q-1");
    expect(payload!.starredRows).toHaveLength(1);
    expect(payload!.starredRows[0].qty).toBe(4);
    expect(payload!.priceAudit).toHaveLength(1);
    expect(payload!.priceAudit[0].item).toBe("rebar-070201");

    const s2 = settingsFrom();
    const warns = applyManualEntries(s2, payload);
    expect(warns).toHaveLength(0);
    const res2 = computeProject([mkTable()], fixture.db as FehrestRow[], s2);
    expect(res2.baseTotal).toBeCloseTo(res.baseTotal, 6);
    expect(res2.grandTotal).toBeCloseTo(res.grandTotal, 6);
    expect(byId(res2)["rebar-070201"].priceStatus).toBe("دستی");
  });

  it("خروجیِ خالی هم شیت‌ها را می‌سازد و payload نسخه دارد", () => {
    const { result, settings } = compute();
    const wb = exportWb(result, settings);
    const data = XLSX.write(wb, { type: "array", bookType: "xlsx" }) as Uint8Array;
    const payload = parseManualEntriesXlsx(data);
    expect(payload).not.toBeNull();
    expect(payload!.manualPrices).toEqual({});
    expect(payload!.starredRows).toEqual([]);
    const p2 = manualEntriesPayload(settings);
    expect(p2.version).toBe(MANUAL_ENTRIES_VERSION);
  });

  it("round-trip فایل کناری JSON: ارقام تا ریال یکسان", () => {
    const s = fullSettings();
    const res = computeProject([mkTable()], fixture.db as FehrestRow[], s);
    const json = JSON.stringify(manualEntriesPayload(s));
    const s2 = settingsFrom();
    const warns = applyManualEntries(s2, JSON.parse(json));
    expect(warns).toHaveLength(0);
    const res2 = computeProject([mkTable()], fixture.db as FehrestRow[], s2);
    expect(res2.baseTotal).toBeCloseTo(res.baseTotal, 6);
    expect(res2.grandTotal).toBeCloseTo(res.grandTotal, 6);
  });
});
