// ─────────────────────────────────────────────────────────────
// T96 — فاز E-۵: پروفایل پروژه
// (آینهٔ test_T96_project_profile.py)
//
// بخش a:
//   - هشدار مغایرت سال فهرست‌بها (سطح «هشدار»، آیتم fehrest_year_mismatch)
//   - نوع رویداد در سابقهٔ ویرایش (price/setting/meta) + مسیر برگشت Excel
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as path from "path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import {
  appendAudit,
  computeProject,
  defaultSettings,
} from "../../src/lib/engine";
import { exportWorkbook } from "../../src/lib/exporters";
import {
  AUDIT_KIND_LABELS,
  type AuditKind,
  type FehrestRow,
  type ProjectMeta,
  type ProjectResult,
  type ProjectSettings,
  type RevitTable,
} from "../../src/lib/types";
import {
  PROFILE_KIND,
  PROFILE_VERSION,
  copyProject,
  loadProjectProfileJson,
  manualEntriesPayload,
  parseManualEntriesXlsx,
  projectProfilePayload,
} from "../../src/lib/manualEntries";
import {
  META_LABELS,
  SETTING_LABELS,
  auditSnap,
  diffAuditEntries,
} from "../../src/lib/auditDiff";
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
  return { ...defaultSettings(), ...extra };
}

function compute(extra: Partial<ProjectSettings> = {}): {
  result: ProjectResult;
  settings: ProjectSettings;
} {
  const settings = settingsFrom(extra);
  const result = computeProject([mkTable()], fixture.db as FehrestRow[], settings);
  return { result, settings };
}

function mismatch(result: ProjectResult) {
  return result.warnings.filter((w) => w.item === "fehrest_year_mismatch");
}

