// ─────────────────────────────────────────────────────────────
// تجزیه‌گر هوشمند خروجی‌های Schedule نرم‌افزار Revit
// • پشتیبانی از CSV نقل‌قول‌دار و TSV (خروجی داینامو)
// • تشخیص خودکار نوع جدول (بتن، قالب، آرماتور، تیرچه و...)
// • حذف ردیف‌های جمع‌جزئی/تکراری و استخراج Grand total
// ─────────────────────────────────────────────────────────────
import type { RevitTable, SemanticCol, TableKind, TableRow } from "./types";
import { normalizeText, parseValueUnit, toSI } from "./normalize";

// ── تجزیهٔ خط CSV با درنظرگرفتن نقل‌قول‌ها ──
export function splitCsvLine(line: string, delim: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else inQ = false;
      } else cur += ch;
    } else if (ch === '"') inQ = true;
    else if (ch === delim) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

/** تشخیص جداکنندهٔ غالب فایل */
export function detectDelimiter(text: string): string {
  const sample = text.split(/\r?\n/).slice(0, 12).join("\n");
  const tabCount = (sample.match(/\t/g) || []).length;
  const commaCount = (sample.match(/","|",|,"/g) || []).length;
  if (tabCount > commaCount) return "\t";
  return ",";
}

/** نگاشت سرستون Revit → ستون معنایی */
const HEADER_MAP: [RegExp, SemanticCol][] = [
  [/^mark$|شماره مارک|مارک/, "mark"],
  [/family and type|family.*type|فامیل/, "familyType"],
  [/^category$|دسته|کتگوری/, "category"],
  [/host category/, "hostCategory"],
  // «Host Mark» مارک المان میزبان آرماتور — مبنای محاسبهٔ per-element
  // تراکم میلگرد در ردیف اختیاری ۰۸۰۳۱۰ (بند ۳-۶ فصل ۸).
  [/host mark/, "hostMark"],
  [/material: name|material name|material$|مصالح: نام/, "material"],
  [/reference level|level|تراز/, "level"],
  [/^count$|تعداد/, "count"],
  [/formwork area|مساحت قالب/, "area"],
  [/material: area|area$|مساحت/, "area"],
  [/material: volume|volume$|حجم/, "volume"],
  [/bar length|^length$|طول/, "length"],
  [/total bar length|lengths|طول کل/, "length"],
  [/^width$|عرض/, "width"],
  [/bar diameter|diameter|قطر/, "diameter"],
  [/bar type|نوع میلگرد|دن/, "barType"],
  [/rebar shape|^shape$|شکل/, "shape"],
  [/spacing|فاصله/, "spacing"],
  [/total weight|وزن|weight|kg/, "weight"],
];

function semanticOf(header: string): SemanticCol | null {
  const h = normalizeText(header);
  for (const [re, col] of HEADER_MAP) if (re.test(h)) return col;
  return null;
}

// ── امضای ستونی برای تشخیص نوع جدول ──
function classify(table: {
  title: string;
  headers: string[];
  kind0?: TableKind;
}): { kind: TableKind; confidence: number } {
  const t = normalizeText(table.title);
  const hs = table.headers.map(normalizeText);
  const has = (re: RegExp) => hs.some((h) => re.test(h));

  // فایل Mapping داینامو: ستون‌های اختصاصی
  if (has(/elementid/) && (has(/mappingmark|marktokens|hostelementid/) || has(/positionindex/)))
    return { kind: "mapping", confidence: 0.99 };

  const rules: [RegExp, TableKind, number][] = [
    [/بتن مگر|lean concrete|بتن نظافت|blinding/, "lean_concrete", 0.97],
    [/قالب بندی پی|foundation formwork/, "formwork_foundation", 0.97],
    [/قالب بندی (سازه|اسکلت)|superstructure formwork|formwork schedule/, "formwork_super", 0.95],
    [/حجم بتن سازه ای|بتن ریزی پی|structural concrete/, "structural_concrete", 0.97],
    [/سقف تیرچه بلوک|joist floor/, "joist_floor", 0.97],
    [/بتن پاشنه|یونولیت|eps block|joist concrete/, "joist_materials", 0.97],
    [/اتصال تیرچه|connection rebar/, "rebar_connection", 0.96],
    [/آرماتور(های)? تیرچه|joist rebar/, "rebar_joist", 0.96],
    [/آرماتور|rebar|لیستوفر|میلگرد/, "rebar_detailed", 0.93],
  ];
  for (const [re, k, c] of rules) if (re.test(t)) return { kind: k, confidence: c };

  // تشخیص از روی امضای ستون‌ها وقتی عنوان کمک نمی‌کند
  if (has(/diameter|bar type/) && has(/weight|kg/)) return { kind: "rebar_detailed", confidence: 0.75 };
  if (has(/formwork area/)) return { kind: "formwork_foundation", confidence: 0.75 };
  if (has(/material: area/) && has(/category/)) return { kind: "formwork_super", confidence: 0.7 };
  if (has(/material: volume/) && has(/category/)) return { kind: "structural_concrete", confidence: 0.7 };
  if (has(/volume/) && has(/mark/)) return { kind: "lean_concrete", confidence: 0.55 };

  return { kind: "unknown", confidence: 0 };
}

