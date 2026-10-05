// ─────────────────────────────────────────────────────────────
// موتور تطبیق فازی متن فارسی — معادل سبکِ RapidFuzz
// ترکیب: Token-Set Ratio + SequenceMatcher Ratio + امتیاز عددی
// (تطبیق کامل با `app.py`: difflib.SequenceMatcher(None, a, b).ratio())
// ─────────────────────────────────────────────────────────────
import { normalizeText } from "./normalize";
import type { FehrestRow } from "./types";

// ─────────────────────────────────────────────────────────────
// نسبت شباهت ترتیبی ۰ تا ۱
//
// پیاده‌سازی دقیقِ `difflib.SequenceMatcher(None, a, b).ratio()` پایتون
// (الگوریتم Longest Matching Block + حذف عناصر پرتکرار در رشته‌های بلند).
// جایگزینِ نسخهٔ قبلیِ مبتنی بر LCS: LCS واقعی همیشه ≥ خروجیِ difflib
// است و باعث اختلاف امتیازدهی فازی میان موتور پایتون و وب می‌شد.
// ─────────────────────────────────────────────────────────────

interface MatchBlock { i: number; j: number; k: number; }

class SequenceMatcher {
  private a: string;
  private b: string;
  private b2j = new Map<string, number[]>();

  constructor(a: string, b: string) {
    this.a = a;
    this.b = b;
    // __chain_b: نگاشت هر نویسه به فهرست اندیس‌هایش در b
    for (let j = 0; j < b.length; j++) {
      const ch = b[j];
      let idxs = this.b2j.get(ch);
      if (!idxs) { idxs = []; this.b2j.set(ch, idxs); }
      idxs.push(j);
    }
    // حذف عناصر پرتکرار (autojunk) برای رشته‌های به طول ≥ ۲۰۰
    const n = b.length;
    if (n >= 200) {
      const ntest = Math.floor(n / 100) + 1;
      for (const [ch, idxs] of [...this.b2j.entries()]) {
        if (idxs.length > ntest) this.b2j.delete(ch);
      }
    }
  }

  findLongestMatch(alo: number, ahi: number, blo: number, bhi: number): MatchBlock {
    const { a, b, b2j } = this;
    let bestI = alo, bestJ = blo, bestSize = 0;
    // در طول حلقه: j2len[j] = طول طولانی‌ترین تطبیق ختم‌شده به a[i-1] و b[j]
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i++) {
      const newJ2len = new Map<number, number>();
      const idxs = b2j.get(a[i]);
      if (idxs) {
        for (const j of idxs) {
          if (j < blo) continue;
          if (j >= bhi) break;
          const k = (j2len.get(j - 1) ?? 0) + 1;
          newJ2len.set(j, k);
          if (k > bestSize) {
            bestI = i - k + 1;
            bestJ = j - k + 1;
            bestSize = k;
          }
        }
      }
      j2len = newJ2len;
    }
    // بسط بهترین تطبیق در دو طرف (isjunk=None پس شرط junk همیشه نادرست)
    while (bestI > alo && bestJ > blo && a[bestI - 1] === b[bestJ - 1]) {
      bestI--; bestJ--; bestSize++;
    }
    while (bestI + bestSize < ahi && bestJ + bestSize < bhi
           && a[bestI + bestSize] === b[bestJ + bestSize]) {
      bestSize++;
    }
    return { i: bestI, j: bestJ, k: bestSize };
  }

  getMatchingBlocks(): MatchBlock[] {
    const la = this.a.length, lb = this.b.length;
    // صف بازگشتی (به‌جای recursion برای جلوگیری از سرریز پشته)
    const queue: [number, number, number, number][] = [[0, la, 0, lb]];
    const blocks: MatchBlock[] = [];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop()!;
      const m = this.findLongestMatch(alo, ahi, blo, bhi);
      if (m.k) {
        blocks.push(m);
        if (alo < m.i && blo < m.j) queue.push([alo, m.i, blo, m.j]);
        if (m.i + m.k < ahi && m.j + m.k < bhi) queue.push([m.i + m.k, ahi, m.j + m.k, bhi]);
      }
    }
    blocks.sort((x, y) => x.i - y.i || x.j - y.j);
    // ادغام بلوک‌های مجاور
    let i1 = 0, j1 = 0, k1 = 0;
    const nonAdjacent: MatchBlock[] = [];
    for (const { i: i2, j: j2, k: k2 } of blocks) {
      if (i1 + k1 === i2 && j1 + k1 === j2) {
        k1 += k2;
      } else {
        if (k1) nonAdjacent.push({ i: i1, j: j1, k: k1 });
        i1 = i2; j1 = j2; k1 = k2;
      }
    }
    if (k1) nonAdjacent.push({ i: i1, j: j1, k: k1 });
    nonAdjacent.push({ i: la, j: lb, k: 0 });
    return nonAdjacent;
  }

  ratio(): number {
    const matches = this.getMatchingBlocks().reduce((s, b) => s + b.k, 0);
    const length = this.a.length + this.b.length;
    return length ? (2 * matches) / length : 1;
  }
}

