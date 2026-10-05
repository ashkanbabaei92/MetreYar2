import { Lock, TrendingUp } from "lucide-react";
import { Card } from "./ui";
import type { ProjectSettings } from "../lib/types";
import { cn } from "../utils/cn";
import { CardHeader, Field, inputCls, JalaliInput } from "./SettingsStep";
import type { ReactNode } from "react";

// ─────────────────────────────────────────────────────────────
// فاز B — دو موتور مجزای تعدیل (قاعدهٔ طلایی ۵: هرگز ادغام نمی‌شوند)
//
//   ۱) تعدیل پیمان    : ΔP = k × Σ_c (It_c/Io_c − ۱) × A_c
//   ۲) برآورد به‌هنگام : A_new = Σ_c A_c × It_c/Io_c
// هر دو می‌توانند همزمان فعال شوند ولی ورودی/فرمول/خروجی هر کدام جداست.
// هر فیلد دستی یک برچسب وضعیت دارد (قاعدهٔ طلایی ۱ و ۲).
// ─────────────────────────────────────────────────────────────

const PERIOD_OPTS: { v: string; t: string }[] = [
  { v: "base", t: "اسفند ۱۴۰۳ (مبنا)" },
  { v: "q1", t: "سه‌ماههٔ اول ۱۴۰۴" },
  { v: "q2", t: "سه‌ماههٔ دوم ۱۴۰۴" },
  { v: "q3", t: "سه‌ماههٔ سوم ۱۴۰۴" },
  { v: "q4", t: "سه‌ماههٔ چهارم ۱۴۰۴" },
];
const QUARTER_OPTS: { v: string; t: string }[] = [
  { v: "1403Q4", t: "اسفند ۱۴۰۳ (مبنا)" },
  { v: "1404Q1", t: "سه‌ماههٔ اول ۱۴۰۴" },
  { v: "1404Q2", t: "سه‌ماههٔ دوم ۱۴۰۴" },
  { v: "1404Q3", t: "سه‌ماههٔ سوم ۱۴۰۴" },
  { v: "1404Q4", t: "سه‌ماههٔ چهارم ۱۴۰۴" },
];
const IT_OPTS: { v: string; t: string }[] = [
  ...PERIOD_OPTS,
  { v: "1405Q1", t: "سه‌ماههٔ اول ۱۴۰۵ (موقت)" },
  { v: "1405Q2", t: "سه‌ماههٔ دوم ۱۴۰۵ (موقت)" },
  { v: "1405Q3", t: "سه‌ماههٔ سوم ۱۴۰۵ (موقت)" },
  { v: "1405Q4", t: "سه‌ماههٔ چهارم ۱۴۰۵ (موقت)" },
];

/** برچسب وضعیتِ یک مقدار: قطعی / دستی / پیش‌فرض اپ */
function StatusPill({ tone, children }: { tone: "emerald" | "gold" | "rose"; children: ReactNode }) {
  const cls = {
    emerald: "bg-emerald/12 text-emerald border-emerald/25",
    gold: "bg-gold/12 text-gold border-gold/25",
    rose: "bg-rose/12 text-rose border-rose/25",
  }[tone];
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-bold leading-4", cls)}>
      {children}
    </span>
  );
}

/** فیلد عددیِ اختیاری با برچسب وضعیت (null = خالی) */
function OptNumField({
  label,
  value,
  onChange,
  step = 0.01,
  min,
  status,
  hint,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  step?: number;
  min?: number;
  status: ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <label className="text-[12.5px] font-bold text-ink/90">{label}</label>
        {status}
      </div>
      <input
        type="number"
        step={step}
        {...(min !== undefined ? { min } : {})}
        value={value ?? ""}
        onChange={(e) => (e.target.value === "" ? onChange(null) : onChange(parseFloat(e.target.value)))}
        className="bg-panel-2 border border-line rounded-lg px-3 py-2 text-[13px] num w-full outline-none focus:border-gold/50"
        placeholder="خالی → موتورها متوقف می‌شوند"
      />
      {hint && <p className="text-[10.5px] text-ink-dim mt-1.5 leading-4">{hint}</p>}
    </div>
  );
}

