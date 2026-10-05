import { Layers } from "lucide-react";
import { Card } from "./ui";
import type {
  FloorRow,
  ProjectSettings,
  QuantityRecord,
} from "../lib/types";
import { cn } from "../utils/cn";
import { faDigits } from "../lib/normalize";
import { floorsTable } from "../lib/floors";
import { CardHeader, inputCls } from "./SettingsStep";

// ─────────────────────────────────────────────────────────────
// ویرایشگر جدول طبقات (ایراد ۳ + بند ۱: انتخاب دستیِ طبقه بودن هر تراز)
//
// هر تراز Revit یک ردیف است: نام | نوع مؤثر | مساحت مدل | مساحت دستی |
// بام/مرجع؟ | طبقه است؟. تراز فونداسیون (Foundation Top) پیش‌فرض غیرطبقه‌ای
// است؛ کاربر می‌تواند آن را به‌عنوان زیرهمکف (B1) علامت بزند.
// ─────────────────────────────────────────────────────────────

const KIND_LABEL: Record<FloorRow["kind"], string> = {
  below_base: "زیر همکف",
  ground: "همکف",
  above: "بالاتر از همکف",
  roof: "بام/مرجع (مستثنی)",
  none: "غیرطبقه‌ای (مستثنی)",
};

function checkboxCls(checked: boolean) {
  return cn(
    "w-4 h-4 accent-gold cursor-pointer",
    !checked && "opacity-60",
  );
}

export function FloorsTableCard({
  records,
  settings,
  setSettings,
}: {
  records: QuantityRecord[];
  settings: ProjectSettings;
  setSettings: (s: ProjectSettings) => void;
}) {
  if (!records.length) return null;
  const rows = floorsTable(records, settings);
  if (!rows.length) return null;

  const data = { ...settings.floorsData };
  const roof = [...(settings.floorsRoofLevels ?? [])];

  /** به‌روزرسانی یک تراز در floorsData (فقط مقادیر غیرپیش‌فرض نگه داشته می‌شوند) */
  function setLevel(name: string, area: number | null, isFloor: boolean | null) {
    const autoKind = rows.find((r) => r.name === name)?.autoKind;
    const rec: Record<string, unknown> = {};
    if (area && area > 0) rec.area = area;
    if (isFloor !== null && isFloor !== (autoKind !== "none")) rec.isFloor = isFloor;
    if (Object.keys(rec).length) data[name] = rec as never;
    else delete data[name];
    setSettings({ ...settings, floorsData: data });
  }

  function toggleRoof(name: string, checked: boolean) {
    const next = checked
      ? [...new Set([...roof, name])]
      : roof.filter((x) => x !== name);
    setSettings({ ...settings, floorsRoofLevels: next });
  }

  return (
    <Card>
      <CardHeader
        icon={<Layers size={20} />}
        title="جدول طبقات و ضریب طبقات (پیوست ۲)"
        sub="مساحت هر تراز را از نقشه‌های مصوب وارد کنید؛ ترازهای فونداسیون پیش‌فرض غیرطبقه‌ای هستند و قابل علامت‌گذاری هستند."
      />
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-[12px] border-collapse">
          <thead>
            <tr className="text-ink-dim text-[10.5px]">
              <th className="text-right font-bold py-2 px-2 whitespace-nowrap">تراز</th>
              <th className="text-right font-bold py-2 px-2 whitespace-nowrap">نوع</th>
              <th className="text-left font-bold py-2 px-2 whitespace-nowrap">مساحت مدل</th>
              <th className="text-left font-bold py-2 px-2 whitespace-nowrap">مساحت دستی (m²)</th>
              <th className="text-center font-bold py-2 px-2 whitespace-nowrap">بام/مرجع</th>
              <th className="text-center font-bold py-2 px-2 whitespace-nowrap">طبقه است</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const entry =
                data[r.name] && typeof data[r.name] === "object"
                  ? (data[r.name] as { area?: number | null; isFloor?: boolean | null })
                  : null;
              const curArea = entry?.area ?? (typeof data[r.name] === "number" ? (data[r.name] as number) : null);
              const curFloor = entry?.isFloor ?? null;
              const autoFloor = r.autoKind !== "none";
              const isFloor = curFloor !== null ? curFloor : autoFloor;
              const isRoof = r.kind === "roof";
              return (
                <tr key={r.name} className="border-t border-line/70">
                  <td className="py-2 px-2 font-bold text-ink whitespace-nowrap">{r.name}</td>
                  <td className="py-2 px-2 text-ink-dim whitespace-nowrap">{KIND_LABEL[r.kind]}</td>
                  <td className="py-2 px-2 text-left num text-ink-dim whitespace-nowrap">
                    {r.areaModel !== null ? faDigits(r.areaModel.toFixed(1)) : "—"}
                  </td>
                  <td className="py-2 px-2">
                    <input
                      type="number"
                      min={0}
                      step={0.1}
                      value={curArea ?? ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        setLevel(r.name, v === "" ? null : parseFloat(v), null);
                      }}
                      className={cn(inputCls, "num w-28 py-1.5 text-[12px]")}
                      placeholder={r.areaModel !== null ? String(r.areaModel) : "نیازمند ورود"}
                    />
                  </td>
                  <td className="py-2 px-2 text-center">
                    <input
                      type="checkbox"
                      checked={isRoof}
                      onChange={(e) => toggleRoof(r.name, e.target.checked)}
                      className={checkboxCls(isRoof)}
                      aria-label={`تراز ${r.name} بام/مرجع است`}
                    />
                  </td>
                  <td className="py-2 px-2 text-center">
                    <input
                      type="checkbox"
                      checked={isFloor}
                      disabled={isRoof}
                      onChange={(e) => setLevel(r.name, null, e.target.checked)}
                      className={checkboxCls(isFloor)}
                      aria-label={`تراز ${r.name} طبقه است`}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[10.5px] text-ink-dim mt-3 leading-5">
        صورت کسر Σ(i×Fi) + Σ(j×Bj) و مخرج ۱۰۰×S فقط شامل ترازهایی است که
        «طبقه» علامت خورده‌اند و بام/مرجع نیستند. تراز فونداسیون (مثل Foundation Top)
        پیش‌فرض در Σ نمی‌آید — اگر در پروژهٔ شما طبقهٔ واقعی است، در ستون
        «طبقه است» علامت بزنید (به‌عنوان زیرهمکف B1 حساب می‌شود).
      </p>
    </Card>
  );
}
