import { useMemo, useRef, useState } from "react";
import {
  BadgeCheck,
  BookOpen,
  CircleAlert,
  CircleDollarSign,
  Database,
  FileUp,
  PenLine,
  Search,
} from "lucide-react";
import { Card, SectionTitle, Badge, Stat } from "./ui";
import { CHAPTERS, parseFehrestText, chapterTitle } from "../data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../data/officialFehrest";
import type { FehrestRow } from "../lib/types";
import { cn } from "../utils/cn";
import { faDigits, fmtNum, fmtRial, normalizeText } from "../lib/normalize";
import { decodeText } from "../lib/decode";

export function FehrestStep({
  db,
  setDb,
  onNext,
}: {
  db: FehrestRow[];
  setDb: (rows: FehrestRow[]) => void;
  onNext: () => void;
}) {
  const [query, setQuery] = useState("");
  const [chapterFilter, setChapterFilter] = useState<string>("all");
  const [msg, setMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const officialCount = db.filter((r) => !r.estimated).length;
  const estimatedCount = db.filter((r) => r.estimated).length;
  // فایل رسمی پیش‌فرض (۱۴۰۴) از ابتدا فعال است؛ این نشانگر فقط فایل
  // اضافیِ بارگذاری‌شده توسط کاربر را آشکار می‌کند.
  const officialUploaded = officialCount > OFFICIAL_1404_FEHREST.filter((r) => !r.estimated).length;

  const filtered = useMemo(() => {
    const q = normalizeText(query);
    return db
      .filter((r) => (chapterFilter === "all" ? true : r.chapter === chapterFilter))
      .filter((r) => (!q ? true : normalizeText(r.desc + " " + r.code).includes(q)))
      .slice(0, 250);
  }, [db, query, chapterFilter]);

  async function handleFile(f: File) {
    try {
      const buffer = await f.arrayBuffer();
      const text = decodeText(new Uint8Array(buffer));
      const { rows, skipped } = parseFehrestText(text);
      if (!rows.length) {
        setMsg("هیچ ردیف معتبری در فایل شناسایی نشد. قالب مورد انتظار: شمارهٔ ۶ رقمی، فصل، شرح، واحد، بهای واحد — جدا شده با تب یا کاما.");
        return;
      }
      const map = new Map<string, FehrestRow>(db.map((r) => [r.code, r]));
      let replaced = 0;
      for (const r of rows) {
        if (map.has(r.code)) replaced++;
        map.set(r.code, { ...r, estimated: false });
      }
      setDb([...map.values()].sort((a, b) => a.code.localeCompare(b.code)));
      setMsg(
        `فهرست‌بها با موفقیت پذیرفته شد: ${fmtNum(rows.length, 0)} ردیف رسمی خوانده شد (${fmtNum(replaced, 0)} ردیف تخمینی جایگزین + ${fmtNum(rows.length - replaced, 0)} ردیف جدید)${skipped ? ` · ${fmtNum(skipped, 0)} سطر ناخوانا` : ""}.`,
      );
    } catch (e) {
      console.error(e);
      setMsg("خطا در خواندن فایل فهرست‌بها. رمزگذاری فایل را بررسی کنید (UTF-8).");
    }
  }

  function savePrice(code: string) {
    const v = parseFloat(editPrice.replace(/[,٬\s]/g, ""));
    if (Number.isFinite(v) && v > 0) {
      setDb(db.map((r) => (r.code === code ? { ...r, price: v, estimated: false } : r)));
    }
    setEditing(null);
  }

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="گام ۲ — پایگاه قیمت"
        title="فهرست‌بهای واحد پایهٔ رشتهٔ ابنیه ۱۴۰۴"
        sub="پایگاه تعبیه‌شده شامل فصل‌های کلیدی است. برای ارقام کاملاً رسمی، فایل متن/اکسل فهرست‌بهای سازمان برنامه (یا نسخهٔ پیوست خود) را بارگذاری کنید؛ ردیف‌های رسمی جایگزین ردیف‌های تخمینی می‌شوند."
      />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Stat label="ردیف‌های پایگاه" value={fmtNum(db.length, 0)} icon={<Database size={18} />} tone="sky" hint={`${fmtNum(CHAPTERS.length, 0)} فصل فعال`} />
        <Stat label="ردیف‌های رسمی" value={fmtNum(officialCount, 0)} icon={<BadgeCheck size={18} />} tone="emerald" hint="از فایل ۱۴۰۴ / بارگذاری کاربر" />
        <Stat label="بهای تخمینی" value={fmtNum(estimatedCount, 0)} icon={<CircleAlert size={18} />} tone={estimatedCount ? "gold" : "emerald"} hint="پیش‌فرض قابل‌ویرایش" />
        <Stat label="فایل رسمی شما" value={officialUploaded ? "بارگذاری شد" : "—"} icon={<FileUp size={18} />} tone={officialUploaded ? "emerald" : "violet"} hint={officialUploaded ? "ارقام سازمان برنامه اعمال شد" : "در انتظار فایل fehrest_1404"} />
      </div>

      {/* آپلود فایل رسمی */}
      <Card className="flex items-center justify-between gap-5 flex-wrap">
        <div className="flex items-start gap-4 min-w-0">
          <div className="w-12 h-12 rounded-2xl bg-violet/15 text-violet grid place-items-center shrink-0">
            <BookOpen size={22} />
          </div>
          <div>
            <h3 className="font-bold text-ink text-[15px]">بارگذاری فهرست‌بهای رسمی (اختیاری ولی توصیه‌شده)</h3>
            <p className="text-ink-dim text-[12.5px] mt-1.5 leading-6 max-w-2xl">
              فایل متنی/CSV فهرست‌بها با ساختار «شماره | فصل | شرح | واحد | بهای واحد» را انتخاب کنید.
              هر ردیفی که کدش با ردیف تعبیه‌شده یکی باشد با قیمت رسمی جایگزین می‌شود؛
              همچنین می‌توانید قیمت هر ردیف را مستقیماً در جدول ویرایش کنید.
            </p>
            {msg && (
              <p className={cn("text-[12px] mt-2 leading-5", msg.startsWith("فهرست‌بها با موفقیت") ? "text-emerald" : "text-rose")}>{msg}</p>
            )}
          </div>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          className="px-5 py-3 rounded-xl bg-violet/15 border border-violet/30 text-violet text-[13px] font-bold hover:bg-violet/25 transition-colors flex items-center gap-2 shrink-0"
        >
          <FileUp size={16} />
          انتخاب فایل فهرست‌بها
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".txt,.csv,.tsv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = "";
          }}
        />
      </Card>

      {/* جدول ردیف‌ها */}
      <Card>
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <div className="relative">
            <Search size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-dim" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جست‌وجو در شرح یا کد ردیف…"
              className="bg-panel-2 border border-line rounded-xl pr-9 pl-3 py-2.5 text-[13px] w-72 outline-none focus:border-gold/50 transition-colors placeholder:text-ink-dim/70"
            />
          </div>
          <select
            value={chapterFilter}
            onChange={(e) => setChapterFilter(e.target.value)}
            className="bg-panel-2 border border-line rounded-xl px-3 py-2.5 text-[12.5px] outline-none focus:border-gold/50 cursor-pointer"
          >
            <option value="all">همهٔ فصل‌ها</option>
            {CHAPTERS.filter((c) => db.some((r) => r.chapter === c.no)).map((c) => (
              <option key={c.no} value={c.no}>فصل {faDigits(c.no)} — {c.title}</option>
            ))}
          </select>
        </div>

        <div className="rounded-xl border border-line/70 overflow-hidden max-h-[430px] overflow-y-auto">
          <table className="dt">
            <thead className="sticky top-0 bg-panel-2 z-10">
              <tr>
                <th>کد ردیف</th>
                <th>شرح آیتم</th>
                <th>واحد</th>
                <th>بهای واحد (ریال)</th>
                <th>وضعیت</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.code}>
                  <td className="num text-gold font-bold text-[12.5px]">{faDigits(r.code)}</td>
                  <td>
                    <div className="text-[12.5px] leading-5 text-ink/90 max-w-xl">{r.desc}</div>
                    <div className="text-[10.5px] text-ink-dim mt-0.5">فصل {faDigits(r.chapter)} · {chapterTitle(r.chapter)}</div>
                  </td>
                  <td className="text-[12px] text-ink-dim whitespace-nowrap">{r.unit}</td>
                  <td className="whitespace-nowrap">
                    {editing === r.code ? (
                      <span className="flex items-center gap-1.5">
                        <input
                          autoFocus
                          value={editPrice}
                          onChange={(e) => setEditPrice(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && savePrice(r.code)}
                          className="bg-panel-2 border border-gold/50 rounded-lg px-2 py-1 text-[12px] num w-32 outline-none"
                        />
                        <button onClick={() => savePrice(r.code)} className="text-emerald text-[11px] font-bold">ثبت</button>
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 group">
                        <span className="num font-semibold text-ink text-[12.5px]">{fmtRial(r.price)}</span>
                        <button
                          onClick={() => { setEditing(r.code); setEditPrice(String(r.price)); }}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-ink-dim hover:text-gold"
                          title="ویرایش بهای واحد"
                        >
                          <PenLine size={13} />
                        </button>
                      </span>
                    )}
                  </td>
                  <td>
                    {r.estimated ? (
                      <Badge tone="gold"><CircleDollarSign size={11} /> تخمینی</Badge>
                    ) : (
                      <Badge tone="emerald"><BadgeCheck size={11} /> رسمی</Badge>
                    )}
                  </td>
                </tr>
              ))}
              {!filtered.length && (
                <tr><td colSpan={5} className="text-center text-ink-dim py-8 text-[13px]">موردی یافت نشد</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-ink-dim mt-3">
          نمایش {fmtNum(filtered.length, 0)} ردیف از {fmtNum(db.length, 0)} — برای دقت کامل بهای‌ها، فایل رسمی را بارگذاری یا قیمت‌ها را دستی ویرایش کنید.
        </p>
      </Card>

      <div className="flex justify-start">
        <button
          onClick={onNext}
          className="px-6 py-3 rounded-xl bg-gold text-[#1a1410] text-[13.5px] font-extrabold hover:bg-gold-2 transition-colors shadow-[0_10px_30px_-10px_rgba(242,179,61,0.6)]"
        >
          ادامه: آپلود جداول Revit
        </button>
      </div>
    </div>
  );
}
