// ─────────────────────────────────────────────────────────────
// T129 — بستهٔ جلسهٔ تصمیم (فاز E-10 §۵).
// (آینهٔ test_T129_decision_meeting.py)
//
// tools/make_decision_meeting.py دو سند می‌سازد: docs/DECISION_MEETING.md
// و docs/DECISION_MEETING.docx. این آزمون قفل می‌کند:
//   ۱) ساختار: شش بخشِ مورد انتظار در .md؛
//   ۲) ترتیب: تصمیم‌ها مرتب بر اساس max |اثر|؛
//   ۳) اعداد: S1 = baseline، S3 = S1، شرطی = ΔPِ D-01، S2 = عددِ پین‌شده؛
//   ۴) بازه: hi − lo = spread و درصدها درست‌اند.
// ─────────────────────────────────────────────────────────────
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.join(__dirname, "..", "..");
const MD = path.join(ROOT, "docs", "DECISION_MEETING.md");
const DOCX = path.join(ROOT, "docs", "DECISION_MEETING.docx");
const SCEN = path.join(ROOT, "tools", "decision_impact_scenarios.json");

const PAYLOAD = JSON.parse(fs.readFileSync(SCEN, "utf-8")) as {
  baseline_metrics: { delta_p: number; base_total: number };
  results: Record<string, {
    kind: string;
    d_delta_p: number | null;
    d_baravord: number | null;
    d_ceiling?: number | null;
    delta_p?: number;
  }>;
};
const RESULTS = PAYLOAD.results;
const BASE_DP = PAYLOAD.baseline_metrics.delta_p;

// عددِ پین‌شدهٔ اجرای ترکیبیِ S2 (هفت گزینهٔ بِ قابلِ پیاده‌شده با هم) —
// با اجرای واقعیِ موتور در فاز E-10 §۵.
const S2_DELTA_P = 10224815159.58;

const FA = "۰۱۲۳۴۵۶۷۸۹";

function fmt(v: number, digits = 2): string {
  const s = v.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return [...s].map((c) => (/\d/.test(c) ? FA[Number(c)] : c)).join("")
    .replace(/,/g, "٬")
    .replace(/\./g, "٫");
}

function readMd(): string {
  return fs.readFileSync(MD, "utf-8");
}

function maxEffect(res: {
  d_delta_p: number | null;
  d_baravord: number | null;
  d_ceiling?: number | null;
}): number | null {
  const vals = [res.d_delta_p, res.d_baravord, res.d_ceiling ?? null]
    .filter((v): v is number => v !== null && v !== undefined)
    .map(Math.abs);
  return vals.length ? Math.max(...vals) : null;
}