/** آیا ردیف، جمع‌جزئی داخلی Revit است؟ (مثل «Rebar - Φ8: 13») */
function isSubtotalRow(cells: string[]): boolean {
  if (!cells.length) return false;
  const first = cells.find((c) => c.trim() !== "") ?? "";
  // الگوی «متن: عدد» در اولین سلول پر، بدون سایر داده‌های نام‌برده
  if (/:\s*\d+\s*$/.test(first) && !/grand total/i.test(first)) return true;
  return false;
}

/** آیا ردیف Grand total است؟ */
function isGrandTotalRow(cells: string[]): boolean {
  const first = (cells[0] || "").toLowerCase();
  return /^\s*grand total/.test(first) || /^grand total\s*:\s*\d+/.test(first);
}

const NUM_COLS: SemanticCol[] = ["count", "length", "width", "diameter", "spacing", "volume", "area", "weight"];
const TEXT_COLS: SemanticCol[] = ["mark", "familyType", "category", "hostCategory", "hostMark", "material", "level", "barType", "shape"];

/** تجزیهٔ کامل یک فایل متنی‌ِ خروجی Revit */
export function parseRevitFile(fileName: string, text: string): RevitTable {
  // حذف BOM (همسان‌سازی با پارسر پایتون)
  text = text.replace(/^\ufeff/, "");
  // تشخیص و نرمال‌سازی فرمت doubled-quote خروجی واقعی Revit:
  // در این فرمت کل سطر به‌عنوان یک فیلد quoted با escape شدن «""» نوشته شده است.
  // با collapse کردن «""» → «"» به CSV استاندارد تبدیل می‌شود (معادل app.py).
  const head = text.split(/\r?\n/).slice(0, 12).join("\n");
  if (/^\s*"[^"\r\n]*""\s*,\s*""[^"\r\n]*"/m.test(head)) {
    text = text.replace(/""/g, '"');
  }
  const delim = detectDelimiter(text);
  const rawLines = text.split(/\r?\n/);
  const grid = rawLines
    .map((ln) => splitCsvLine(ln, delim))
    .filter((cells) => cells.some((c) => c !== ""));

  const warnings: string[] = [];
  if (grid.length < 2) {
    return {
      id: crypto.randomUUID(), fileName, title: fileName, headers: [], rows: [],
      kind: "unknown", kindConfidence: 0, colMap: {},
      warnings: ["فایل قابل‌تشخیص نیست؛ ساختار جدول یافت نشد."],
    };
  }

  // سطر اول: عنوان جدول (فارسی - Title انگلیسی)
  let title = grid[0].find((c) => c) || fileName;
  title = title.replace(/\s+-\s+.*/, "").trim() || title;

  // سرستون: اولین سطری با ≥۲ سلول پر یا سطر دوم
  let headerIdx = -1;
  for (let i = 0; i < Math.min(grid.length, 6); i++) {
    const filled = grid[i].filter((c) => c !== "").length;
    if (i > 0 && filled >= 2) {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) headerIdx = 1;
  const headers = grid[headerIdx].map((h) => h.replace(/^"|"$/g, "").trim());

  // نگاشت معنایی سرستون‌ها
  const colMap: Partial<Record<SemanticCol, number>> = {};
  headers.forEach((h, i) => {
    const sem = semanticOf(h);
    if (sem && colMap[sem] === undefined) colMap[sem] = i;
  });

  // رکوردهای داده + Grand total
  const rows: TableRow[] = [];
  let grandTotal: Record<string, number> | undefined;

  for (let i = headerIdx + 1; i < grid.length; i++) {
    const cells = grid[i];
    if (isGrandTotalRow(cells)) {
      grandTotal = {};
      cells.forEach((c, j) => {
        const pv = parseValueUnit(c);
        if (pv) {
          const sem = Object.entries(colMap).find(([, idx]) => idx === j)?.[0] as SemanticCol | undefined;
          const conv = toSI(pv.value, pv.unit);
          const key = sem && NUM_COLS.includes(sem) ? sem : `col${j}`;
          grandTotal![key] = conv.si ? conv.value : pv.value;
        }
      });
      continue;
    }
    const subtotal = isSubtotalRow(cells);
    const values: Partial<Record<SemanticCol, number>> = {};
    const texts: Partial<Record<SemanticCol, string>> = {};
    (Object.entries(colMap) as [SemanticCol, number][]).forEach(([sem, idx]) => {
      const c = cells[idx] ?? "";
      if (NUM_COLS.includes(sem)) {
        const pv = parseValueUnit(c);
        if (pv) {
          const conv = toSI(pv.value, pv.unit);
          values[sem] = conv.si ? conv.value : pv.value;
          if (!conv.si && pv.unit && c.replace(/\d|[.,\s,]/g, "")) {
            warnings.push(`واحد ناشناخته «${pv.unit}» در ستون «${headers[idx] || sem}»`);
          }
        }
      } else if (TEXT_COLS.includes(sem)) {
        texts[sem] = c;
      }
    });
    // سطر جمع بدون برچسب Revit: هیچ ستون متنی پر ندارد و فقط مقدار عددی دارد
    // ⇒ Grand total همان Schedule تلقی میشود و رکورد متره نمیسازد.
    const hasText = Object.values(texts).some((v) => String(v ?? "").trim() !== "");
    if (!hasText && Object.keys(values).length > 0) {
      if (!grandTotal) grandTotal = { ...(values as Record<string, number>) };
      continue;
    }
    rows.push({ cells, values, texts, isSubtotal: subtotal });
  }

  const { kind, confidence } = classify({ title, headers });
  if (kind === "unknown") warnings.push("نوع جدول به‌صورت خودکار تشخیص داده نشد؛ لطفاً دستی تعیین کنید.");

  return {
    id: crypto.randomUUID(),
    fileName,
    title,
    headers,
    rows,
    grandTotal,
    kind,
    kindConfidence: confidence,
    colMap,
    warnings: [...new Set(warnings)].slice(0, 6),
  };
}

/** محل فارسی هر نوع جدول برای نمایش */
export const KIND_LABEL: Record<TableKind, string> = {
  lean_concrete: "ریزمترهٔ بتن مگر",
  structural_concrete: "ریزمترهٔ بتن سازه‌ای",
  formwork_foundation: "قالب‌بندی پی",
  formwork_super: "قالب‌بندی سازه",
  joist_floor: "سقف تیرچه‌بلوک",
  joist_materials: "بتن پاشنه و یونولیت",
  rebar_detailed: "لیستوفر تفصیلی آرماتور",
  rebar_joist: "آرماتور تیرچه",
  rebar_connection: "آرماتور اتصال تیرچه",
  mapping: "Mapping داینامو",
  unknown: "جدول نامشخص",
};

export const KIND_COLOR: Record<TableKind, string> = {
  lean_concrete: "sky",
  structural_concrete: "teal",
  formwork_foundation: "violet",
  formwork_super: "violet",
  joist_floor: "gold",
  joist_materials: "gold",
  rebar_detailed: "rose",
  rebar_joist: "rose",
  rebar_connection: "rose",
  mapping: "emerald",
  unknown: "zinc",
};

// ── تبدیل جدول به رکوردهای کمیت استاندارد ──
import type { QuantityRecord } from "./types";

/** تشخیص گروه سازه‌ای از نام Mark/Family/Category */
export function structuralGroup(text: string, kind: TableKind): string {
  const raw = text.toUpperCase();
  if (/FOUNDATION|WF_|FOOTING|پی |فونداسیون|شالوده/.test(raw)) return "پی";
  if (/(^|[^A-Z])STR(?![A-Z])|STAIR|پله/.test(raw)) return "پله";
  if (/JST|JOIST|تیرچه/.test(raw)) return "سقف تیرچه";
  if (/(^|[^A-Z])C\d|COLUMN|ستون/.test(raw)) return "ستون";
  if (/(^|[^A-Z])B\d|BEAM|FRAMING|تیر /.test(raw) || /^B\d+X\d+/.test(raw)) return "تیر";
  if (/SLAB|FLOOR|دال|سقف/.test(raw)) return "سقف";
  if (/WALL|دیوار/.test(raw)) return "دیوار";
  if (/^L\(|^T\(|LG|TR\(|FOUND/.test(raw)) return "پی";
  if (kind === "lean_concrete") return "پی";
  if (kind === "formwork_foundation" || kind === "joist_floor" || kind === "joist_materials")
    return kind === "formwork_foundation" ? "پی" : "سقف تیرچه";
  return "سایر";
}

// واژگان گروه سازه‌ایِ لیستوفر (ایراد ۱۱): «Floor» میزبان = دال (سقفِ یکپارچه).
// «سقف تیرچه» حفظ می‌شود (گروهی واقعی و متمایز از دال).
const REBAR_GROUP_VOCAB: Record<string, string> = { "سقف": "دال" };

/** گروه سازه‌ای لیستوفر آرماتور (ایراد ۱۱ — آینهٔ rebar_list_group در app.py).
 *
 * اولویت: **Host Category** المان میزبان > نام/مارک. گروه هرگز «سایر» نیست
 * (قاعدهٔ صریح ایراد ۱۱)؛ در صورت عدم تشخیص «نامشخص» برمی‌گردد تا با هشدار
 * متناظر نمایش داده شود (قاعدهٔ طلایی ۳: برچسب ساخته نمی‌شود).
 * خروجی: [گروه، آیا نامشخص است]. */
export function rebarListGroup(
  hostCat: string,
  text: string,
  kind: TableKind,
): [string, boolean] {
  let g = "سایر";
  const hc = (hostCat ?? "").trim();
  if (hc && hc.toLowerCase() !== "<varies>") g = structuralGroup(hc, kind);
  if (g === "سایر") g = structuralGroup(text, kind);
  if (g === "سایر") return ["نامشخص", true];
  return [REBAR_GROUP_VOCAB[g] ?? g, false];
}

/** مارک لیستوفر آرماتور (ایراد ۱۱ — آینهٔ rebar_list_mark در app.py).
 *
 * اولین مقدار غیرخالی از کاندیداهای ورودی (پارامتر Revit «Rebar
 * Number»/«Mark»، سپس Schedule Mark، سپس Family Type). اگر هیچ‌کدام نبود
 * **«بدون مارک»** برمی‌گردد — هرگز «—» (قاعدهٔ صریح ایراد ۱۱). */
export function rebarListMark(...candidates: (string | null | undefined)[]): string {
  for (const c of candidates) {
    const v = String(c ?? "").trim();
    if (v) return v;
  }
  return "بدون مارک";
}

/** استخراج همهٔ کمیت‌های یک جدول به فرم استاندارد سانتی‌مترک‌دونی (SI) */
import { parseConcreteStrength } from "./normalize";

export function toQuantityRecords(table: RevitTable): QuantityRecord[] {
  const recs: QuantityRecord[] = [];
  const dataRows = table.rows.filter((r) => !r.isSubtotal);
  const fileRef = table.fileName;

  const push = (r: TableRow, qty: number, unit: QuantityRecord["unit"], detail: string, fromGT = false) => {
    const ref = r.texts.mark || r.texts.familyType || r.texts.category || r.texts.material || "—";
    recs.push({
      tableId: table.id,
      fileName: fileRef,
      tableTitle: table.title,
      kind: table.kind,
      ref,
      group: structuralGroup(`${ref} ${r.texts.familyType ?? ""} ${r.texts.category ?? ""}`, table.kind),
      material: r.texts.material || "",
      // مقاومت فشاری از نام متریال (ایراد ۱): "Concrete - ... - 35 MPa" → 35
      // فقط ستون متریال — «Family and Type» مثل «Column: C 45×45»
      // ابعاد مقطع است و نباید مقاومت فرض شود.
      strengthMpa: parseConcreteStrength(r.texts.material || ""),
      level: r.texts.level || "",
      qty,
      unit,
      detail,
      fromGrandTotal: fromGT,
    });
  };

  switch (table.kind) {
    case "lean_concrete":
    case "structural_concrete": {
      for (const r of dataRows) {
        const v = r.values.volume ?? 0;
        if (v > 0) push(r, v, "m3", `${r.texts.category ?? ""} ${r.texts.familyType ?? r.texts.mark ?? ""}`.trim());
      }
      break;
    }
    case "formwork_foundation":
    case "formwork_super": {
      for (const r of dataRows) {
        const a = r.values.area ?? 0;
        if (a > 0) push(r, a, "m2", `${r.texts.category ?? ""} ${r.texts.mark ?? r.texts.familyType ?? ""}`.trim());
      }
      break;
    }
    case "joist_floor": {
      for (const r of dataRows) {
        const len = r.values.length ?? 0;
        const count = r.values.count ?? 1;
        if (len > 0) push(r, len * count, "m", `تیرچه ${r.texts.mark ?? ""} | طبقه ${r.texts.level ?? ""}`);
      }
      break;
    }
    case "joist_materials": {
      for (const r of dataRows) {
        const v = r.values.volume ?? 0;
        if (v > 0) push(r, v, "m3", r.texts.material || r.texts.familyType || "مصالح سقف");
      }
      break;
    }
    case "rebar_detailed":
    case "rebar_joist":
    case "rebar_connection": {
      for (const r of dataRows) {
        const w = r.values.weight ?? 0;
        if (w > 0) {
          push(r, w, "kg", `${r.texts.mark ?? ""} ${r.texts.barType ? " | " + r.texts.barType : ""}`);
        }
      }
      break;
    }
    default:
      break;
  }
  return recs;
}
