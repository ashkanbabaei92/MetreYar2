// T63 - تطابق تابع normalizeText میان تایپ‌اسکریپت و پایتون
//
// normalize.ts یک بازهٔ `^_+|_+$` اضافه داشت که در پایتون نبود؛ این بازه
// اکنون حذف شده زیرا اضافی بود (زیرخط‌ها در همان مرحلهٔ بعدی به فاصله تبدیل
// و در پایان trim می‌شوند). این تست تطابق را با golden پایتون تضمین می‌کند.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { normalizeText } from "../../src/lib/normalize";

const FIXTURE = path.join(__dirname, "..", "char_shared", "fixtures", "normalize_cases.json");
const PY_GOLDEN = path.join(__dirname, "..", "char_python", "golden", "T63_normalize.json");
const TS_GOLDEN = path.join(__dirname, "golden", "T63_normalize.json");

interface Case { id: string; input: string; }
interface Result { id: string; input: string; output: string; }

function compute(): Result[] {
  const cases: Case[] = JSON.parse(fs.readFileSync(FIXTURE, "utf-8"));
  return cases.map((c) => ({ id: c.id, input: c.input, output: normalizeText(c.input) }));
}

describe("T63 normalize parity (TS vs Python)", () => {
  it("زیرخط ابتدا/انتها مانند پایتون نرمال می‌شود", () => {
    expect(normalizeText("_بتن مگر_")).toBe(normalizeText("بتن مگر"));
    expect(normalizeText("___")).toBe("");
    expect(normalizeText("تهیه_و_اجرا")).toBe("تهیه و اجرا");
  });

  it("خروجی‌ها با golden پایتون دقیقاً برابرند", () => {
    if (!fs.existsSync(PY_GOLDEN)) {
      console.warn("Python golden وجود ندارد؛ ابتدا GENERATE=1 در سمت پایتون اجرا کنید");
      return;
    }
    const results = compute();
    const py: { cases: Result[] } = JSON.parse(fs.readFileSync(PY_GOLDEN, "utf-8"));
    expect(py.cases.length).toBe(results.length);
    for (const expected of py.cases) {
      const got = results.find((r) => r.id === expected.id)!;
      expect(got).toBeDefined();
      expect(got.output).toBe(expected.output);
    }
    fs.mkdirSync(path.dirname(TS_GOLDEN), { recursive: true });
    fs.writeFileSync(TS_GOLDEN, JSON.stringify({ cases: results }, null, 2), "utf-8");
  });
});
