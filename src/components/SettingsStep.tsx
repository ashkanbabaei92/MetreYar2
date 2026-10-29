import {
  Building2,
  CalendarDays,
  Layers,
  Landmark,
  Ruler,
  Settings2,
  Scale,
  TrendingUp,
  Truck,
  Wallet,
} from "lucide-react";
import { Card, SectionTitle } from "./ui";
import {
  CONCRETE_STRENGTH_CODES,
  JOIST_BLOCK_STRENGTH_SURCHARGE,
  JOIST_BLOCK_THICKNESS_CODES,
  LEAN_CEMENT_CODES,
  OVERHEAD_PRESETS,
  type ProjectMeta,
  type ProjectSettings,
  type QuantityRecord,
} from "../lib/types";
import { cn } from "../utils/cn";
import { faDigits, fmtNum } from "../lib/normalize";
import { todayJalali, isValidJalaliDate, moneyToWords, g2j, fa } from "../lib/farsi";
import { validateMeta } from "../lib/adjustment";
import { IndexTable } from "../lib/indices";
import { PhaseBCard } from "./SettingsStep_PhaseB";
import { FloorsTableCard } from "./SettingsStep_Floors";
import type { ChangeEvent, ReactNode } from "react";
import { useRef } from "react";

const STRENGTH_OPTS = Object.keys(CONCRETE_STRENGTH_CODES).map(Number);
const LEAN_OPTS = Object.keys(LEAN_CEMENT_CODES).map(Number);
const JOIST_OPTS = Object.keys(JOIST_BLOCK_THICKNESS_CODES).map(Number);
const JOIST_STRENGTH_OPTS = Object.keys(JOIST_BLOCK_STRENGTH_SURCHARGE).map(Number);

