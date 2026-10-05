import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BadgeCheck,
  ChevronDown,
  CircleAlert,
  Cpu,
  Eraser,
  Eye,
  FileSearch2,
  ListFilter,
  PenLine,
  RotateCcw,
  Search,
  Sparkles,
} from "lucide-react";
import { Badge, Card, Confidence, SectionTitle, Stat } from "./ui";
import type { BoqLine, FehrestRow, ProjectResult, ProjectSettings } from "../lib/types";
import { MANUAL_SOURCES } from "../lib/types";
import { searchFehrest } from "../lib/matching";
import { appendAudit, excludedIds, manualCodeOf, manualRecord } from "../lib/engine";
import { isValidJalaliDate, jalaliNowStr } from "../lib/farsi";
import { cn } from "../utils/cn";
import { faDigits, fmtNum, fmtRial } from "../lib/normalize";

const METHOD_LABEL: Record<string, { label: string; tone: "emerald" | "teal" | "gold" | "sky" }> = {
  "rule-exact": { label: "قانون + کد دقیق", tone: "emerald" },
  "rule-fuzzy": { label: "قانون فازی", tone: "teal" },
  fuzzy: { label: "تطبیق فازی", tone: "gold" },
  manual: { label: "تأیید دستی", tone: "sky" },
  "direct-code": { label: "کد مستقیم", tone: "emerald" },
  "manual-starred": { label: "ردیف ستاره‌دار (دستی)", tone: "gold" },
};

