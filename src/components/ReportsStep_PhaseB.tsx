// ─────────────────────────────────────────────────────────────
// تب موتورهای تعدیل فاز B — کارت‌های مجزای دو موتور
// (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند؛ هر دو می‌توانند همزمان فعال باشند)
// ─────────────────────────────────────────────────────────────
import { AlertTriangle, FileWarning, Lock, Sigma } from "lucide-react";
import { Badge, Card } from "./ui";
import type {
  AdjChainRow,
  AdjChapterRow,
  AdjPending,
  AdjustmentResult,
  BaravordResult,
  ProjectResult,
  TadilResult,
} from "../lib/types";
import { faDigits, fmtNum } from "../lib/normalize";
import {
  splitRounded,
  quarterLabel,
  ioLabel,
  PENDING_INTERPRETATIONS,
} from "../lib/adjustment";

function money(n: number): string {
  return fmtNum(Math.round(n), 0);
}

/** بنر «پیش‌نویس» برای موتورهای تأییدنشده */
function DraftBanner({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-gold/30 bg-gold/[0.06] px-3.5 py-2.5 flex items-center gap-2.5 mb-4">
      <Lock size={14} className="text-gold shrink-0" />
      <span className="text-[11.5px] text-gold/95 leading-5">
        خروجی {label} <b>«پیش‌نویس»</b> است — مقادیر با منبع تصویری یا دستی تا تأیید شما
        قطعی نمی‌شوند. رجیستری «مقادیر منتظر تأیید» را در پایین بررسی کنید.
      </span>
    </div>
  );
}

/** پیام خطای توقف موتور */
function ErrorBanner({ error }: { error: string }) {
  return (
    <div className="rounded-xl border border-rose/35 bg-rose/[0.06] px-3.5 py-3 flex items-start gap-2.5">
      <AlertTriangle size={15} className="text-rose shrink-0 mt-0.5" />
      <div>
        <div className="text-[12px] font-bold text-rose mb-1">موتور متوقف شد</div>
        <span className="text-[11.5px] text-ink-dim leading-5">{error}</span>
      </div>
    </div>
  );
}

