// ─────────────────────────────────────────────────────────────
// پنل قیمت دستی (فاز C — §۱۵-۴) — گام مستقل در نسخهٔ وب
//
// محلِ واحدِ ورود قیمت‌های دستی، ردیف‌های ستاره‌دار، فایل کناری و
// سابقهٔ ویرایش. ویرایشِ مقادیرِ هر ردیف در گام «تطبیق هوشمند» انجام
// می‌شود و اینجا ذخیره می‌گردد.
// ─────────────────────────────────────────────────────────────
import { useRef, useState } from "react";
import {
  ClipboardList,
  Coins,
  Copy,
  Download,
  FileUp,
  Plus,
  Save,
  Star,
  Trash2,
} from "lucide-react";
import { Card, SectionTitle, Stat } from "./ui";
import type {
  AuditEntry,
  ProjectMeta,
  ProjectResult,
  ProjectSettings,
  StarredRow,
} from "../lib/types";
import {
  AUDIT_KIND_LABELS,
  MANUAL_SOURCES,
  MANUAL_STATUSES,
} from "../lib/types";
import { appendAudit } from "../lib/engine";
import { chapterTitle } from "../data/fehrest";
import {
  applyManualEntries,
  downloadProjectProfile,
  parseManualEntriesXlsx,
} from "../lib/manualEntries";
import { isValidJalaliDate, jalaliNowStr } from "../lib/farsi";
import { faDigits, fmtNum, fmtRial } from "../lib/normalize";

const CHAPTER_OPTS = [
  "08", "06", "07", "10", "28", "01", "02", "03", "04", "05", "09", "11",
  "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23",
  "24", "25", "26", "27", "29", "31", "33", "41", "99",
];

const STATUS_ICON: Record<string, string> = {
  "قطعی": "✅", "موقت": "⏳", "پیش‌فرض اپ": "⚙️", "دستی": "✏️", "نیازمند ورود": "⚠️",
};

