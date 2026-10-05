import * as fs from "fs";
import * as path from "path";
import { toEnDigits } from "../../src/lib/normalize";

export const FIXTURES_DIR = path.join(__dirname, "fixtures");
export const OUTPUT_DIR = path.join(__dirname, "output");
export const GOLDEN_DIR = path.join(__dirname, "golden");

export function loadFixture(name: string): string {
  return fs.readFileSync(path.join(FIXTURES_DIR, name), "utf-8");
}

export function loadJsonFixture(name: string): any {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), "utf-8"));
}

export function saveJson(data: any, filename: string, dir?: string): string {
  const target = dir || OUTPUT_DIR;
  fs.mkdirSync(target, { recursive: true });
  const filepath = path.join(target, filename);
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2), "utf-8");
  return filepath;
}

export function loadJson(filepath: string): any {
  return JSON.parse(fs.readFileSync(filepath, "utf-8"));
}

export function goldenPath(testId: string): string {
  return path.join(GOLDEN_DIR, `${testId}.json`);
}

export function record(testId: string, data: any, generate: boolean = false): any {
  const gp = goldenPath(testId);
  // ساختن golden فقط با پرچم صریح مجاز است — golden مفقود باید تست را FAIL کند
  // تا رگرسیون‌ها پنهان نمانند.
  const allowCreate = generate || process.env.UPDATE_GOLDENS === "1";
  if (!fs.existsSync(gp)) {
    if (!allowCreate) {
      throw new Error(
        `golden مفقود: «${gp}». اگر این رفتار جدید و مورد انتظار است، ` +
        `آن را با GENERATE=1 یا UPDATE_GOLDENS=1 بسازید. ساختن خاموش ` +
        `golden ممنوع است (رگرسیون پنهان می‌شود).`);
    }
    saveJson(data, `${testId}.json`, GOLDEN_DIR);
    return { status: "golden_created", path: gp };
  }
  if (generate) {
    // بازنویسی صریح golden موجود (تولید دوبارهٔ عمدی)
    saveJson(data, `${testId}.json`, GOLDEN_DIR);
    return { status: "golden_updated", path: gp };
  }
  const existing = loadJson(gp);
  return { status: "compare", golden: existing, actual: data };
}

export function excludeId(result: any): any {
  if (result && typeof result === "object") {
    const { id, ...rest } = result;
    return rest;
  }
  return result;
}

export function excludeIdFromArray(results: any[]): any[] {
  return results.map((r) => excludeId(r));
}
