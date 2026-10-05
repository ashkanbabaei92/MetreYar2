// ─────────────────────────────────────────────────────────────
// شاخص‌های تعدیل فهرست‌بها (کلیات فهرست‌بهای ۱۴۰۴، بند ۲۲)
//
// شاخص‌ها از فایل «indices/abnieh.json» خوانده می‌شوند. هر رکورد:
//     period  : دورهٔ شاخص (مثلاً «1403Q4»)
//     chapter : شمارهٔ فصل (دو رقم) و در صورت نیاز group (چهار رقم)
//     value   : مقدار شاخص
//     kind    : «قطعی» یا «موقت»
//     source  : شماره/تاریخ بخشنامه
// شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل است (بنابراین مقدار ذخیره‌شده
// برای رکورد موقت یک «ضریب» نسبت به آخرین شاخص قطعی قبل از آن دوره است).
//
// ضریب تعدیل هر فصل = I(دورهٔ هدف) ÷ I(دورهٔ مبنا) روی مبلغ ردیف، بر
// اساس دو رقم اول کد فهرست‌بها، قبل از ضرایب زنجیرهٔ مالی اعمال می‌شود.
//
// منطبق با app.py:IndexTable — خروجی‌ها باید bit-identical باشند.
// ─────────────────────────────────────────────────────────────
import type {
  IndexChapterRow,
  IndexRecord,
  IndexReport,
  IndexTableData,
} from "./types";
import abniehData from "../../indices/abnieh.json";

export class IndexTable {
  basePeriod: string | null;
  periods: string[];
  records: IndexRecord[];

  constructor(data: IndexTableData) {
    this.basePeriod = data.base_period ?? null;
    this.periods = data.periods ?? [];
    this.records = (data.indices ?? []) as IndexRecord[];
  }

  /** بارگذاری از فایل canonical پروژه. */
  static load(): IndexTable {
    return new IndexTable(abniehData as IndexTableData);
  }

  /** جدول خالی — هیچ شاخصی موجود نیست (تعدیل غیرفعال). */
  static empty(): IndexTable {
    return new IndexTable({ base_period: null, periods: [], indices: [] });
  }

  /** رکوردهای یک دوره/فصل — جست‌جو فقط بر اساس فصل (دو رقم) است. */
  private recordsFor(period: string, chapter: string): IndexRecord[] {
    return this.records.filter((r) => r.period === period && r.chapter === chapter);
  }

  /** مستوى شاخص یک فصل در یک دوره (شامل بازکردن شاخص موقت). */
  private level(period: string, chapter: string): number {
    const recs = this.recordsFor(period, chapter);
    if (recs.length === 0) {
      throw new Error(
        `شاخص تعدیل فصل ${chapter} در دورهٔ «${period}» یافت نشد. ` +
          `مقادیر رسمی شاخص را از بخشنامهٔ مربوطه در فایل ` +
          `«indices/abnieh.json» وارد کنید.`,
      );
    }
    const rec = recs[0];
    if (rec.kind === "موقت") {
      // شاخص موقت = ضریب × شاخص قطعی دورهٔ قبل
      const idx = this.periods.indexOf(period);
      let prevDef: string | null = null;
      for (let i = idx - 1; i >= 0; i--) {
        const pr = this.recordsFor(this.periods[i], chapter);
        if (pr.length > 0 && pr[0].kind === "قطعی") {
          prevDef = this.periods[i];
          break;
        }
      }
      if (prevDef === null) {
        throw new Error(
          `شاخص موقت فصل ${chapter} در دورهٔ «${period}» به یک شاخص ` +
            `قطعی در دورهٔ قبل نیاز دارد؛ هیچ شاخص قطعیی یافت نشد.`,
        );
      }
      return (rec.value ?? 0) * this.level(prevDef, chapter);
    }
    return rec.value ?? 0;
  }

  /** ضریب تعدیل یک ردیف فهرست‌بها (بر اساس دو رقم اول کد). */
  factor(code: string, targetPeriod: string): number {
    const chapter = code.slice(0, 2);
    const base = this.basePeriod;
    if (base === null || targetPeriod === base) return 1.0;
    const lv = this.level(targetPeriod, chapter);
    const baseLv = this.level(base, chapter);
    if (baseLv === 0) {
      throw new Error(`شاخص دورهٔ مبنا برای فصل ${chapter} صفر است.`);
    }
    return lv / baseLv;
  }

  /** گزارش شاخص هر فصل برای دورهٔ هدف: ضریب، نوع، منبع و مستوى. */
  report(targetPeriod: string): IndexReport {
    const rows: IndexChapterRow[] = [];
    const chapters = [...new Set(this.records.map((r) => r.chapter))].sort();
    for (const ch of chapters) {
      const recs = this.recordsFor(targetPeriod, ch);
      const rec = recs.length > 0 ? recs[0] : null;
      let f: number | null;
      try {
        f = this.factor(`${ch}0000`, targetPeriod);
      } catch {
        f = null;
      }
      rows.push({
        chapter: ch,
        factor: f,
        kind: rec ? rec.kind : null,
        source: rec ? rec.source : null,
        level: rec ? this.level(targetPeriod, ch) : null,
      });
    }
    const provisional = rows.some((r) => r.kind === "موقت");
    return {
      basePeriod: this.basePeriod,
      targetPeriod,
      provisional,
      chapters: rows,
    };
  }
}
