import { useId } from "react";
import { fmtNum } from "../lib/normalize";

// ─────────────────────────────────────────────────────────────
// نمودارهای SVG دست‌ساز: دونات (سهم فصل‌ها) و میله‌ای
// ─────────────────────────────────────────────────────────────

const PALETTE = ["#f2b33d", "#2dd4bf", "#38bdf8", "#a78bfa", "#fb7a93", "#34d399", "#f472b6", "#94a3b8"];

export function Donut({
  data,
  size = 208,
  thickness = 26,
  centerLabel,
  centerValue,
}: {
  data: { label: string; value: number; hint?: string }[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const id = useId();
  const total = data.reduce((a, d) => a + d.value, 0) || 1;
  const r = (size - thickness) / 2;
  const cx = size / 2;
  let acc = -Math.PI / 2;

  const slices = data
    .filter((d) => d.value > 0)
    .map((d, i) => {
      const ang = (d.value / total) * Math.PI * 2;
      const a0 = acc;
      acc += ang;
      const a1 = acc;
      const large = ang > Math.PI ? 1 : 0;
      const p = (a: number, rad: number) => [cx + rad * Math.cos(a), cx + rad * Math.sin(a)] as const;
      const [x0, y0] = p(a0 + 0.012, r);
      const [x1, y1] = p(a1 - 0.012, r);
      const dPath = `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
      return { dPath, color: PALETTE[i % PALETTE.length], ...d, share: d.value / total };
    });

  return (
    <div className="flex items-center gap-6 flex-wrap justify-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="drop-shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
          <circle cx={cx} cy={cx} r={r} fill="none" stroke="rgba(148,163,184,0.10)" strokeWidth={thickness} />
          {slices.map((s, i) => (
            <path
              key={`${id}-${i}`}
              d={s.dPath}
              fill="none"
              stroke={s.color}
              strokeWidth={thickness}
              strokeLinecap="round"
              style={{ transition: "all .6s cubic-bezier(.4,0,.2,1)" }}
            >
              <title>{`${s.label}: ${fmtNum(s.share * 100, 1)}٪`}</title>
            </path>
          ))}
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center pointer-events-none">
          <div>
            {centerValue && <div className="text-2xl font-extrabold text-ink num">{centerValue}</div>}
            {centerLabel && <div className="text-[11px] text-ink-dim mt-1 max-w-[110px] leading-5">{centerLabel}</div>}
          </div>
        </div>
      </div>
      <ul className="space-y-2 min-w-[220px]">
        {slices.map((s, i) => (
          <li key={`${id}-lg-${i}`} className="flex items-center gap-2.5 text-[13px]">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: s.color }} />
            <span className="text-ink/90 flex-1">{s.label}</span>
            {s.hint && <span className="text-ink-dim num text-xs">{s.hint}</span>}
            <span className="text-ink font-semibold num">{fmtNum(s.share * 100, 1)}٪</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function HBar({
  data,
  valueFmt,
  color = "#f2b33d",
  maxItems = 10,
  unit,
}: {
  data: { label: string; value: number; hint?: string }[];
  valueFmt?: (v: number) => string;
  color?: string;
  maxItems?: number;
  unit?: string;
}) {
  const items = [...data].sort((a, b) => b.value - a.value).slice(0, maxItems);
  const max = Math.max(...items.map((d) => d.value), 1);
  const fmt = valueFmt ?? ((v: number) => fmtNum(v, 1));
  return (
    <div className="space-y-3">
      {items.map((d, i) => (
        <div key={i}>
          <div className="flex justify-between text-[12px] mb-1.5">
            <span className="text-ink/90 truncate max-w-[60%]">{d.label}</span>
            <span className="text-ink font-semibold num">
              {fmt(d.value)}
              {d.hint && <span className="text-ink-dim font-normal"> {d.hint}</span>}
              {unit && <span className="text-ink-dim font-normal"> {unit}</span>}
            </span>
          </div>
          <div className="h-2 rounded-full bg-white/[0.045] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.max(2, (d.value / max) * 100)}%`,
                background: `linear-gradient(to left, ${color}, ${color}88)`,
                boxShadow: `0 0 12px ${color}44`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
