// T126 — فاز E-10 §۱ — قفلِ اعداد مرجع به docs/REFERENCE_NUMBERS.md
// (آینهٔ test_T126_reference_pin.py)
//
// این آزمون همهٔ اعداد مرجع را با اجرایِ خطِ لولهٔ کاملِ پروژهٔ مرجع
// بازمحاسبه می‌کند و با بلوکِ JSONِ fenced در docs/REFERENCE_NUMBERS.md
// مقایسه می‌کند. **اگر کسی موتور را طوری تغییر دهد که این اعداد تغییر
// کنند و REFERENCE_NUMBERS.md را به‌روز نکند، این آزمون قرمز می‌شود.**
//
// ریشهٔ تغییرِ ΔP از ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴ به ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲: commit 8760bd3
// (baseline: E-6 complete) — گردکردنِ بند ۸-۲ بخشنامهٔ ۲۰۸۰ پیش‌فرض شد.
// اختلاف = +۴۶٬۸۶۹٬۵۳۰٫۵۸ (= D-03).
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const REF_MD = path.join(ROOT, "docs", "REFERENCE_NUMBERS.md");

const PROV_COEF = 1.1530518586507572;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹";
const WP_MIX: [string, string] = ["۱۴۰۴/۰۱/۰۱", "۱۴۰۵/۰۲/۱۵"];
const WP_ALLDEF: [string, string] = ["۱۴۰۴/۰۱/۰۱", "۱۴۰۴/۱۲/۲۹"];

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

function pipeline(extra: Partial<ProjectSettings> = {}): ProjectResult {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .filter((f) => f.endsWith(".txt"))
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows: unknown[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const sd = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(sd).isDirectory()) continue;
    for (const fn of fs.readdirSync(sd).sort()) {
      if (!fn.endsWith(".txt")) continue;
      (rows as unknown[]).push(
        ...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows,
      );
    }
  }
  return computeProject(
    tables,
    OFFICIAL_1404_FEHREST,
    { ...defaultSettings(), ...extra },
    {
      rows: rows as never,
      format: "v2",
      recordCount: rows.length,
      warnings: [],
    } as never,
  );
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    proposalDate: PROPOSAL_DATE,
    ...extra,
  };
}

/** خواندنِ بلوکِ JSONِ fenced از REFERENCE_NUMBERS.md */
function pinned(): Record<string, number> {
  const txt = fs.readFileSync(REF_MD, "utf-8");
  const m = /```json\r?\n([\s\S]*?)\r?\n```/.exec(txt);
  expect(m, "بلوکِ JSON در docs/REFERENCE_NUMBERS.md پیدا نشد").toBeTruthy();
  return JSON.parse(m![1]);
}

const KEYS = [
  "base_total",
  "grand_total",
  "dp_total",
  "dp_definitive",
  "dp_provisional",
  "dp_fallback",
  "baravord_q4",
  "baravord_1405q1",
] as const;

function r2(x: number): number {
  return Math.round(x * 100) / 100;
}

describe("T126 — قفلِ اعداد مرجع", () => {
  it("اعدادِ موتور با REFERENCE_NUMBERS.md مطابق‌اند", () => {
    const doc = pinned();
    expect(Object.keys(doc).sort()).toEqual([...KEYS].sort());

    const got: Record<string, number> = {};

    const r0 = pipeline();
    got.base_total = r2(r0.baseTotal);
    got.grand_total = r2(r0.grandTotal);

    const r1 = pipeline(
      on({
        baravordEnabled: true,
        workPeriodStart: WP_MIX[0],
        workPeriodEnd: WP_MIX[1],
        provisionalCoef1405q1: PROV_COEF,
      }),
    );
    const t = r1.adjustment.tadil;
    expect(t, "موتور تعدیل باید روشن باشد").toBeTruthy();
    got.dp_total = r2(t!.delta_p);
    got.dp_definitive = r2(t!.delta_p_definitive);
    got.dp_provisional = r2(t!.delta_p_provisional);

    // یکپارچگیِ داخلی: قطعی + علی‌الحساب ≡ مجموع
    expect(got.dp_definitive + got.dp_provisional).toBeCloseTo(
      got.dp_total,
      6,
    );

    const r2x = pipeline(
      on({ provisionalCoef1405q1: PROV_COEF }),
    );
    got.dp_fallback = r2(r2x.adjustment.tadil!.delta_p);
    expect(
      r2x.warnings.some((w) => w.item === "work_period_missing_for_it"),
      "دورهٔ کارکردِ خالی باید هشدارِ work_period_missing_for_it بدهد",
    ).toBe(true);

    const r3 = pipeline(
      on({
        baravordEnabled: true,
        baravordItPeriod: "q4",
        workPeriodStart: WP_ALLDEF[0],
        workPeriodEnd: WP_ALLDEF[1],
        provisionalCoef1405q1: PROV_COEF,
      }),
    );
    got.baravord_q4 = r2(r3.adjustment.baravord!.grand_updated);

    const r4 = pipeline(
      on({
        baravordEnabled: true,
        baravordItPeriod: "1405Q1",
        workPeriodStart: WP_ALLDEF[0],
        workPeriodEnd: WP_ALLDEF[1],
        provisionalCoef1405q1: PROV_COEF,
      }),
    );
    got.baravord_1405q1 = r2(r4.adjustment.baravord!.grand_updated);

    const bad = KEYS.filter((k) => doc[k] !== got[k]);
    expect(
      bad,
      "اعداد مرجع با docs/REFERENCE_NUMBERS.md مطابق نیستند — اگر موتور " +
        "را تغییر داده‌اید، آن سند را هم به‌روز کنید: " +
        bad.map((k) => `${k}: سند=${doc[k]} موتور=${got[k]}`).join("؛ "),
    ).toEqual([]);
  });

  it("ریشهٔ تغییرِ ΔP: گردکردن ۸-۲ ⇒ +۴۶٬۸۶۹٬۵۳۰٫۵۸ (= D-03)", () => {
    const mk = (rounding: boolean) =>
      pipeline(
        on({
          baravordEnabled: true,
          workPeriodStart: WP_MIX[0],
          workPeriodEnd: WP_MIX[1],
          provisionalCoef1405q1: PROV_COEF,
          coefRounding2080: rounding,
        }),
      );
    const dOn = mk(true).adjustment.tadil!.delta_p;
    const dOff = mk(false).adjustment.tadil!.delta_p;
    expect(r2(dOn)).toBe(9984277408.22);
    expect(r2(dOff)).toBe(9937407877.64);
    expect(r2(dOn - dOff)).toBe(46869530.58);
  });
});