/** بخش یک موتور (مرز بصری واضح بین دو موتور) */
function EnginePanel({
  index,
  title,
  formula,
  enabled,
  onToggle,
  children,
}: {
  index: string;
  title: string;
  formula: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className={cn("rounded-2xl border p-4 transition-colors", enabled ? "border-gold/30 bg-gold/[0.04]" : "border-line/70 bg-white/[0.02]")}>
      <div className="flex items-center justify-between gap-3 mb-3.5 flex-wrap">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-lg bg-gold/15 text-gold grid place-items-center text-[11px] font-extrabold num shrink-0">{index}</span>
          <div>
            <h4 className="font-bold text-ink text-[13.5px]">{title}</h4>
            <code className="text-[10.5px] text-ink-dim num block" dir="ltr">{formula}</code>
          </div>
        </div>
        <div className="flex rounded-lg overflow-hidden border border-line shrink-0">
          {[
            { v: false, t: "خاموش" },
            { v: true, t: "روشن" },
          ].map((o) => (
            <button
              key={String(o.v)}
              type="button"
              onClick={() => onToggle(o.v)}
              className={cn(
                "px-3.5 py-1.5 text-[11.5px] font-bold transition-colors",
                enabled === o.v ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
              )}
            >
              {o.t}
            </button>
          ))}
        </div>
      </div>
      {enabled && children}
    </div>
  );
}

/** ویرایشگر تمدیدهای مدت پیمان (بخشنامهٔ ۲۰۸۰، بند ۲-۵) */
function ContractExtensionsEditor({
  settings,
  patch,
}: {
  settings: ProjectSettings;
  patch: <K extends keyof ProjectSettings>(key: K, value: ProjectSettings[K]) => void;
}) {
  const exts = settings.contractExtensions;
  const upd = (i: number, partial: Partial<ProjectSettings['contractExtensions'][number]>) => {
    const next = exts.map((e, j) => (j === i ? { ...e, ...partial } : e));
    patch('contractExtensions', next);
  };
  const del = (i: number) => patch('contractExtensions', exts.filter((_, j) => j !== i));
  return (
    <div className="mt-3">
      <div className="flex items-center gap-2.5 mb-2 flex-wrap">
        <span className="text-[11.5px] text-ink-dim">تمدیدهای مدت پیمان (بند ۲-۵)</span>
        <button
          type="button"
          onClick={() =>
            patch('contractExtensions', [...exts, { date: '', months: 1, kind: 'تعیین‌نشده', docNo: '' }])
          }
          className="px-2.5 py-1 rounded-md border border-line text-[11px] font-bold text-ink-dim hover:text-ink hover:border-gold/40 transition-colors"
        >
          + افزودن تمدید
        </button>
      </div>
      {exts.map((e, i) => (
        <div key={i} className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-2 items-center">
          <JalaliInput value={e.date} onChange={(v) => upd(i, { date: v })} />
          <input
            type="number"
            min={1}
            max={60}
            value={e.months}
            onChange={(ev) => upd(i, { months: Number(ev.target.value) || 1 })}
            className={cn(inputCls, 'w-full')}
            aria-label="مدت تمدید (ماه)"
          />
          <select
            value={e.kind}
            onChange={(ev) => upd(i, { kind: ev.target.value as ProjectSettings['contractExtensions'][number]['kind'] })}
            className={cn(inputCls, 'w-full appearance-none cursor-pointer')}
            aria-label="نوع تأخیر"
          >
            <option value="مجاز">مجاز</option>
            <option value="غیرمجاز">غیرمجاز</option>
            <option value="تعیین‌نشده">تعیین‌نشده</option>
          </select>
          <input
            value={e.docNo}
            onChange={(ev) => upd(i, { docNo: ev.target.value })}
            className={cn(inputCls, 'w-full')}
            placeholder="شماره سند"
            aria-label="شماره سند تمدید"
          />
          <button
            type="button"
            onClick={() => del(i)}
            className="px-2 py-1 rounded-md border border-line text-[11px] font-bold text-rose/80 hover:bg-rose/10 transition-colors"
          >
            حذف
          </button>
        </div>
      ))}
      {exts.length === 0 && (
        <span className="text-[10.5px] text-ink-dim">تمدی ثبت نشده است.</span>
      )}
    </div>
  );
}

