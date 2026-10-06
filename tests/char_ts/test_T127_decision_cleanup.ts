// ─────────────────────────────────────────────────────────────
// T127 — پاک‌سازیِ فهرستِ تصمیم‌ها (فاز E-10 §۳).
// (آینهٔ test_T127_decision_cleanup.py)
//
// بعد از این فاز هیچ گزینه‌ای در DECISION_SHEET.md نماند که در کد قابلِ
// اجرا نباشد. این آزمون قفل می‌کند:
//   ۱) شش تصمیمِ «ردشده در طراحی» از DECISION_SHEET حذف شده‌اند؛
//   ۲) D-11 به‌جای حذف، «ادغام‌شده در D-13» است و شناسه‌ها باز‌شماری نشده‌اند؛
//   ۳) فلگِ D-04 وجود دارد و رفتارِ گردکردنِ منفی درست است.
// ─────────────────────────────────────────────────────────────
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { defaultSettings } from "../../src/lib/engine";
import { roundCoef2080 } from "../../src/lib/adjustment";

const ROOT = path.join(__dirname, "..", "..");
const SHEET = path.join(ROOT, "docs", "DECISION_SHEET.md");
const PENDING = path.join(ROOT, "docs", "PENDING_DECISIONS.md");

// تصمیم‌هایی که در فاز E-10 §۳ «ردشده در طراحی» شدند و از DECISION_SHEET
// حذف شده‌اند (ولی شناسه‌ها در PENDING_DECISIONS باقی می‌مانند).
const REJECTED = ["D-02", "D-05", "D-06", "D-07", "D-12", "D-17"];

// تصمیم‌هایی که هنوز در DECISION_SHEET هستند (۱۲ تصمیمِ باز + D-01 + D-11).
const REMAINING = [
  "D-01", "D-03", "D-04", "D-08", "D-09", "D-10", "D-11",
  "D-13", "D-14", "D-15", "D-16", "D-18", "D-19", "D-20",
];

const ID_RE = /^## (D-\d\d)\b/;
const ROW_RE = /^\|\s*(D-\d\d)\s*\|/;

function read(p: string): string {
  return fs.readFileSync(p, "utf-8");
}

function headings(p: string): string[] {
  return read(p)
    .split(/\r?\n/)
    .map((ln) => ln.trim())
    .flatMap((ln) => {
      const m = ID_RE.exec(ln);
      return m ? [m[1]] : [];
    });
}

function registryIds(p: string): string[] {
  const out: string[] = [];
  for (const ln of read(p).split(/\r?\n/)) {
    const m = ROW_RE.exec(ln);
    if (m) out.push(m[1]);
  }
  return [...new Set(out)];
}

function section(p: string, did: string): string {
  const lines = read(p).split(/\r?\n/);
  const out: string[] = [];
  let on = false;
  for (const ln of lines) {
    if (ID_RE.test(ln.trim())) {
      on = ln.trim().startsWith(`## ${did} `);
      continue;
    }
    if (on) out.push(ln);
  }
  return out.join("\n");
}

describe("T127 — پاک‌سازیِ فهرستِ تصمیم‌ها (E-10 §۳)", () => {
  it("تصمیم‌های ردشده از DECISION_SHEET حذف شده‌اند", () => {
    const hs = headings(SHEET);
    for (const did of REJECTED) {
      expect(hs).not.toContain(did);
    }
  });

  it("شناسه‌ها حذف یا باز‌شماری نشده‌اند (هر ۲۰ در رجیستری)", () => {
    const ids = registryIds(PENDING).sort();
    expect(ids).toEqual(
      Array.from({ length: 20 }, (_, i) => `D-${String(i + 1).padStart(2, "0")}`).sort(),
    );
  });

  it("D-11 ادغام‌شده در D-13 است (حذف نشده)", () => {
    const sec = section(SHEET, "D-11");
    expect(sec.length).toBeGreaterThan(0);
    expect(sec).toContain("D-13");
    expect(sec.replace("ادغام‌شده", "ادغام")).toContain("ادغام");
    // متنِ کاملِ گزینه‌ها فقط یک‌بار (در D-13) آمده است
    expect(section(SHEET, "D-13").split("گزینهٔ الف").length - 1).toBe(1);
  });

  it("DECISION_SHEET فقط تصمیم‌های قابلِ اجرا را دارد", () => {
    expect(headings(SHEET).sort()).toEqual([...REMAINING].sort());
  });

  it("فلگِ D-04 در تنظیماتِ پیش‌فرض وجود دارد (away_from_zero)", () => {
    const s = defaultSettings();
    expect(s.negativeCoefRounding).toBe("away_from_zero");
    expect(s.coefRounding2080).toBe(true);
  });

  it.each([
    [0.125, 0.13, 0.13],
    [-0.125, -0.13, -0.12],
    [-0.124, -0.12, -0.12],
    [-0.126, -0.13, -0.12],
    [0.0, 0.0, 0.0],
  ])(
    "گردکردنِ منفی: %s ⇒ الف %s، ب %s",
    (x, away, toward) => {
      expect(roundCoef2080(x)).toBe(away);
      expect(roundCoef2080(x, false)).toBe(away);
      expect(roundCoef2080(x, true)).toBe(toward);
    },
  );
});