export function MatchStep({
  result,
  settings,
  setSettings,
  db,
  projectName,
}: {
  result: ProjectResult | null;
  settings: ProjectSettings;
  setSettings: (s: ProjectSettings) => void;
  db: FehrestRow[];
  projectName: string;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [searchTexts, setSearchTexts] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<"all" | "review" | "estimated">("all");

  if (!result || !result.lines.length) {
    return (
      <Card className="text-center py-16">
        <FileSearch2 size={42} className="mx-auto text-ink-dim mb-4" />
        <h3 className="text-ink font-bold text-lg">هنوز ردیفی برای تطبیق وجود ندارد</h3>
        <p className="text-ink-dim text-[13px] mt-2">ابتدا در گام «جداول Revit» خروجی‌های پروژه را بارگذاری کنید.</p>
      </Card>
    );
  }

  const setManual = (lineId: string, code: string | null) => {
    const next = { ...settings, manualCodes: { ...settings.manualCodes } };
    const line = result.lines.find((l) => l.id === lineId);
    if (code) {
      const prevCode = manualCodeOf(settings, lineId);
      next.manualCodes[lineId] = {
        code,
        reason: "انتخاب دستی از نامزدهای فهرست‌بها",
        user: settings.priceUser,
        at: jalaliNowStr(),
      };
      if (prevCode !== code) {
        appendAudit(next, line?.code ?? lineId, "code", prevCode || code, code, "انتخاب از گام تطبیق");
      }
    } else {
      delete next.manualCodes[lineId];
    }
    setSettings(next);
  };
  const savePrice = (
    lineId: string,
    price: number | null,
    source: string,
    docNo: string,
    docDate: string,
  ) => {
    const line = result.lines.find((l) => l.id === lineId);
    const prev = settings.manualPrices[lineId];
    const next = { ...settings, manualPrices: { ...settings.manualPrices } };
    if (price !== null && price > 0) {
      next.manualPrices[lineId] = manualRecord(
        price,
        source,
        docNo,
        docDate,
        prev?.note ?? "",
        "دستی",
        line?.chapter ?? prev?.chapter ?? "",
        settings.priceUser,
        jalaliNowStr(),
      );
      appendAudit(next, line?.code ?? lineId, "price", prev?.price ?? line?.price ?? 0, price, source);
    } else {
      delete next.manualPrices[lineId];
      if (prev) appendAudit(next, line?.code ?? lineId, "price", prev.price, line?.price ?? null, "حذف قیمت دستی");
    }
    setSettings(next);
  };
  const clearPrice = (lineId: string) => savePrice(lineId, null, "", "", "");
  const toggleExcluded = (lineId: string) => {
    const line = result.lines.find((l) => l.id === lineId);
    const ex = excludedIds(settings);
    const next = { ...settings, excluded: [...settings.excluded] };
    if (ex.has(lineId)) {
      next.excluded = next.excluded.filter((e) => (typeof e === "string" ? e : e.id) !== lineId);
    } else {
      next.excluded.push({
        id: lineId,
        reason: "استثنا از گام تطبیق",
        user: settings.priceUser,
        at: jalaliNowStr(),
      });
      appendAudit(next, line?.code ?? lineId, "exclude", false, true, "استثنا دستی");
    }
    setSettings(next);
  };

  const lines = result.lines.filter((l) => {
    if (filter === "review") return l.needsReview;
    if (filter === "estimated") return l.estimatedPrice;
    return true;
  });

  const q = result.quality;

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="گام ۵ — بررسی انسانی با کمک هوش مصنوعی"
        title="تطبیق هوشمند متره‌ها با فهرست‌بهای ۱۴۰۴"
        sub="هر ردیف توسط موتور قوانین سازه‌ای + الگوریتم فازی فارسی تطبیق داده شده است. ردیف‌های کم‌اطمینان یا دارای بهای تخمینی را بازبینی و در صورت نیاز اصلاح کنید."
        action={
          <div className="flex rounded-xl overflow-hidden border border-line">
            {(["all", "review", "estimated"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "px-4 py-2.5 text-[12px] font-bold transition-colors flex items-center gap-1.5",
                  filter === f ? "bg-gold/15 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                )}
              >
                <ListFilter size={13} />
                {f === "all" ? "همهٔ ردیف‌ها" : f === "review" ? "نیازمند بررسی" : "بهای تخمینی"}
              </button>
            ))}
          </div>
        }
      />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Stat label="ردیف‌های تولیدشده" value={fmtNum(q.linesMatched, 0)} icon={<Cpu size={18} />} tone="sky" />
        <Stat label="تطبیق دقیق" value={fmtNum(q.linesExact, 0)} icon={<BadgeCheck size={18} />} tone="emerald" hint="کد ردیف مستقیماً یافت شد" />
        <Stat label="تطبیق فازی" value={fmtNum(q.linesFuzzy, 0)} icon={<Sparkles size={18} />} tone="teal" hint="بر اساس شباهت متنی شرح" />
        <Stat label="نیازمند بررسی" value={fmtNum(q.linesNeedReview, 0)} icon={<CircleAlert size={18} />} tone={q.linesNeedReview ? "gold" : "emerald"} />
      </div>

      <div className="space-y-3">
        {lines.map((l) => (
          <LineCard
            key={l.id}
            line={l}
            expanded={expanded === l.id}
            onToggle={() => setExpanded(expanded === l.id ? null : l.id)}
            db={db}
            searchText={searchTexts[l.id] ?? ""}
            onSearch={(t) => setSearchTexts({ ...searchTexts, [l.id]: t })}
            onPick={(code) => setManual(l.id, code)}
            onClearManual={() => setManual(l.id, null)}
            onToggleExcluded={() => toggleExcluded(l.id)}
            settings={settings}
            onSavePrice={savePrice}
            onClearPrice={clearPrice}
            projectName={projectName}
          />
        ))}
        {!lines.length && (
          <Card className="text-center py-10 text-ink-dim text-[13px]">
            ردیفی با این فیلتر یافت نشد — همه‌چیز سالم است.
          </Card>
        )}
      </div>
    </div>
  );
}

