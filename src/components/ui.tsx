import { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "../utils/cn";
import { confLabel, fmtNum, fmtRial } from "../lib/normalize";

// ─────────────────────────────────────────────────────────────
// اجزای اتمی رابط کاربری (طراحی‌شده برای تم تیرهٔ دفتر فنی)
// ─────────────────────────────────────────────────────────────

export function Card({ children, className, glow }: { children: ReactNode; className?: string; glow?: boolean }) {
  return (
    <div
      className={cn(
        "glass rounded-2xl p-5 relative overflow-hidden",
        glow && "shadow-[0_0_60px_-15px_rgba(242,179,61,0.25)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ kicker, title, sub, action }: { kicker?: string; title: string; sub?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
      <div>
        {kicker && (
          <div className="text-gold text-[11px] font-bold tracking-wider mb-1.5 flex items-center gap-2">
            <span className="w-6 h-px bg-gold/60 inline-block" />
            {kicker}
          </div>
        )}
        <h2 className="text-xl font-extrabold text-ink leading-8">{title}</h2>
        {sub && <p className="text-ink-dim text-[13px] mt-1.5 leading-6">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
  tone = "gold",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  tone?: "gold" | "teal" | "sky" | "emerald" | "rose" | "violet";
}) {
  const tones: Record<string, string> = {
    gold: "from-gold/15 text-gold",
    teal: "from-teal/15 text-teal",
    sky: "from-sky/15 text-sky",
    emerald: "from-emerald/15 text-emerald",
    rose: "from-rose/15 text-rose",
    violet: "from-violet/15 text-violet",
  };
  return (
    <div className="glass-soft rounded-2xl p-4 flex items-start gap-3.5">
      {icon && (
        <div className={cn("w-10 h-10 rounded-xl bg-gradient-to-br to-transparent grid place-items-center shrink-0", tones[tone])}>
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <div className="text-[11.5px] text-ink-dim mb-1">{label}</div>
        <div className="text-lg font-extrabold text-ink num leading-6 truncate">{value}</div>
        {hint && <div className="text-[11px] text-ink-dim mt-1 leading-4">{hint}</div>}
      </div>
    </div>
  );
}

export function Badge({ children, tone = "zinc", className }: { children: ReactNode; tone?: "gold" | "teal" | "sky" | "emerald" | "rose" | "violet" | "zinc"; className?: string }) {
  const tones: Record<string, string> = {
    gold: "bg-gold/12 text-gold border-gold/25",
    teal: "bg-teal/12 text-teal border-teal/25",
    sky: "bg-sky/12 text-sky border-sky/25",
    emerald: "bg-emerald/12 text-emerald border-emerald/25",
    rose: "bg-rose/12 text-rose border-rose/25",
    violet: "bg-violet/12 text-violet border-violet/25",
    zinc: "bg-white/8 text-ink-dim border-white/10",
  };
  return (
    <span className={cn("inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-[11px] font-semibold leading-4", tones[tone], className)}>
      {children}
    </span>
  );
}

/** نمایشگر درجهٔ اطمینان تطبیق */
export function Confidence({ value, showLabel = true }: { value: number; showLabel?: boolean }) {
  const pct = Math.round(value * 100);
  const tone = value >= 0.92 ? "emerald" : value >= 0.78 ? "teal" : value >= 0.62 ? "gold" : "rose";
  return (
    <div className="flex items-center gap-2 min-w-[110px]">
      <div className="h-1.5 w-14 rounded-full bg-white/[0.07] overflow-hidden">
        <div
          className={cn("h-full rounded-full", {
            "bg-emerald": tone === "emerald",
            "bg-teal": tone === "teal",
            "bg-gold": tone === "gold",
            "bg-rose": tone === "rose",
          })}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <Badge tone={tone as never}>
          {confLabel(value)} · {fmtNum(pct, 0)}٪
        </Badge>
      )}
    </div>
  );
}

/** عدد بزرگِ ریال با تبدیل کمکی به میلیارد تومان */
export function BigMoney({ rial, className, size = "lg" }: { rial: number; className?: string; size?: "lg" | "xl" }) {
  return (
    <div className={className}>
      <div className={cn("font-extrabold text-ink num tracking-tight", size === "xl" ? "text-4xl" : "text-2xl")}>
        {fmtRial(rial)}
        <span className="text-[13px] font-medium text-ink-dim mr-2">ریال</span>
      </div>
      <div className="text-[12px] text-ink-dim mt-1">معادل {fmtNum(rial / 1e10, 2)} میلیارد تومان</div>
    </div>
  );
}

export function PulseDot({ tone = "gold" }: { tone?: "gold" | "emerald" | "rose" }) {
  const c = tone === "gold" ? "bg-gold" : tone === "emerald" ? "bg-emerald" : "bg-rose";
  return (
    <span className="relative flex h-2.5 w-2.5">
      <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-50", c)} />
      <span className={cn("relative inline-flex rounded-full h-2.5 w-2.5", c)} />
    </span>
  );
}

export const fadeUp = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const },
};

export function AnimatedNumber({ value, format }: { value: number; format?: (n: number) => string }) {
  const fmt = format ?? ((n: number) => fmtNum(n, 0));
  return (
    <motion.span
      key={value}
      initial={{ opacity: 0.4, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="num"
    >
      {fmt(value)}
    </motion.span>
  );
}