/** نسبت شباهت ترتیبی ۰ تا ۱ — معادل `difflib.SequenceMatcher.ratio()` */
function quickRatio(a: string, b: string): number {
  if (!a && !b) return 1;
  if (!a || !b) return 0;
  return new SequenceMatcher(a, b).ratio();
}

function tokenize(text: string): string[] {
  const stop = new Set(["و", "به", "از", "در", "با", "برای", "هر", "نوع", "تا", "مورد"]);
  return normalizeText(text)
    .split(" ")
    .filter((t) => t && !stop.has(t));
}

/** Token-Set Ratio به سبک RapidFuzz */
export function tokenSetRatio(a: string, b: string): number {
  const ta = [...new Set(tokenize(a))];
  const tb = [...new Set(tokenize(b))];
  if (!ta.length || !tb.length) return 0;
  const setB = new Set(tb);
  const inter = ta.filter((t) => setB.has(t)).sort();
  const diffA = ta.filter((t) => !setB.has(t)).sort();
  const setA = new Set(ta);
  const diffB = tb.filter((t) => !setA.has(t)).sort();
  const s0 = inter.join(" ");
  const s1 = (inter.concat(diffA)).join(" ");
  const s2 = (inter.concat(diffB)).join(" ");
  return Math.max(quickRatio(s0, s1), quickRatio(s0, s2), quickRatio(s1, s2));
}

/** امتیاز افزودهٔ اشتراک اعداد (مثل عیار ۳۵۰ یا قطر ۱۶) */
function numericBonus(a: string, b: string): number {
  const nums = (s: string) => normalizeText(s).match(/\d+(\.\d+)?/g) ?? [];
  const na = nums(a), nb = new Set(nums(b));
  if (!na.length) return 0;
  const shared = na.filter((t) => nb.has(t)).length;
  return Math.min(0.06, (shared / na.length) * 0.08);
}

/** امتیاز نهایی تطبیق دوتایی (۰ تا ۱) */
export function fuzzyScore(a: string, b: string): number {
  const base = tokenSetRatio(a, b);
  const bonus = numericBonus(a, b);
  return Math.min(1, base * 0.94 + bonus + (base >= 0.995 ? 0.06 : 0));
}

export interface FehrestCandidate {
  row: FehrestRow;
  score: number;
}

/**
 * جست‌وجوی فازی در پایگاه فهرست‌بها با امکان محدودسازی به یک فصل
 * خروجی: تا topN بهترین نامزدها به ترتیب امتیاز
 */
export function searchFehrest(
  db: FehrestRow[],
  query: string,
  opts: { chapter?: string; codePrefix?: string; top?: number; minScore?: number } = {},
): FehrestCandidate[] {
  const { chapter, codePrefix, top = 5, minScore = 0.3 } = opts;
  const scored: FehrestCandidate[] = [];
  for (const row of db) {
    if (chapter && row.chapter !== chapter) continue;
    if (codePrefix && !row.code.startsWith(codePrefix)) continue;
    const s = fuzzyScore(query, row.desc);
    if (s >= minScore) scored.push({ row, score: s });
  }
  scored.sort((x, y) => y.score - x.score);
  return scored.slice(0, top);
}

/** یافتن مستقیم بر اساس کد ردیف */
export function byCode(db: FehrestRow[], code: string): FehrestRow | undefined {
  return db.find((r) => r.code === code);
}
