// T64 - رفتار سخت‌گیرانهٔ record(): golden مفقود باید FAIL شود، نه ساخته شود.
//
// قبل از این، record() در نبود golden آن را خاموش از مقدار فعلی می‌ساخت و
// تست بی‌صدا پاس می‌شد — یعنی حذف تصادفی یک golden رگرسیون را پنهان می‌کرد.
// اکنون ساختن فقط با پرچم صریح (GENERATE / UPDATE_GOLDENS) مجاز است.
import { describe, it, expect, afterEach } from "vitest";
import * as fs from "fs";
import { goldenPath, record, loadJson } from "./helper";

const TID_THROW = "T64_strict_probe";
const TID_FLAGGED = "T64_strict_probe_flagged";
const TID_OVERWRITE = "T64_strict_probe_overwrite";

afterEach(() => {
  for (const t of [TID_THROW, TID_FLAGGED, TID_OVERWRITE]) {
    const p = goldenPath(t);
    if (fs.existsSync(p)) fs.rmSync(p);
  }
});

describe("T64 strict golden behavior", () => {
  it("بدون پرچم، golden مفقود باید خطا بدهد", () => {
    const gp = goldenPath(TID_THROW);
    expect(fs.existsSync(gp)).toBe(false);
    expect(() => record(TID_THROW, { probe: 1 })).toThrowError(/golden مفقود/);
    expect(fs.existsSync(gp)).toBe(false);
  });

  it("با پرچم UPDATE_GOLDENS، golden ساخته و سپس مقایسه می‌شود", () => {
    const gp = goldenPath(TID_FLAGGED);
    expect(fs.existsSync(gp)).toBe(false);
    process.env.UPDATE_GOLDENS = "1";
    try {
      const created = record(TID_FLAGGED, { probe: 2 });
      expect(created.status).toBe("golden_created");
      expect(fs.existsSync(gp)).toBe(true);
      delete process.env.UPDATE_GOLDENS;
      const cmp = record(TID_FLAGGED, { probe: 2 });
      expect(cmp.status).toBe("compare");
    } finally {
      delete process.env.UPDATE_GOLDENS;
    }
  });

  it("با پرچم GENERATE، golden موجود بازنویسی می‌شود", () => {
    const gp = goldenPath(TID_OVERWRITE);
    expect(fs.existsSync(gp)).toBe(false);
    try {
      record(TID_OVERWRITE, { version: 1 }, true);
      expect(loadJson(gp).version).toBe(1);
      const out = record(TID_OVERWRITE, { version: 2 }, true);
      expect(out.status).toBe("golden_updated");
      expect(loadJson(gp).version).toBe(2);
      const cmp = record(TID_OVERWRITE, { version: 2 });
      expect(cmp.status).toBe("compare");
    } finally {
      if (fs.existsSync(gp)) fs.rmSync(gp);
    }
  });
});
