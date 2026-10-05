import { useCallback, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CloudUpload,
  FileText,
  FlaskConical,
  Layers,
  MousePointerClick,
  Table2,
  Trash2,
  TriangleAlert,
  Wand2,
  X,
} from "lucide-react";
import { Card, SectionTitle, Badge, Confidence } from "./ui";
import { KIND_COLOR, KIND_LABEL, parseRevitFile } from "../lib/revitParser";
import { parseDynamoMapping } from "../lib/mappingParser";
import type { LoadedFile, MappingData, RevitTable, TableKind } from "../lib/types";
import { cn } from "../utils/cn";
import { fmtNum } from "../lib/normalize";
import { DEMO_FILES } from "../data/demo";
import { decodeText } from "../lib/decode";

const KINDS: TableKind[] = [
  "lean_concrete", "structural_concrete", "formwork_foundation", "formwork_super",
  "joist_floor", "joist_materials", "rebar_detailed", "rebar_joist", "rebar_connection", "mapping", "unknown",
];

export function UploadStep({
  files,
  setFiles,
  onNext,
  setDemoLoaded,
}: {
  files: LoadedFile[];
  setFiles: (f: LoadedFile[]) => void;
  onNext: () => void;
  setDemoLoaded: (b: boolean) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const readFiles = useCallback(
    async (list: FileList | File[]) => {
      setBusy(true);
      const arr = Array.from(list);
      const loaded: LoadedFile[] = [];
      for (const f of arr) {
        try {
          const buffer = await f.arrayBuffer();
          const text = decodeText(new Uint8Array(buffer));
          const table = parseRevitFile(f.name, text);
          let mappingData: MappingData | undefined;
          // هدرهای فارسی ۱۶ستونی (v2) و TSV انگلیسی (v1) امضای Schedule رویت را ندارند و
          // «ناشناخته» تشخیص داده می‌شوند؛ پس برای آن‌ها نیز پارس Mapping آزموده می‌شود.
          if (table.kind === "mapping" || table.kind === "unknown") {
            mappingData = tryParseMapping(buffer, f.name);
          }
          loaded.push({ id: crypto.randomUUID(), name: f.name, size: f.size, text, table, mappingData });
        } catch (e) {
          console.error(e);
        }
      }
      setFiles(dedupe([...files, ...loaded]));
      setBusy(false);
    },
    [files, setFiles],
  );

  function dedupe(fs: LoadedFile[]): LoadedFile[] {
    const seen = new Set<string>();
    return fs.filter((f) => {
      const k = `${f.name}:${f.size}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  /** تلاش برای پارس فایل به‌عنوان خروجی Mapping داینامو — فقط در صورت پارس سالم */
  function tryParseMapping(buffer: ArrayBuffer, fileName: string): MappingData | undefined {
    try {
      const md = parseDynamoMapping(buffer, fileName);
      if (md.error || md.format === "unknown" || !md.rows.length) return undefined;
      return md;
    } catch {
      return undefined;
    }
  }

  function loadDemo() {
    const loaded: LoadedFile[] = DEMO_FILES.map((d) => {
      const table = parseRevitFile(d.name, d.text);
      return { id: crypto.randomUUID(), name: d.name, size: d.text.length, text: d.text, table };
    });
    setFiles(loaded);
    setDemoLoaded(true);
  }

  function setTableKind(id: string, kind: TableKind) {
    setFiles(
      files.map((f) => {
        if (f.id !== id || !f.table) return f;
        const table = { ...f.table, kind, kindConfidence: 1, warnings: [] } as RevitTable;
        let mappingData = f.mappingData;
        if (kind === "mapping" && !mappingData) {
          const enc = new TextEncoder().encode(f.text);
          mappingData = tryParseMapping(enc.buffer as ArrayBuffer, f.name);
        }
        return { ...f, table, mappingData };
      }),
    );
  }

  const unknownCount = files.filter((f) => f.table?.kind === "unknown").length;
  const totalRows = files.reduce((a, f) => a + (f.table?.rows.length ?? 0), 0);

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="گام ۳ — ورود داده‌های BIM"
        title="آپلود خروجی‌های Schedule نرم‌افزار Revit"
        sub="فایل‌های TXT/CSV خروجی جداول Revit و خروجی Mapping اسکریپت Dynamo را رها کنید. سامانه نوع هر جدول، سرستون‌ها و واحدها را به‌صورت خودکار تشخیص می‌دهد."
        action={
          <button
            onClick={loadDemo}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gold/10 border border-gold/30 text-gold text-[13px] font-bold hover:bg-gold/20 transition-colors"
          >
            <FlaskConical size={16} />
            بارگذاری پروژهٔ نمونه (دمو)
          </button>
        }
      />

      {/* ناحیهٔ رها کردن */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          readFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-300 relative overflow-hidden",
          dragging ? "border-gold bg-gold/[0.06] scale-[1.005]" : "border-line hover:border-gold/40 hover:bg-white/[0.02]",
        )}
      >
        <div className="absolute inset-0 blueprint-grid opacity-40 pointer-events-none" style={{ position: "absolute", maskImage: "none" }} />
        <div className="relative">
          <div className={cn("mx-auto w-16 h-16 rounded-2xl grid place-items-center mb-4 transition-all", dragging ? "bg-gold text-[#1a1410]" : "bg-white/[0.05] text-gold")}>
            <CloudUpload size={28} strokeWidth={1.8} />
          </div>
          <p className="font-bold text-ink text-[15px]">
            {busy ? "در حال خواندن و تجزیهٔ فایل‌ها…" : "فایل‌ها را این‌جا رها کنید یا کلیک کنید"}
          </p>
          <p className="text-ink-dim text-[12.5px] mt-2 leading-6">
            فرمت‌های پشتیبانی‌شده: TXT و CSV خروجی مستقیم Revit Schedule (با نقل‌قول) و TSV خروجی Dynamo
            <br />
            خواندن چند فایل هم‌زمان · تشخیص خودکار نام جدول از روی عنوان و امضای ستون‌ها
          </p>
          <div className="flex items-center justify-center gap-2 mt-4 text-[11px] text-ink-dim">
            <MousePointerClick size={13} />
            بدون ارسال به سرور — پردازش تماماً روی مرورگر شما انجام می‌شود
          </div>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".txt,.csv,.tsv"
          className="hidden"
          onChange={(e) => {
            if (e.target.files) readFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {/* هشدار جداول نامشخص */}
      {unknownCount > 0 && (
        <div className="flex items-start gap-3 rounded-xl bg-gold/[0.07] border border-gold/25 p-4">
          <TriangleAlert size={18} className="text-gold shrink-0 mt-0.5" />
          <div className="text-[12.5px] leading-6 text-ink/90">
            <b className="text-gold">{fmtNum(unknownCount, 0)} جدول نامشخص</b> — نوع این جداول به‌صورت خودکار تشخیص داده نشده است.
            از فهرست کشویی روی هر کارت، نوع صحیح را انتخاب کنید تا در محاسبات لحاظ شوند.
          </div>
        </div>
      )}

      {/* کارت‌های فایل */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid gap-3 xl:grid-cols-2">
            {files.map((f) => {
              const t = f.table;
              return (
                <motion.div key={f.id} layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}>
                  <Card className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-xl bg-white/[0.05] grid place-items-center text-sky shrink-0">
                          <FileText size={18} />
                        </div>
                        <div className="min-w-0">
                          <div className="text-[13px] font-bold text-ink truncate">{f.name}</div>
                          <div className="text-[11px] text-ink-dim mt-0.5 flex items-center gap-2 flex-wrap">
                            <span className="num">{fmtNum(f.size / 1024, 1)} کیلوبایت</span>
                            <span className="text-white/15">•</span>
                            <Layers size={11} className="inline" /> {fmtNum(t?.rows.length ?? 0, 0)} ردیف
                            <span className="text-white/15">•</span>
                            <Table2 size={11} className="inline" /> {fmtNum(t?.grandTotal ? 1 : 0, 0) === "۱" && t?.grandTotal ? "دارای Grand total" : "بدون Grand total"}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => setFiles(files.filter((x) => x.id !== f.id))}
                        className="w-8 h-8 rounded-lg grid place-items-center text-ink-dim hover:text-rose hover:bg-rose/10 transition-colors shrink-0"
                        title="حذف فایل"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>

                    {t && (
                      <div className="mt-4 flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge tone={(KIND_COLOR[t.kind] ?? "zinc") as never}>
                            <Wand2 size={11} />
                            {KIND_LABEL[t.kind]}
                          </Badge>
                          {t.kind !== "unknown" && <Confidence value={t.kindConfidence} />}
                        </div>
                        {t.kind === "unknown" && (
                          <select
                            onChange={(e) => setTableKind(f.id, e.target.value as TableKind)}
                            value="unknown"
                            className="bg-panel-2 border border-gold/40 text-gold text-[11.5px] rounded-lg px-2.5 py-1.5 outline-none cursor-pointer"
                          >
                            <option value="unknown">تعیین دستی نوع جدول…</option>
                            {KINDS.filter((k) => k !== "unknown").map((k) => (
                              <option key={k} value={k}>{KIND_LABEL[k]}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    )}

                    {t && t.warnings.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {t.warnings.slice(0, 2).map((w, i) => (
                          <div key={i} className="flex items-start gap-1.5 text-[11px] text-gold/90 leading-4">
                            <TriangleAlert size={11} className="shrink-0 mt-0.5" /> {w}
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* جمع‌بندی و ادامه */}
      {files.length > 0 && (
        <Card glow className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-6 text-[13px]">
            <span className="text-ink-dim">
              <b className="text-ink num text-base">{fmtNum(files.length, 0)}</b> جدول
            </span>
            <span className="text-white/15">|</span>
            <span className="text-ink-dim">
              <b className="text-ink num text-base">{fmtNum(totalRows, 0)}</b> ردیف داده
            </span>
            <span className="text-white/15">|</span>
            <span className="text-ink-dim">
              <b className={cn("num text-base", unknownCount > 0 ? "text-gold" : "text-emerald")}>{fmtNum(files.length - unknownCount, 0)}</b> تشخیص موفق
            </span>
          </div>
          <button
            onClick={onNext}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gold text-[#1a1410] text-[13.5px] font-extrabold hover:bg-gold-2 transition-colors shadow-[0_10px_30px_-10px_rgba(242,179,61,0.6)]"
          >
            ادامه: رفتن به تطبیق هوشمند
            <X size={0} className="hidden" />
          </button>
        </Card>
      )}
    </div>
  );
}
