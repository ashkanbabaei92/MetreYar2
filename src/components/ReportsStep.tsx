import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Banknote,
  Boxes,
  ChartColumn,
  ClipboardList,
  FileDigit,
  History,
  Layers3,
  Save,
  ShieldCheck,
  Sigma,
  Trash2,
} from "lucide-react";
import { Badge, Card, SectionTitle, Stat, BigMoney } from "./ui";
import { Donut, HBar } from "./charts";
import type { ProjectMeta, ProjectResult, ProjectSettings, StatusReportRecord } from "../lib/types";
import { cn } from "../utils/cn";
import { faDigits, fmtKg, fmtNum, fmtRial } from "../lib/normalize";
import { fmtMoneyVal, moneyToWords } from "../lib/farsi";
import { AdjustmentTab } from "./ReportsStep_PhaseB";

type Tab = "financial" | "boq" | "detail" | "rebar" | "analysis" | "adjustment";

const TABS: { id: Tab; title: string; icon: typeof Banknote }[] = [
  { id: "financial", title: "خلاصهٔ مالی", icon: Banknote },
  { id: "boq", title: "خلاصه‌متره و صورت‌وضعیت", icon: ClipboardList },
  { id: "detail", title: "ریزمترهٔ تفصیلی", icon: Layers3 },
  { id: "rebar", title: "لیستوفر آرماتور", icon: Boxes },
  { id: "analysis", title: "آنالیز و کیفیت", icon: ChartColumn },
  { id: "adjustment", title: "موتورهای تعدیل (فاز B)", icon: Sigma },
];

export function ReportsStep({
  result,
  settings,
  meta,
  history,
  setHistory,
}: {
  result: ProjectResult | null;
  settings: ProjectSettings;
  meta: ProjectMeta;
  history: StatusReportRecord[];
  setHistory: (h: StatusReportRecord[]) => void;
}) {
  const [tab, setTab] = useState<Tab>("financial");

  if (!result || !result.lines.length) {
    return (
      <Card className="text-center py-16">
        <FileDigit size={42} className="mx-auto text-ink-dim mb-4" />
        <h3 className="text-ink font-bold text-lg">گزارشی برای نمایش وجود ندارد</h3>
        <p className="text-ink-dim text-[13px] mt-2">ابتدا جداول Revit را بارگذاری و پردازش را تکمیل کنید.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {TABS.filter((t) => t.id !== "adjustment" || (result.adjustment?.tadil || result.adjustment?.baravord)).map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-2 px-[18px] py-2.5 rounded-xl text-[12.5px] font-bold whitespace-nowrap transition-all border",
                active
                  ? "bg-gold/15 border-gold/40 text-gold"
                  : "bg-panel-2/60 border-line/60 text-ink-dim hover:text-ink hover:border-line",
              )}
            >
              <Icon size={15} />
              {t.title}
            </button>
          );
        })}
      </div>

      <motion.div key={tab} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
        {tab === "financial" && <FinancialTab result={result} settings={settings} meta={meta} history={history} setHistory={setHistory} />}
        {tab === "boq" && <BoqTab result={result} />}
        {tab === "detail" && <DetailTab result={result} />}
        {tab === "rebar" && <RebarTab result={result} />}
        {tab === "analysis" && <AnalysisTab result={result} />}
        {tab === "adjustment" && <AdjustmentTab result={result} />}
      </motion.div>
    </div>
  );
}

