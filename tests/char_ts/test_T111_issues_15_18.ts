/**
 * T111 — ایرادهای ۱۵ تا ۱۸ (سندِ خلاصهٔ ۱۲ مرحله، خارج از مخزن).
 *
 * ایرادهای ۱۵ (اعدادِ مرحلهٔ ۸ و ۹ کپی هم‌اند)، ۱۶ (جمعِ بخش ۲ مرحلهٔ ۱۱ باید
 * ۵۵− باشد نه ۴۸−)، ۱۷ («۲۹٫۷۵T» → «۲۹٫۷۵B») و ۱۸ («۰۲۸xxxx» → «۲۸xxxx»)
 * همگی به سندی خارج از مخزن اشاره دارند (ACCEPTANCE §۱۸-۸-۳). این فایل
 * جایگاهِ آزمونِ آن‌ها را نگه می‌دارد. وقتی سند رسید:
 *
 * ۱. `ISSUES_DOC_AVAILABLE = true` کنید.
 * ۲. فقط مقدارهای `EXPECTED_15_18` را با سند تطبیق دهید.
 * ۳. آزمونِ xfail به xpass (سبز) تبدیل می‌شود.
 *
 * تا آن موقع، طبق قاعدهٔ طلایی، هیچ عددی حدس زده نمی‌شود.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const ROOT = path.resolve(__dirname, "..", "..");

// ── پرچمِ رسیدنِ سند. فقط این مقدار و مقدارهای زیر عوض می‌شوند. ──
export const ISSUES_DOC_AVAILABLE = false;

// مقدارهای مورد انتظار پس از رسیدنِ سند (فعلاً خودِ خواستهٔ کاربر).
export const EXPECTED_15_18: Record<number, string> = {
  15: "اعدادِ مرحلهٔ ۸ و ۹ باید یکتا باشند (الان کپیِ هم‌اند)",
  16: "جمعِ بخش ۲ مرحلهٔ ۱۱ باید ۵۵− باشد (الان ۴۸−)",
  17: "مقدار «۲۹٫۷۵T» باید به «۲۹٫۷۵B» تصحیح شود",
  18: "کدهای «۰۲۸xxxx» باید به «۲۸xxxx» تصحیح شوند",
};

// الگوهای متمایزی که نباید در مخزن باشند (مگر پس از تصحیح).
const SUSPECT_PATTERNS = ["۲۹٫۷۵T", "۰۲۸"];

// فقط کد و داده (نه مستندات .md و نه تست‌ها — آن‌ها این الگوها را
// به‌صورتِ متنی مستند می‌کنند).
const SCAN_DIRS = ["src", "config", "data"];
const SCAN_FILE = "app.py";
const SCAN_EXT = /\.(ts|js|json|csv|txt)$/;

function* walk(dir: string): Generator<string> {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === "node_modules" || e.name === "__pycache__") continue;
      yield* walk(full);
    } else if (SCAN_EXT.test(e.name)) {
      yield full;
    }
  }
}

function* repoFiles(): Generator<string> {
  for (const d of SCAN_DIRS) {
    yield* walk(path.join(ROOT, d));
  }
  const appPy = path.join(ROOT, SCAN_FILE);
  if (fs.existsSync(appPy)) yield appPy;
}

describe("T111 — ایرادهای ۱۵ تا ۱۸ (سند خارج از مخزن)", () => {
  it("ثبتِ کامل: هر ۴ ایراد با کلیدهای ۱۵..۱۸", () => {
    expect(Object.keys(EXPECTED_15_18).map(Number).sort((a, b) => a - b))
      .toEqual([15, 16, 17, 18]);
  });

  it("مقدارِ مورد انتظار برای هر ایراد ثبت و غیرخالی است", () => {
    for (const [key, text] of Object.entries(EXPECTED_15_18)) {
      expect(typeof text, key).toBe("string");
      expect(text.trim().length, key).toBeGreaterThan(0);
    }
  });

  it.fails("وقتی سند برسد و ISSUES_DOC_AVAILABLE=true شود، این آزمون سبز می‌شود", () => {
    // xfailِ فعلی: سند هنوز نرسیده — ACCEPTANCE §۱۸-۸-۳
    expect(ISSUES_DOC_AVAILABLE).toBe(true);
  });

  it("الگوهای مشکوک در کد/داده نیستند — تصحیحِ حدسی نشده", () => {
    const hits: Array<[string, string]> = [];
    for (const f of repoFiles()) {
      let text: string;
      try {
        text = fs.readFileSync(f, "utf-8");
      } catch {
        continue;
      }
      for (const pat of SUSPECT_PATTERNS) {
        if (text.includes(pat)) {
          hits.push([path.relative(ROOT, f), pat]);
        }
      }
    }
    expect(hits, "الگوی مشکوک در مخزن پیدا شد").toEqual([]);
  });
});