function LineCard({
  line: l,
  expanded,
  onToggle,
  db,
  searchText,
  onSearch,
  onPick,
  onClearManual,
  onToggleExcluded,
  settings,
  onSavePrice,
  onClearPrice,
}: {
  line: BoqLine;
  expanded: boolean;
  onToggle: () => void;
  db: FehrestRow[];
  searchText: string;
  onSearch: (t: string) => void;
  onPick: (code: string) => void;
  onClearManual: () => void;
  onToggleExcluded: () => void;
  settings: ProjectSettings;
  onSavePrice: (lineId: string, price: number | null, source: string, docNo: string, docDate: string) => void;
  onClearPrice: (lineId: string) => void;
  projectName: string;
}) {
  const m = METHOD_LABEL[l.matchMethod];
  const searched =
    searchText.trim().length >= 3
      ? searchFehrest(db, searchText, { top: 6, minScore: 0.25 }).map((c) => ({
          code: c.row.code,
          desc: c.row.desc,
          price: c.row.price,
          score: c.score,
        }))
      : l.candidates;

  return (
    <Card className={cn("p-0 overflow-visible transition-all", l.needsReview && "border-gold/30")}>
      <div className="flex items-center gap-4 p-4 flex-wrap">
        <button onClick={onToggle} className="flex items-center gap-4 flex-1 min-w-0 text-right flex-wrap">
          <span className="w-8 h-8 rounded-lg bg-white/[0.05] grid place-items-center text-[12px] num font-bold text-ink-dim shrink-0">
            {faDigits(String(l.rowNo))}
          </span>
          <div className="flex-1 min-w-[200px]">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="num text-gold font-extrabold text-[13.5px]">{faDigits(l.code)}</span>
              <Badge tone={m.tone}>{m.label}</Badge>
              {l.estimatedPrice && <Badge tone="gold"><CircleAlert size={11} /> بهای تخمینی</Badge>}
              {l.note && <Badge tone="violet"><Eye size={11} /> محاسبهٔ استنتاجی</Badge>}
            </div>
            <div className="text-[13px] text-ink/90 font-medium leading-6 mt-1 truncate">{l.desc}</div>
            <div className="text-[11px] text-ink-dim mt-0.5">
              فصل {faDigits(l.chapter)} ({l.chapterTitle}) · مقدار: <b className="text-ink num">{fmtNum(l.qty, 2)}</b> {l.unit}
              {l.indexFactor !== 1 && <span> (ضریب تعدیل: {fmtNum(l.indexFactor, 4)})</span>}
            </div>
          </div>
          <div className="text-left shrink-0">
            <div className="num font-extrabold text-ink text-[15px]">{fmtRial(l.total)}</div>
            <div className="text-[10.5px] text-ink-dim mt-0.5">ریال</div>
          </div>
          <Confidence value={l.confidence} />
          <ChevronDown size={17} className={cn("text-ink-dim transition-transform shrink-0", expanded && "rotate-180")} />
        </button>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-line/60 p-4 space-y-4 bg-white/[0.015]">
              {l.note && (
                <div className="text-[12px] text-violet bg-violet/10 border border-violet/25 rounded-lg px-3.5 py-2.5 leading-6">{l.note}</div>
              )}

              {/* منابع کمیت */}
              <div>
                <div className="text-[11.5px] font-bold text-ink-dim mb-2">منبع کمیت (ردیابی تا جدول Revit)</div>
                <div className="flex flex-wrap gap-1.5">
                  {l.sources.slice(0, 6).map((s, i) => (
                    <span key={i} className="text-[10.5px] bg-white/[0.045] border border-line/60 rounded-md px-2 py-1 text-ink-dim">
                      {s.tableTitle} — {s.ref} <b className="text-ink/80 num">{fmtNum(s.qty, 2)}</b>
                    </span>
                  ))}
                  {l.sources.length > 6 && (
                    <span className="text-[10.5px] bg-gold/10 border border-gold/25 rounded-md px-2 py-1 text-gold">
                      + {fmtNum(l.sources.length - 6, 0)} منبع دیگر
                    </span>
                  )}
                </div>
              </div>

              {/* ویرایش قیمت و حذف */}
              <ManualPriceEditor
                line={l}
                settings={settings}
                onSave={(price, source, docNo, docDate) => onSavePrice(l.id, price, source, docNo, docDate)}
                onClear={() => onClearPrice(l.id)}
              />
              <div className="flex items-center gap-3 flex-wrap">
                {l.matchMethod === "manual" && (
                  <button onClick={onClearManual} className="flex items-center gap-1 text-[11.5px] text-sky hover:text-sky/80 font-semibold">
                    <RotateCcw size={12} /> بازگشت به تطبیق خودکار
                  </button>
                )}
                <button onClick={onToggleExcluded} className="flex items-center gap-1 text-[11.5px] text-rose hover:text-rose/80 font-semibold mr-auto">
                  <Eraser size={12} /> {excludedIds(settings).has(l.id) ? "بازگردانی به صورت‌وضعیت" : "حذف این ردیف از صورت‌وضعیت"}
                </button>
              </div>

              {/* جست‌وجو و نامزدهای جایگزین */}
              <div>
                <div className="relative mb-2.5">
                  <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-dim" />
                  <input
                    value={searchText}
                    onChange={(e) => onSearch(e.target.value)}
                    placeholder="جست‌وجوی ردیف جایگزین در فهرست‌بها… (مثلاً: قالب پی)"
                    className="w-full bg-panel-2 border border-line rounded-xl pr-9 pl-3 py-2.5 text-[12.5px] outline-none focus:border-gold/50 placeholder:text-ink-dim/70"
                  />
                </div>
                <div className="grid gap-1.5">
                  {searched.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => onPick(c.code)}
                      className={cn(
                        "flex items-center gap-3 text-right rounded-xl border px-3.5 py-2.5 transition-colors",
                        c.code === l.code
                          ? "border-gold/50 bg-gold/[0.07]"
                          : "border-line/60 hover:border-gold/30 hover:bg-white/[0.03]",
                      )}
                    >
                      <span className="num text-gold font-bold text-[12px] shrink-0 w-14">{faDigits(c.code)}</span>
                      <span className="text-[12px] text-ink/90 leading-5 flex-1">{c.desc}</span>
                      <span className="num text-[11.5px] text-ink-dim shrink-0">{fmtRial(c.price)} ریال</span>
                      <span className={cn("text-[10px] font-bold num shrink-0", c.score >= 0.8 ? "text-emerald" : c.score >= 0.6 ? "text-gold" : "text-ink-dim")}>
                        {fmtNum(Math.round(c.score * 100), 0)}٪
                      </span>
                    </button>
                  ))}
                  {!searched.length && <div className="text-[12px] text-ink-dim py-2">نامزدی یافت نشد؛ عبارت دیگری را جست‌وجو کنید.</div>}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

