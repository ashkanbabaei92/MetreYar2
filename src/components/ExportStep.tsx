import { useState } from "react";
import { Download, FileSpreadsheet, Printer, Share2, ShieldCheck } from "lucide-react";
import { Card, SectionTitle, BigMoney } from "./ui";
import type { ProjectMeta, ProjectResult, ProjectSettings, StatusReportRecord } from "../lib/types";
import { exportWorkbook } from "../lib/exporters";

export function ExportStep({
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
  const [done, setDone] = useState<string | null>(null);
  const [draftMode, setDraftMode] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  if (!result || !result.lines.length) {
    return (
      <Card className="text-center py-16">
        <FileSpreadsheet size={42} className="mx-auto text-ink-dim mb-4" />
        <h3 className="text-ink font-bold text-lg">داده‌ای برای برون‌بری وجود ندارد</h3>
        <p className="text-ink-dim text-[13px] mt-2">ابتدا پردازش پروژه را کامل کنید.</p>
      </Card>
    );
  }

  const flash = (msg: string) => {
    setDone(msg);
    setTimeout(() => setDone(null), 3200);
  };

  // فاز E-10 §۲ — قفلِ خروجیِ نهاییِ تعدیل: دورهٔ کارکرد خالی ⇒ فقط پیش‌نویس
  const tadilRes = result.adjustment?.tadil;
  const wpMissing = !!(tadilRes && tadilRes.work_period_missing);

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="گام ۷ — تحویل خروجی"
        title="برون‌بری گزارش‌های رسمی دفتر فنی"
        sub="خروجی Excel شامل ۵ برگه کامل (خلاصهٔ مالی، صورت‌وضعیت، ریزمتره، لیستوفر آرماتور و کیفیت) و خروجی چاپ فارسی مناسب امضا و ارائه به کارفرما."
      />

      <div className="grid md:grid-cols-3 gap-4">
        <Card className="text-center p-8">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald/15 text-emerald grid place-items-center mb-4">
            <FileSpreadsheet size={26} />
          </div>
          <h3 className="font-bold text-ink text-[15px]">کتاب‌کار Excel کامل</h3>
          <p className="text-ink-dim text-[12px] mt-2 leading-6 mb-5">
            ۵ برگه با محاسبات نهایی · راست‌به‌چپ · آماده برای صورت‌وضعیت‌های دوره‌ای
          </p>
          {wpMissing ? (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-right text-[12px] leading-6 text-red-700">
              دورهٔ کارکرد (دورهٔ انجامِ کار) وارد نشده است — خروجیِ نهاییِ
              Excel ساخته نمی‌شود، چون موتورِ تعدیل تمامِ کارکرد را به
              آخرین شاخصِ قطعی منتسب می‌کند و مبلغِ تعدیل با حالتِ «شاخصِ
              هر سه‌ماهه» متفاوت است. «تاریخ شروع/پایان دورهٔ صورت‌وضعیت» را
              در تنظیمات وارد کنید.
              <label className="mt-2 flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={draftMode}
                  onChange={(e) => setDraftMode(e.target.checked)}
                />
                خروجیِ پیش‌نویس (واترمارک «پیش‌نویس – دورهٔ کارکرد وارد نشده»
                روی همهٔ شیت‌ها)
              </label>
            </div>
          ) : null}
          {errMsg ? (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-right text-[12px] leading-6 text-red-700">
              {errMsg}
            </div>
          ) : null}
          <button
            onClick={() => {
              try {
                exportWorkbook(
                  wpMissing && draftMode
                    ? { ...meta, reportType: `پیش‌نویس — ${meta.reportType || "موقت"}` }
                    : meta,
                  result,
                  settings,
                  history,
                );
                setErrMsg(null);
                flash(
                  wpMissing && draftMode
                    ? "فایل Excel پیش‌نویس دانلود شد."
                    : "فایل Excel با موفقیت دانلود شد.",
                );
              } catch (e) {
                setErrMsg(e instanceof Error ? e.message : String(e));
              }
            }}
            className="w-full px-5 py-3 rounded-xl bg-emerald text-[#062018] font-extrabold text-[13px] hover:brightness-110 transition-all flex items-center justify-center gap-2"
          >
            <Download size={16} />
            {wpMissing && draftMode ? "دانلود Excel پیش‌نویس" : "دانلود Excel (.xlsx)"}
          </button>
        </Card>

        <Card className="text-center p-8">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-sky/15 text-sky grid place-items-center mb-4">
            <Printer size={26} />
          </div>
          <h3 className="font-bold text-ink text-[15px]">نسخهٔ چاپی فارسی / PDF</h3>
          <p className="text-ink-dim text-[12px] mt-2 leading-6 mb-5">
            صورت‌وضعیت رسمی با سربرگ و امضا — از چاپگر مرورگر «Save as PDF» را انتخاب کنید
          </p>
          <button
            onClick={() => window.print()}
            className="w-full px-5 py-3 rounded-xl bg-sky text-[#04121c] font-extrabold text-[13px] hover:brightness-110 transition-all flex items-center justify-center gap-2"
          >
            <Printer size={16} />
            چاپ / ذخیرهٔ PDF
          </button>
        </Card>

        <Card className="text-center p-8">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-violet/15 text-violet grid place-items-center mb-4">
            <Share2 size={26} />
          </div>
          <h3 className="font-bold text-ink text-[15px]">پشتیبان‌داده (JSON)</h3>
          <p className="text-ink-dim text-[12px] mt-2 leading-6 mb-5">
            کل تولیدات پروژه در قالب JSON برای آرشیو یا پردازش‌های بعدی در نرم‌افزارهای دیگر
          </p>
          <button
            onClick={() => {
              const blob = new Blob(
                [JSON.stringify({ meta, settings, result, history, exportedAt: new Date().toISOString() }, null, 2)],
                { type: "application/json" },
              );
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = `MetreYar_${(meta.projectName || "project").replace(/[\\/:*?"<>|\s]+/g, "_")}.json`;
              a.click();
              flash("فایل JSON دانلود شد.");
            }}
            className="w-full px-5 py-3 rounded-xl bg-violet text-[#12061e] font-extrabold text-[13px] hover:brightness-110 transition-all flex items-center justify-center gap-2"
          >
            <Download size={16} />
            دانلود JSON
          </button>
        </Card>
      </div>

      <Card className="flex items-center justify-between gap-5 flex-wrap">
        <div className="flex items-center gap-3">
          <ShieldCheck size={20} className="text-emerald" />
          <div>
            <div className="text-[13px] font-bold text-ink">مبلغ نهایی گزارش جاری</div>
            <div className="text-[11.5px] text-ink-dim mt-0.5">شامل {result.lines.length} ردیف فهرست‌بها + ضرایب قرارداد</div>
          </div>
        </div>
        <BigMoney rial={result.grandTotal} />
      </Card>

      {done && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl bg-emerald text-[#062018] px-5 py-3 text-[13px] font-bold shadow-2xl flex items-center gap-2">
          <ShieldCheck size={16} />
          {done}
        </div>
      )}
    </div>
  );
}
