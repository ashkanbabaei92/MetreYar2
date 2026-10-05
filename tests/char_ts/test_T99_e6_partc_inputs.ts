// ─────────────────────────────────────────────────────────────
// T99 — فاز E-6 Part C (گام ۱): ورودی‌های قرارداد در تنظیمات
// (آینهٔ test_T99_e6_partc_inputs.py — پاریتی کامل).
//
// بندهای مرجع (بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰):
//   ۱-۶-۱/۱-۶-۲: روش شاخص مبنا (baseIndexMethod، finalOfferDate)
//   ۲-۱/۲-۲:     مسیر رشته‌ای/گروهی (indexMethod، contractInitialAmount)
//   ۲-۵:         مدت پیمان و تمدیدها (contractDurationMonths، contractExtensions)
//   ۲-۶:         آخرین صورت‌وضعیت موقت (lastProvisionalDate)
//   ۶/۷:         وضعیت خاتمه (contractStatus)
//   نامه-۶:      سقف ۱۰٪ (contractInitialAmount)
//
// قاعدهٔ طلاییِ این گام: پیش‌فرض‌ها طوری انتخاب شده‌اند که هیچ‌کدام از
// اعداد مرجعِ پروژه تغییر نمی‌کنند.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import * as path from "node:path";
import { defaultSettings } from "../../src/lib/engine";
import {
  copyProject,
  loadProjectProfileJson,
  projectProfilePayload,
  type ContractExtension,
} from "../../src/lib/manualEntries";
import { SETTING_LABELS } from "../../src/lib/auditDiff";
import type { ProjectSettings } from "../../src/lib/types";

const NEW_FIELDS: Record<string, unknown> = {
  baseIndexMethod: "proposal_period",
  finalOfferDate: "",
  contractDurationMonths: null,
  contractExtensions: [],
  contractStatus: "فعال",
  contractInitialAmount: null,
  indexMethod: "گروهی",
  lastProvisionalDate: "",
};