export function CardHeader({ icon, title, sub }: { icon: ReactNode; title: string; sub?: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="w-11 h-11 rounded-xl bg-gold/15 text-gold grid place-items-center shrink-0">{icon}</div>
      <div>
        <h3 className="font-bold text-ink text-[15px]">{title}</h3>
        {sub && <p className="text-[11.5px] text-ink-dim mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export function Field({
  label,
  children,
  span,
}: {
  label: string;
  children: ReactNode;
  span?: boolean;
}) {
  return (
    <label className={cn("block", span && "md:col-span-2")}>
      <span className="text-[11.5px] text-ink-dim block mb-1.5">{label}</span>
      {children}
    </label>
  );
}

export const inputCls =
  "w-full bg-panel-2 border border-line rounded-xl px-3.5 py-2.5 text-[13px] outline-none focus:border-gold/50 transition-colors placeholder:text-ink-dim/60";

export function SettingsStep({
  meta,
  setMeta,
  settings,
  setSettings,
  records,
  onNext,
}: {
  meta: ProjectMeta;
  setMeta: (m: ProjectMeta) => void;
  settings: ProjectSettings;
  setSettings: (s: ProjectSettings) => void;
  records: QuantityRecord[];
  onNext: () => void;
}) {
  const patch = <K extends keyof ProjectSettings>(key: K, value: ProjectSettings[K]) =>
    setSettings({ ...settings, [key]: value });
  const patchMeta = <K extends keyof ProjectMeta>(key: K, value: ProjectMeta[K]) =>
    setMeta({ ...meta, [key]: value });

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="گام ۴ — تنظیمات کاربردی دفتر فنی"
        title="مشخصات پروژه، صورت‌وضعیت و ضرایب قرارداد"
        sub="این اطلاعات در هدرِ رسمی گزارش‌های Excel و نسخهٔ چاپی درج می‌شوند و تمام محاسبات مالی را شکل می‌دهند."
      />

      {/* ── مشخصات ثبتی پروژه ── */}
      <Card>
        <CardHeader
          icon={<Building2 size={20} />}
          title="مشخصات پروژه و قرارداد"
          sub="هویت ثبتی که در گزارش‌های رسمی نمایش داده می‌شود"
        />
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          <Field label="نام پروژه" span>
            <input value={meta.projectName} onChange={(e) => patchMeta("projectName", e.target.value)} className={inputCls} placeholder="مثلاً: مجتمع مسکونی ویلای ساحلی — فاز اسکلت" />
          </Field>
          <Field label="نام کارفرما">
            <input value={meta.employer} onChange={(e) => patchMeta("employer", e.target.value)} className={inputCls} placeholder="مثلاً: آقای مهندس احمدی" />
          </Field>
          <Field label="نام پیمانکار">
            <input value={meta.contractor} onChange={(e) => patchMeta("contractor", e.target.value)} className={inputCls} placeholder="مثلاً: شرکت ساختمانی پویان" />
          </Field>
          <Field label="نام مشاور">
            <input value={meta.consultant} onChange={(e) => patchMeta("consultant", e.target.value)} className={inputCls} placeholder="مثلاً: شرکت مهندسین مشاور آرمان" />
          </Field>
          <Field label="شماره قرارداد">
            <input value={meta.contractNo} onChange={(e) => patchMeta("contractNo", e.target.value)} className={inputCls} placeholder="مثلاً: ۱۴۰۴-۱۲۵" />
          </Field>
          <Field label="تاریخ شروع پیمان">
            <JalaliInput value={meta.contractDate} onChange={(v) => patchMeta("contractDate", v)} />
          </Field>
          <Field label="محل اجرا">
            <input value={meta.location} onChange={(e) => patchMeta("location", e.target.value)} className={inputCls} placeholder="مثلاً: مازندران، چمستان" />
          </Field>
        </div>
      </Card>

      {/* ── متا دیتای صورت‌وضعیت ── */}
      <Card glow>
        <CardHeader
          icon={<CalendarDays size={20} />}
          title="متا دیتای صورت‌وضعیت جاری"
          sub="شماره، نوع و دورهٔ کارکرد — در هدر همهٔ خروجی‌ها درج می‌شود"
        />
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          <Field label="شمارهٔ صورت‌وضعیت">
            <input value={meta.reportNo} onChange={(e) => patchMeta("reportNo", e.target.value)} className={cn(inputCls, "num")} placeholder="مثلاً: ۳" />
          </Field>
          <Field label="نوع صورت‌وضعیت">
            <div className="flex rounded-xl overflow-hidden border border-line">
              {(["موقت", "قطعی"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => patchMeta("reportType", t)}
                  className={cn(
                    "flex-1 py-2.5 text-[12.5px] font-bold transition-colors",
                    meta.reportType === t ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
          </Field>
          <Field label="تاریخ شروع دورهٔ صورت‌وضعیت">
            <JalaliInput value={meta.periodStart} onChange={(v) => patchMeta("periodStart", v)} placeholder={todayJalali()} />
          </Field>
          <Field label="تاریخ پایان دورهٔ صورت‌وضعیت">
            <JalaliInput value={meta.periodEnd} onChange={(v) => patchMeta("periodEnd", v)} placeholder={todayJalali()} />
          </Field>
        </div>
        {/* خطاهای اعتبارسنجی تاریخ‌ها (ایراد ۱۲) — محاسبه تا اصلاح متوقف می‌شود */}
        {validateMeta(meta).length > 0 && (
          <div className="mt-3 rounded-xl border border-rose/40 bg-rose/8 p-3 space-y-1.5">
            {validateMeta(meta).map((e, i) => (
              <p key={i} className="text-[11.5px] text-rose font-bold flex items-start gap-1.5">
                <span className="shrink-0 mt-px">✕</span>
                <span>{e.message} {e.action}</span>
              </p>
            ))}
          </div>
        )}
        <p className="text-[11px] text-ink-dim mt-3 flex items-center gap-1.5">
          <CalendarDays size={12} />
          تاریخ امروز به وقت ایران: <b className="text-ink/80">{todayJalali()}</b> — قالب تاریخ: سال/ماه/روز (مثلاً ۱۴۰۴/۰۳/۳۱)
        </p>
      </Card>

      {/* ── زنجیرهٔ مالی (دستورالعمل کاربرد بندهای ۲-۷ و ۲-۸) ── */}
      <Card>
        <CardHeader
          icon={<Scale size={20} />}
          title="زنجیرهٔ مالی صورت‌وضعیت"
          sub="ترتیب: جمع ردیف‌ها × ضریب طبقات × ضریب بالاسری × ضریب منطقه‌ای + تجهیز و برچیدن کارگاه"
        />
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          <CoefField label="ضریب طبقات" value={settings.floorsCoef} onChange={(v) => patch("floorsCoef", v)} presets={[1, 1.03, 1.05, 1.1]} hint="پیوست ۲ — در صورت نیاز" />
          <CoefField label="ضریب منطقه‌ای" value={settings.regionalCoef} onChange={(v) => patch("regionalCoef", v)} presets={[1, 1.02, 1.05, 1.1]} hint="بر اساس بخشنامهٔ مناطق" />
          <Field label="تجهیز و برچیدن کارگاه (ریال — مبلغ)">
            <input
              type="number"
              value={settings.siteSetupAmount || ""}
              onChange={(e) => patch("siteSetupAmount", parseFloat(e.target.value) || 0)}
              className={cn(inputCls, "num")}
              placeholder="0"
              step={1000000}
              min={0}
            />
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              {settings.siteSetupAmount
                ? moneyToWords(settings.siteSetupAmount)
                : "مبلغ واردشدهٔ کاربر (درصد گرفته نمی‌شود)"}
              {" — "}هشدار: سقف تجهیز و برچیدن ۴٪ مبلغ قبل از آن است (دستورالعمل ۲-۸).
            </span>
          </Field>
        </div>
        <div className="mt-4">
          <span className="text-[11.5px] text-ink-dim block mb-2">پیش‌فرض‌های ضریب بالاسری (دستورالعمل کاربرد بند ۲-۷):</span>
          <div className="flex gap-1.5 flex-wrap">
            {OVERHEAD_PRESETS.map(([key, coef, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => patch("overheadCoef", coef)}
                className={cn(
                  "px-3.5 py-1.5 rounded-lg text-[12px] font-bold border transition-colors",
                  settings.overheadCoef === coef ? "bg-gold/15 border-gold/40 text-gold" : "bg-panel-2 border-line text-ink-dim hover:text-ink",
                )}
              >
                {label} — {fmtNum(coef, 2)}
              </button>
            ))}
          </div>
          <div className="mt-3">
            <CoefField label="ضریب بالاسری" value={settings.overheadCoef} onChange={(v) => patch("overheadCoef", v)} presets={[1, 1.2, 1.3, 1.4]} hint="یکی از پیش‌فرض‌های بالا یا مقدار سفارشی" />
          </div>
        </div>
      </Card>

      {/* ── جدول طبقات (ایراد ۳ + بند ۱: انتخاب دستیِ طبقه بودن هر تراز) ── */}
      <FloorsTableCard
        records={records}
        settings={settings}
        setSettings={setSettings}
      />

      {/* ── شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) ── */}
      <IndexCard settings={settings} patch={patch} />

      {/* ── فاز B: دو موتور مجزای تعدیل (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند) ── */}
      <PhaseBCard settings={settings} patch={patch} />

      {/* ── کسورات قانونی (فقط برای «خالص پرداختی») ── */}
      <Card>
        <CardHeader
          icon={<Landmark size={20} />}
          title="کسورات قانونی"
          sub="بر «ناخالص نهایی» اثر ندارند و فقط در خروجی جداگانهٔ «خالص پرداختی» محاسبه می‌شوند"
        />
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          <PctField label="بیمه (٪)" value={settings.insurancePct} onChange={(v) => patch("insurancePct", v)} max={15} hint="معمولاً ۷٫۸٪" />
          <PctField label="مالیات (٪)" value={settings.taxPct} onChange={(v) => patch("taxPct", v)} max={15} hint="معمولاً ۵٪" />
          <PctField label="حسن انجام کار (٪)" value={settings.goodJobPct} onChange={(v) => patch("goodJobPct", v)} max={20} hint="معمولاً ۱۰٪ — برگشتی در پایان" />
          <Field label="پیش‌پرداخت (ریال)">
            <input
              type="number"
              value={settings.advancePayment || ""}
              onChange={(e) => patch("advancePayment", parseFloat(e.target.value) || 0)}
              className={cn(inputCls, "num")}
              placeholder="0"
            />
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">{settings.advancePayment ? moneyToWords(settings.advancePayment) : "کسر از خالص پرداخت این دوره"}</span>
          </Field>
        </div>
      </Card>

      {/* ── تنظیمات نمایش ── */}
      <Card>
        <CardHeader icon={<Wallet size={20} />} title="تنظیمات نمایش" sub="واحد پول و قالب‌بندی اعداد در گزارش‌ها" />
        <div className="grid md:grid-cols-2 gap-4">
          <Field label="واحد پول نمایش">
            <div className="flex rounded-xl overflow-hidden border border-line">
              {(["rial", "toman"] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => patch("currency", c)}
                  className={cn(
                    "flex-1 py-2.5 text-[12.5px] font-bold transition-colors",
                    settings.currency === c ? "bg-emerald/15 text-emerald" : "bg-panel-2 text-ink-dim hover:text-ink",
                  )}
                >
                  {c === "rial" ? "ریال" : "تومان"}
                </button>
              ))}
            </div>
          </Field>
          <Field label="رند کردن مبالغ">
            <div className="flex rounded-xl overflow-hidden border border-line">
              {[
                { v: true, t: "رند به ۱۰۰۰ ریال" },
                { v: false, t: "دقیق" },
              ].map((o) => (
                <button
                  key={String(o.v)}
                  type="button"
                  onClick={() => patch("rounding", o.v)}
                  className={cn(
                    "flex-1 py-2.5 text-[12.5px] font-bold transition-colors",
                    settings.rounding === o.v ? "bg-emerald/15 text-emerald" : "bg-panel-2 text-ink-dim hover:text-ink",
                  )}
                >
                  {o.t}
                </button>
              ))}
            </div>
          </Field>
        </div>
      </Card>

      {/* ── پارامتر هندسهٔ سقف ── */}
      <Card>
        <CardHeader
          icon={<Ruler size={20} />}
          title="پارامترهای هندسی تیرچه‌بلوک"
          sub="برای تبدیل «طول تیرچه» از Revit به «مساحت سقف» در ردیف ۱۰۰x فهرست‌بها"
        />
        <div className="flex items-center gap-4 flex-wrap">
          <label className="text-[12.5px] text-ink-dim">فاصلهٔ محور تا محور تیرچه (متر):</label>
          {[0.5, 0.55, 0.6, 0.65].map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => patch("joistSpacing", v)}
              className={cn(
                "px-4 py-2 rounded-lg text-[13px] num font-bold border transition-colors",
                settings.joistSpacing === v ? "bg-teal/15 border-teal/40 text-teal" : "bg-panel-2 border-line text-ink-dim hover:text-ink",
              )}
            >
              {fmtNum(v, 2)}
            </button>
          ))}
          <input
            type="number"
            step={0.01}
            min={0.4}
            max={1}
            value={settings.joistSpacing}
            onChange={(e) => patch("joistSpacing", parseFloat(e.target.value) || 0.55)}
            className="bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] num w-24 outline-none focus:border-teal/50"
          />
        </div>
      </Card>

      {/* ── فرض‌های فنی پروژه ── */}
      <Card>
        <CardHeader
          icon={<Layers size={20} />}
          title="فرض‌های فنی پروژه"
          sub="کد و بهای ردیف‌های بتن و سقف تیرچه‌بلوک از فهرست‌بهای ۱۴۰۴ بر اساس این مقادیر انتخاب می‌شود"
        />
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          <SelectField
            label="مقاومت فشاری بتن پی (MPa)"
            value={settings.concreteStrengthMpa.foundation}
            options={STRENGTH_OPTS}
            onChange={(v) => patch("concreteStrengthMpa", { ...settings.concreteStrengthMpa, foundation: v })}
            format={(v) => `${faDigits(v)} مگاپاسکال — ${CONCRETE_STRENGTH_CODES[v][0]}`}
          />
          <SelectField
            label="مقاومت فشاری بتن ستون و تیر (MPa)"
            value={settings.concreteStrengthMpa.columnBeam}
            options={STRENGTH_OPTS}
            onChange={(v) => patch("concreteStrengthMpa", { ...settings.concreteStrengthMpa, columnBeam: v })}
            format={(v) => `${faDigits(v)} مگاپاسکال — ${CONCRETE_STRENGTH_CODES[v][0]}`}
          />
          <SelectField
            label="مقاومت فشاری بتن سقف (MPa)"
            value={settings.concreteStrengthMpa.slab}
            options={STRENGTH_OPTS}
            onChange={(v) => patch("concreteStrengthMpa", { ...settings.concreteStrengthMpa, slab: v })}
            format={(v) => `${faDigits(v)} مگاپاسکال — ${CONCRETE_STRENGTH_CODES[v][0]}`}
          />
          <SelectField
            label="مقاومت فشاری بتن پله (MPa)"
            value={settings.concreteStrengthMpa.stair}
            options={STRENGTH_OPTS}
            onChange={(v) => patch("concreteStrengthMpa", { ...settings.concreteStrengthMpa, stair: v })}
            format={(v) => `${faDigits(v)} مگاپاسکال — ${CONCRETE_STRENGTH_CODES[v][0]}`}
          />
          <SelectField
            label="عیار سیمان بتن مگر (kg/m³)"
            value={settings.leanCementKg}
            options={LEAN_OPTS}
            onChange={(v) => patch("leanCementKg", v)}
            format={(v) => `${faDigits(v)} کیلوگرم — ${LEAN_CEMENT_CODES[v][0]}`}
          />
          <SelectField
            label="ضخامت سقف تیرچه‌بلوک (cm)"
            value={settings.joistBlockThicknessCm}
            options={JOIST_OPTS}
            onChange={(v) => patch("joistBlockThicknessCm", v)}
            format={(v) => `${faDigits(v)} سانتی‌متر — ${JOIST_BLOCK_THICKNESS_CODES[v][0]}`}
          />
          <SelectField
            label="مقاومت بتن سقف تیرچه‌بلوک (MPa)"
            value={settings.joistBlockConcreteMpa}
            options={JOIST_STRENGTH_OPTS}
            onChange={(v) => patch("joistBlockConcreteMpa", v)}
            format={(v) =>
              `${faDigits(v)} مگاپاسکال — ${JOIST_BLOCK_STRENGTH_SURCHARGE[v] === null ? "بدون اضافه‌بها" : JOIST_BLOCK_STRENGTH_SURCHARGE[v]![0]}`
            }
            hint="بند ۸ الزامات عمومی فصل دهم: ۲۰ MPa فرض است؛ ۲۵ → اضافه‌بهای ۱۰۰۷۰۱ (۵۹٬۵۰۰ ریال/m²)، ۳۰ → ۱۰۰۷۰۲ (۷۶٬۵۰۰ ریال/m²) روی کل مساحت سقف."
          />
          <Field label="ضخامت بتن روی بلوک طبق مشخصات (cm)">
            <input
              type="number"
              min={0}
              max={30}
              step={0.5}
              value={settings.joistBlockTopThicknessCm}
              onChange={(e) => patch("joistBlockTopThicknessCm", parseFloat(e.target.value) || 0)}
              className={cn(inputCls, "num")}
            />
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              بند ۹ الزامات عمومی فصل دهم: تا ۵ cm بتن روی بلوک داخل نرخ ۱۰۰۳۰۵ است. فقط بتن
              مازاد بر ۵ cm (طبق مشخصات فنی) به ردیف بتن متناظر افزوده می‌شود. اختلاف هندسی
              Revit (مثلاً ۵٫۲ cm) مازاد محسوب نمی‌شود.
            </span>
          </Field>
        </div>
      </Card>

      {/* ── حمل و نقل و اضافه‌بها ── */}
      <Card>
        <CardHeader
          icon={<Truck size={20} />}
          title="حمل و نقل و اضافه‌بها"
          sub="پیشنهادهای خودکار فهرست‌بهای ۱۴۰۴ بر اساس داده‌های پروژه"
        />
        <div className="grid md:grid-cols-2 gap-4">
          <Field label="مسافت حمل مصالح (کیلومتر)">
            <input
              type="number"
              min={0}
              max={200}
              step={5}
              value={settings.haulDistanceKm}
              onChange={(e) => patch("haulDistanceKm", parseInt(e.target.value) || 0)}
              className={cn(inputCls, "num")}
            />
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              ردیف ۲۸۰۱۰۱: بازهٔ ۳۰–۷۵ کیلومتر — کمیت = وزن آرماتور (تن) × (مسافت − ۳۰)
            </span>
          </Field>
          <Field label="اضافه‌بهای سختی ارتعاش بتن (۰۸۰۳۱۱)">
            <div className="flex rounded-xl overflow-hidden border border-line">
              {[
                { v: false, t: "غیرفعال" },
                { v: true, t: "فعال" },
              ].map((o) => (
                <button
                  key={String(o.v)}
                  type="button"
                  onClick={() => patch("surchargeRebarDensity", o.v)}
                  className={cn(
                    "flex-1 py-2.5 text-[12.5px] font-bold transition-colors",
                    settings.surchargeRebarDensity === o.v ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                  )}
                >
                  {o.t}
                </button>
              ))}
            </div>
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              فهرست‌بهای ۱۴۰۴: هرگاه تراکم میلگرد بیش از ۱۸۰ کیلوگرم بر مترمکعب بتن باشد،
              ۳۶۳٬۵۰۰ ریال به ازای هر مترمکعب بتن سازه‌ای. تراکم خودکار از داده‌های آرماتور
              و بتن محاسبه می‌شود (مبنای این ردیف حجم بتن به‌جز سیستم سقف تیرچه‌بلوک است
              و در دادهٔ نمونه ≈ ۳۱ kg/m³ &lt; ۱۸۰ است و ردیفی افزوده نمی‌شود).
            </span>
          </Field>
          <Field label="اضافه‌بهای بتن مسلح (۰۸۰۳۱۰)">
            <div className="flex rounded-xl overflow-hidden border border-line">
              {[
                { v: false, t: "غیرفعال" },
                { v: true, t: "فعال" },
              ].map((o) => (
                <button
                  key={String(o.v)}
                  type="button"
                  onClick={() => patch("surchargeReinforcedConcrete", o.v)}
                  className={cn(
                    "flex-1 py-2.5 text-[12.5px] font-bold transition-colors",
                    settings.surchargeReinforcedConcrete === o.v ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                  )}
                >
                  {o.t}
                </button>
              ))}
            </div>
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              فهرست‌بهای ۱۴۰۴: «در صورت مصرف بتن در بتن مسلح»، ۱۴۵٬۵۰۰ ریال به ازای هر
              مترمکعب بتن. تراکم هر المان = وزن آرماتور میزبان آن (ستون «Host Mark») ÷ حجم
              همان المان؛ فقط المان‌هایی که تراکم خودشان &gt; ۱۸۰ kg/m³ است (بند ۳-۶ فصل ۸).
              حجم سقف تیرچه‌بلوک از مبنای اضافه‌بها کسر می‌شود (بند ۳-۵).
            </span>
          </Field>
          <Field label="اضافه‌بهای ضخامت کم بتن (۰۸۰۳۰۴)">
            <div className="flex rounded-xl overflow-hidden border border-line">
              {[
                { v: false, t: "غیرفعال" },
                { v: true, t: "فعال" },
              ].map((o) => (
                <button
                  key={String(o.v)}
                  type="button"
                  onClick={() => patch("surchargeThinConcrete", o.v)}
                  className={cn(
                    "flex-1 py-2.5 text-[12.5px] font-bold transition-colors",
                    settings.surchargeThinConcrete === o.v ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                  )}
                >
                  {o.t}
                </button>
              ))}
            </div>
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              فهرست‌بهای ۱۴۰۴ (فصل ۸ بند ۳-۳): «هرگاه ضخامت بتن برابر ۱۵ سانتی‌متر یا
              کمتر باشد»، ۳۰۴٬۰۰۰ ریال به ازای هر مترمکعب. مختص کف‌سازی بتنی روی زمین
              (دال روی زمین)؛ سقف‌های معلق شامل نمی‌شوند. ضخامت = حجم ÷ مساحت ردیف
              در جدول خودش (مثل بتن‌مگر و بتن‌ریزی پی).
            </span>
          </Field>
        </div>
      </Card>

      <div className="flex justify-start">
        <button
          onClick={onNext}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gold text-[#1a1410] text-[13.5px] font-extrabold hover:bg-gold-2 transition-colors shadow-[0_10px_30px_-10px_rgba(242,179,61,0.6)]"
        >
          <Settings2 size={16} />
          ادامه: تطبیق هوشمند ردیف‌ها
        </button>
      </div>
    </div>
  );
}