export function PhaseBCard({
  settings,
  patch,
}: {
  settings: ProjectSettings;
  patch: <K extends keyof ProjectSettings>(key: K, value: ProjectSettings[K]) => void;
}) {
  return (
    <Card>
      <CardHeader
        icon={<TrendingUp size={20} />}
        title="موتورهای تعدیل فاز B"
        sub="دو موتور کاملاً مستقل: «تعدیل پیمان» و «برآورد به‌هنگام» — هرگز با هم ادغام نمی‌شوند، ولی می‌توانند همزمان فعال شوند. این موتورها روی زنجیرهٔ مالی اصلی بی‌اثرند."
      />

      {/* ── مقادیر مشترک ── */}
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mb-5">
        <Field label="تاریخ تسلیم پیشنهاد پیمانکار (شمسی)">
          <JalaliInput value={settings.proposalDate} onChange={(v) => patch("proposalDate", v)} />
          <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
            <b className="text-gold/90">الزامی برای موتور تعدیل پیمان</b> — Io = سه‌ماههٔ مهلت
            تسلیم (یا همین تاریخ در ترک تشریفات) — پیوست ۳، بند ۱-۲. خالی یا نامعتبر ⇒
            موتور ۱ با خطا متوقف می‌شود. موتور برآورد به این تاریخ نیاز ندارد (پیش‌فرض:
            اسفند ۱۴۰۳).
          </span>
        </Field>
        <Field label="مهلت تسلیم پیشنهاد (شمسی) — در ترک تشریفات خالی">
          <JalaliInput value={settings.proposalDeadline} onChange={(v) => patch("proposalDeadline", v)} />
          <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
            اگر مهلت تسلیم در <b className="text-gold/90">تابستان ۱۴۰۵</b> باشد، Io شاخص
            ماهانهٔ خرداد ۱۴۰۵ است (بخشنامهٔ ۱۴۴۳۷۴). تا این شاخص وارد نشده، موتورها
            با خطا متوقف می‌شوند.
          </span>
        </Field>
        <OptNumField
          label="ضریب پیشنهادی پیمانکار"
          value={settings.proposalCoef}
          onChange={(v) => patch("proposalCoef", v ?? 1)}
          status={<StatusPill tone="gold">دستی — نیازمند تأیید</StatusPill>}
          hint="در مبلغ پایهٔ A ضرب می‌شود (مبلغ کارکرد به قیمت پیمان). منبع: پروندهٔ قرارداد / مدیریت پیمان."
        />
        <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4">
          <div className="flex items-center justify-between gap-2 mb-2">
            <label className="text-[12.5px] font-bold text-ink/90">مبنای مبلغ پایه (A)</label>
            <StatusPill tone="gold">انتخاب کاربر</StatusPill>
          </div>
          <div className="flex rounded-lg overflow-hidden border border-line">
            {(["با ضرایب", "بدون ضرایب"] as const).map((o) => (
              <button
                key={o}
                type="button"
                onClick={() => patch("aBasis", o)}
                className={cn(
                  "flex-1 py-2 text-[11.5px] font-bold transition-colors",
                  settings.aBasis === o ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                )}
              >
                {o}
              </button>
            ))}
          </div>
          <p className="text-[10.5px] text-ink-dim mt-1.5 leading-4">
            «با ضرایب» = مبلغ کارکرد به قیمت پیمان (درخواست کاربر). «بدون ضرایب» = قیمت فهرست‌بها؛
            آن‌گاه ضرایب پس از It/Io اعمال می‌شوند.
          </p>
        </div>
        <OptNumField
          label="ضریب شاخص موقت سه‌ماههٔ اول ۱۴۰۵"
          value={settings.provisionalCoef1405q1}
          onChange={(v) => patch("provisionalCoef1405q1", v)}
          status={<StatusPill tone="rose">دستی — منبع تصویری</StatusPill>}
          hint="شاخص موقت ۱۴۰۵Q1 = این ضریب × آخرین شاخص قطعی (۱۴۰۴Q4). منبع: بخشنامهٔ ۱۴۴۳۷۳ (PDF تصویری — متن استخراج نشد). خالی ⇒ هر دو موتور در صورت رسیدن کارکرد به ۱۴۰۵Q1 متوقف می‌شوند."
        />
        <div className="grid grid-cols-2 gap-3">
          <Field label="شروع دورهٔ انجام کار">
            <JalaliInput value={settings.workPeriodStart} onChange={(v) => patch("workPeriodStart", v)} />
          </Field>
          <Field label="پایان دورهٔ انجام کار">
            <JalaliInput value={settings.workPeriodEnd} onChange={(v) => patch("workPeriodEnd", v)} />
          </Field>
        </div>
      </div>

      {/* ── فاز E-6 Part C: ورودی‌های قرارداد (بخشنامهٔ ۲۰۸۰) ── */}
      <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4 mb-5">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <h4 className="font-bold text-ink text-[13px]">ورودی‌های قرارداد</h4>
          <span className="text-[10.5px] text-ink-dim">— بخشنامهٔ ۱-۹۷۰۶/۵۴/۲۰۸۰ (۱۳۷۰/۰۶/۲۳)</span>
        </div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          <SelectFieldStr
            label="روش شاخص مبنا (Io)"
            value={settings.baseIndexMethod}
            options={[
              { v: 'proposal_period', t: 'دورهٔ تسلیم پیشنهاد (بند ۱-۶-۱ دوم)' },
              { v: 'fehrest_period', t: 'دورهٔ تهیهٔ فهرست‌بها (بند ۱-۶-۱ یکم)' },
              { v: 'no_base_list', t: 'پیمان بدون فهرست‌بها (بند ۱-۶-۲)' },
            ]}
            onChange={(v) => patch('baseIndexMethod', v as ProjectSettings['baseIndexMethod'])}
            hint="روش اول: Io از دورهٔ قیمت پایهٔ فهرست‌بها (در config نیازمند ورود). روش دوم: از تاریخ‌های تسلیم پیشنهاد."
          />
          <Field label="تاریخ تسلیم کتبیِ پیشنهاد نهایی — ترک تشریفات">
            <JalaliInput value={settings.finalOfferDate} onChange={(v) => patch('finalOfferDate', v)} />
            <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">
              در ترک تشریفاتِ مناقصه ملاکِ Io این تاریخ است (بند ۱-۶-۱ دوم). خالی ⇒ مهلت
              تسلیم، و اگر آن هم نبود تاریخ تسلیم پیشنهاد.
            </span>
          </Field>
          <SelectFieldStr
            label="وضعیت خاتمهٔ پیمان"
            value={settings.contractStatus}
            options={[
              { v: 'فعال', t: 'فعال' },
              { v: 'خاتمه بدون قصور', t: 'خاتمه بدون قصور (بند ۶)' },
              { v: 'فسخ با قصور', t: 'فسخ با قصور — ۵٪ کسر (بند ۷)' },
            ]}
            onChange={(v) => patch('contractStatus', v as ProjectSettings['contractStatus'])}
          />
          {settings.contractStatus === 'فسخ با قصور' && (
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4 flex items-center gap-2.5">
              <input
                type="checkbox"
                checked={settings.faultDeductionOnNegative}
                onChange={(e) => patch('faultDeductionOnNegative', e.target.checked)}
                className="accent-emerald w-4 h-4"
                id="fault-deduction-on-negative"
              />
              <label htmlFor="fault-deduction-on-negative" className="text-[12px] text-ink-dim cursor-pointer">
                کسر ۵٪ حتی در صورت تعدیلِ منفی (بند ۷ — تفسیر، منتظر تأیید کاربر)
              </label>
            </div>
          )}
          <OptNumField
            label="مبلغ اولیهٔ پیمان (ریال)"
            value={settings.contractInitialAmount}
            onChange={(v) => patch('contractInitialAmount', v)}
            step={1_000_000_000}
            min={0}
            status={<StatusPill tone="gold">ورودی کاربر</StatusPill>}
            hint="ملاک مسیر رشته‌ای/گروهی (بندهای ۲-۱/۲-۲) و سقف ۱۰٪ (نامه، بند ۶)."
          />
          <SelectFieldStr
            label="مسیر شاخص تعدیل"
            value={settings.indexMethod}
            options={[
              { v: 'گروهی', t: 'گروهی (بند ۲-۲)' },
              { v: 'رشته‌ای', t: 'رشته‌ای (بند ۲-۱)' },
              { v: 'خودکار', t: 'خودکار از روی مبلغ اولیه' },
            ]}
            onChange={(v) => patch('indexMethod', v as ProjectSettings['indexMethod'])}
            hint="خودکار: مبلغ اولیه کمتر از آستانه ⇒ رشته‌ای (۲-۱)؛ آستانه و بیشتر ⇒ گروهی (۲-۲). آستانه از config/index_bulletins.json (bulletin_2080.threshold_rail) خوانده می‌شود."
          />
          <OptNumField
            label="مدت اولیهٔ پیمان (ماه)"
            value={settings.contractDurationMonths}
            onChange={(v) => patch('contractDurationMonths', v)}
            step={1}
            min={0}
            status={<StatusPill tone="gold">ورودی کاربر</StatusPill>}
            hint="بند ۲-۵ — ملاک طبقه‌بندی تأخیرهای مجاز/غیرمجاز/تعیین‌نشده."
          />
          <Field label="تاریخ آخرین صورت‌وضعیت موقت (بند ۲-۶)">
            <JalaliInput value={settings.lastProvisionalDate} onChange={(v) => patch('lastProvisionalDate', v)} />
          </Field>
          <SelectFieldStr
            label="روش شاخصِ مابه‌التفاوتِ موقت و قطعی (بند ۲-۶)"
            value={settings.provisionalDiffMethod}
            options={[
              { v: 'average', t: 'میانگین شاخص‌ها (متنِ بند)' },
              { v: 'own_period', t: 'شاخصِ هر سه‌ماهه (تبصرهٔ ۱)' },
            ]}
            onChange={(v) => patch('provisionalDiffMethod', v as ProjectSettings['provisionalDiffMethod'])}
            hint="متنِ اصلیِ بند: میانگین شاخص‌های سه‌ماهه‌های بین شروع پیمان و آخرین موقت. تبصرهٔ ۱: اگر دورهٔ انجام قابل تشخیص است، شاخص همان دوره."
          />
        </div>
          <SelectFieldStr
            label="روش قیمتِ کار جدید (بندهای ۳-۱..۳-۵)"
            value={settings.newItemMethod ?? "فهرست پیمان"}
            options={[
              { v: 'فهرست پیمان', t: 'فهرست پیمان (۳-۱)' },
              { v: 'فهرست پایه', t: 'فهرست پایه (۳-۲)' },
              { v: 'قیمت روز', t: 'قیمت روز (۳-۳)' },
              { v: 'ترکیب', t: 'ترکیب (۳-۴)' },
            ]}
            onChange={(v) => patch('newItemMethod', v)}
            hint="۳-۱: شاخص مبنا همان مبنای پیمان؛ ۳-۲/۳-۳: شاخص دورهٔ آن قیمت‌ها؛ ۳-۴: هر بخش طبق روشِ خودش. ۳-۵: قیمت بر ۰٫۹۵ تقسیم و در ضریبِ Io پیمان ÷ Io کار جدید ضرب می‌شود."
          />
          <OptNumField
            label="مبلغ کار جدید (ریال)"
            value={settings.newItemAmount ?? null}
            onChange={(v) => patch('newItemAmount', v ?? 0)}
            step={1_000_000_000}
            min={0}
            status={<StatusPill tone="gold">ورودی کاربر</StatusPill>}
          />
          {settings.newItemMethod === 'ترکیب' && (
            <OptNumField
              label="مبلغ بخشِ ۳-۱ در ترکیب (ریال)"
              value={settings.newItemAmountAttached ?? null}
              onChange={(v) => patch('newItemAmountAttached', v ?? 0)}
              step={1_000_000_000}
              min={0}
              status={<StatusPill tone="gold">ورودی کاربر</StatusPill>}
            />
          )}
          {settings.newItemMethod && settings.newItemMethod !== 'فهرست پیمان' && (
            <SelectFieldStr
              label="دورهٔ شاخص مبنای کار جدید (سه‌ماهه)"
              value={settings.newItemBasePeriod ?? ""}
              options={QUARTER_OPTS}
              onChange={(v) => patch('newItemBasePeriod', v)}
              hint="شاخصِ مبنا برای ۳-۲/۳-۳ (و بخشِ ۳-۲ در ترکیب) — از شاخصِ رشتهٔ پروژه خوانده می‌شود."
            />
          )}
        <ContractExtensionsEditor settings={settings} patch={patch} />
      </div>
      {/* ── مرز بصری بین دو موتور ── */}
      <div className="space-y-4">
        <EnginePanel
          index="۱"
          title="موتور تعدیل پیمان"
          formula="ΔP = k × Σ_c (It_c/Io_c − 1) × A_c"
          enabled={settings.tadilEnabled}
          onToggle={(v) => patch("tadilEnabled", v)}
        >
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3.5">
            <OptNumField
              label="ضریب قانونی تعدیل (k)"
              value={settings.tadilCoef}
              onChange={(v) => patch("tadilCoef", v ?? 0.95)}
              min={0}
              status={<StatusPill tone="rose">پیش‌فرض اپ — منبع تصویری</StatusPill>}
              hint="k = ۰٫۹۵ از بخشنامهٔ ۲۰۸۰ (فقط PDF تصویری موجود است). تا تأیید کاربر، خروجی موتور «پیش‌نویس» است."
            />
            <SelectFieldStr
              label="دورهٔ مبنا (Io)"
              value={settings.tadilIoPeriod}
              options={PERIOD_OPTS}
              onChange={(v) => patch("tadilIoPeriod", v)}
              hint="اگر تاریخ تسلیم پر شده باشد، Io از آن تاریخ گرفته می‌شود (این گزینه نادیده گرفته می‌شود)."
            />
            <SelectFieldStr
              label="دورهٔ هدف (It)"
              value={settings.tadilItPeriod}
              options={PERIOD_OPTS}
              onChange={(v) => patch("tadilItPeriod", v)}
            />
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4">
              <label className="text-[11.5px] text-ink-dim block mb-1.5">کسر پیش‌پرداخت</label>
              <div className="flex rounded-lg overflow-hidden border border-line">
                {(["کل مبلغ کارکرد", "کسر پیش‌پرداخت"] as const).map((o) => (
                  <button
                    key={o}
                    type="button"
                    onClick={() => patch("tadilAdvanceMode", o)}
                    className={cn(
                      "flex-1 py-2 text-[11px] font-bold transition-colors",
                      settings.tadilAdvanceMode === o ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                    )}
                  >
                    {o}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-ink-dim block mt-1.5 leading-4">فقط روی موتور ۱ اثر دارد.</p>
            </div>
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4">
              <label className="text-[11.5px] text-ink-dim block mb-1.5">دورهٔ تأخیر</label>
              <div className="flex rounded-lg overflow-hidden border border-line">
                {(["مشمول کل دوره", "مستثنی کردن دورهٔ تأخیر"] as const).map((o) => (
                  <button
                    key={o}
                    type="button"
                    onClick={() => patch("tadilDelayMode", o)}
                    className={cn(
                      "flex-1 py-2 text-[11px] font-bold transition-colors",
                      settings.tadilDelayMode === o ? "bg-gold/20 text-gold" : "bg-panel-2 text-ink-dim hover:text-ink",
                    )}
                  >
                    {o}
                  </button>
                ))}
              </div>
              {settings.tadilDelayMode === "مستثنی کردن دورهٔ تأخیر" && (
                <div className="mt-2.5">
                  <JalaliInput value={settings.tadilDelayDate} onChange={(v) => patch("tadilDelayDate", v)} placeholder="تاریخ تحویل قرارداد" />
                </div>
              )}
            </div>
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4 flex flex-col gap-2.5">
              <label className="text-[12.5px] font-bold text-ink/90">سایر تنظیمات</label>
              <label className="flex items-center gap-2.5 text-[12px] text-ink-dim cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.tadilAllowNegative}
                  onChange={(e) => patch("tadilAllowNegative", e.target.checked)}
                  className="accent-gold w-4 h-4"
                />
                اجازهٔ تعدیل منفی
              </label>
              <label className="flex items-center gap-2.5 text-[12px] text-ink-dim cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.tadilApproved}
                  onChange={(e) => patch("tadilApproved", e.target.checked)}
                  className="accent-emerald w-4 h-4"
                />
                تأیید خروجی (تا تأیید، «پیش‌نویس» است)
              </label>
            </div>
          </div>
        </EnginePanel>

        <EnginePanel
          index="۲"
          title="موتور برآورد به‌هنگام"
          formula="A_new = Σ_c A_c × It_c/Io_c"
          enabled={settings.baravordEnabled}
          onToggle={(v) => patch("baravordEnabled", v)}
        >
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3.5">
            <SelectFieldStr
              label="دورهٔ مبنا (Io)"
              value={settings.baravordIoPeriod}
              options={PERIOD_OPTS}
              onChange={(v) => patch("baravordIoPeriod", v)}
            />
            <SelectFieldStr
              label="دورهٔ هدف (It)"
              value={settings.baravordItPeriod}
              options={IT_OPTS}
              onChange={(v) => patch("baravordItPeriod", v)}
              hint="گزینهٔ «سه‌ماههٔ اول ۱۴۰۵ (موقت)» فقط با ضریب موقت (بالا) کار می‌کند."
            />
            <div className="rounded-xl bg-white/[0.03] border border-line/70 p-4 flex items-center gap-2.5">
              <input
                type="checkbox"
                checked={settings.baravordApproved}
                onChange={(e) => patch("baravordApproved", e.target.checked)}
                className="accent-emerald w-4 h-4"
                id="baravord-approved"
              />
              <label htmlFor="baravord-approved" className="text-[12px] text-ink-dim cursor-pointer">
                تأیید خروجی (تا تأیید، «پیش‌نویس» است)
              </label>
            </div>
          </div>
        </EnginePanel>
      </div>

      {/* ── بنر مقادیر منتظر تأیید ── */}
      <div className="mt-5 rounded-xl border border-gold/25 bg-gold/[0.05] p-3.5 flex items-start gap-3">
        <Lock size={15} className="text-gold shrink-0 mt-0.5" />
        <p className="text-[11px] text-ink-dim leading-5">
          مقادیر دارای برچسب <b className="text-gold">«پیش‌فرض اپ»</b> یا <b className="text-gold">«دستی»</b> تا تأیید شما
          «پیش‌نویس» محسوب می‌شوند. خروجی موتورها در رجیستری «مقادیر منتظر تأیید» (در گزارش‌ها و شیت Excel جداگانه)
          با منبع، شماره صفحه و وضعیت هر مقدار ثبت می‌شود. هیچ عددی حدس زده نمی‌شود؛ منابع تصویری (بخشنامه‌های
          ۲۰۸۰ و ۱۴۴۳۷۳) باید به‌صورت دستی وارد و تأیید شوند.
        </p>
      </div>
    </Card>
  );
}

// ── فیلد dropdown رشته‌ای ──
function SelectFieldStr({
  label,
  value,
  options,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  options: { v: string; t: string }[];
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11.5px] text-ink-dim block mb-1.5">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(inputCls, "w-full appearance-none cursor-pointer")}
      >
        {options.map((o) => (
          <option key={o.v} value={o.v}>
            {o.t}
          </option>
        ))}
      </select>
      {hint && <span className="text-[10px] text-ink-dim block mt-1.5 leading-4">{hint}</span>}
    </label>
  );
}