// ── تب ۱: خلاصهٔ مالی ──
function FinancialTab({
  result,
  settings,
  meta,
  history,
  setHistory,
}: {
  result: ProjectResult;
  settings: ProjectSettings;
  meta: ProjectMeta;
  history: StatusReportRecord[];
  setHistory: (h: StatusReportRecord[]) => void;
}) {
  const fo = { currency: settings.currency, rounding: settings.rounding };
  const donutData = result.chapterSums.map((c) => ({
    label: `فصل ${faDigits(c.chapter)} · ${c.title}`,
    value: c.total,
    hint: fmtNum(c.total / 1e10, 1),
  }));

  // یادداشت دورهٔ شاخص تعدیل (در صورت تفاوت با دورهٔ مبنا)
  const idx = result.index;
  let idxNote = "";
  if (idx && idx.targetPeriod && idx.targetPeriod !== idx.basePeriod) {
    idxNote = ` — تعدیل به دورهٔ ${idx.targetPeriod}` + (idx.provisional ? " (شاخص موقت)" : "");
  }
  // هشدار سقف ۴٪ تجهیز و برچیدن (دستورالعمل کاربرد بند ۲-۸)
  let siteSetupWarning: string | null = null;
  if (result.regionalAmount > 0) {
    const cap = 0.04 * result.regionalAmount;
    if (result.siteSetup > cap) {
      siteSetupWarning =
        `هشدار: مبلغ تجهیز و برچیدن کارگاه بیش از ۴٪ مبلغ قبل از آن ` +
        `(${fmtMoneyVal(cap, { currency: settings.currency })}) است (دستورالعمل کاربرد بند ۲-۸).`;
    }
  }
  // گزارش شاخص فقط وقتی دورهٔ هدف با مبنا متفاوت است
  const indexTable =
    idx && idx.targetPeriod && idx.targetPeriod !== idx.basePeriod ? idx : null;

  function saveToHistory() {
    const prev = history[history.length - 1];
    const record: StatusReportRecord = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      reportNo: meta.reportNo || faDigits(String(history.length + 1)),
      reportType: meta.reportType === "قطعی" ? "قطعی" : "موقت",
      periodStart: meta.periodStart,
      periodEnd: meta.periodEnd,
      grossPayable: result.grossPayable,
      totalDeductions: result.totalDeductions,
      netPayable: result.netPayable,
      currentWork: result.netPayable - (prev?.netPayable ?? 0),
    };
    setHistory([...history, record]);
  }

  return (
    <div className="grid gap-5 xl:grid-cols-5">
      {/* ستون صورت‌جمع مالی */}
      <Card glow className="xl:col-span-2">
        <SectionTitle
          kicker="صورت‌جمع مالی"
          title={`صورت‌وضعیت ${meta.reportType} شماره ${faDigits(meta.reportNo || "—")}`}
          sub={`دورهٔ کارکرد: ${meta.periodStart || "—"} تا ${meta.periodEnd || "—"}`}
        />
        <div className="space-y-3">
          <FinRow label={`الف) جمع ناخالص ردیف‌های فهرست‌بها${idxNote}`} value={result.baseTotal} fo={fo} tone="ink" />
          <div className="rounded-xl bg-white/[0.025] border border-line/50 p-3 space-y-2">
            <div className="text-[10.5px] font-bold text-teal mb-1">ضرایب فهرست‌بها</div>
            <FinRow label={`ضریب طبقات (× ${fmtNum(settings.floorsCoef, 2)})`} value={result.floorsAmount} fo={fo} small />
            <FinRow label={`ضریب بالاسری (× ${fmtNum(settings.overheadCoef, 2)})`} value={result.overheadAmount} fo={fo} small />
            <FinRow label={`ضریب منطقه‌ای (× ${fmtNum(result.coefs.regional.value ?? 1, 2)})`} value={result.regionalAmount} fo={fo} small />
          </div>
          <FinRow label="تجهیز و برچیدن کارگاه (مبلغ)" value={result.siteSetup} fo={fo} plus />
          <FinRow label="ب) مبلغ ناخالص نهایی قابل پرداخت" value={result.grossPayable} fo={fo} tone="gold" />
          {siteSetupWarning && (
            <div className="flex items-start gap-2 rounded-xl bg-amber/[0.07] border border-amber/30 p-3 text-[11.5px] text-amber leading-6">
              <AlertTriangle size={14} className="shrink-0 mt-1" />
              <span>{siteSetupWarning}</span>
            </div>
          )}
          {indexTable && (
            <div className="rounded-xl bg-white/[0.025] border border-line/50 p-3 space-y-2">
              <div className="text-[10.5px] font-bold text-teal mb-1">
                گزارش شاخص تعدیل فهرست‌بها — دورهٔ مبنا: {indexTable.basePeriod} — دورهٔ هدف: {indexTable.targetPeriod}
                {indexTable.provisional ? " — شاخص موقت" : ""}
              </div>
              <div className="overflow-x-auto">
                <table className="dt">
                  <thead>
                    <tr>
                      <th className="text-right">فصل</th>
                      <th className="text-right">ضریب</th>
                      <th className="text-right">نوع شاخص</th>
                      <th className="text-right">منبع (بخشنامه)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {indexTable.chapters.filter((r) => r.factor !== null && r.factor !== 1).map((r) => (
                      <tr key={r.chapter}>
                        <td className="num">{faDigits(r.chapter)}</td>
                        <td className="num">{r.factor !== null ? fmtNum(r.factor, 4) : "—"}</td>
                        <td>{r.kind ?? "—"}{r.kind === "موقت" ? <span className="text-[10px] text-amber mr-1">(موقت)</span> : null}</td>
                        <td className="text-[11px] text-ink-dim">{r.source ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {indexTable.chapters.every((r) => r.factor === null || r.factor === 1) && (
                <p className="text-[11px] text-ink-dim">ضریب همهٔ فصل‌ها در این دوره برابر ۱ است.</p>
              )}
            </div>
          )}
          {/* ── بلوک جداگانهٔ «خالص پرداختی» — بر ناخالص اثر ندارد ── */}
          <div className="rounded-xl bg-white/[0.025] border border-line/50 p-3 space-y-2">
            <div className="text-[10.5px] font-bold text-ink-dim mb-1">محاسبهٔ جداگانهٔ خالص پرداختی (کسورات قانونی)</div>
            <FinRow label="مبلغ ناخالص نهایی" value={result.grossPayable} fo={fo} small />
            <FinRow label={`کسورات: بیمه (${fmtNum(settings.insurancePct, 1)}٪)`} value={-result.insurance} fo={fo} small />
            <FinRow label={`کسورات: مالیات (${fmtNum(settings.taxPct, 1)}٪)`} value={-result.tax} fo={fo} small />
            <FinRow label={`کسورات: حسن انجام کار (${fmtNum(settings.goodJobPct, 1)}٪)`} value={-result.goodJob} fo={fo} small />
            <FinRow label="کسورات: پیش‌پرداخت" value={-result.advancePayment} fo={fo} small />
            <hr className="dot-rule" />
            <FinRow label="مجموع کسورات" value={-result.totalDeductions} fo={fo} tone="rose" small={false} />
          </div>
          <div className="rounded-xl bg-gold/[0.07] border border-gold/25 p-4">
            <div className="text-[11.5px] text-gold/90 font-bold mb-1.5">خالص پرداختی پس از کسورات</div>
            <BigMoney rial={result.netPayable} size="xl" />
            <p className="text-[11.5px] text-ink-dim mt-2.5 leading-6 border-t border-gold/15 pt-2.5">
              <span className="text-gold/80 font-semibold">به حروف: </span>
              {moneyToWords(Math.round(result.netPayable))}
            </p>
          </div>
          <button
            onClick={saveToHistory}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-emerald/15 border border-emerald/30 text-emerald text-[13px] font-bold hover:bg-emerald/25 transition-colors"
          >
            <Save size={15} />
            ثبت این صورت‌وضعیت در سوابق (تجمعی)
          </button>
        </div>
      </Card>

      {/* ستون نمودار + سوابق */}
      <div className="xl:col-span-3 space-y-5">
        <Card>
          <SectionTitle kicker="ساختار هزینه" title="سهم فصل‌های فهرست‌بها" sub="توزیع بهای کل بر اساس فصول فعال پروژه" />
          <Donut data={donutData} centerValue={fmtNum(result.baseTotal / 1e10, 1)} centerLabel="میلیارد تومان — بهای پایه" />
        </Card>

        <Card>
          <SectionTitle
            kicker="سوابق"
            title="صورت‌وضعیت‌های قبلی (تجمعی)"
            sub="«کارکرد این دوره» = خالص تجمعی فعلی منهای خالص تجمعی سابقهٔ قبلی"
          />
          {history.length === 0 ? (
            <p className="text-[12.5px] text-ink-dim leading-6">
              هنوز صورت‌وضعیتی ثبت نشده است. پس از محاسبهٔ هر دوره، دکمهٔ «ثبت در سوابق» را بزنید تا زنجیرهٔ تجمعی شکل بگیرد.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-line/60">
              <table className="dt">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>نوع</th>
                    <th>دوره از</th>
                    <th>دوره تا</th>
                    <th>خالص تجمعی</th>
                    <th>کارکرد این دوره</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => {
                    const prev = history[i - 1];
                    const current = h.netPayable - (prev?.netPayable ?? 0);
                    return (
                      <tr key={h.id}>
                        <td className="num font-bold text-gold">{faDigits(h.reportNo)}</td>
                        <td><Badge tone={h.reportType === "قطعی" ? "emerald" : "sky"}>{h.reportType}</Badge></td>
                        <td className="num text-[12px] text-ink-dim">{h.periodStart || "—"}</td>
                        <td className="num text-[12px] text-ink-dim">{h.periodEnd || "—"}</td>
                        <td className="num text-[12.5px] font-bold">{fmtMoneyVal(h.netPayable, fo)}</td>
                        <td className="num text-[12.5px] font-extrabold text-emerald">{fmtMoneyVal(current, fo)}</td>
                        <td className="w-10">
                          <button
                            onClick={() => setHistory(history.filter((x) => x.id !== h.id))}
                            className="w-7 h-7 rounded-lg grid place-items-center text-ink-dim hover:text-rose hover:bg-rose/10 transition-colors"
                            title="حذف این رکورد"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {history.length > 0 && (
            <p className="mt-3 text-[11px] text-ink-dim flex items-center gap-1.5">
              <History size={12} />
              مجموع {faDigits(String(history.length))} دوره — خالص تجمعی نهایی:{" "}
              <b className="text-ink">{fmtMoneyVal(history[history.length - 1].netPayable, fo)}</b>
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}

function FinRow({
  label,
  value,
  fo,
  tone = "dim",
  plus,
  small,
}: {
  label: string;
  value: number;
  fo: { currency: "rial" | "toman"; rounding: boolean };
  tone?: "dim" | "ink" | "gold" | "rose";
  plus?: boolean;
  small?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className={cn("text-[12.5px]", small ? "text-ink-dim/90 text-[12px]" : "text-ink-dim")}>{label}</span>
      <span
        className={cn(
          "num font-bold",
          small ? "text-[12.5px]" : "text-[13.5px]",
          tone === "gold" ? "text-gold" : tone === "rose" ? "text-rose" : tone === "ink" ? "text-ink" : "text-ink",
        )}
      >
        {plus && "+"}
        {fmtMoneyVal(value, { ...fo, withUnit: true })}
        {plus && <></>}
      </span>
    </div>
  );
}


// ── تب ۲: خلاصه‌متره / صورت‌وضعیت ──
function BoqTab({ result }: { result: ProjectResult }) {
  const chapters = [...new Set(result.lines.map((l) => l.chapter))];
  return (
    <Card className="p-0 overflow-hidden">
      <div className="p-5 pb-0">
        <SectionTitle kicker="خلاصه‌متره" title="صورت‌وضعیت ردیف‌های فهرست‌بها" sub="گروه‌بندی بر اساس فصل — قابل چاپ و برون‌بری" />
      </div>
      <div className="overflow-x-auto">
        <table className="dt">
          <thead>
            <tr>
              <th>ردیف</th>
              <th>کد فهرست‌بها</th>
              <th>شرح آیتم</th>
              <th>واحد</th>
              <th>مقدار</th>
              <th>بهای واحد</th>
              <th>بهای کل (پایه)</th>
              <th>ضریب تعدیل</th>
              <th>بهای کل (به‌هنگام)</th>
            </tr>
          </thead>
          <tbody>
            {chapters.map((ch) => {
              const lines = result.lines.filter((l) => l.chapter === ch);
              const chSum = lines.reduce((a, l) => a + l.totalIndexed, 0);
              return (
                <ChapterBlock key={ch} chapter={ch} title={lines[0]?.chapterTitle ?? ch} lines={lines} chSum={chSum} />
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={8} className="text-[13px]">جمع کل ردیف‌های فهرست‌بها</td>
              <td className="num text-[14px]">{fmtRial(result.baseTotal)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  );
}

function ChapterBlock({ chapter, title, lines, chSum }: { chapter: string; title: string; lines: ProjectResult["lines"]; chSum: number }) {
  return (
    <>
      <tr>
        <td colSpan={9} className="!py-3">
          <div className="flex items-center justify-between bg-gradient-to-l from-gold/[0.09] to-transparent rounded-lg px-4 py-2 border border-gold/15">
            <span className="text-[13px] font-extrabold text-gold">فصل {faDigits(chapter)} — {title}</span>
            <span className="num text-[12.5px] font-bold text-ink/90">{fmtRial(chSum)} <span className="text-ink-dim font-normal text-[10.5px]">ریال</span></span>
          </div>
        </td>
      </tr>
      {lines.map((l) => (
        <tr key={l.id}>
          <td className="num text-ink-dim w-10">{faDigits(String(l.rowNo))}</td>
          <td className="num font-bold text-gold text-[12.5px]">{faDigits(l.code)}</td>
          <td className="max-w-[380px]">
            <div className="text-[12.5px] leading-5 text-ink/95">{l.desc}</div>
            {l.estimatedPrice && <Badge tone="gold" className="mt-1">بهای تخمینی</Badge>}
            {l.note && <div className="text-[10.5px] text-violet mt-1 leading-4">{l.note}</div>}
          </td>
          <td className="text-[12px] text-ink-dim whitespace-nowrap">{l.unit}</td>
          <td className="num text-[12.5px] text-ink/90 whitespace-nowrap">{fmtNum(l.qty, 2)}</td>
          <td className="num text-[12.5px] text-ink/90 whitespace-nowrap">{fmtRial(l.price)}</td>
          <td className="num text-[13px] font-extrabold text-ink whitespace-nowrap">{fmtRial(l.total)}</td>
          <td className="num text-[12px] text-ink-dim whitespace-nowrap">
            {l.indexFactor !== 1 ? fmtNum(l.indexFactor, 4) : "—"}
          </td>
          <td className="num text-[13px] font-extrabold text-gold whitespace-nowrap">{fmtRial(l.totalIndexed)}</td>
        </tr>
      ))}
    </>
  );
}

// ── تب ۳: ریزمتره ──
function DetailTab({ result }: { result: ProjectResult }) {
  const [kindFilter, setKindFilter] = useState("all");
  const kinds = useMemo(() => [...new Set(result.lines.map((l) => l.code))], [result]);
  const flat = useMemo(
    () =>
      result.lines.flatMap((l) =>
        (l.sources.length ? l.sources : [null]).map((s) => ({ l, s })),
      ),
    [result],
  );
  const filtered = flat.filter(({ l }) => kindFilter === "all" || l.code === kindFilter);
  const shown = filtered.slice(0, 400);

  return (
    <Card className="p-0 overflow-hidden">
      <div className="p-5 pb-0 flex items-start justify-between flex-wrap gap-3">
        <SectionTitle kicker="ریزمترهٔ باز" title="جزئیات استخراج کمیت‌ها" sub="هر رقم، به فایل و جدول و ردیف Revit خود قابل ردیابی است" />
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          className="bg-panel-2 border border-line rounded-xl px-3 py-2.5 text-[12px] outline-none cursor-pointer focus:border-gold/50"
        >
          <option value="all">همهٔ ردیف‌های فهرست‌بها</option>
          {kinds.map((k) => (
            <option key={k} value={k}>ردیف {faDigits(k)}</option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
        <table className="dt">
          <thead className="sticky top-0 bg-panel-2 z-10">
            <tr>
              <th>ردیف BOQ</th>
              <th>جدول منبع</th>
              <th>عنصر / مارک</th>
              <th>گروه سازه‌ای</th>
              <th>شرح</th>
              <th>مقدار</th>
              <th>واحد</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ l, s }, i) => (
              <tr key={i}>
                <td className="num text-gold font-bold text-[12px]">{faDigits(l.code)}</td>
                <td className="text-[11.5px] text-ink-dim">{s?.tableTitle ?? "—"}</td>
                <td className="text-[12px] font-semibold text-ink/90">{s?.ref ?? "—"}</td>
                <td><Badge tone="sky">{s?.group ?? "—"}</Badge></td>
                <td className="text-[11.5px] text-ink-dim max-w-[300px] leading-5">{s?.detail ?? l.note ?? "—"}</td>
                <td className="num text-[12.5px] font-bold text-ink">{fmtNum(s?.qty ?? l.qty, 2)}</td>
                <td className="text-[11.5px] text-ink-dim">
                  {s ? { m3: "مترمکعب", m2: "مترمربع", kg: "کیلوگرم", m: "متر", count: "عدد" }[s.unit] : l.unit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && <div className="text-center text-ink-dim py-10 text-[13px]">داده‌ای برای نمایش نیست</div>}
      </div>
      {filtered.length > shown.length && (
        <p className="px-5 py-3 text-[11px] text-ink-dim">
          نمایش {fmtNum(shown.length, 0)} ردیف از مجموع {fmtNum(filtered.length, 0)} — فهرست کامل در خروجی Excel موجود است.
        </p>
      )}
    </Card>
  );
}

// ── تب ۴: لیستوفر آرماتور ──
function RebarTab({ result }: { result: ProjectResult }) {
  const byDiameter = useMemo(() => {
    const map = new Map<string, { weight: number; count: number }>();
    for (const r of result.rebar) {
      const key = r.diameter ? `Φ${r.diameter}` : r.barType || "—";
      const cur = map.get(key) ?? { weight: 0, count: 0 };
      cur.weight += r.weight;
      cur.count += r.count;
      map.set(key, cur);
    }
    return [...map.entries()].map(([label, v]) => ({ label, value: v.weight, hint: `${fmtNum(v.count, 0)} شاخه` }));
  }, [result]);

  // جمع وزن بر اساس گروه سازه‌ای (ایراد ۱۱)
  const byGroup = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of result.rebar) map.set(r.group, (map.get(r.group) ?? 0) + r.weight);
    return [...map.entries()].map(([label, value]) => ({ label, value }));
  }, [result]);

  const totalW = result.rebar.reduce((a, r) => a + r.weight, 0);
  const totalLen = result.rebar.reduce((a, r) => a + r.totalLength, 0);

  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <Card className="xl:col-span-1">
        <SectionTitle kicker="خلاصهٔ لیستوفر" title="وزن آرماتور بر اساس قطر" />
        <HBar data={byDiameter} valueFmt={(v) => fmtKg(v)} unit="کیلوگرم" color="#fb7a93" />
        <hr className="dot-rule my-4" />
        <SectionTitle kicker="خلاصهٔ لیستوفر" title="وزن آرماتور بر اساس گروه سازه‌ای" />
        <HBar data={byGroup} valueFmt={(v) => fmtKg(v)} unit="کیلوگرم" color="#8b9dff" />
        <hr className="dot-rule my-4" />
        <div className="grid grid-cols-2 gap-3">
          <Stat label="وزن کل آرماتور" value={`${fmtKg(totalW)} kg`} tone="rose" />
          <Stat label="مجموع طول شاخه‌ها" value={`${fmtNum(totalLen, 0)} m`} tone="sky" />
        </div>
      </Card>
      <Card className="xl:col-span-2 p-0 overflow-hidden">
        <div className="p-5 pb-0">
          <SectionTitle kicker="لیستوفر" title="جدول آرماتوربندی" sub="بر اساس خروجی Rebar Schedule رویت" />
        </div>
        <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
          <table className="dt">
            <thead className="sticky top-0 bg-panel-2 z-10">
              <tr>
                <th>مارک</th>
                <th>گروه سازه‌ای</th>
                <th>طبقه</th>
                <th>قطر (mm)</th>
                <th>تعداد</th>
                <th>طول هر شاخه (m)</th>
                <th>طول کل (m)</th>
                <th>وزن واحد (kg/m)</th>
                <th>وزن کل (kg)</th>
                <th>شکل خم</th>
              </tr>
            </thead>
            <tbody>
              {result.rebar.map((r, i) => (
                <tr key={i}>
                  <td className="text-[12px] font-bold text-ink">{r.mark}</td>
                  <td><Badge tone="violet">{r.group}</Badge></td>
                  <td className="text-[11.5px] text-ink-dim">{r.level || "—"}</td>
                  <td className="num text-[12px] text-ink/90">{r.diameter ? `Φ${r.diameter}` : "—"}</td>
                  <td className="num text-[12px]">{fmtNum(r.count, 0)}</td>
                  <td className="num text-[12px]">{fmtNum(r.perBarLength, 2)}</td>
                  <td className="num text-[12px]">{fmtNum(r.totalLength, 2)}</td>
                  <td className="num text-[12px] text-ink-dim">{fmtNum(r.unitWeight, 3)}</td>
                  <td className="num text-[12px] font-bold">{fmtNum(r.weight, 2)}</td>
                  <td className="text-[11.5px] text-ink-dim">{r.shape || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ── تب ۵: آنالیز و کیفیت ──
function AnalysisTab({ result }: { result: ProjectResult }) {
  const q = result.quality;
  const ok = q.linesEstimatedPrice === 0 && q.linesNeedReview === 0;
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <SectionTitle kicker="آنالیز" title="بهای هر فصل از فهرست‌بها" />
        <HBar
          data={result.chapterSums.map((c) => ({ label: `فصل ${faDigits(c.chapter)} | ${c.title}`, value: c.total, hint: `${((c.total / result.baseTotal) * 100).toFixed(1)}٪` }))}
          valueFmt={(v) => `${fmtNum(v / 1e10, 2)}`}
          unit="همت"
          color="#f2b33d"
        />
      </Card>
      <Card>
        <SectionTitle kicker="کنترل کیفیت" title="گزارش سلامت داده و تطبیق" sub="نسخهٔ بازرس‌شدهٔ خط لولهٔ پردازش" />
        <div className="grid grid-cols-2 gap-3 mb-5">
          <Stat label="جداول پردازش‌شده" value={fmtNum(q.tablesParsed, 0)} icon={<Sigma size={18} />} tone="sky" />
          <Stat label="ردیف‌های داده" value={fmtNum(q.rowsRead, 0)} icon={<ClipboardList size={18} />} tone="violet" />
          <Stat label="تطبیق دقیق" value={fmtNum(q.linesExact, 0)} icon={<ShieldCheck size={18} />} tone="emerald" />
          <Stat label="بهای تخمینی باقی‌مانده" value={fmtNum(q.linesEstimatedPrice, 0)} icon={<AlertTriangle size={18} />} tone={q.linesEstimatedPrice ? "gold" : "emerald"} />
        </div>
        <div
          className={cn(
            "rounded-xl border p-4 text-[12.5px] leading-6 flex items-start gap-3",
            ok ? "bg-emerald/[0.07] border-emerald/25 text-emerald" : "bg-gold/[0.07] border-gold/25 text-ink/85",
          )}
        >
          {ok ? <ShieldCheck size={18} className="shrink-0 mt-0.5" /> : <AlertTriangle size={18} className="shrink-0 mt-0.5 text-gold" />}
          <div>
            {ok
              ? "همهٔ ردیف‌ها با اطمینان کامل و بهای رسمی/تأییدشده تطبیق داده شده‌اند. گزارش آمادهٔ ارائه به کارفرما است."
              : "برای نهایی‌سازی، ردیف‌های دارای «بهای تخمینی» یا «نیازمند بررسی» را در گام تطبیق هوشمند اصلاح کنید یا فایل رسمی فهرست‌بها را بارگذاری نمایید."}
          </div>
        </div>
        {q.warnings.length > 0 && (
          <div className="mt-4 space-y-2">
            {q.warnings.slice(0, 5).map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-[11.5px] text-ink-dim leading-5">
                <AlertTriangle size={12} className="text-gold shrink-0 mt-1" />
                {w}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