// ── شاخص تعدیل فهرست‌بها (کلیات بند ۲۲) ──
function IndexCard({
  settings,
  patch,
}: {
  settings: ProjectSettings;
  patch: <K extends keyof ProjectSettings>(key: K, value: ProjectSettings[K]) => void;
}) {
  const it = IndexTable.load();
  const periods = it.periods;
  if (periods.length === 0) {
    return (
      <Card>
        <CardHeader
          icon={<TrendingUp size={20} />}
          title="شاخص تعدیل فهرست‌بها (کلیات بند ۲۲)"
          sub="فایل شاخص (indices/abnieh.json) یافت نشد — تعدیل غیرفعال است."
        />
      </Card>
    );
  }
  const tgt = settings.indexTargetPeriod || it.basePeriod || periods[0];
  const cur = periods.includes(tgt) ? tgt : periods[0];
  return (
    <Card>
      <CardHeader
        icon={<TrendingUp size={20} />}
        title="شاخص تعدیل فهرست‌بها (کلیات بند ۲۲)"
        sub="ضریب هر فصل = شاخص دورهٔ هدف ÷ شاخص دورهٔ مبنا، روی مبلغ ردیف، قبل از ضرایب زنجیرهٔ مالی"
      />
      <Field label="دورهٔ هدف شاخص">
        <select
          value={cur}
          onChange={(e) => patch("indexTargetPeriod", e.target.value)}
          className={cn(inputCls, "w-full appearance-none cursor-pointer")}
        >
          {periods.map((p) => (
            <option key={p} value={p}>
              {p === it.basePeriod ? `${p} (مبنا — بدون تعدیل)` : p}
            </option>
          ))}
        </select>
        <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
          مقادیر رسمی شاخص را از بخشنامهٔ مربوطه در فایل «indices/abnieh.json» وارد کنید.
          شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل است.
        </span>
      </Field>
    </Card>
  );
}

