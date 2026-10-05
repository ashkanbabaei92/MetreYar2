import type { ProjectMeta, ProjectResult, ProjectSettings, StatusReportRecord } from "../lib/types";
import { faDigits, fmtNum, fmtRial } from "../lib/normalize";
import { moneyToWords, todayJalali } from "../lib/farsi";

/**
 * نسخهٔ رسمی چاپی صورت‌وضعیت — فقط در حالت چاپ نمایش داده می‌شود
 * (استایل‌ها این‌لاین‌اند تا با چاپگرها سازگار بمانند)
 */
const th: React.CSSProperties = {
  border: "1px solid #888",
  padding: "5px 7px",
  fontSize: 10,
  fontWeight: 700,
  background: "#f0f0f0",
  textAlign: "center",
};
const td: React.CSSProperties = { border: "1px solid #999", padding: "5px 7px", fontSize: 10, verticalAlign: "top" };
const tdNum: React.CSSProperties = { ...td, textAlign: "left", direction: "ltr", fontFamily: "Tahoma" };

export function PrintReport({
  result,
  settings,
  meta,
  history,
}: {
  result: ProjectResult | null;
  settings: ProjectSettings;
  meta: ProjectMeta;
  history: StatusReportRecord[];
}) {
  if (!result) return null;

  const date = todayJalali();

  // یادداشت دورهٔ شاخص تعدیل (در صورت تفاوت با دورهٔ مبنا)
  const idx = result.index;
  let idxNote = "";
  if (idx && idx.targetPeriod && idx.targetPeriod !== idx.basePeriod) {
    idxNote = ` — تعدیل به دورهٔ ${idx.targetPeriod}` + (idx.provisional ? " (شاخص موقت)" : "");
  }
  // هشدار سقف ۴٪ تجهیز و برچیدن (دستورالعمل کاربرد بند ۲-۸)
  let siteSetupWarning = "";
  if (result.regionalAmount > 0) {
    const cap = 0.04 * result.regionalAmount;
    if (result.siteSetup > cap) {
      siteSetupWarning =
        `هشدار: مبلغ تجهیز و برچیدن کارگاه بیش از ۴٪ مبلغ قبل از آن ` +
        `(${fmtRial(cap)}) است (دستورالعمل کاربرد بند ۲-۸).`;
    }
  }

  return (
    <div id="print-root" dir="rtl">
      {/* سربرگ رسمی صورت‌وضعیت */}
      <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 10 }} border={1} cellPadding={6}>
        <tbody>
          <tr>
            <td colSpan={2} style={{ fontSize: 13, fontWeight: 800, textAlign: "center", background: "#f5edd8" }}>
              صورت وضعیت {meta.reportType} شماره {faDigits(meta.reportNo || "—")} — پیمان شماره {faDigits(meta.contractNo || "—")}
            </td>
          </tr>
          <tr>
            <td style={{ width: "50%", fontSize: 11 }}><b>نام پروژه:</b> {meta.projectName || "—"}</td>
            <td style={{ width: "50%", fontSize: 11 }}><b>محل اجرا:</b> {meta.location || "—"}</td>
          </tr>
          <tr>
            <td style={{ fontSize: 11 }}><b>کارفرما:</b> {meta.employer || "—"}</td>
            <td style={{ fontSize: 11 }}><b>پیمانکار:</b> {meta.contractor || "—"}</td>
          </tr>
          <tr>
            <td style={{ fontSize: 11 }}>
              <b>دورهٔ کارکرد:</b> از {meta.periodStart || "—"} تا {meta.periodEnd || "—"}
            </td>
            <td style={{ fontSize: 11 }}>
              <b>مهندس مشاور:</b> {meta.consultant || "—"} — <b>تاریخ صدور:</b> {date}
            </td>
          </tr>
        </tbody>
      </table>

      <h2 style={{ fontSize: 13, margin: "0 0 8px", textAlign: "center" }}>
        خلاصه‌متره و صورت‌وضعیت ردیف‌های فهرست‌بها (فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴)
      </h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={th}>ردیف</th>
            <th style={th}>کد</th>
            <th style={{ ...th, width: "34%" }}>شرح آیتم</th>
            <th style={th}>واحد</th>
            <th style={th}>مقدار</th>
            <th style={th}>بهای واحد</th>
            <th style={th}>بهای کل (پایه)</th>
            <th style={th}>ضریب تعدیل</th>
            <th style={th}>بهای کل (به‌هنگام)</th>
          </tr>
        </thead>
        <tbody>
          {result.lines.map((l) => (
            <tr key={l.id}>
              <td style={{ ...td, textAlign: "center" }}>{faDigits(String(l.rowNo))}</td>
              <td style={{ ...td, textAlign: "center", fontFamily: "Tahoma", direction: "ltr" }}>{l.code}</td>
              <td style={{ ...td, fontSize: 9.5, lineHeight: 1.5 }}>{l.desc}{l.estimatedPrice ? " [بهای تخمینی]" : ""}</td>
              <td style={{ ...td, textAlign: "center", fontSize: 9 }}>{l.unit}</td>
              <td style={tdNum}>{fmtNum(l.qty, 2)}</td>
              <td style={tdNum}>{fmtRial(l.price)}</td>
              <td style={tdNum}>{fmtRial(l.total)}</td>
              <td style={{ ...tdNum, fontSize: 9 }}>{l.indexFactor !== 1 ? fmtNum(l.indexFactor, 4) : "۱"}</td>
              <td style={{ ...tdNum, fontWeight: 700 }}>{fmtRial(l.totalIndexed)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* زنجیرهٔ مالی */}
      <h3 style={{ fontSize: 12, margin: "12px 0 6px" }}>صورت‌جمع مالی</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }} border={1}>
        <tbody>
          <FinPRow label={`الف) جمع ناخالص ردیف‌های فهرست‌بها${idxNote}`} value={result.baseTotal} />
          <FinPRow label={`ضریب طبقات (× ${fmtNum(settings.floorsCoef, 2)})`} value={result.floorsAmount} />
          <FinPRow label={`ضریب بالاسری (× ${fmtNum(settings.overheadCoef, 2)})`} value={result.overheadAmount} />
          <FinPRow label={`ضریب منطقه‌ای (× ${fmtNum(result.coefs.regional.value ?? 1, 2)})`} value={result.regionalAmount} />
          <FinPRow label="تجهیز و برچیدن کارگاه (مبلغ)" value={result.siteSetup} />
          <FinPRow label="ب) مبلغ ناخالص نهایی قابل پرداخت" value={result.grossPayable} strong />
          {siteSetupWarning && (
            <tr>
              <td style={{ ...td, fontSize: 10, color: "#9a5b00", lineHeight: 1.6 }} colSpan={2}>{siteSetupWarning}</td>
            </tr>
          )}
          {/* ── بلوک جداگانهٔ «خالص پرداختی» — بر ناخالص اثر ندارد ── */}
          <tr>
            <td style={{ ...td, fontSize: 11, fontWeight: 800, background: "#f7f7f7" }} colSpan={2}>محاسبهٔ جداگانهٔ خالص پرداختی (کسورات قانونی)</td>
          </tr>
          <FinPRow label="مبلغ ناخالص نهایی" value={result.grossPayable} />
          <FinPRow label={`کسورات: بیمه (${fmtNum(settings.insurancePct, 1)}٪)`} value={-result.insurance} />
          <FinPRow label={`کسورات: مالیات (${fmtNum(settings.taxPct, 1)}٪)`} value={-result.tax} />
          <FinPRow label={`کسورات: حسن انجام کار (${fmtNum(settings.goodJobPct, 1)}٪)`} value={-result.goodJob} />
          <FinPRow label="کسورات: پیش‌پرداخت" value={-result.advancePayment} />
          <FinPRow label="مجموع کسورات" value={-result.totalDeductions} strong />
          <tr style={{ background: "#f5edd8" }}>
            <td style={{ ...td, fontSize: 12, fontWeight: 800 }}>خالص پرداختی پس از کسورات — ریال</td>
            <td style={{ ...tdNum, fontWeight: 800, fontSize: 12 }}>{fmtRial(result.netPayable)}</td>
          </tr>
          <tr>
            <td style={{ ...td, fontSize: 10, lineHeight: 1.8 }} colSpan={2}>
              <b>به حروف:</b> {moneyToWords(Math.round(result.netPayable))}
            </td>
          </tr>
        </tbody>
      </table>

      {/* ── ضمیمهٔ موتورهای تعدیل فاز B (کاملاً مجزا از زنجیرهٔ مالی) ── */}
      {result.adjustment && (result.adjustment.tadil || result.adjustment.baravord) && (
        <>
          <h3 style={{ fontSize: 12, margin: "14px 0 4px" }}>ضمیمهٔ موتورهای تعدیل (فاز B)</h3>
          <p style={{ fontSize: 9, margin: "0 0 6px", color: "#7a5b00", lineHeight: 1.7 }}>
            این ضمیمه کاملاً مجزا از صورت‌جمع مالی بالاست و هیچ تأثیری روی ارقام رسمی
            ندارد. دو موتور «تعدیل پیمان» و «برآورد به‌هنگام» مستقل‌اند و تا تأیید شما
            خروجی آن‌ها «پیش‌نویس» است.
          </p>
          {result.adjustment.tadil && (
            <PrintEngine
              title={result.adjustment.tadil.mode}
              formula={result.adjustment.tadil.formula}
              draft={result.adjustment.tadil.draft}
              error={result.adjustment.tadil.error}
              rows={[
                ["مبلغ پایه (A + تجهیز)", result.adjustment.tadil.base_amount],
                ["جمع تعدیل (شامل علی‌الحساب)", result.adjustment.tadil.delta_p],
                ["بخش قطعی (شاخص‌های قطعی ۱۴۰۴)", result.adjustment.tadil.delta_p_definitive],
                ["بخش علی‌الحساب (شاخص موقت ۱۴۰۵Q1)", result.adjustment.tadil.delta_p_provisional],
                ...(Math.abs(result.adjustment.tadil.deduction_fault) >= 0.01
                  ? [["کسر ۵٪ — فسخ با قصور پیمانکار (بند ۷)",
                      result.adjustment.tadil.deduction_fault] as [string, number]]
                  : []),
                ["مبلغ نهایی (A + جمع تعدیل)", result.adjustment.tadil.result_amount],
              ]}
              chapters={result.adjustment.tadil.chapters}
            />
          )}
          {result.adjustment.baravord && (
            <PrintEngine
              title={result.adjustment.baravord.mode}
              formula={result.adjustment.baravord.formula}
              draft={result.adjustment.baravord.draft}
              error={result.adjustment.baravord.error}
              rows={[
                ["مبلغ پایه (A + تجهیز)", result.adjustment.baravord.base_amount],
                ["برآورد به‌هنگام‌شده (A_new)", result.adjustment.baravord.result_amount],
                ["جمع کل به‌هنگام‌شده (قیمت پیمان)", result.adjustment.baravord.grand_updated],
              ]}
              chapters={result.adjustment.baravord.chapters}
            />
          )}
        </>
      )}

      {/* سوابق تجمعی */}
      {history.length > 0 && (
        <>
          <h3 style={{ fontSize: 12, margin: "12px 0 6px" }}>سوابق صورت‌وضعیت‌ها (تجمعی)</h3>
          <table style={{ width: "100%", borderCollapse: "collapse" }} border={1}>
            <tbody>
              <tr style={{ background: "#f0f0f0", fontWeight: 700 }}>
                <td style={{ ...td, textAlign: "center" }}>شماره</td>
                <td style={{ ...td, textAlign: "center" }}>نوع</td>
                <td style={{ ...td, textAlign: "center" }}>دوره از</td>
                <td style={{ ...td, textAlign: "center" }}>دوره تا</td>
                <td style={{ ...td, textAlign: "center" }}>خالص تجمعی</td>
                <td style={{ ...td, textAlign: "center" }}>کارکرد این دوره</td>
              </tr>
              {history.map((h, i) => {
                const prev = history[i - 1];
                const current = h.netPayable - (prev?.netPayable ?? 0);
                return (
                  <tr key={h.id}>
                    <td style={{ ...td, textAlign: "center" }}>{faDigits(h.reportNo)}</td>
                    <td style={{ ...td, textAlign: "center" }}>{h.reportType}</td>
                    <td style={{ ...td, textAlign: "center", fontSize: 9 }}>{h.periodStart || "—"}</td>
                    <td style={{ ...td, textAlign: "center", fontSize: 9 }}>{h.periodEnd || "—"}</td>
                    <td style={tdNum}>{fmtRial(h.netPayable)}</td>
                    <td style={{ ...tdNum, fontWeight: 700 }}>{fmtRial(current)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}

      {/* امضاها */}
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 20 }} border={1} cellPadding={10}>
        <tbody>
          <tr style={{ textAlign: "center", fontSize: 11 }}>
            <td><b>مهندس دفتر فنی</b><br /><br /><br />نام و امضا:</td>
            <td><b>سرپرست کارگاه</b><br /><br /><br />نام و امضا:</td>
            <td><b>مهندس ناظر / مشاور</b><br /><br /><br />نام و امضا:</td>
            <td><b>کارفرما</b><br /><br /><br />نام و امضا:</td>
          </tr>
        </tbody>
      </table>

      <p style={{ fontSize: 8.5, marginTop: 8, color: "#555", lineHeight: 1.7 }}>
        یادداشت: مقادیر این سند به‌صورت خودکار از خروجی‌های مدل BIM (Revit) استخراج و با فهرست‌بهای واحد پایهٔ ابنیه سال ۱۴۰۴ تطبیق داده شده است.
        بهای ردیف‌های دارای علامت «تخمینی» در گزارش الکترونیکی، پیش از ارائهٔ نهایی باید با نسخهٔ ابلاغی کنترل شود.
      </p>
    </div>
  );
}

const td2: React.CSSProperties = { border: "1px solid #999", padding: "5px 7px", fontSize: 10, verticalAlign: "top" };

function FinPRow({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <tr>
      <td style={{ ...td2, fontSize: 11, ...(strong ? { fontWeight: 700, background: "#faf6ea" } : {}) }}>{label}</td>
      <td style={{ ...td2, textAlign: "left", direction: "ltr", fontFamily: "Tahoma", fontWeight: strong ? 700 : 400 }}>
        {faDigits(Math.round(value).toLocaleString("en-US"))}
      </td>
    </tr>
  );
}

/** ضمیمهٔ چاپی یک موتور تعدیل — جداگانه از زنجیرهٔ مالی رسمی */
function PrintEngine({
  title,
  formula,
  draft,
  error,
  rows,
  chapters,
}: {
  title: string;
  formula: string;
  draft: boolean;
  error?: string;
  rows: [string, number][];
  chapters: { chapter: string; title: string; amount: number; io: number; it: number | null; ratio: number | null; value: number; status: string }[];
}) {
  return (
    <div style={{ border: "1.5px dashed #b08800", borderRadius: 6, padding: "8px 10px", marginBottom: 10, background: "#fffdf5" }}>
      <div style={{ fontSize: 11, fontWeight: 800, marginBottom: 2 }}>{title}</div>
      <div style={{ fontSize: 9, fontFamily: "Tahoma", direction: "ltr", textAlign: "left", marginBottom: 4 }}>{formula}</div>
      {error ? (
        <div style={{ fontSize: 9.5, color: "#a00", lineHeight: 1.6 }}>توقف موتور: {error}</div>
      ) : (
        <>
          {draft && (
            <div style={{ fontSize: 9, color: "#7a5b00", marginBottom: 4 }}>
              پیش‌نویس — مقادیر با منبع تصویری/دستی تا تأیید شما قطعی نمی‌شوند.
            </div>
          )}
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 6 }} border={1}>
            <tbody>
              {rows.map(([label, value], i) => (
                <tr key={i}>
                  <td style={{ ...td2, fontSize: 9.5, width: "62%" }}>{label}</td>
                  <td style={{ ...td2, textAlign: "left", direction: "ltr", fontFamily: "Tahoma", fontSize: 9.5, fontWeight: 700 }}>
                    {faDigits(Math.round(value).toLocaleString("en-US"))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {chapters.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse" }} border={1}>
              <thead>
                <tr style={{ background: "#f0ead8" }}>
                  <th style={th}>فصل</th>
                  <th style={{ ...th, width: "40%" }}>عنوان</th>
                  <th style={th}>A_c</th>
                  <th style={th}>Io</th>
                  <th style={th}>It</th>
                  <th style={th}>نسبت</th>
                  <th style={th}>مبلغ</th>
                  <th style={th}>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {chapters.map((r) => (
                  <tr key={r.chapter}>
                    <td style={{ ...td2, fontSize: 9, textAlign: "center" }}>{faDigits(r.chapter)}</td>
                    <td style={{ ...td2, fontSize: 8.5 }}>{r.title}</td>
                    <td style={{ ...tdNum, fontSize: 9 }}>{fmtRial(r.amount)}</td>
                    <td style={{ ...tdNum, fontSize: 9 }}>{fmtNum(r.io, 1)}</td>
                    <td style={{ ...tdNum, fontSize: 9 }}>{r.it !== null ? fmtNum(r.it, 1) : "—"}</td>
                    <td style={{ ...tdNum, fontSize: 9 }}>{r.ratio !== null ? fmtNum(r.ratio, 4) : "—"}</td>
                    <td style={{ ...tdNum, fontSize: 9, fontWeight: 700 }}>{fmtRial(r.value)}</td>
                    <td style={{ ...td2, fontSize: 8.5, textAlign: "center" }}>{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
