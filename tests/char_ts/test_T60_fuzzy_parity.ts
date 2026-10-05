// T60 - تطبیق پاریتی موتور فازی میان تایپ‌اسکریپت و پایتون
//
// هدف: اطمینان از اینکه `fuzzyScore`/`tokenSetRatio` در src/lib/matching.ts
// برای ورودی یکسان، دقیقاً همان امتیاز `fuzzy_match`/`_token_set_ratio` در
// app.py را می‌دهد. golden مرجع با محاسبهٔ واقعی موتور پایتون تولید شده
// (GENERATE=1 در سمت پایتون)؛ این تست باید دقیقاً به آن برسد.
//
// موارد: الگوریتم‌های divergent بین LCS و difflib (adv_*)، فارسی واقعی،
// رشته‌های بلند برای autojunk، و حالت‌های تهی.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { fuzzyScore, tokenSetRatio } from "../../src/lib/matching";

const FIXTURE = path.join(__dirname, "..", "char_shared", "fixtures", "fuzzy_parity_cases.json");
const PY_GOLDEN = path.join(__dirname, "..", "char_python", "golden", "T60_fuzzy_parity.json");
const TS_GOLDEN = path.join(__dirname, "golden", "T60_fuzzy_parity.json");

interface Case { id: string; a: string; b: string; }
interface Scored { id: string; a: string; b: string; fuzzy_score: number; token_set_ratio: number; }

function compute(): Scored[] {
  const cases: Case[] = JSON.parse(fs.readFileSync(FIXTURE, "utf-8"));
  return cases.map((c) => ({
    id: c.id, a: c.a, b: c.b,
    fuzzy_score: round(fuzzyScore(c.a, c.b), 6),
    token_set_ratio: round(tokenSetRatio(c.a, c.b), 6),
  }));
}

function round(n: number, d: number): number {
  const f = Math.pow(10, d);
  return Math.round(n * f) / f;
}

describe("T60 fuzzy parity (TS vs Python)", () => {
  it("scores match the Python golden exactly", () => {
    if (!fs.existsSync(PY_GOLDEN)) {
      console.warn("Python golden وجود ندارد؛ ابتدا GENERATE=1 در سمت پایتون اجرا کنید");
      return;
    }
    const results = compute();
    const py: { cases: Scored[] } = JSON.parse(fs.readFileSync(PY_GOLDEN, "utf-8"));
    expect(py.cases.length).toBe(results.length);
    for (const expected of py.cases) {
      const got = results.find((r) => r.id === expected.id)!;
      expect(got).toBeDefined();
      expect(got.fuzzy_score).toBe(expected.fuzzy_score);
      expect(got.token_set_ratio).toBe(expected.token_set_ratio);
    }
    // ثبت golden سمت TS برای قابلیت ردیابی
    fs.mkdirSync(path.dirname(TS_GOLDEN), { recursive: true });
    fs.writeFileSync(TS_GOLDEN, JSON.stringify({ cases: results }, null, 2), "utf-8");
  });
});
