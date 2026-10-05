import { motion } from "framer-motion";
import {
  ArrowLeft,
  BookOpenCheck,
  Bot,
  Boxes,
  FileSpreadsheet,
  FlaskConical,
  Gauge,
  GitBranch,
  HardHat,
  Landmark,
  ScanSearch,
  Workflow,
} from "lucide-react";
import { Badge, BigMoney, Card, Stat, fadeUp } from "./ui";
import type { ProjectResult, Step } from "../lib/types";
import { DEMO_PROJECT_META } from "../data/demo";
import { fmtNum } from "../lib/normalize";

const FLOW = [
  { icon: FileSpreadsheet, title: "خوانش خروجی Revit", desc: "تجزیهٔ CSV/TXT جداول Schedule و خروجی Mapping داینامو — تشخیص خودکار عنوان، سرستون و واحدها", tone: "sky" },
  { icon: ScanSearch, title: "طبقه‌بندی هوشمند", desc: "تشخیص نوع جدول (بتن، قالب، آرماتور، تیرچه) با امضای ستونی + کلیدواژه‌های فارسی/انگلیسی", tone: "teal" },
  { icon: GitBranch, title: "قوانین دفتر فنی", desc: "تجمیع به سبک مترورها: تفکیک ستون/تیر/دال/پله، استنتاج حجم پی از ابعاد قالب، سینی‌بندی آرماتور بر اساس قطر", tone: "violet" },
  { icon: Bot, title: "تطبیق فازی فهرست‌بها", desc: "جست‌وجوی شباهت فارسی + کد دقیق ردیف، با درجهٔ اطمینان و پیشنهاد نامزدهای جایگزین", tone: "gold" },
  { icon: Landmark, title: "صورت‌وضعیت و آنالیز", desc: "خلاصه‌متره، ریزمترهٔ ردیابی‌پذیر، لیستوفر آرماتور، ضرایب قرارداد و خروجی Excel/PDF", tone: "emerald" },
];

