// T61 - پشتیبانی از انکودینگ‌های غیر UTF-8 (مرحلهٔ ۳)
//
// زنجیرهٔ رمزگشایی `decodeText`: UTF-8-BOM → UTF-8 → Windows-1256.
// هیچ فایل ورودی واقعی پروژه غیر از UTF-8 نیست، ولی خروجی Revit در
// ویندوز فارسی‌محورِ قدیمی می‌تواند cp1256 باشد؛ این تست آن مسیر را
// پوشش می‌دهد. fixture مشترک با سمت پایتون (char_shared) است.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { decodeText } from "../../src/lib/decode";
import { normalizeText } from "../../src/lib/normalize";

const FIXTURE = path.join(__dirname, "..", "char_shared", "fixtures", "encoding_samples.json");

interface Sample {
  id: string; text: string; text_cp1256: string;
  utf8_hex: string; utf8_bom_hex: string; cp1256_hex: string;
}

const SAMPLES: Sample[] = JSON.parse(fs.readFileSync(FIXTURE, "utf-8"));

function fromHex(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return out;
}

describe("T61 encoding support", () => {
  it("utf-8 (no BOM)", () => {
    for (const s of SAMPLES) {
      expect(decodeText(fromHex(s.utf8_hex))).toBe(s.text);
    }
  });

  it("utf-8 with BOM (خروجی واقعی Revit)", () => {
    for (const s of SAMPLES) {
      expect(decodeText(fromHex(s.utf8_bom_hex))).toBe(s.text);
    }
  });

  it("windows-1256 (ی فارسی به‌صورت ی عربی U+064A)", () => {
    for (const s of SAMPLES) {
      expect(decodeText(fromHex(s.cp1256_hex))).toBe(s.text_cp1256);
    }
  });

  it("فایل cp1256 بعد از normalize با فایل UTF-8 یکسان می‌شود", () => {
    for (const s of SAMPLES) {
      expect(normalizeText(decodeText(fromHex(s.cp1256_hex)))).toBe(normalizeText(s.text));
    }
  });
});