function exportWb(result: ProjectResult, settings: ProjectSettings): XLSX.WorkBook {
  const writeFile = XLSX.writeFile as unknown as { mock: { calls: unknown[][] } };
  exportWorkbook(
    {
      reportType: "موقت", reportNo: "1", contractNo: "T96", projectName: "T96",
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

// ── هشدار مغایرت سال فهرست‌بها ──

describe("T96 فاز E-۵ — هشدار مغایرت سال فهرست‌بها", () => {
  it("هم‌خوانی پیش‌فرض ⇒ بدون هشدار", () => {
    const { result } = compute();
    expect(mismatch(result)).toHaveLength(0);
  });

  it("مغایرت (۱۴۰۳ vs ۱۴۰۴) ⇒ یک هشدار سطح «هشدار»", () => {
    const { result } = compute({ fehrestYear: "۱۴۰۳" });
    const m = mismatch(result);
    expect(m).toHaveLength(1);
    expect(m[0].level).toBe("هشدار");
    expect(m[0].category).toBe("فهرست‌بها");
    expect(result.warningsByLevel["هشدار"] ?? 0).toBeGreaterThanOrEqual(1);
  });

  it("ارقام فارسی و لاتین یکسان در نظر گرفته می‌شوند", () => {
    const { result } = compute({ fehrestYear: "1404" });
    expect(mismatch(result)).toHaveLength(0);
  });

  it("سال فهرستِ بارگذاری‌شدهٔ خالی ⇒ بدون هشدار", () => {
    const { result } = compute({ fehrestDbYear: "" });
    expect(mismatch(result)).toHaveLength(0);
  });
});

// ── نوع رویداد در سابقهٔ ویرایش ──

describe("T96 فاز E-۵ — نوع رویداد در سابقهٔ ویرایش", () => {
  it("پیش‌فرض price و نوع‌های صریح", () => {
    const s = settingsFrom();
    appendAudit(s, "۰۶۰۳۰۱", "price", 100, 120, "استعلام");
    appendAudit(s, "تنظیمات", "tadilCoef", 0.95, 1.0, "سایدبار", "setting");
    appendAudit(s, "پیمان", "contractNo", "", "۹۹", "فرم", "meta" as AuditKind);
    expect(s.priceAudit.map((a) => a.kind)).toEqual(["price", "setting", "meta"]);
    expect(AUDIT_KIND_LABELS.meta).toBe("مشخصات");
  });

  it("مسیر برگشت Excel: نوع رویداد حفظ می‌شود", () => {
    const s = settingsFrom();
    appendAudit(s, "۰۶۰۳۰۱", "price", 100, 120, "استعلام");
    appendAudit(s, "تنظیمات", "tadilCoef", 0.95, 1.0, "سایدبار", "setting");
    const res = computeProject([mkTable()], fixture.db as FehrestRow[], s);
    const wb = exportWb(res, s);
    const data = XLSX.write(wb, { type: "array", bookType: "xlsx" }) as Uint8Array;
    const payload = parseManualEntriesXlsx(data);
    expect(payload).not.toBeNull();
    expect(payload!.priceAudit.map((a) => a.kind)).toEqual(["price", "setting"]);
  });

  it("رکورد قدیمی بدون kind ⇒ پیش‌فرض price در مسیر برگشت", () => {
    const s = settingsFrom();
    s.priceAudit = [
      { at: "۱۴۰۴/۰۱/۰۱", user: "u", item: "x", field: "price", old: 1, new: 2, source: "" },
    ] as never;
    const res = computeProject([mkTable()], fixture.db as FehrestRow[], s);
    const wb = exportWb(res, s);
    const data = XLSX.write(wb, { type: "array", bookType: "xlsx" }) as Uint8Array;
    const payload = parseManualEntriesXlsx(data);
    expect(payload!.priceAudit[0].kind).toBe("price");
  });

  it("تفاضلِ تنظیمات: تغییرات در رجیستری ثبت می‌شوند", () => {
    const s = settingsFrom();
    const snap = auditSnap(s);
    s.tadilCoef = 0.9;
    s.fehrestYear = "۱۴۰۳";
    const entries = diffAuditEntries(
      snap, s, "setting", SETTING_LABELS, "تنظیمات پروژه",
    );
    expect(entries).toHaveLength(2);
    expect(new Set(entries.map((e) => e.field))).toEqual(
      new Set(["ضریب k تعدیل", "سال فهرست‌بهای پروژه"]),
    );
    expect(entries.every((e) => e.item === "تنظیمات پروژه")).toBe(true);
    expect(entries.every((e) => e.kind === "setting")).toBe(true);
  });

  it("تفاضلِ تنظیمات: بدون تغییر ⇒ خالی", () => {
    const s = settingsFrom();
    const snap = auditSnap(s);
    expect(
      diffAuditEntries(snap, s, "setting", SETTING_LABELS, "تنظیمات پروژه"),
    ).toHaveLength(0);
  });

  it("تفاضلِ تنظیمات: کلیدهای ورودیِ دستیِ قیمت مستثنی‌اند", () => {
    const s = settingsFrom();
    const snap = auditSnap(s);
    s.manualPrices["x"] = { price: 100 } as never;
    s.excluded.push("y" as never);
    expect(
      diffAuditEntries(snap, s, "setting", SETTING_LABELS, "تنظیمات پروژه"),
    ).toHaveLength(0);
  });

  it("تفاضلِ مشخصات: تغییر contract_no با برچسب فارسی", () => {
    const meta = { projectName: "الف", reportNo: "۱", contractNo: "" } as never;
    const snap = auditSnap(meta);
    meta.contractNo = "۹۹";
    const entries = diffAuditEntries(
      snap, meta, "meta", META_LABELS, "مشخصات پیمان",
    );
    expect(entries).toHaveLength(1);
    expect(entries[0].field).toBe("شماره پیمان");
    expect(entries[0].kind).toBe("meta");
  });

  // ── بخش c: پروفایل پروژه ──

  const profileMeta: ProjectMeta = {
    projectName: "پروژهٔ آزمایشی", employer: "", contractor: "", consultant: "",
    contractNo: "۹۹", contractDate: "۱۴۰۴/۰۱/۰۱", location: "",
    reportNo: "۳", reportType: "موقت", periodStart: "۱۴۰۴/۰۱", periodEnd: "۱۴۰۴/۰۶",
  };

  it("پروفایل: payload با kind/نسخه و کپیِ مستقل", () => {
    const s = settingsFrom({ tadilCoef: 0.9 });
    const p = projectProfilePayload(s, profileMeta);
    expect(p.kind).toBe(PROFILE_KIND);
    expect(p.version).toBe(PROFILE_VERSION);
    expect(p.meta.contractNo).toBe("۹۹");
    expect(p.settings.tadilCoef).toBe(0.9);
    // تغییرِ بعدیِ s روی payload اثر نمی‌کند
    s.tadilCoef = 1.0;
    expect(p.settings.tadilCoef).toBe(0.9);
  });

  it("پروفایل: ذخیره/بارگذاری round-trip", () => {
    const s = settingsFrom({ tadilCoef: 0.9, fehrestYear: "۱۴۰۳" });
    s.manualPrices["A-1"] = { price: 1000, docNo: "۱۲۳" } as never;
    const text = JSON.stringify(projectProfilePayload(s, profileMeta), null, 1);
    const r = loadProjectProfileJson(text);
    expect(r.settings).not.toBeNull();
    expect(r.meta!.contractNo).toBe("۹۹");
    expect(r.settings!.tadilCoef).toBe(0.9);
    expect(r.settings!.fehrestYear).toBe("۱۴۰۳");
    expect(r.settings!.manualPrices["A-1"].docNo).toBe("۱۲۳");
    expect(r.warns).toHaveLength(0);
  });

  it("پروفایل: فایل کناریِ قدیمی ⇒ meta=null", () => {
    const s = settingsFrom({ priceDiffWarnPct: 45 });
    s.manualPrices["A-1"] = { price: 1000, docNo: "۱۲۳" } as never;
    const legacy = JSON.stringify(manualEntriesPayload(s), null, 1);
    const r = loadProjectProfileJson(legacy);
    expect(r.meta).toBeNull();
    expect(r.settings!.priceDiffWarnPct).toBe(45);
    expect(r.settings!.manualPrices["A-1"].docNo).toBe("۱۲۳");
  });

  it("پروفایل: فایل خراب ⇒ settings=null + یک هشدار", () => {
    const r = loadProjectProfileJson("not json at all");
    expect(r.settings).toBeNull();
    expect(r.meta).toBeNull();
    expect(r.warns).toHaveLength(1);
  });

  it("پروفایل: نسخهٔ متفاوت ⇒ هشدار", () => {
    const p = projectProfilePayload(settingsFrom(), profileMeta);
    p.version = 99;
    const r = loadProjectProfileJson(JSON.stringify(p));
    expect(r.settings).not.toBeNull();
    expect(r.warns.some((w) => w.includes("نسخه"))).toBe(true);
  });

  it("پروفایل: کلیدهای ناشناخته نادیده گرفته و هشدار داده می‌شوند", () => {
    const p = projectProfilePayload(settingsFrom(), profileMeta);
    (p.settings as Record<string, unknown>).bogus_key = 1;
    (p.meta as Record<string, unknown>).bogus_meta = 2;
    const r = loadProjectProfileJson(JSON.stringify(p));
    expect(r.settings).not.toBeNull();
    expect(r.warns.some((w) => w.includes("ناشناخته"))).toBe(true);
  });

  it("پروفایل: کلیدهای snake_caseِ پایتون پذیرفته می‌شوند", () => {
    const py = {
      kind: PROFILE_KIND,
      version: PROFILE_VERSION,
      exportedAt: "2026-10-02T00:00:00.000Z",
      meta: { project_name: "از پایتون", contract_no: "۵", report_no: "۲" },
      settings: { tadil_coef: 0.8, fehrest_year: "۱۴۰۳", price_user: "دفتر فنی" },
    };
    const r = loadProjectProfileJson(JSON.stringify(py));
    expect(r.settings!.tadilCoef).toBe(0.8);
    expect(r.settings!.fehrestYear).toBe("۱۴۰۳");
    expect(r.settings!.priceUser).toBe("دفتر فنی");
    expect(r.meta!.projectName).toBe("از پایتون");
    expect(r.meta!.contractNo).toBe("۵");
    expect(r.meta!.reportNo).toBe("۲");
  });

  // ── بخش d: پروژهٔ جدید از روی این پروژه ──

  it("کپی پروژه: پاک‌شدنِ هویتی/زمانی + نگه‌داشتنِ فنی + یک رویداد", () => {
    const s = settingsFrom({
      proposalDate: "۱۴۰۵/۰۴/۰۱",
      proposalDeadline: "۱۴۰۵/۰۵/۰۱",
      proposalCoef: 1.15,
      workPeriodStart: "۱۴۰۴/۰۱",
      workPeriodEnd: "۱۴۰۴/۰۶",
      tadilCoef: 0.9,
    });
    s.manualPrices["A-1"] = { price: 1000, docNo: "۱۲۳" } as never;
    const r = copyProject(s, profileMeta);
    expect(r.meta.projectName).toBe("کپی از پروژهٔ آزمایشی");
    expect(r.meta.reportNo).toBe("۱");
    expect(r.meta.contractNo).toBe("");
    expect(r.meta.contractDate).toBe("");
    expect(r.meta.periodStart).toBe("");
    expect(r.settings.proposalDate).toBe("");
    expect(r.settings.proposalDeadline).toBe("");
    expect(r.settings.proposalCoef).toBe(1.0);
    expect(r.settings.workPeriodStart).toBe("");
    expect(r.settings.workPeriodEnd).toBe("");
    expect(r.settings.tadilCoef).toBe(0.9);
    expect(Object.keys(r.settings.manualPrices)).toContain("A-1");
    expect(r.settings.priceAudit).toHaveLength(1);
    const a = r.settings.priceAudit[0];
    expect(a.kind).toBe("meta");
    expect(a.field).toBe("copy");
    expect(a.old).toBe("پروژهٔ آزمایشی");
    expect(a.new).toBe("کپی از پروژهٔ آزمایشی");
    // پروژهٔ اصلی دست‌نخورده می‌ماند
    expect(s.proposalDate).toBe("۱۴۰۵/۰۴/۰۱");
    expect(s.priceAudit).toHaveLength(0);
  });
});