export function HomeStep({
  onStep,
  onLoadDemo,
  result,
  fehrestCount,
  tablesCount,
  demoLoaded,
}: {
  onStep: (s: Step) => void;
  onLoadDemo: () => void;
  result: ProjectResult | null;
  fehrestCount: number;
  tablesCount: number;
  demoLoaded: boolean;
}) {
  return (
    <div className="space-y-8">
      {/* هیرو */}
      <motion.div {...fadeUp} className="relative overflow-hidden rounded-3xl glass p-8 lg:p-12">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-gold/[0.07] blur-3xl" />
        <div className="absolute -bottom-32 -right-16 w-80 h-80 rounded-full bg-sky/[0.06] blur-3xl" />
        <div className="relative">
          <Badge tone="gold" className="mb-5">
            <HardHat size={12} />
            سامانهٔ دفتر فنی خودکار — رشتهٔ ابنیه · فهرست‌بهای ۱۴۰۴
          </Badge>
          <h2 className="text-3xl lg:text-[42px] font-black text-ink leading-[1.35] max-w-3xl">
            از خروجی Revit تا
            <span className="text-transparent bg-clip-text bg-gradient-to-l from-gold to-gold-2"> صورت‌وضعیت رسمی </span>
            با یک کلیک
          </h2>
          <p className="text-ink-dim text-[14.5px] leading-8 mt-4 max-w-2xl">
            جداول Schedule و خروجی Mapping پروژهٔ ساختمانی‌تان را رها کنید؛ سامانه کمیت‌ها را استخراج،
            با فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴ تطبیق و خلاصه‌متره، ریزمتره، لیستوفر آرماتور و خلاصهٔ مالی را
            در چند ثانیه تولید می‌کند — بدون سرور، بدون ارسال داده، کاملاً روی مرورگر شما.
          </p>
          <div className="flex items-center gap-3 mt-7 flex-wrap">
            <button
              onClick={() => onStep("upload")}
              className="group flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-gold text-[#1a1410] font-extrabold text-[14px] hover:bg-gold-2 transition-all shadow-[0_14px_40px_-12px_rgba(242,179,61,0.7)]"
            >
              شروع پروژهٔ جدید
              <ArrowLeft size={17} className="group-hover:-translate-x-1 transition-transform" />
            </button>
            <button
              onClick={onLoadDemo}
              className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-white/[0.05] border border-line text-ink font-bold text-[14px] hover:bg-white/[0.09] hover:border-gold/40 transition-all"
            >
              <FlaskConical size={17} className="text-gold" />
              {demoLoaded ? "بارگذاری دوبارهٔ دادهٔ نمونه" : "آزمایش با پروژهٔ نمونه (دمو)"}
            </button>
          </div>
          <p className="text-[11px] text-ink-dim mt-3.5 flex items-center gap-1.5">
            <Gauge size={12} />
            {DEMO_PROJECT_META.name} — {DEMO_PROJECT_META.note}
          </p>
        </div>
      </motion.div>

      {/* شاخص‌های وضعیت */}
      <motion.div {...fadeUp} transition={{ delay: 0.08 }} className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Stat label="جداول Revit بارگذاری‌شده" value={fmtNum(tablesCount, 0)} icon={<FileSpreadsheet size={18} />} tone="sky" hint="خروجی Schedule و Mapping" />
        <Stat label="ردیف‌های پایگاه فهرست‌بها" value={fmtNum(fehrestCount, 0)} icon={<BookOpenCheck size={18} />} tone="teal" hint="ابنیه ۱۴۰۴ به‌همراه ردیف‌های کاربر" />
        <Stat label="ردیف‌های صورت‌وضعیت" value={fmtNum(result?.lines.length ?? 0, 0)} icon={<Boxes size={18} />} tone="violet" hint="تولیدشده به‌صورت خودکار" />
        <div className="glass-soft rounded-2xl p-4">
          <div className="text-[11.5px] text-ink-dim mb-1.5">مبلغ نهایی فعلی</div>
          {result ? <BigMoney rial={result.grandTotal} /> : <div className="text-ink-dim text-[13px] mt-2">— در انتظار پردازش</div>}
        </div>
      </motion.div>

      {/* خط لولهٔ پردازش */}
      <motion.div {...fadeUp} transition={{ delay: 0.14 }}>
        <div className="flex items-center gap-3 mb-4">
          <Workflow size={18} className="text-gold" />
          <h3 className="font-extrabold text-ink text-[17px]">خط لولهٔ پردازش خودکار</h3>
        </div>
        <div className="grid md:grid-cols-2 xl:grid-cols-5 gap-3">
          {FLOW.map((f, i) => {
            const Icon = f.icon;
            return (
              <Card key={i} className="p-5 group hover:border-gold/25 transition-colors">
                <div className={`w-10 h-10 rounded-xl grid place-items-center mb-3.5 bg-${f.tone}/15 text-${f.tone}`}>
                  <Icon size={19} />
                </div>
                <div className="text-[10px] text-ink-dim num mb-1">مرحلهٔ {fmtNum(i + 1, 0)}</div>
                <h4 className="font-bold text-ink text-[13.5px] leading-6">{f.title}</h4>
                <p className="text-ink-dim text-[11.5px] leading-5 mt-2">{f.desc}</p>
              </Card>
            );
          })}
        </div>
      </motion.div>

      {/* پوشش فصول */}
      <motion.div {...fadeUp} transition={{ delay: 0.2 }}>
        <Card>
          <h3 className="font-extrabold text-ink text-[15px] mb-4">فصل‌های فهرست‌بهای ابنیه تحت پوشش تطبیق خودکار</h3>
          <div className="flex flex-wrap gap-2">
            {[
              "۰۵ قالب‌بندی غیرفولادی", "۰۶ قالب‌بندی فولادی", "۰۷ کارهای فولادی با میلگرد", "۰۸ بتن درجا",
              "۱۰ سقف تیرچه و بلوک", "۱۱ آجرکاری و شفته‌ریزی", "۱۲ بلوک‌چینی", "۲۸ حمل و نقل",
              "۰۱ عملیات تخریب (رسمی)", "۰۳ عملیات خاکی با ماشین (رسمی)",
            ].map((c, i) => (
              <span key={i} className="text-[11.5px] bg-white/[0.045] border border-line/70 rounded-lg px-3 py-1.5 text-ink/85">{c}</span>
            ))}
            <span className="text-[11.5px] bg-gold/10 border border-gold/25 rounded-lg px-3 py-1.5 text-gold font-bold">
              + تمام فصل‌ها با بارگذاری فایل رسمی
            </span>
          </div>
        </Card>
      </motion.div>
    </div>
  );
}
