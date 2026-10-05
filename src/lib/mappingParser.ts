// ─────────────────────────────────────────────────────────────
// پارسر خروجی داینامو Mapping (v1 TSV / v2 TSV / xlsx)
// • ستون‌ها را به نام‌های کانونیکال تبدیل می‌کند
// • ارقام فارسی/عربی در fehrest_code را نرمال‌سازی می‌کند
// • ستون‌های عددی را از رشته‌های واحد‌دار استخراج می‌کند
// معادل کلاس DynamoMappingParser از app.py
// ─────────────────────────────────────────────────────────────
import * as XLSX from "xlsx";
import type { MappingRow, MappingData } from "./types";
import { parseValueUnit } from "./normalize";
import { toEnSafe } from "../data/fehrest";
import { decodeText } from "./decode";

const V2_HEADER_CANON: Record<string, string> = {
  "ElementId": "element_id", "دسته": "category", "Family": "family", "Type": "type",
  "Mark": "mark", "طبقه": "level", "فاز": "phase", "متریال": "material",
  "کد فهرست بها": "fehrest_code", "توضیحات": "note",
  "حجم (m³)": "volume_m3", "سطح (m²)": "area_m2", "طول (m)": "length_m",
  "قالب‌بندی (m²)": "formwork_m2", "جزئیات میلگرد": "rebar_detail",
  "وزن کل میلگرد (kg)": "rebar_weight_kg",
};

const V1_HEADER_CANON: Record<string, string> = {
  "ElementId": "element_id", "Category": "category", "Family": "family", "Type": "type",
  "Mark": "mark", "MappingMark": "mark", "Prefix": "prefix",
  "HostCategory": "category", "HostFamily": "host_family", "HostType": "type",
  "HostMark": "host_mark", "HostLevel": "level",
  "Diameter_mm": "diameter_mm", "SteelType": "steel_type",
  "Length_mm": "length_m", "Quantity": "quantity",
  "Material": "material", "RebarShape": "rebar_detail",
  "Volume_m3": "volume_m3", "Area_m2": "area_m2",
  "HostVolume_m3": "host_volume_m3", "HostArea_m2": "host_area_m2",
  "Position": "position", "StructuralContext": "position",
};

const MAP_CANON_COLS: string[] = [
  "element_id", "category", "family", "type", "mark", "level", "phase",
  "material", "fehrest_code", "note", "volume_m3", "area_m2", "length_m",
  "formwork_m2", "rebar_detail", "rebar_weight_kg",
  "diameter_mm", "steel_type", "prefix", "host_mark", "host_family", "position",
];

const V2_NUMERIC_COLS: string[] = [
  "volume_m3", "area_m2", "length_m", "formwork_m2", "rebar_weight_kg", "diameter_mm",
];

const V1_NUMERIC_COLS: string[] = [
  "volume_m3", "area_m2", "length_m", "diameter_mm",
];

function canonV2Header(h: string): string {
  if (h in V2_HEADER_CANON) return V2_HEADER_CANON[h];
  let hn = h.replace("ي", "ی").replace("ك", "ک").replace("‌", " ").trim();
  if (hn in V2_HEADER_CANON) return V2_HEADER_CANON[hn];
  const best = Object.keys(V2_HEADER_CANON).find((k) => k === hn);
  if (best) return V2_HEADER_CANON[best];
  return hn.replace(/\s+/g, "_") || h;
}

function canonV1Header(h: string): string {
  if (h in V1_HEADER_CANON) return V1_HEADER_CANON[h];
  return (V1_HEADER_CANON[h] ?? h.replace(/\s+/g, "_")) || h;
}

function parseNum(raw: unknown): number {
  if (typeof raw === "number") return raw;
  if (raw === null || raw === undefined) return 0;
  const s = String(raw).trim();
  if (!s) return 0;
  const pv = parseValueUnit(s);
  return pv ? pv.value : 0;
}

function parseRow(
  headers: string[],
  row: string[],
  canonMap: Record<string, string>,
  numericCols: string[],
  sourceFormat: "v1" | "v2",
): MappingRow {
  const rowMap: Record<string, string> = {};
  headers.forEach((h, i) => { rowMap[h] = row[i] ?? ""; });

  const rec: Record<string, string | number> = {};
  for (const col of MAP_CANON_COLS) {
    // منطبق با app.py:_rows_to_records — ستون دیرتر در فایل برنده می‌شود
    // (مثلاً MappingMark روی Mark خالی، HostCategory روی Category).
    let src: string | undefined;
    for (const [h, c] of Object.entries(canonMap)) if (c === col) src = h;
    const raw = src ? rowMap[src] : "";
    if (col === "fehrest_code") {
      rec[col] = toEnSafe(String(raw ?? "").trim());
    } else if (numericCols.includes(col)) {
      rec[col] = parseNum(raw);
    } else {
      rec[col] = String(raw ?? "");
    }
  }
  // فرمت مبدأ رکورد (v1/v2) — برای گروه‌بندی و شناسهٔ ردیف‌های مستقیم Mapping لازم است
  rec["source_format"] = sourceFormat;
  return rec as unknown as MappingRow;
}