// ── فیلد درصد با اسلایدر ──
function PctField({
  label,
  value,
  onChange,
  max,
  hint,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  max: number;
  hint?: string;
}) {
  return (
    <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4">
      <label className="text-[12.5px] font-bold text-ink/90 block mb-1">{label}</label>
      <input
        type="range"
        min={0}
        max={max}
        step={0.1}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-gold mt-2"
      />
      <div className="num text-gold font-extrabold text-[15px] mt-1.5">{fmtNum(value, 2)}٪</div>
      {hint && <p className="text-[10.5px] text-ink-dim mt-1 leading-4">{hint}</p>}
    </div>
  );
}

export function JalaliInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const invalid = value.trim() !== "" && !isValidJalaliDate(value);
  // انتخاب از تقویم میلادی مرورگر → تبدیل به شمسی (ایراد ۱۳: date-picker).
  // فیلد اصلی شمسی می‌ماند؛ این فقط راهی بصری برای ورود تاریخ است.
  const pickerRef = useRef<HTMLInputElement>(null);
  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    const iso = e.target.value; // YYYY-MM-DD (میلادی)
    if (!iso) return;
    const parts = iso.split("-").map(Number);
    if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return;
    const [gy, gm, gd] = parts;
    const [jy, jm, jd] = g2j(gy, gm, gd);
    onChange(fa(`${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`));
  };
  return (
    <div>
      <div className="relative flex gap-1.5">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(inputCls, "num", "flex-1", invalid && "border-rose/60 focus:border-rose")}
          placeholder={placeholder ?? "۱۴۰۴/۰۱/۱۵"}
        />
        <div className="relative shrink-0">
          <button
            type="button"
            title="انتخاب از تقویم"
            onClick={() => pickerRef.current?.showPicker?.()}
            className="h-full px-2.5 rounded-xl border border-line bg-panel-2 text-ink-dim hover:text-gold hover:border-gold/40 transition-colors"
          >
            <CalendarDays size={15} />
          </button>
          <input
            ref={pickerRef}
            type="date"
            onChange={onPick}
            className="absolute inset-0 w-0 h-0 opacity-0 pointer-events-none"
            tabIndex={-1}
            aria-hidden
          />
        </div>
      </div>
      {invalid && <span className="text-[10.5px] text-rose block mt-1.5">قالب تاریخ نامعتبر است (مثال: ۱۴۰۴/۰۳/۳۱)</span>}
    </div>
  );
}

