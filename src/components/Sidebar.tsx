import {
  BookOpenCheck,
  Boxes,
  Coins,
  Cpu,
  FileSpreadsheet,
  Gauge,
  LayoutDashboard,
  Ruler,
  Settings2,
  Sparkles,
} from "lucide-react";
import { cn } from "../utils/cn";
import type { Step } from "../lib/types";
import { PulseDot } from "./ui";
import { fmtNum } from "../lib/normalize";

export const STEPS: { id: Step; title: string; sub: string; icon: typeof Gauge }[] = [
  { id: "home", title: "داشبورد", sub: "نمای کلی پروژه", icon: LayoutDashboard },
  { id: "fehrest", title: "فهرست‌بهای ۱۴۰۴", sub: "پایگاه قیمت ابنیه", icon: BookOpenCheck },
  { id: "upload", title: "جداول Revit", sub: "آپلود و تشخیص خودکار", icon: FileSpreadsheet },
  { id: "settings", title: "تنظیمات و ضرایب", sub: "پرت، بالاسری، مالیات", icon: Settings2 },
  { id: "match", title: "تطبیق هوشمند", sub: "بررسی ردیف‌های فهرست‌بها", icon: Cpu },
  { id: "manual", title: "قیمت‌های دستی", sub: "ورود قیمت، ستاره‌دار، سابقه", icon: Coins },
  { id: "reports", title: "گزارش‌های دفتر فنی", sub: "متره، صورت‌وضعیت، لیستوفر", icon: Boxes },
  { id: "export", title: "خروجی نهایی", sub: "Excel و PDF", icon: Sparkles },
];

export function Sidebar({
  step,
  onStep,
  progress,
  tablesCount,
  linesCount,
  fehrestOk,
}: {
  step: Step;
  onStep: (s: Step) => void;
  progress: Record<Step, "done" | "active" | "idle">;
  tablesCount: number;
  linesCount: number;
  fehrestOk: boolean;
}) {
  return (
    <aside className="app-chrome w-[298px] shrink-0 h-screen sticky top-0 flex flex-col border-l border-line/60 bg-panel/80 backdrop-blur-xl">
      {/* برند */}
      <div className="px-6 pt-7 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-gold to-[#b97f14] grid place-items-center shadow-[0_8px_24px_-6px_rgba(242,179,61,0.55)]">
            <Ruler size={21} className="text-[#1a1410]" strokeWidth={2.4} />
          </div>
          <div>
            <h1 className="font-black text-lg text-ink leading-6">متره‌یار هوشمند</h1>
            <p className="text-[10.5px] text-ink-dim mt-0.5">دفتر فنی خودکار · BIM → فهرست‌بهای ۱۴۰۴</p>
          </div>
        </div>
      </div>

      {/* وضعیت زنده پروژه */}
      <div className="mx-4 mb-4 rounded-xl bg-white/[0.03] border border-line/60 px-4 py-3">
        <div className="flex items-center gap-2 text-[11px] text-ink-dim mb-2">
          <PulseDot tone="emerald" />
          وضعیت خط لولهٔ پردازش
        </div>
        <div className="flex items-center justify-between text-[11.5px]">
          <span className={cn("flex items-center gap-1.5", fehrestOk ? "text-emerald" : "text-ink-dim")}>
            <span className={cn("w-1.5 h-1.5 rounded-full", fehrestOk ? "bg-emerald" : "bg-white/20")} />
            فهرست‌بها
          </span>
          <span className="text-white/15">|</span>
          <span className={cn("flex items-center gap-1.5", tablesCount > 0 ? "text-emerald" : "text-ink-dim")}>
            <span className={cn("w-1.5 h-1.5 rounded-full", tablesCount > 0 ? "bg-emerald" : "bg-white/20")} />
            جداول: {fmtNum(tablesCount, 0)}
          </span>
          <span className="text-white/15">|</span>
          <span className={cn("flex items-center gap-1.5", linesCount > 0 ? "text-gold" : "text-ink-dim")}>
            <span className={cn("w-1.5 h-1.5 rounded-full", linesCount > 0 ? "bg-gold" : "bg-white/20")} />
            ردیف BOQ: {fmtNum(linesCount, 0)}
          </span>
        </div>
      </div>

      {/* گام‌ها */}
      <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-1">
        {STEPS.map((s, i) => {
          const st = progress[s.id];
          const Icon = s.icon;
          const active = step === s.id;
          return (
            <button
              key={s.id}
              onClick={() => onStep(s.id)}
              className={cn(
                "w-full text-right flex items-center gap-3.5 px-3.5 py-3 rounded-xl transition-all duration-300 group relative",
                active
                  ? "bg-gradient-to-l from-gold/[0.13] to-transparent border border-gold/25"
                  : "hover:bg-white/[0.04] border border-transparent",
              )}
            >
              <div
                className={cn(
                  "w-9 h-9 rounded-[10px] grid place-items-center shrink-0 transition-colors",
                  active
                    ? "bg-gold text-[#1a1410]"
                    : st === "done"
                      ? "bg-emerald/15 text-emerald"
                      : "bg-white/[0.05] text-ink-dim group-hover:text-ink",
                )}
              >
                <Icon size={17} strokeWidth={2.2} />
              </div>
              <div className="flex-1 min-w-0">
                <div className={cn("text-[13px] font-bold leading-5", active ? "text-gold" : "text-ink/90")}>{s.title}</div>
                <div className="text-[10.5px] text-ink-dim mt-0.5">{s.sub}</div>
              </div>
              <span
                className={cn(
                  "text-[10px] num font-bold w-5 h-5 rounded-md grid place-items-center border",
                  st === "done"
                    ? "border-emerald/30 text-emerald bg-emerald/10"
                    : "border-white/10 text-ink-dim",
                )}
              >
                {fmtNum(i + 1, 0)}
              </span>
              {active && <span className="absolute right-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-full bg-gold" />}
            </button>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-line/50">
        <p className="text-[10px] text-ink-dim leading-5">
          نسخهٔ وب ۳٫۰ · کاملاً سمت کاربر — بدون سرور، بدون ارسال داده
          <br />
          منطبق با ساختار فهرست‌بهای واحد پایهٔ ابنیه ۱۴۰۴
        </p>
      </div>
    </aside>
  );
}