describe("T129 — بستهٔ جلسهٔ تصمیم (E-10 §۵)", () => {
  it("هر دو فایل وجود دارند", () => {
    expect(fs.existsSync(MD)).toBe(true);
    expect(fs.statSync(DOCX).size).toBeGreaterThan(10_000);
  });

  it("هفت بخشِ مورد انتظار در .md موجودند", () => {
    const t = readMd();
    for (const h of [
      "# بستهٔ جلسهٔ تصمیم",
      "## ۵ تصمیمِ اول — بیشترین |اثر|",
      "## همهٔ تصمیم‌ها — مرتب بر اساس max |اثر|",
      "## تحلیل حساسیت — سه سناریو",
      "## بازهٔ حساسیتِ واقعی (envelope)",
      "## نمودار tornado",
      "## تصمیم‌های ردشده، ادغام‌شده و منتظر داده",
    ]) {
      expect(t).toContain(h);
    }
  });

  it("۵ تصمیمِ اول مرتب بر اساس max |اثر| هستند", () => {
    const t = readMd();
    const topPart = t.split("## ۵ تصمیمِ اول")[1].split("## همهٔ تصمیم‌ها")[0];
    const ids = [...topPart.matchAll(/### (D-\d\d) —/g)].map((m) => m[1]);
    expect(ids).toHaveLength(5);
    for (let i = 0; i < ids.length - 1; i++) {
      const a = maxEffect(RESULTS[ids[i]]);
      const b = maxEffect(RESULTS[ids[i + 1]]);
      expect(a).not.toBeNull();
      expect(b).not.toBeNull();
      expect(a as number).toBeGreaterThanOrEqual(b as number);
    }
  });

  it("جدولِ کامل شاملِ همهٔ تصمیم‌های باز/داده و مرتب است", () => {
    const t = readMd();
    const table = t.split("## همهٔ تصمیم‌ها")[1].split("## تحلیل حساسیت")[0];
    const ids = [...table.matchAll(/\| \d+ \| (D-\d\d)/g)].map((m) => m[1]);
    const expected = Array.from({ length: 20 }, (_, n) => `D-${String(n + 1).padStart(2, "0")}`)
      .filter((i) => RESULTS[i] && RESULTS[i].kind !== "rejected"
        && RESULTS[i].kind !== "merged");
    expect([...ids].sort()).toEqual([...expected].sort());
    const keys = ids.map((i) => {
      const v = maxEffect(RESULTS[i]);
      return [v !== null, v ?? 0] as [boolean, number];
    });
    for (let i = 0; i < keys.length - 1; i++) {
      const [ha, va] = keys[i];
      const [hb, vb] = keys[i + 1];
      expect(ha && !hb ? true : ha === hb ? va >= vb : true).toBe(true);
    }
  });

  it("اعدادِ سناریوها درست هستند", () => {
    const t = readMd();
    const lines = t.split(/\r?\n/);
    // S1 = baseline
    expect(t).toContain(fmt(BASE_DP));
    // S3 = S1
    const s3 = lines.find((ln) => ln.startsWith("| **S3**"));
    expect(s3).toBeDefined();
    expect(s3).toContain(fmt(BASE_DP));
    // شرطی = همان ΔPِ اندازه‌گیری‌شدهٔ D-01
    const cond = lines.find((ln) => ln.startsWith("| **شرطی**"));
    expect(cond).toBeDefined();
    expect(cond).toContain(fmt(RESULTS["D-01"].delta_p as number));
    // S2 = عددِ پین‌شده
    const s2 = lines.find((ln) => ln.startsWith("| **S2**"));
    expect(s2).toBeDefined();
    expect(s2).toContain(fmt(S2_DELTA_P));
  });

  it("بازه و درصدها بسامند هستند", () => {
    const t = readMd();
    const lo = BASE_DP;
    const hi = S2_DELTA_P;
    const spread = hi - lo;
    const line = t.split(/\r?\n/).find((ln) => ln.includes("بازهٔ کمینه تا بیشینهٔ ΔP"));
    expect(line).toBeDefined();
    expect(line).toContain(fmt(lo));
    expect(line).toContain(fmt(hi));
    expect(line).toContain(fmt(spread));
    expect(line).toContain(fmt((100.0 * spread) / BASE_DP));
    expect(line).toContain(
      fmt((100.0 * spread) / PAYLOAD.baseline_metrics.base_total),
    );
  });

  it("یادداشتِ هم‌کنش (جمع‌زدن ممنوع) موجود است", () => {
    const t = readMd();
    const flips = ["D-01", "D-03", "D-04", "D-08", "D-09", "D-10", "D-13"];
    const naive = flips.reduce(
      (s, i) => s + (RESULTS[i].d_delta_p as number),
      0,
    );
    expect(t).toContain("هم‌کنش");
    expect(t).toContain(fmt(naive));
  });

  it("tornado هر تصمیمِ قابلِ اندازه‌گیری به‌جز D-18 را دارد", () => {
    const t = readMd();
    const tor = t.split("## نمودار tornado")[1].split("## تصمیم‌های ردشده")[0];
    const ids = [...tor.matchAll(/^\| (D-\d\d) \|/gm)].map((m) => m[1]);
    expect(ids).not.toContain("D-18");
    const want = Array.from(
      { length: 20 },
      (_, n) => `D-${String(n + 1).padStart(2, "0")}`,
    ).filter(
      (i) => RESULTS[i] && RESULTS[i].d_delta_p !== null && i !== "D-18",
    );
    expect([...ids].sort()).toEqual([...want].sort());
  });

  it("جهتِ نوارهای tornado با علامتِ بزرگ‌ترین کانال هم‌خوان است", () => {
    const t = readMd();
    const tor = t.split("## نمودار tornado")[1].split("## تصمیم‌های ردشده")[0];
    for (const ln of tor.split(/\r?\n/)) {
      const m = /^\| (D-\d\d) \| [^|]+\| ([−+])[^|]+\| (.*?)\|/.exec(ln);
      if (!m) continue;
      const [, did, sign, bar] = m;
      const d = RESULTS[did];
      const vals = [d.d_delta_p, d.d_baravord].filter(
        (v): v is number => v !== null && v !== undefined,
      );
      if (!vals.length) continue;
      const v = vals.reduce((a, b) => (Math.abs(b) > Math.abs(a) ? b : a));
      if (v === 0) continue;
      const neg = v < 0;
      expect(sign === "−").toBe(neg);
      expect(bar.includes("◄")).toBe(neg);
      expect(bar.includes("►")).toBe(!neg);
    }
  });
});