describe("T99 فاز E-6 Part C — ورودی‌های قرارداد", () => {
  it("پیش‌فرض‌های خنثی برای همهٔ فیلدهای جدید", () => {
    const s = defaultSettings();
    for (const [k, v] of Object.entries(NEW_FIELDS)) {
      expect(k in s).toBe(true);
      expect((s as unknown as Record<string, unknown>)[k]).toEqual(v);
    }
  });

  it("هر فیلد جدید در سابقهٔ ویرایش برچسب فارسی دارد", () => {
    for (const k of Object.keys(NEW_FIELDS)) {
      expect(k in SETTING_LABELS).toBe(true);
      expect((SETTING_LABELS as Record<string, string>)[k].trim().length).toBeGreaterThan(0);
    }
  });

  it("copyProject: تاریخ‌ها/تمدیدها/وضعیت پاک، فلگ‌ها و شاخص‌های دستی می‌مانند", () => {
    const s: ProjectSettings = {
      ...defaultSettings(),
      finalOfferDate: "۱۴۰۳/۱۲/۲۰",
      lastProvisionalDate: "۱۴۰۵/۰۱/۰۱",
      contractDurationMonths: 14,
      contractExtensions: [
        { date: "۱۴۰۴/۰۶/۰۱", months: 2, kind: "مجاز", docNo: "ت-۱" },
      ],
      contractStatus: "فسخ با قصور",
      contractInitialAmount: 4e9,
      indexMethod: "خودکار",
      baseIndexMethod: "fehrest_period",
      completedWithinTerm: true,
      chapterIndexManual: { "06": { io: 7273.8, it: 10632.1, src: "پیوست ۳" } },
      disciplineIndexManual: { io: 5000.0, it: 8000.0 },
      coefRounding2080: false,
      floorsData: { Story1: 120.0, Story2: 100.0 },
      manualPrices: { "A-1": { price: 1000.0, source: "بخشنامه" } },
    };
    const { settings: ns } = copyProject(s, { projectName: "پروژه نمونه" });
    // پاک می‌شوند
    expect(ns.finalOfferDate).toBe("");
    expect(ns.lastProvisionalDate).toBe("");
    expect(ns.contractExtensions).toEqual([]);
    expect(ns.contractStatus).toBe("فعال");
    expect(ns.contractDurationMonths).toBeNull();
    expect(ns.completedWithinTerm).toBeNull();
    expect(Object.keys(ns.floorsData).length).toBe(0);
    // می‌مانند
    expect(ns.contractInitialAmount).toBe(4e9);
    expect(ns.indexMethod).toBe("خودکار");
    expect(ns.baseIndexMethod).toBe("fehrest_period");
    expect(ns.coefRounding2080).toBe(false);
    expect(ns.chapterIndexManual["06"].io).toBeCloseTo(7273.8, 9);
    // گام ۸: منبعِ شاخص دستی هم می‌مانَد
    expect(ns.chapterIndexManual["06"].src).toBe("پیوست ۳");
    expect(ns.disciplineIndexManual.io).toBeCloseTo(5000.0, 9);
    expect(ns.manualPrices["A-1"].price).toBeCloseTo(1000.0, 9);
  });

  it("پروفایل همهٔ فیلدهای جدید را حمل می‌کند (round-trip)", () => {
    const ext: ContractExtension = {
      date: "۱۴۰۴/۰۳/۰۱", months: 3, kind: "غیرمجاز", docNo: "ت-۲",
    };
    const s: ProjectSettings = {
      ...defaultSettings(),
      baseIndexMethod: "no_base_list",
      finalOfferDate: "۱۴۰۳/۱۲/۲۰",
      contractDurationMonths: 9,
      contractExtensions: [ext],
      contractStatus: "خاتمه بدون قصور",
      contractInitialAmount: 4e9,
      indexMethod: "رشته‌ای",
      lastProvisionalDate: "۱۴۰۵/۰۲/۰۱",
      chapterIndexManual: {
        "06": { io: 7273.8, it: 10632.1, src: "پیوست ۳، صفحهٔ ۸۲" },
      },
      disciplineIndexManual: { io: 5000.0, it: 8000.0, src: "نامهٔ کارفرما" },
    };
    const payload = projectProfilePayload(s, {
      projectName: "P",
      reportNo: "۱", reportType: "", periodStart: "", periodEnd: "",
      contractNo: "", contractDate: "", location: "",
      employer: "", contractor: "", consultant: "",
    } as never);
    const text = JSON.stringify(payload, null, 1);
    const back = loadProjectProfileJson(text);
    expect(back.settings.baseIndexMethod).toBe("no_base_list");
    expect(back.settings.finalOfferDate).toBe("۱۴۰۳/۱۲/۲۰");
    expect(back.settings.contractDurationMonths).toBe(9);
    expect(back.settings.contractExtensions).toEqual([ext]);
    expect(back.settings.contractStatus).toBe("خاتمه بدون قصور");
    expect(back.settings.contractInitialAmount).toBe(4e9);
    expect(back.settings.indexMethod).toBe("رشته‌ای");
    expect(back.settings.lastProvisionalDate).toBe("۱۴۰۵/۰۲/۰۱");
    // گام ۸: منبعِ شاخص دستی در round-trip می‌مانَد
    expect(back.settings.chapterIndexManual).toEqual({
      "06": { io: 7273.8, it: 10632.1, src: "پیوست ۳، صفحهٔ ۸۲" },
    });
    expect(back.settings.disciplineIndexManual).toEqual({
      io: 5000.0, it: 8000.0, src: "نامهٔ کارفرما",
    });
  });

  it("سه نوع تأخیر بند ۲-۵ و سه وضعیت خاتجهٔ بندهای ۶/۷", () => {
    const kinds: ContractExtension["kind"][] = ["مجاز", "غیرمجاز", "تعیین‌نشده"];
    for (const kind of kinds) {
      const ext: ContractExtension = {
        date: "۱۴۰۴/۰۱/۰۱", months: 1, kind, docNo: "",
      };
      expect(kinds).toContain(ext.kind);
    }
    const statuses: ProjectSettings["contractStatus"][] = [
      "فعال", "خاتمه بدون قصور", "فسخ با قصور",
    ];
    for (const st of statuses) {
      const s: ProjectSettings = { ...defaultSettings(), contractStatus: st };
      expect(s.contractStatus).toBe(st);
    }
  });
});