/** ویرایشگر قیمت دستی یک ردیف: قیمت + منبع + شماره/تاریخ سند (فاز C — §۱۵-۴). */
function ManualPriceEditor({
  line: l,
  settings,
  onSave,
  onClear,
}: {
  line: BoqLine;
  settings: ProjectSettings;
  onSave: (price: number | null, source: string, docNo: string, docDate: string) => void;
  onClear: () => void;
}) {
  const rec = settings.manualPrices[l.id];
  const [open, setOpen] = useState(false);
  const [price, setPrice] = useState(String(rec?.price ?? l.price));
  const [source, setSource] = useState(rec?.source ?? "استعلام");
  const [docNo, setDocNo] = useState(rec?.docNo ?? "");
  const [docDate, setDocDate] = useState(rec?.docDate ?? "");
  const [err, setErr] = useState("");

  const srcOpts = MANUAL_SOURCES.filter((s) => s !== "ویرایش قدیمی (قبل از مرحلهٔ ۱۳)");

  const submit = () => {
    const v = parseFloat(price.replace(/[,٬\s]/g, ""));
    if (!Number.isFinite(v) || v <= 0) {
      setErr("بهای واحد باید عددی بزرگتر از صفر باشد.");
      return;
    }
    if (docDate.trim() && !isValidJalaliDate(docDate.trim())) {
      setErr("تاریخ سند شمسی معتبر نیست (نمونه: ۱۴۰۵/۰۴/۱۲).");
      return;
    }
    setErr("");
    setOpen(false);
    onSave(v, source, docNo.trim(), docDate.trim());
  };

  const diffPct = l.diffPct;
  const overThreshold =
    diffPct != null && Math.abs(diffPct) > (settings.priceDiffWarnPct ?? 30);

  return (
    <div className="rounded-xl border border-line/60 bg-panel-2/40 px-3.5 py-3 space-y-2.5">
      <div className="flex items-center gap-3 flex-wrap text-[12px]">
        <span className="text-ink-dim">بهای واحد:</span>
        <b className="num text-ink">{fmtRial(l.price)}</b>
        <span className="text-ink-dim">ریال</span>
        {rec ? (
          <>
            <Badge tone={overThreshold ? "gold" : "sky"}>
              {rec.status} · {rec.source}
              {rec.docNo ? ` · سند ${faDigits(rec.docNo)}` : ""}
              {rec.docDate ? ` · ${faDigits(rec.docDate)}` : ""}
            </Badge>
            {l.appPrice != null && (
              <span className={cn("text-[11px]", overThreshold ? "text-gold font-bold" : "text-ink-dim")}>
                قیمت فهرست: {fmtRial(l.appPrice)} · اختلاف{" "}
                {faDigits((diffPct ?? 0).toFixed(1))}٪
                {overThreshold && " — بیش از آستانهٔ بازبینی"}
              </span>
            )}
            <button
              onClick={() => {
                setPrice(String(rec.price));
                setSource(rec.source);
                setDocNo(rec.docNo);
                setDocDate(rec.docDate);
                setErr("");
                setOpen(true);
              }}
              className="text-ink-dim hover:text-gold transition-colors"
              title="ویرایش قیمت دستی"
            >
              <PenLine size={13} />
            </button>
            <button
              onClick={onClear}
              className="flex items-center gap-1 text-[11px] text-rose hover:text-rose/80 font-semibold"
            >
              <RotateCcw size={11} /> حذف قیمت دستی
            </button>
          </>
        ) : (
          <button
            onClick={() => {
              setPrice(String(l.price));
              setSource("استعلام");
              setDocNo("");
              setDocDate("");
              setErr("");
              setOpen(true);
            }}
            className="flex items-center gap-1 text-[11.5px] text-gold hover:text-gold/80 font-semibold"
          >
            <PenLine size={12} /> ورود قیمت دستی
          </button>
        )}
      </div>

      {open && (
        <div className="flex items-center gap-2 flex-wrap pt-1">
          <input
            autoFocus
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="بهای واحد (ریال)"
            className="bg-panel-2 border border-gold/50 rounded-lg px-2.5 py-1.5 text-[12px] num w-40 outline-none"
          />
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] outline-none"
          >
            {srcOpts.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            value={docNo}
            onChange={(e) => setDocNo(e.target.value)}
            placeholder="شماره سند"
            className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-28 outline-none"
          />
          <input
            value={docDate}
            onChange={(e) => setDocDate(e.target.value)}
            placeholder="تاریخ سند (۱۴۰۵/۰۴/۱۲)"
            className="bg-panel-2 border border-line rounded-lg px-2.5 py-1.5 text-[12px] num w-32 outline-none"
          />
          <button
            onClick={submit}
            className="text-emerald text-[11.5px] font-bold px-2.5 py-1.5 rounded-lg hover:bg-emerald/10 transition-colors"
          >
            ثبت قیمت دستی
          </button>
          <button
            onClick={() => {
              setOpen(false);
              setErr("");
            }}
            className="text-ink-dim text-[11.5px] font-semibold px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors"
          >
            انصراف
          </button>
          {err && <span className="text-rose text-[11px]">{err}</span>}
        </div>
      )}
    </div>
  );
}