// ── فیلد ضریب با مقادیر پیش‌فرض ──
function CoefField({
  label,
  value,
  onChange,
  presets,
  hint,
}: {
  label: string;
  value: number | null;
  onChange: (v: number) => void;
  presets: number[];
  hint?: string;
}) {
  return (
    <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4">
      <label className="text-[12.5px] font-bold text-ink/90 block mb-2.5">{label}</label>
      <div className="flex gap-1.5 flex-wrap">
        {presets.map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-[12px] num font-bold border transition-colors",
              value === v ? "bg-gold/15 border-gold/40 text-gold" : "bg-panel-2 border-line text-ink-dim hover:text-ink",
            )}
          >
            {fmtNum(v, 2)}
          </button>
        ))}
      </div>
      <input
        type="number"
        step={0.01}
        value={value ?? ""}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="mt-2.5 bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] num w-full outline-none focus:border-gold/50"
      />
      {hint && <p className="text-[10.5px] text-ink-dim mt-1.5 leading-4">{hint}</p>}
    </div>
  );
}

// ── فیلد dropdown با مقادیر مجاز ──
function SelectField<T extends number>({  label,
  value,
  options,
  onChange,
  format,
  hint,
}: {
  label: string;
  value: T;
  options: number[];
  onChange: (v: T) => void;
  format?: (v: T) => string;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11.5px] text-ink-dim block mb-1.5">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value) as T)}
        className={cn(inputCls, "w-full appearance-none cursor-pointer")}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {format ? format(o as T) : String(o)}
          </option>
        ))}
      </select>
      {hint && <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">{hint}</span>}
    </label>
  );
}