/** زنجیرهٔ شفافِ محاسبهٔ A */
function ChainTable({ rows }: { rows: AdjChainRow[] }) {
  return (
    <div className="rounded-xl border border-line/70 overflow-hidden mb-4">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="bg-white/[0.04] text-ink-dim">
            <th className="text-right font-bold py-2 px-3 w-[38%]">گام محاسبه</th>
            <th className="text-left font-bold py-2 px-3 num">مبلغ (ریال)</th>
            <th className="text-right font-bold py-2 px-3 text-[11px]">توضیح</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line/40">
              <td className="py-2 px-3 text-ink/90">{r[0]}</td>
              <td className="py-2 px-3 num text-ink font-bold text-left whitespace-nowrap">{money(r[1])}</td>
              <td className="py-2 px-3 text-ink-dim text-[11px]">{r[2]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** جدول فصل‌های یک موتور */
function ChapterTable({
  rows,
  showQuarters,
  split,
}: {
  rows: AdjChapterRow[];
  showQuarters: boolean;
  split?: [string, number][];
}) {
  const qs = split?.map((x) => x[0]) ?? [];
  return (
    <div className="rounded-xl border border-line/70 overflow-hidden mb-4">
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] whitespace-nowrap">
          <thead>
            <tr className="bg-white/[0.04] text-ink-dim">
              <th className="text-right font-bold py-2 px-3">فصل</th>
              <th className="text-left font-bold py-2 px-3 num">A_c (ریال)</th>
              <th className="text-left font-bold py-2 px-3 num">Io</th>
              {showQuarters ? (
                qs.map((q) => (
                  <th key={q} className="text-left font-bold py-2 px-2 num text-[11px]">
                    {quarterLabel(q)}
                  </th>
                ))
              ) : (
                <th className="text-left font-bold py-2 px-3 num">It</th>
              )}
              <th className="text-left font-bold py-2 px-3 num">نسبت</th>
              <th className="text-left font-bold py-2 px-3 num">مقدار (ریال)</th>
              <th className="text-right font-bold py-2 px-3">وضعیت</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.chapter} className="border-t border-line/40">
                <td className="py-2 px-3">
                  <span className="num font-bold text-ink">{faDigits(r.chapter)}</span>
                  <span className="text-ink-dim text-[11px] mr-1.5">{r.title}</span>
                </td>
                <td className="py-2 px-3 num text-left">{money(r.amount)}</td>
                <td className="py-2 px-3 num text-left">{faDigits(fmtNum(r.io, 1))}</td>
                {showQuarters ? (
                  (r.quarters ?? []).map((q) => (
                    <td key={q[0]} className="py-2 px-2 num text-left text-[11px]">
                      {faDigits(fmtNum(q[1], 1))}
                      <span className={q[2] === "موقت" ? "text-gold" : "text-ink-dim"}> {q[2] === "موقت" ? "موقت" : ""}</span>
                    </td>
                  ))
                ) : (
                  <td className="py-2 px-3 num text-left">{r.it !== null ? faDigits(fmtNum(r.it, 1)) : "—"}</td>
                )}
                <td className="py-2 px-3 num text-left text-ink-dim">
                  {r.ratio !== null ? faDigits(fmtNum(r.ratio, 4)) : "—"}
                </td>
                <td className="py-2 px-3 num text-left font-bold text-ink">{money(r.value)}</td>
                <td className="py-2 px-3 text-right">
                  <span className={r.status === "موقت" ? "text-gold text-[11px] font-bold" : "text-ink-dim text-[11px]"}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** کارت موتور ۱ — تعدیل پیمان */
function TadilCard({ t }: { t: TadilResult }) {
  const [dpR, dpDef, dpProv] = splitRounded(t.delta_p, t.delta_p_definitive, 0);
  return (
    <Card className="border-gold/25">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gold/15 text-gold grid place-items-center shrink-0">
            <Sigma size={18} />
          </div>
          <div>
            <h3 className="font-bold text-ink text-[15px]">{t.mode}</h3>
            <code className="text-[11px] text-ink-dim num block" dir="ltr">{t.formula}</code>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {t.draft ? (
            <Badge tone="gold">پیش‌نویس</Badge>
          ) : (
            <Badge tone="emerald">تأییدشده</Badge>
          )}
          {t.incomplete && <Badge tone="rose">ناقص</Badge>}
          <Badge tone="zinc">k = {faDigits(fmtNum(t.coef, 2))}</Badge>
          <Badge tone="zinc">Io = {ioLabel(t)}</Badge>
        </div>
      </div>
      {t.index_method_resolved && (
        <div className="text-[10.5px] text-ink-dim mb-3 leading-4">
          مسیر شاخصِ حل‌شده: {t.index_method_resolved.method} —{' '}
          {t.index_method_resolved.source} (گام ۶ — بندهای ۲-۱/۲-۲)
        </div>
      )}

      {t.error ? (
        <ErrorBanner error={t.error} />
      ) : (
        <>
          {t.draft && <DraftBanner label="موتور تعدیل پیمان" />}
          {/* فاز E-10 §۲ — واترمارکِ «پیش‌نویس – دورهٔ کارکرد وارد نشده» */}
          {t.work_period_missing && (
            <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-red-300/40 bg-red-50 px-3.5 py-2.5">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-red-600" />
              <span className="text-[11.5px] leading-5 text-red-700">
                <b>پیش‌نویس – دورهٔ کارکرد وارد نشده.</b> موتورِ تعدیل تمامِ
                کارکرد را به آخرین شاخصِ قطعی منتسب می‌کند و ΔP با حالتِ
                «شاخصِ هر سه‌ماهه» متفاوت است؛ خروجیِ نهاییِ Excel ساخته
                نمی‌شود (فقط پیش‌نویس).
              </span>
            </div>
          )}
          {/* فاز E-10 §۲ — برچسبِ «علی‌الحساب – k = ۰٫۹۵» */}
          {t.k_provisional && (
            <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-gold/30 bg-gold/[0.06] px-3.5 py-2.5">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-gold" />
              <span className="text-[11.5px] leading-5 text-gold/95">
                <b>علی‌الحساب – k = ۰٫۹۵</b> — وضعیتِ اتمامِ کار در مدتِ پیمان
                نامشخص است (بند ۱-۸ بخشنامهٔ ۲۰۸۰). خروجی مجاز است، ولی تا
                مشخص‌شدنِ تکلیفِ قطعی، علی‌الحساب می‌ماند.
              </span>
            </div>
          )}
          <ChainTable rows={t.chain} />

          <div className="grid md:grid-cols-3 gap-3 mb-4">
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-3.5">
              <div className="text-[11px] text-ink-dim mb-1">مبلغ پایه (A + تجهیز)</div>
              <div className="num font-extrabold text-ink text-[15px]">{money(t.base_amount)}</div>
            </div>
            <div className="rounded-xl bg-gold/[0.06] border border-gold/25 p-3.5">
              <div className="text-[11px] text-ink-dim mb-1">جمع تعدیل (شامل علی‌الحساب)</div>
              <div className="num font-extrabold text-gold text-[15px]">{money(dpR)}</div>
            </div>
            <div className="rounded-xl bg-gold/[0.06] border border-gold/25 p-3.5">
              <div className="text-[11px] text-ink-dim mb-1">مبلغ نهایی (A + ΔP)</div>
              <div className="num font-extrabold text-gold text-[15px]">{money(t.result_amount)}</div>
            </div>
          </div>

          {/* ── فاز E-6 Part C گام ۴: کسر ۵٪ فسخ با قصور (بند ۷) ── */}
          {Math.abs(t.deduction_fault) >= 0.01 && (
            <div className="rounded-xl border border-rose/35 bg-rose/[0.06] p-3.5 mb-4">
              <div className="text-[11px] text-ink-dim mb-1">
                کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷)
              </div>
              <div className="num font-extrabold text-rose text-[15px]">
                {money(-t.deduction_fault)}
              </div>
              <div className="text-[10.5px] text-ink-dim mt-1">
                ۵٪ از مبلغ تعدیل کسر می‌شود — مبلغ نهایی شامل این کسر است.
              </div>
            </div>
          )}

          {/* ── تفکیک بخش قطعی و علی‌الحساب ── */}
          {Math.abs(dpProv) >= 1 && (
            <div className="rounded-xl border border-gold/25 bg-gold/[0.04] p-3.5 mb-4">
              <div className="text-[11.5px] font-bold text-ink/90 mb-2">تفکیک بخش قطعی و علی‌الحساب</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[10.5px] text-ink-dim block">بخش قطعی (شاخص‌های قطعی ۱۴۰۴)</span>
                  <span className="num font-bold text-ink text-[13.5px]">{money(dpDef)}</span>
                </div>
                <div>
                  <span className="text-[10.5px] text-gold/90 block">بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1)</span>
                  <span className="num font-bold text-gold text-[13.5px]">{money(dpProv)}</span>
                </div>
              </div>
              <p className="text-[10px] text-ink-dim mt-2 leading-4">
                جمع دو بخش برابر ΔP است (باقی‌ماندهٔ گردسازی به بخش علی‌الحساب می‌رسد).
                شاخص موقت = ضریب دستی × آخرین شاخص قطعی (۱۴۰۴Q4).
              </p>
            </div>
          )}

          {t.setup_row && (
            <div className="rounded-xl border border-line/70 bg-white/[0.02] p-3.5 mb-4">
              <div className="text-[11.5px] font-bold text-ink/90 mb-1.5">
                تجهیز و برچیدن کارگاه — شاخص رشته‌ای (بند ۴)
              </div>
              <div className="flex gap-5 flex-wrap text-[12px]">
                <span className="text-ink-dim">مبلغ: <b className="num text-ink">{money(t.setup_row.amount)}</b></span>
                <span className="text-ink-dim">Io: <b className="num text-ink">{faDigits(fmtNum(t.setup_row.io, 1))}</b></span>
                <span className="text-ink-dim">It: <b className="num text-ink">{faDigits(fmtNum(t.setup_row.it, 1))}</b></span>
                <span className="text-ink-dim">ΔP تجهیز: <b className="num text-gold">{money(t.setup_row.delta)}</b></span>
              </div>
            </div>
          )}

          <div className="text-[11.5px] font-bold text-ink/90 mb-2">جدول فصل × سه‌ماهه — شاخص It هر فصل</div>
          <ChapterTable rows={t.chapters} showQuarters split={t.split} />

          {t.missing.length > 0 && (
            <div className="text-[11px] text-rose">
              شاخص ناموجود: {t.missing.map(([c, w, q]) => `${faDigits(c)} (${w} ${faDigits(q)})`).join("، ")}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

/** کارت موتور ۲ — برآورد به‌هنگام */
function BaravordCard({ b }: { b: BaravordResult }) {
  return (
    <Card className="border-teal/25">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal/15 text-teal grid place-items-center shrink-0">
            <Sigma size={18} />
          </div>
          <div>
            <h3 className="font-bold text-ink text-[15px]">{b.mode}</h3>
            <code className="text-[11px] text-ink-dim num block" dir="ltr">{b.formula}</code>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {b.draft ? <Badge tone="gold">پیش‌نویس</Badge> : <Badge tone="emerald">تأییدشده</Badge>}
          {b.incomplete && <Badge tone="rose">ناقص</Badge>}
          <Badge tone="zinc">Io = {ioLabel(b)}</Badge>
          <Badge tone="zinc">It = {faDigits(String(b.it_q ?? "—"))}</Badge>
          {b.it_status && (
            <Badge tone={b.it_status === "موقت" ? "gold" : "emerald"}>
              {b.it_status}
            </Badge>
          )}
          {b.prov !== null && b.prov !== undefined && b.it_status === "موقت" && (
            <Badge tone="gold">
              ضریب موقت ۱۴۰۵Q1 = {faDigits(b.prov.toFixed(4))}
              {b.prov_manual ? " (دستی)" : ""}
            </Badge>
          )}
        </div>
      </div>
      {b.index_method_resolved && (
        <div className="text-[10.5px] text-ink-dim mb-3 leading-4">
          مسیر شاخصِ حل‌شده: {b.index_method_resolved.method} —{' '}
          {b.index_method_resolved.source} (گام ۶ — بندهای ۲-۱/۲-۲)
        </div>
      )}

      {b.error ? (
        <ErrorBanner error={b.error} />
      ) : (
        <>
          {b.draft && <DraftBanner label="موتور برآورد به‌هنگام" />}
          <ChainTable rows={b.chain} />

          <div className="grid md:grid-cols-3 gap-3 mb-4">
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-3.5">
              <div className="text-[11px] text-ink-dim mb-1">مبلغ پایه (A + تجهیز)</div>
              <div className="num font-extrabold text-ink text-[15px]">{money(b.base_amount)}</div>
            </div>
            <div className="rounded-xl bg-teal/[0.06] border border-teal/25 p-3.5">
              <div className="text-[11px] text-ink-dim mb-1">برآورد به‌هنگام‌شده (A_new)</div>
              <div className="num font-extrabold text-teal text-[15px]">{money(b.result_amount)}</div>
            </div>
            <div className="rounded-xl bg-teal/[0.06] border border-teal/25 p-3.5">
              <div className="text-[11px] text-ink-dim mb-1">جمع کل به‌هنگام‌شده (قیمت پیمان)</div>
              <div className="num font-extrabold text-teal text-[15px]">{money(b.grand_updated)}</div>
              <div className="text-[10px] text-ink-dim mt-1">جمع کل فعلی: {money(b.grand_current)}</div>
            </div>
          </div>

          {b.setup_row && (
            <div className="rounded-xl border border-line/70 bg-white/[0.02] p-3.5 mb-4">
              <div className="text-[11.5px] font-bold text-ink/90 mb-1.5">
                تجهیز و برچیدن کارگاه — شاخص رشته‌ای (بند ۴)
              </div>
              <div className="flex gap-5 flex-wrap text-[12px]">
                <span className="text-ink-dim">مبلغ: <b className="num text-ink">{money(b.setup_row.amount)}</b></span>
                <span className="text-ink-dim">Io: <b className="num text-ink">{faDigits(fmtNum(b.setup_row.io, 1))}</b></span>
                <span className="text-ink-dim">It: <b className="num text-ink">{faDigits(fmtNum(b.setup_row.it, 1))}</b></span>
                <span className="text-ink-dim">مبلغ به‌هنگام‌شده: <b className="num text-teal">{money(b.setup_row.value)}</b></span>
              </div>
            </div>
          )}

          <div className="text-[11.5px] font-bold text-ink/90 mb-2">جدول فصل‌ها</div>
          <ChapterTable rows={b.chapters} showQuarters={false} />

          {b.missing.length > 0 && (
            <div className="text-[11px] text-rose">
              شاخص ناموجود: {b.missing.map(([c, w, q]) => `${faDigits(c)} (${w} ${faDigits(q)})`).join("، ")}
            </div>
          )}
        </>
      )}
    </Card>
  );
}

/** رجیستری «مقادیر منتظر تأیید» — مشترک بین دو موتور */
function PendingRegistry({ items }: { items: AdjPending[] }) {
  if (items.length === 0) return null;
  return (
    <Card className="mt-6">
      <div className="flex items-center gap-2.5 mb-4">
        <FileWarning size={17} className="text-gold" />
        <h3 className="font-bold text-ink text-[14px]">مقادیر منتظر تأیید</h3>
        <Badge tone="gold">{faDigits(String(items.length))} مورد</Badge>
      </div>
      <div className="rounded-xl border border-line/70 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] whitespace-nowrap">
            <thead>
              <tr className="bg-white/[0.04] text-ink-dim">
                <th className="text-right font-bold py-2 px-3">مقدار</th>
                <th className="text-left font-bold py-2 px-3 num">مقدار</th>
                <th className="text-right font-bold py-2 px-3">منبع</th>
                <th className="text-right font-bold py-2 px-3">صفحه</th>
                <th className="text-right font-bold py-2 px-3">وضعیت</th>
                <th className="text-right font-bold py-2 px-3">اقدام موردنیاز</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p, i) => (
                <tr key={i} className="border-t border-line/40">
                  <td className="py-2 px-3 text-ink/90 font-semibold">{p.item}</td>
                  <td className="py-2 px-3 num text-left font-bold text-gold">
                    {p.value !== null ? faDigits(fmtNum(p.value, 4)) : "—"}
                  </td>
                  <td className="py-2 px-3 text-ink-dim text-[11px]">{p.source}</td>
                  <td className="py-2 px-3 text-ink-dim text-[11px] num">{p.page}</td>
                  <td className="py-2 px-3">
                    <Badge tone="gold">{p.status}</Badge>
                  </td>
                  <td className="py-2 px-3 text-ink-dim text-[11px]">{p.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

export function AdjustmentTab({ result }: { result: ProjectResult }) {
  const adj: AdjustmentResult | null = result.adjustment;
  if (!adj || (!adj.tadil && !adj.baravord)) {
    return (
      <Card className="text-center py-14">
        <Sigma size={38} className="mx-auto text-ink-dim mb-4" />
        <h3 className="text-ink font-bold text-lg">موتور تعدیل فعالی نیست</h3>
        <p className="text-ink-dim text-[13px] mt-2">
          در گام ۴ (تنظیمات)، یکی از موتورهای «تعدیل پیمان» یا «برآورد به‌هنگام» را روشن کنید.
          هر دو می‌توانند همزمان فعال باشند ولی هرگز با هم ادغام نمی‌شوند.
        </p>
      </Card>
    );
  }
  const pending: AdjPending[] = [
    ...(adj.tadil?.pending ?? []),
    ...(adj.baravord?.pending ?? []),
  ];
  // حذف تکراری‌ها (مثلاً ضریب پیشنهادی یا فصل fallback در هر دو موتور)
  const seen = new Set<string>();
  const dedup = pending.filter((p) => {
    const k = `${p.item}|${p.value}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-line/60 bg-white/[0.02] px-4 py-3">
        <p className="text-[11.5px] text-ink-dim leading-5">
          <b className="text-ink/90">قاعدهٔ طلایی ۵:</b> دو موتور «تعدیل پیمان» و «برآورد به‌هنگام»
          کاملاً مستقل‌اند — ورودی، فرمول و خروجی هر کدام جداست و <b>هیچ‌گاه روی زنجیرهٔ مالی اصلی
          اثر نمی‌گذارند</b>. اعداد زنجیرهٔ مالی (خلاصهٔ مالی) بدون تغییر می‌مانند.
        </p>
      </div>
      {adj.tadil && <TadilCard t={adj.tadil} />}
      {adj.baravord && <BaravordCard b={adj.baravord} />}
      <PendingRegistry items={dedup} />
      <InputsStatusPanel result={result} />
    </div>
  );
}

/** ── فاز E-6 Part C گام ۱۲ (حرف g): پنلِ «وضعیت ورودی‌ها» ──
 * ورودی‌های ناقص (از هشدارها) + تفسیرهای «منتظر تأیید کاربر» در یک نگاه.
 * هم‌سان با پنلِ «وضعیت ورودی‌ها» در app.py (Streamlit). */
function InputsStatusPanel({ result }: { result: ProjectResult }) {
  const warns = result.warnings ?? [];
  const errs = warns.filter((x) => x.level === "خطا");
  const ws = warns.filter((x) => x.level === "هشدار");
  return (
    <Card className="mt-6">
      <div className="flex items-center gap-2.5 mb-4">
        <AlertTriangle size={17} className="text-gold" />
        <h3 className="font-bold text-ink text-[14px]">وضعیت ورودی‌ها (گام ۱۲)</h3>
        <Badge tone={errs.length > 0 ? "rose" : "teal"}>
          {errs.length > 0
            ? `${faDigits(String(errs.length))} خطا`
            : "کامل"}
        </Badge>
      </div>
      {errs.length > 0 ? (
        <>
          <div className="text-[12px] font-bold text-rose/90 mb-2">
            ⛔ ورودی‌های ناقص (خطا — تا اصلاح رسمی نیست)
          </div>
          <div className="rounded-xl border border-line/70 overflow-hidden mb-5">
            <div className="overflow-x-auto">
              <table className="w-full text-[12px] whitespace-nowrap">
                <thead>
                  <tr className="bg-white/[0.04] text-ink-dim">
                    <th className="text-right font-bold py-2 px-3">المان</th>
                    <th className="text-right font-bold py-2 px-3">شرح</th>
                    <th className="text-right font-bold py-2 px-3">اقدام</th>
                    <th className="text-right font-bold py-2 px-3">بند</th>
                  </tr>
                </thead>
                <tbody>
                  {errs.map((x, i) => (
                    <tr key={i} className="border-t border-line/40">
                      <td className="py-2 px-3 text-ink/90 font-semibold">{x.item}</td>
                      <td className="py-2 px-3 text-ink-dim text-[11px]">{x.message}</td>
                      <td className="py-2 px-3 text-ink-dim text-[11px]">{x.action}</td>
                      <td className="py-2 px-3 text-ink-dim text-[11px]">{x.ref}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <div className="text-[12px] text-teal mb-5">✅ هیچ ورودیِ ناقصی نیست.</div>
      )}
      {ws.length > 0 && (
        <>
          <div className="text-[12px] font-bold text-gold mb-2">
            ⚠ هشدارها (نیازمند بررسی)
          </div>
          <div className="rounded-xl border border-line/70 overflow-hidden mb-5">
            <div className="overflow-x-auto">
              <table className="w-full text-[12px] whitespace-nowrap">
                <thead>
                  <tr className="bg-white/[0.04] text-ink-dim">
                    <th className="text-right font-bold py-2 px-3">المان</th>
                    <th className="text-right font-bold py-2 px-3">شرح</th>
                    <th className="text-right font-bold py-2 px-3">اقدام</th>
                    <th className="text-right font-bold py-2 px-3">بند</th>
                  </tr>
                </thead>
                <tbody>
                  {ws.map((x, i) => (
                    <tr key={i} className="border-t border-line/40">
                      <td className="py-2 px-3 text-ink/90 font-semibold">{x.item}</td>
                      <td className="py-2 px-3 text-ink-dim text-[11px]">{x.message}</td>
                      <td className="py-2 px-3 text-ink-dim text-[11px]">{x.action}</td>
                      <td className="py-2 px-3 text-ink-dim text-[11px]">{x.ref}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      <div className="text-[12px] font-bold text-ink/90 mb-2">
        تصمیماتِ باز — منتظر تأیید کاربر ({faDigits(String(PENDING_INTERPRETATIONS.length))} مورد)
      </div>
      <div className="rounded-xl border border-line/70 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] whitespace-nowrap">
            <thead>
              <tr className="bg-white/[0.04] text-ink-dim">
                <th className="text-right font-bold py-2 px-3">شناسه</th>
                <th className="text-right font-bold py-2 px-3">موضوع</th>
                <th className="text-right font-bold py-2 px-3">تفسیرِ پیاده‌شده</th>
                <th className="text-right font-bold py-2 px-3">گزینهٔ دیگر</th>
                <th className="text-right font-bold py-2 px-3">اثر عددی</th>
              </tr>
            </thead>
            <tbody>
              {PENDING_INTERPRETATIONS.map((it) => (
                <tr key={it.id} className="border-t border-line/40">
                  <td className="py-2 px-3 num text-ink/90 font-bold">{it.id}</td>
                  <td className="py-2 px-3 text-ink/90 font-semibold">{it.subject}</td>
                  <td className="py-2 px-3 text-ink-dim text-[11px]">{it.implemented}</td>
                  <td className="py-2 px-3 text-ink-dim text-[11px]">{it.alternative}</td>
                  <td className="py-2 px-3 text-ink-dim text-[11px]">{it.effect}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}
