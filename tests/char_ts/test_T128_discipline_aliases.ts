// ─────────────────────────────────────────────────────────────
// T128 — نگاشتِ املای ۱۱ نام رشته (فاز E-10 §۴).
// (آینهٔ test_T128_discipline_aliases.py)
//
// نامِ ۱۱ رشته در PDF رسمیِ بخشنامهٔ ۱۴۴۳۷۳ با املایِ متفاوتی از
// کلیدهای m_by_discipline در config ظاهر می‌شود (تفاوت در همزه،
// نیم‌فاصله، یا ترتیبِ شکستنِ سطرها در استخراج). جدولِ m_aliases در
// config/provisional_m.json نامِ رسمیِ PDF (canonical) را به کلیدِ config
// (alias) نگاشت می‌کند و موتور هر دو را می‌پذیرد.
//
// این آزمون قفل می‌کند:
//   ۱) هر دو املا برای هر ۱۱ نام، coef یکسانی برمی‌گردانند (دقیقاً مساوی)؛
//   ۲) trace نشان می‌دهد کدام املا استفاده شده (discipline_key)؛
//   ۳) هیچ کلیدِ موجودی از m_by_discipline حذف نشده است؛
//   ۴) نامِ ناشناخته همچنان null می‌دهد (قاعدهٔ طلایی: حدس زده نمی‌شود).
// ─────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";
import provisionalM from "../../config/provisional_m.json";
import cpiMonthly from "../../config/cpi_monthly.json";
import { provisionalCoef1405q1 } from "../../src/lib/adjustment";

type Cfg = {
  meta: {
    numerator_month: { year: string; month: string };
    denominator_months: Array<{ year: string; month: string }>;
  };
  m_by_discipline: Record<string, number>;
  m_aliases: Record<string, string>;
};

const CFG = provisionalM as unknown as Cfg;
const CPI = (cpiMonthly as unknown as {
  months: Record<string, Record<string, number>>;
}).months;

// جفت‌ها از خودِ config خوانده می‌شوند (منبعِ واحد) — کلیدِ «_note»
// توضیح است و جزو aliasها نیست.
const ALIASES = Object.entries(CFG.m_aliases).filter(
  ([k]) => !k.startsWith("_"),
);

function expectedCoef(m: number): number {
  const num = CFG.meta.numerator_month;
  const den = CFG.meta.denominator_months;
  const nV = Number(CPI[String(num.year)][String(num.month)]);
  const dVs = den.map((d) => Number(CPI[String(d.year)][String(d.month)]));
  const mean = dVs.reduce((a, b) => a + b, 0) / dVs.length;
  return 1 + m * (nV / mean - 1);
}

describe("T128 — نگاشتِ املای ۱۱ نام رشته (E-10 §۴)", () => {
  it("جدولِ alias شکلِ درست دارد (۱۱ نام، همه به کلیدِ موجود)", () => {
    expect(ALIASES).toHaveLength(11);
    expect(new Set(ALIASES.map(([c]) => c)).size).toBe(11);
    for (const [, key] of ALIASES) {
      expect(CFG.m_by_discipline).toHaveProperty(key);
    }
  });

  it("کلیدهای فعلیِ m_by_discipline حذف نشده‌اند", () => {
    expect(CFG.m_by_discipline["ابنیه"]).toBe(0.7);
    expect(CFG.m_by_discipline["توزیع نیروی برق"]).toBe(1.1);
  });

  it.each(ALIASES.map(([c, k]) => [c, k] as [string, string]))(
    "هر دو املا یک مقدار می‌دهند: %s ↔ %s",
    (cano, key) => {
      const [cCan, stCan, trCan] = provisionalCoef1405q1(cano);
      const [cKey, stKey, trKey] = provisionalCoef1405q1(key);
      expect(stCan).toBe("محاسبه‌شده");
      expect(stKey).toBe("محاسبه‌شده");
      // دقیقاً مساوی (bit-identical در همان زبان)
      expect(cCan).toBe(cKey);
      expect(cCan).toBeCloseTo(expectedCoef(CFG.m_by_discipline[key]), 12);
      // trace: نامِ درخواست‌شده و کلیدِ حل‌شده
      const tCan = trCan as { discipline: string; discipline_key: string; m: number };
      const tKey = trKey as { discipline: string; discipline_key: string; m: number };
      expect(tCan.discipline).toBe(cano);
      expect(tCan.discipline_key).toBe(key);
      expect(tKey.discipline_key).toBe(key);
      expect(tCan.m).toBe(CFG.m_by_discipline[key]);
    },
  );

  it("نامِ ناشناخته همچنان null می‌دهد", () => {
    const [cx, stx] = provisionalCoef1405q1("رشتهٔ ناشناخته");
    expect(cx).toBeNull();
    expect(stx).toBe("ناموجود");
  });

  it("مسیرِ استثنا («به جز فصل ۱۵») دست‌نخورده است", () => {
    const [c, st] = provisionalCoef1405q1("راهداری", "15");
    expect(c).toBeNull();
    expect(st).toBe("استثنا");
  });
});