// ست‌های مقادیر کانونیکال v2 — برای تشخیص سطر واقعیِ سرستون از سطر متادیتای «# گزارش Mapping»
const V2_CANON_SET = new Set(Object.values(V2_HEADER_CANON));

function parseV2Lines(lines: string[]): MappingData {
  const result: MappingData = { rows: [], format: "v2", recordCount: 0, warnings: [] };
  let headerIdx = -1;
  for (let i = 0; i < Math.min(lines.length, 8); i++) {
    const cells = lines[i].split("\t").map((c) => c.trim());
    if (cells.length < 5) continue;
    const known = cells.filter((c) => V2_CANON_SET.has(canonV2Header(c))).length;
    const isMeta = cells[0].startsWith("#") || /تاریخ|نسخه/.test(lines[i]);
    // سطر متادیتای «# گزارش Mapping پروژه … تاریخ … نسخه اسکریپت» بدون هیچ ستون شناخته‌شده را رد کن
    if (isMeta && known === 0) continue;
    // سطر سرستون واقعی: حداقل دو ستون کانونیکال شناخته‌شده (یا ستون ElementId)
    if (known >= 2 || cells.includes("ElementId")) { headerIdx = i; break; }
  }
  if (headerIdx < 0) { result.error = "سرستون یافت نشد."; return result; }

  const headers = lines[headerIdx].split("\t").map((h) => h.trim());
  const canon: Record<string, string> = {};
  headers.forEach((h) => { const c = canonV2Header(h); canon[h] = c; });

  for (let i = headerIdx + 1; i < lines.length; i++) {
    const cells = lines[i].split("\t");
    if (cells.every((c) => !c.trim())) continue;
    // رد سطرهای خلاصه/کامنت (شروع‌شونده با #) — در غیر این صورت سطر پایانی
    // «# مجموع تعداد کل المان‌ها: …» به‌عنوان یک رکورد با کمیت‌های صفر
    // جذب می‌شد (۸۳۶ رکورد به‌جای ۸۳۵). مطابق app.py (_rows_to_records).
    if (lines[i].trimStart().startsWith("#")) continue;
    const row = parseRow(headers, cells, canon, V2_NUMERIC_COLS, "v2");
    result.rows.push(row);
  }
  result.recordCount = result.rows.length;
  return result;
}

function parseV1Lines(lines: string[]): MappingData {
  const result: MappingData = { rows: [], format: "v1", recordCount: 0, warnings: [] };
  let headerIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes("ElementId")) { headerIdx = i; break; }
  }
  if (headerIdx < 0) { result.error = "سرستون ElementId یافت نشد."; return result; }

  const headers = lines[headerIdx].split("\t").map((h) => h.trim());
  const canon: Record<string, string> = {};
  headers.forEach((h) => { const c = canonV1Header(h); canon[h] = c; });

  for (let i = headerIdx + 1; i < lines.length; i++) {
    const cells = lines[i].split("\t");
    if (cells.every((c) => !c.trim())) continue;
    const row = parseRow(headers, cells, canon, V1_NUMERIC_COLS, "v1");
    // واحد طول در v1 میلی‌متر است (ستون Length_mm) → تبدیل به متر،
    // منطبق با app.py:936 (df["length_m"] /= 1000).
    row.length_m = row.length_m / 1000;
    result.rows.push(row);
  }
  result.recordCount = result.rows.length;
  return result;
}

function parseText(text: string, _fileName: string): MappingData {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) { return { rows: [], format: "unknown", recordCount: 0, warnings: [], error: "فایل خالی است." }; }

  const firstLine = lines.slice(0, 6).join("\n");
  if (firstLine.includes("کد فهرست") || firstLine.includes("طبقه") || firstLine.includes("حجم")) {
    return parseV2Lines(lines);
  }
  if (firstLine.includes("ElementId") && (firstLine.includes("HostElementId") || firstLine.includes("MarkTokens") || firstLine.includes("Position"))) {
    return parseV1Lines(lines);
  }
  return { rows: [], format: "unknown", recordCount: 0, warnings: [], error: "فرمت فایل تشخیص داده نشد." };
}

export function parseDynamoMapping(fileBytes: ArrayBuffer, _fileName: string): MappingData {
  const bytes = new Uint8Array(fileBytes);
  const isXlsx = bytes.length > 4 && bytes[0] === 0x50 && bytes[1] === 0x4B && bytes[2] === 0x03 && bytes[3] === 0x04;

  if (isXlsx) {
    try {
      const wb = XLSX.read(bytes, { type: "array" });
      if (!wb.SheetNames.length) { return { rows: [], format: "v2", recordCount: 0, warnings: [], error: "فایل اکسل خالی است." }; }
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows: string[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" });
      const tsv = rows.map((r) => r.map((c) => String(c)).join("\t")).join("\n");
      return parseV2TSV(tsv);
    } catch (e) {
      return { rows: [], format: "v2", recordCount: 0, warnings: [], error: `خطا در خواندن فایل اکسل Mapping: ${e}` };
    }
  }

  const text = decodeText(bytes);
  return parseText(text, _fileName);
}

function parseV2TSV(tsv: string): MappingData {
  const lines = tsv.split(/\r?\n/).filter((l) => l.trim());
  return parseV2Lines(lines);
}
