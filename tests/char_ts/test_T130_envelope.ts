// ─────────────────────────────────────────────────────────────
// T130 — بازهٔ حساسیتِ واقعی (فاز E-10.1 §۱).
// (آینهٔ test_T130_envelope.py)
//
// tools/make_decision_meeting.py چهار سناریوی envelope را با اجرای همزمان
// می‌سازد و در tools/meeting_scenarios.json می‌نویسد. این آزمون قفل می‌کند:
//   ۱) انتخابِ هر سناریو با اندازه‌گیریِ فردیِ تصمیم‌ها هم‌خوان است؛
//   ۲) کمینه ≤ پایه ≤ بیشینه برای هر دو سنجه؛
//   ۳) اعداد و پهنای بازه در .md با JSON هم‌خوان‌اند؛
//   ۴) هر توصیه یک برچسبِ منبع دارد و ادعای اشتباهِ E-9 رد می‌شود.
// ─────────────────────────────────────────────────────────────
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.join(__dirname, "..", "..");
const MEET = path.join(ROOT, "tools", "meeting_scenarios.json");
const IMPACT = path.join(ROOT, "tools", "decision_impact_scenarios.json");
const MD = path.join(ROOT, "docs", "DECISION_MEETING.md");

interface MeetingPayload {
  baseline: { delta_p: number; baravord: number };
  envelope: Record<string, {
    name: string;
    metric: string;
    delta_p: number;
    baravord: number;
    flips: string[];
  }>;
}
interface ImpactPayload {
  results: Record<string, {
    d_delta_p: number | null;
    d_baravord: number | null;
  }>;
  scenarios: { id: string; kind: string }[];
}

const M = JSON.parse(fs.readFileSync(MEET, "utf-8")) as MeetingPayload;
const IMP = JSON.parse(fs.readFileSync(IMPACT, "utf-8")) as ImpactPayload;
const R = IMP.results;

const FIX_IDS = ["D-14", "D-15", "D-16"];
const SETTING_IDS = IMP.scenarios
  .filter((s) => s.kind === "setting" && !FIX_IDS.includes(s.id))
  .map((s) => s.id);
const FIX_VARIANTS = ["D-14", "D-15"];

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

type Metric = "d_delta_p" | "d_baravord";

function metricOf(id: string, metric: Metric): number | null {
  const v = (R[id] as Record<string, number | null>)[metric];
  return v === undefined ? null : v;
}

function expected(metric: Metric, wantMax: boolean): string[] {
  const out: string[] = [];
  for (const id of SETTING_IDS) {
    const d = metricOf(id, metric);
    if (d !== null && ((wantMax && d > 0) || (!wantMax && d < 0))) {
      out.push(id);
    }
  }
  const cands = FIX_VARIANTS
    .map((f) => [f, metricOf(f, metric)] as const)
    .filter((t) => t[1] !== null) as [string, number][];
  if (cands.length > 0) {
    const bf = wantMax
      ? cands.reduce((a, b) => (b[1] > a[1] ? b : a))
      : cands.reduce((a, b) => (b[1] < a[1] ? b : a));
    if ((wantMax && bf[1] > 0) || (!wantMax && bf[1] < 0)) {
      out.push(bf[0] + " [FIX]");
    }
  }
  return out;
}

describe("T130 — بازهٔ حساسیتِ واقعی (فاز E-10.1 §۱)", () => {
  const cases: [string, Metric, boolean][] = [
    ["E-min-dp", "d_delta_p", false],
    ["E-max-dp", "d_delta_p", true],
    ["E-min-bar", "d_baravord", false],
    ["E-max-bar", "d_baravord", true],
  ];
  for (const [eid, metric, wantMax] of cases) {
    it(`انتخابِ ${eid} با اندازه‌گیریِ فردی هم‌خوان است`, () => {
      expect([...M.envelope[eid].flips].sort())
        .toEqual(expected(metric, wantMax).sort());
    });
  }

  it("کمینه ≤ پایه ≤ بیشینه (ΔP و برآورد)", () => {
    const checks: [string, string, "delta_p" | "baravord"][] = [
      ["E-min-dp", "E-max-dp", "delta_p"],
      ["E-min-bar", "E-max-bar", "baravord"],
    ];
    for (const [lo, hi, key] of checks) {
      expect(M.envelope[lo][key]).toBeLessThanOrEqual(M.baseline[key]);
      expect(M.envelope[hi][key]).toBeGreaterThanOrEqual(M.baseline[key]);
    }
  });

  it("اعداد و پهنای بازه در .md با JSON هم‌خوان‌اند", () => {
    const t = readMd();
    const seg = t.split("## بازهٔ حساسیتِ واقعی")[1]
      .split("## نمودار tornado")[0];
    for (const eid of ["E-min-dp", "E-max-dp", "E-min-bar", "E-max-bar"]) {
      const v = M.envelope[eid];
      expect(seg).toContain(fmt(v.delta_p));
      expect(seg).toContain(fmt(v.baravord));
    }
    const wDp = M.envelope["E-max-dp"].delta_p - M.envelope["E-min-dp"].delta_p;
    const wBr = M.envelope["E-max-bar"].baravord
      - M.envelope["E-min-bar"].baravord;
    expect(seg).toContain(fmt(wDp));
    expect(seg).toContain(fmt(wBr));
  });

  it("ادعای اشتباهِ E-9 رد و مقادیرِ درست ذکر می‌شوند", () => {
    const seg = readMd().split("## بازهٔ حساسیتِ واقعی")[1]
      .split("## نمودار tornado")[0];
    expect(seg).toContain("۲٬۴۷۰٬۸۶۱٬۰۸۳٫۱۳");
    expect(seg).toContain("۲٬۳۳۳٬۴۶۳٬۵۸۰٫۸۴");
    const d14 = metricOf("D-14", "d_baravord") as number;
    const d15 = metricOf("D-15", "d_baravord") as number;
    expect(seg).toContain(fmt(d14));
    expect(seg).toContain(fmt(d15));
  });

  it("هر توصیه یک برچسبِ منبعِ صریح دارد", () => {
    const t = readMd();
    const table = t.split("## همهٔ تصمیم‌ها")[1].split("## تحلیل حساسیت")[0];
    const rows = [...table.matchAll(/^\| \d+ \| (D-\d\d)/gm)].map((m) => m[1]);
    expect(rows).toHaveLength(13);
    for (const lbl of [
      "[متن بخشنامه]",
      "[انتخاب مهندسی]",
      "[رویهٔ رایج، نیازمند تأیید مشاور]",
      "[وضعیت فعلی]",
      "[دادهٔ ورودی — واقعیتِ پروژه]",
    ]) {
      expect(table).toContain(lbl);
    }
    const top = t.split("## ۵ تصمیمِ اول")[1].split("## همهٔ تصمیم‌ها")[0];
    expect([...top.matchAll(/- \*\*منبع توصیه:\*\*/g)]).toHaveLength(5);
  });
});