export function ManualPricesStep({
  result,
  settings,
  setSettings,
  projectName,
  meta,
  onCopyProject,
  onLoadProfileText,
}: {
  result: ProjectResult | null;
  settings: ProjectSettings;
  setSettings: (s: ProjectSettings) => void;
  projectName: string;
  meta: ProjectMeta;
  onCopyProject: () => void;
  onLoadProfileText: (text: string) => string[];
}) {
  const fileXlsx = useRef<HTMLInputElement>(null);
  const fileJson = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // ── فرم ردیف ستاره‌دار ──
  const [mode, setMode] = useState<"direct" | "dims">("direct");
  const [fCode, setFCode] = useState("");
  const [fDesc, setFDesc] = useState("");
  const [fUnit, setFUnit] = useState("عدد");
  const [fChapter, setFChapter] = useState("31");
  const [fQty, setFQty] = useState("");
  const [fCnt, setFCnt] = useState("");
  const [fLen, setFLen] = useState("");
  const [fWid, setFWid] = useState("");
  const [fHt, setFHt] = useState("");
  const [fPrice, setFPrice] = useState("");
  const [fSource, setFSource] = useState<string>(MANUAL_SOURCES[0]);
  const [fDocNo, setFDocNo] = useState("");
  const [fDocDate, setFDocDate] = useState("");
  const [fNote, setFNote] = useState("");
  const [errs, setErrs] = useState<string[]>([]);

  if (!result || !result.lines.length) {
    return (
      <Card className="text-center py-16">
        <Coins size={42} className="mx-auto text-ink-dim mb-4" />
        <h3 className="text-ink font-bold text-lg">هنوز ردیفی وجود ندارد</h3>
        <p className="text-ink-dim text-[13px] mt-2">
          ابتدا در گام «جداول Revit» خروجی‌های پروژه را بارگذاری کنید.
        </p>
      </Card>
    );
  }

  const qtyFromDims = Number(fCnt) * Number(fLen) * Number(fWid) * Number(fHt);

  const patch = (p: Partial<ProjectSettings>) => setSettings({ ...settings, ...p });

  const addStarred = () => {
    const e: string[] = [];
    if (!fDesc.trim()) e.push("شرح ردیف الزامی است.");
    const q = mode === "direct" ? Number(fQty) : qtyFromDims;
    const p = Number(fPrice.replace(/[,٬\s]/g, ""));
    if (!Number.isFinite(q) || q <= 0) e.push("مقدار باید بزرگتر از صفر باشد.");
    if (!Number.isFinite(p) || p <= 0) e.push("بهای واحد باید بزرگتر از صفر باشد.");
    if (fDocDate.trim() && !isValidJalaliDate(fDocDate.trim())) {
      e.push("تاریخ سند شمسی معتبر نیست (نمونه: ۱۴۰۵/۰۴/۱۲).");
    }
    if (e.length) {
      setErrs(e);
      return;
    }
    const row: StarredRow = {
      code: fCode.trim(),
      desc: fDesc.trim(),
      unit: fUnit,
      qty: q,
      price: p,
      chapter: fChapter,
      source: fSource,
      docNo: fDocNo.trim(),
      docDate: fDocDate.trim(),
      note: fNote.trim(),
      user: settings.priceUser,
      at: jalaliNowStr(),
    };
    const next = { ...settings, starredRows: [...settings.starredRows, row] };
    appendAudit(next, fCode.trim() || "(ستاره‌دار)", "starred_row", null, `${q} × ${p}`, fSource);
    setSettings(next);
    setErrs([]);
    // پاک کردن فرم
    setFCode(""); setFDesc(""); setFQty(""); setFCnt(""); setFLen(""); setFWid("");
    setFHt(""); setFPrice(""); setFDocNo(""); setFDocDate(""); setFNote("");
    setMsg({ ok: true, text: `ردیف ستاره‌دار اضافه شد: ${fmtRial(q * p)}` });
  };

  const delStarred = (i: number) => {
    const sr = settings.starredRows[i];
    const next = { ...settings, starredRows: settings.starredRows.filter((_, j) => j !== i) };
    appendAudit(next, sr.code || "(ستاره‌دار)", "starred_row", `${sr.qty} × ${sr.price}`, null, "حذف دستی");
    setSettings(next);
  };

  const onImportXlsx = async (file: File) => {
    try {
      const buf = new Uint8Array(await file.arrayBuffer());
      const payload = parseManualEntriesXlsx(buf);
      if (!payload) {
        setMsg({ ok: false, text: "در این فایل شیت «قیمت‌های دستی» پیدا نشد." });
        return;
      }
      const next = { ...settings };
      const warns = applyManualEntries(next, payload);
      appendAudit(next, "فایل Excel", "import", null, `${Object.keys(payload.manualPrices).length} قیمت`, "ورود از Excel");
      setSettings(next);
      setMsg({
        ok: warns.length === 0,
        text: warns.length ? warns.join(" | ") : "قیمت‌ها از Excel وارد شدند.",
      });
    } catch (ex) {
      setMsg({ ok: false, text: `خواندن فایل Excel ناموفق بود: ${String(ex)}` });
    }
    if (fileXlsx.current) fileXlsx.current.value = "";
  };

  const onImportJson = async (file: File) => {
    try {
      const warns = onLoadProfileText(await file.text());
      setMsg({
        ok: warns.length === 0,
        text: warns.length
          ? warns.join(" | ")
          : `پروفایل از ${file.name} بارگذاری شد.`,
      });
    } catch (ex) {
      setMsg({ ok: false, text: `خواندن فایل JSON ناموفق بود: ${String(ex)}` });
    }
    if (fileJson.current) fileJson.current.value = "";
  };

  const ps = result.priceStatusSummary ?? {};
  const npe = result.needsPriceEntry ?? 0;

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="گام ۶ — پنل قیمت دستی"
        title="ورود قیمت‌های دستی، ردیف‌های ستاره‌دار و سابقهٔ ویرایش"
        sub="هر قیمت دارای منبع، شماره سند و تاریخ است (قاعدهٔ طلایی ۲). خروجی تا تأیید ردیف‌های «نیازمند ورود» «پیش‌نویس» است."
      />

      {msg && (
        <div
          className={`rounded-xl px-4 py-3 text-[12.5px] leading-6 border ${
            msg.ok
              ? "bg-emerald/10 border-emerald/30 text-emerald"
              : "bg-rose/10 border-rose/30 text-rose"
          }`}
        >
          {msg.text}
        </div>
      )}

      {/* ══ ۱) تنظیمات و جابه‌جایی فایل ══ */}
      <Card className="p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="block">
            <span className="text-[11.5px] font-bold text-ink-dim block mb-1.5">نام کاربر</span>
            <input
              value={settings.priceUser}
              onChange={(e) => patch({ priceUser: e.target.value })}
              placeholder="دفتر فنی"
              className="bg-panel-2 border border-line rounded-lg px-3 py-2 text-[12.5px] w-full outline-none focus:border-gold/50"
            />
          </label>
          <label className="block">
            <span className="text-[11.5px] font-bold text-ink-dim block mb-1.5">
              آستانهٔ هشدار اختلاف (٪)
            </span>
            <input
              type="number"
              min={1}
              max={200}
              value={String(settings.priceDiffWarnPct ?? 30)}
              onChange={(e) => patch({ priceDiffWarnPct: Number(e.target.value) || 30 })}
              className="bg-panel-2 border border-line rounded-lg px-3 py-2 text-[12.5px] num w-full outline-none focus:border-gold/50"
            />
          </label>
          <div className="flex items-end gap-2 flex-wrap">
            <button
              onClick={() => {
                const name = downloadProjectProfile(settings, meta, projectName);
                setMsg({ ok: true, text: `پروفایل پروژه دانلود شد: ${name}` });                setMsg({ ok: true, text: `فایل کناری قیمت‌ها دانلود شد: ${name}` });
              }}
              className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-2 rounded-lg bg-sky/10 border border-sky/30 text-sky hover:bg-sky/20 transition-colors"
            >
              <Save size={13} /> ذخیره پروفایل پروژه
            </button>
            <button
              onClick={onCopyProject}
              className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-2 rounded-lg bg-white/[0.05] border border-line text-ink-dim hover:text-ink transition-colors"
            >
              <Copy size={13} /> پروژهٔ جدید از روی این پروژه
            </button>
            <button
              onClick={() => fileJson.current?.click()}
              className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-2 rounded-lg bg-white/[0.05] border border-line text-ink-dim hover:text-ink transition-colors"
            >
              <Download size={13} /> بارگذاری JSON
            </button>
            <button
              onClick={() => fileXlsx.current?.click()}
              className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-2 rounded-lg bg-white/[0.05] border border-line text-ink-dim hover:text-ink transition-colors"
            >
              <FileUp size={13} /> ورود از Excel
            </button>
            <input
              ref={fileXlsx}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && onImportXlsx(e.target.files[0])}
            />
            <input
              ref={fileJson}
              type="file"
              accept=".json"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && onImportJson(e.target.files[0])}
            />
          </div>
        </div>
      </Card>

      {/* ══ ۲) وضعیت کلی قیمت‌ها ══ */}
      <div className="grid grid-cols-2 xl:grid-cols-6 gap-3">
        {MANUAL_STATUSES.map((st) => (
          <Stat
            key={st}
            label={`${STATUS_ICON[st] ?? ""} ${st}`}
            value={fmtNum(ps[st] ?? 0, 0)}
            tone={st === "نیازمند ورود" ? "gold" : st === "دستی" ? "sky" : "emerald"}
          />
        ))}
      </div>
      {npe > 0 && (
        <div className="rounded-xl bg-gold/10 border border-gold/30 px-4 py-3 text-[12.5px] leading-6 text-gold">
          ⚠️ {faDigits(String(npe))} ردیف «نیازمند ورود» هستند — خروجی تا تأیید آن‌ها
          «پیش‌نویس» است (بازبینی در گام «تطبیق هوشمند»).
        </div>
      )}
      {result.starredTotal > 0 && (
        <div className="rounded-xl bg-white/[0.04] border border-line/60 px-4 py-3 text-[12.5px] leading-6 text-ink">
          ⭐ جمع ردیف‌های ستاره‌دار: <b className="num">{fmtRial(result.starredTotal)}</b> ریال
          {" — "}
          {faDigits((result.starredPct ?? 0).toFixed(1))}٪ از برآورد کل
        </div>
      )}

      {/* ═ـ ۳) ردیف‌های ستاره‌دار ══ */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center gap-2 text-[13px] font-bold text-ink">
          <Star size={15} className="text-gold" />
          افزودن ردیف ستاره‌دار (غیرفهرستی — ورود کامل دستی)
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">کد (اختیاری)</span>
            <input
              value={fCode}
              onChange={(e) => setFCode(e.target.value)}
              placeholder="۹۹۰۱۰۱"
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none focus:border-gold/50"
            />
          </label>
          <label className="block md:col-span-2">
            <span className="text-[10.5px] text-ink-dim block mb-1">شرح ردیف*</span>
            <input
              value={fDesc}
              onChange={(e) => setFDesc(e.target.value)}
              placeholder="قفل‌سازی و یراق‌آلات درب‌ها"
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] w-full outline-none focus:border-gold/50"
            />
          </label>
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">واحد</span>
            <select
              value={fUnit}
              onChange={(e) => setFUnit(e.target.value)}
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] w-full outline-none"
            >
              {["عدد", "مترطول", "مترمربع", "مترمکعب", "کیلوگرم", "تن", "فقره"].map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">فصل (برای شاخص تعدیل)</span>
            <select
              value={fChapter}
              onChange={(e) => setFChapter(e.target.value)}
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none"
            >
              {CHAPTER_OPTS.map((c) => (
                <option key={c} value={c}>{`${c} — ${chapterTitle(c)}`}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex items-center gap-2 text-[11.5px]">
          <span className="text-ink-dim font-bold">روش ورود مقدار (ریزمتره):</span>
              <button
            onClick={() => setMode("direct")}
            className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
              mode === "direct" ? "bg-gold/15 text-gold" : "bg-white/[0.05] text-ink-dim"
            }`}
          >
            عدد مستقیم
          </button>
          <button
            onClick={() => setMode("dims")}
            className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
              mode === "dims" ? "bg-gold/15 text-gold" : "bg-white/[0.05] text-ink-dim"
            }`}
          >
            تعداد × طول × عرض × ارتفاع
          </button>
        </div>

        {mode === "direct" ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            <label className="block">
              <span className="text-[10.5px] text-ink-dim block mb-1">مقدار*</span>
              <input
                value={fQty}
                onChange={(e) => setFQty(e.target.value)}
                placeholder="۱۲"
                className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none focus:border-gold/50"
              />
            </label>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            {[
              ["تعداد*", fCnt, setFCnt],
              ["طول (متر)", fLen, setFLen],
              ["عرض (متر)", fWid, setFWid],
              ["ارتفاع/ضخامت (متر)", fHt, setFHt],
            ].map(([label, val, set]) => (
              <label key={label as string} className="block">
                <span className="text-[10.5px] text-ink-dim block mb-1">{label as string}</span>
                <input
                  value={val as string}
                  onChange={(e) => (set as (v: string) => void)(e.target.value)}
                  className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none focus:border-gold/50"
                />
              </label>
            ))}
          </div>
        )}
        {mode === "dims" && Number(fCnt) > 0 && (
          <div className="text-[11.5px] text-ink-dim">
            مقدار محاسبه‌شده:{" "}
            <b className="text-ink num">{fmtNum(qtyFromDims, 2)}</b> {fUnit}
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">بهای واحد (ریال)*</span>
            <input
              value={fPrice}
              onChange={(e) => setFPrice(e.target.value)}
              placeholder="۲٬۵۰۰٬۰۰۰"
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none focus:border-gold/50"
            />
          </label>
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">منبع*</span>
            <select
              value={fSource}
              onChange={(e) => setFSource(e.target.value)}
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] w-full outline-none"
            >
              {MANUAL_SOURCES.filter((s) => s !== "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)").map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">شماره سند</span>
            <input
              value={fDocNo}
              onChange={(e) => setFDocNo(e.target.value)}
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none focus:border-gold/50"
            />
          </label>
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">تاریخ سند (شمسی)</span>
            <input
              value={fDocDate}
              onChange={(e) => setFDocDate(e.target.value)}
              placeholder="۱۴۰۵/۰۴/۱۲"
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-full outline-none focus:border-gold/50"
            />
          </label>
          <label className="block">
            <span className="text-[10.5px] text-ink-dim block mb-1">توضیح محل/کاربرد</span>
            <input
              value={fNote}
              onChange={(e) => setFNote(e.target.value)}
              className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] w-full outline-none focus:border-gold/50"
            />
          </label>
        </div>

        {errs.length > 0 && (
          <div className="space-y-1">
            {errs.map((e) => (
              <div key={e} className="text-rose text-[11.5px]">• {e}</div>
            ))}
          </div>
        )}
        <button
          onClick={addStarred}
          className="flex items-center gap-1.5 text-[12.5px] font-bold px-4 py-2.5 rounded-xl bg-gold/15 border border-gold/30 text-gold hover:bg-gold/25 transition-colors"
        >
          <Plus size={14} /> افزودن ردیف ستاره‌دار
        </button>

        {settings.starredRows.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-line/60">
            <div className="text-[12px] font-bold text-ink-dim">
              ردیف‌های ستاره‌دار ثبت‌شده ({faDigits(String(settings.starredRows.length))})
            </div>
            {settings.starredRows.map((sr, i) => (
              <div
                key={`${sr.code}-${i}`}
                className="flex items-center gap-3 flex-wrap rounded-lg bg-white/[0.03] border border-line/60 px-3 py-2 text-[12px]"
              >
                <span className="num text-gold font-bold">{faDigits(sr.code || "—")}*</span>
                <span className="text-ink/90 flex-1 min-w-[160px]">
                  {sr.desc}
                  {sr.note ? <span className="text-ink-dim"> ({sr.note})</span> : null}
                </span>
                <span className="num text-ink-dim text-[11px]">
                  {fmtNum(sr.qty, 2)} {sr.unit}
                </span>
                <span className="num text-ink-dim text-[11px]">{fmtRial(sr.price)}</span>
                <b className="num text-ink">{fmtRial(sr.qty * sr.price)}</b>
                <span className="text-[10.5px] text-ink-dim">
                  {sr.source} · {sr.docNo || "بدون سند"} · {sr.docDate || "بدون تاریخ"} · فصل{" "}
                  {faDigits(sr.chapter)}
                </span>
                <button
                  onClick={() => delStarred(i)}
                  className="text-rose hover:text-rose/80 transition-colors"
                  title="حذف ردیف ستاره‌دار"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ══ ۴) سابقهٔ ویرایش ══ */}
      <Card className="p-4 space-y-3">
        <div className="flex items-center gap-2 text-[13px] font-bold text-ink">
          <ClipboardList size={15} className="text-sky" />
          سابقهٔ ویرایش
          <span className="text-ink-dim font-normal text-[11.5px]">
            ({faDigits(String(settings.priceAudit.length))} رویداد — جدیدترین در بالا)
          </span>
        </div>
        {settings.priceAudit.length === 0 ? (
          <div className="text-[12px] text-ink-dim py-3">
            هنوز رویدادی ثبت نشده است. هر ویرایش قیمت، کد یا استثنا در اینجا با
            زمان، کاربر و منبع ذخیره می‌شود.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11.5px] border-collapse">
              <thead>
                <tr className="text-ink-dim border-b border-line/60">
                  {["زمان", "کاربر", "ردیف", "فیلد", "مقدار قبلی", "مقدار جدید", "منبع", "نوع"].map((h) => (
                    <th key={h} className="text-right font-bold py-2 px-2 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...settings.priceAudit].reverse().map((a: AuditEntry, i) => (
                  <tr key={i} className="border-b border-line/30">
                    <td className="py-1.5 px-2 num whitespace-nowrap">{a.at}</td>
                    <td className="py-1.5 px-2 whitespace-nowrap">{a.user}</td>
                    <td className="py-1.5 px-2 num whitespace-nowrap">{faDigits(a.item)}</td>
                    <td className="py-1.5 px-2 whitespace-nowrap">{a.field}</td>
                    <td className="py-1.5 px-2 num whitespace-nowrap">{fmtAuditVal(a.old)}</td>
                    <td className="py-1.5 px-2 num whitespace-nowrap">{fmtAuditVal(a.new)}</td>
                    <td className="py-1.5 px-2 whitespace-nowrap">{a.source}</td>
                    <td className="py-1.5 px-2 whitespace-nowrap">{AUDIT_KIND_LABELS[a.kind ?? "price"] ?? "قیمت/کد"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function fmtAuditVal(v: unknown): string {
  if (v == null || v === "") return "—";
  if (typeof v === "number") return fmtNum(v, 0);
  return faDigits(String(v));
}
