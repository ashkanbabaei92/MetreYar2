import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./components/Sidebar";
import { HomeStep } from "./components/HomeStep";
import { FehrestStep } from "./components/FehrestStep";
import { UploadStep } from "./components/UploadStep";
import { SettingsStep } from "./components/SettingsStep";
import { MatchStep } from "./components/MatchStep";
import { ManualPricesStep } from "./components/ManualPricesStep";
import { ReportsStep } from "./components/ReportsStep";
import { ExportStep } from "./components/ExportStep";
import { PrintReport } from "./components/PrintReport";
import type { FehrestRow, LoadedFile, MappingData, ProjectMeta, ProjectSettings, StatusReportRecord, Step } from "./lib/types";
import { appendAudit, computeProject, defaultSettings } from "./lib/engine";
import { validateMeta } from "./lib/adjustment";
import { OFFICIAL_1404_FEHREST } from "./data/officialFehrest";
import { DEMO_FILES, DEMO_PROJECT_META } from "./data/demo";
import { parseRevitFile } from "./lib/revitParser";
import { jalaliNowStr, todayJalali } from "./lib/farsi";
import {
  META_LABELS,
  SETTING_LABELS,
  auditSnap,
  diffAuditEntries,
} from "./lib/auditDiff";
import { copyProject, loadProjectProfileJson } from "./lib/manualEntries";

const HISTORY_KEY = "metreyar_status_history_v1";

function defaultMeta(): ProjectMeta {
  return {
    projectName: DEMO_PROJECT_META.name,
    employer: "",
    contractor: "",
    consultant: "",
    contractNo: "",
    contractDate: todayJalali(),
    location: "",
    reportNo: "۱",
    reportType: "موقت",
    periodStart: "",
    periodEnd: "",
  };
}

function loadHistory(): StatusReportRecord[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [step, setStep] = useState<Step>("home");
  const [meta, setMeta] = useState<ProjectMeta>(defaultMeta);
  const [files, setFiles] = useState<LoadedFile[]>([]);
  const [db, setDb] = useState<FehrestRow[]>(OFFICIAL_1404_FEHREST);
  const [settings, setSettings] = useState<ProjectSettings>(defaultSettings());
  const [demoLoaded, setDemoLoaded] = useState(false);
  const [history, setHistory] = useState<StatusReportRecord[]>(loadHistory);

  // ذخیره‌سازی پایدار سوابق صورت‌وضعیت در مرورگر کاربر
  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch {
      /* حافظهٔ مرورگر در دسترس نیست — بدون اخلال ادامه می‌دهیم */
    }
  }, [history]);

  // ── فاز E-۵: ثبت تغییراتِ ورودی‌های پروژه در سابقهٔ ویرایش ──
  // هر تغییرِ تنظیمات یا مشخصاتِ پیمان در رجیستریِ واحدِ سابقهٔ ویرایش
  // ثبت می‌شود (priceAudit). کلیدهای مستثنی در auditDiff.ts آمده‌اند.
  const settingsSnap = useRef(auditSnap(settings));
  useEffect(() => {
    const entries = diffAuditEntries(
      settingsSnap.current, settings, "setting", SETTING_LABELS, "تنظیمات پروژه",
    );
    settingsSnap.current = auditSnap(settings);
    if (entries.length) {
      setSettings((s) => ({
        ...s,
        priceAudit: [
          ...s.priceAudit,
          ...entries.map((e) => ({
            ...e, at: jalaliNowStr(), user: s.priceUser ?? "",
          })),
        ],
      }));
    }
  }, [settings]);

  const metaSnap = useRef(auditSnap(meta));
  useEffect(() => {
    const entries = diffAuditEntries(
      metaSnap.current, meta, "meta", META_LABELS, "مشخصات پیمان",
    );
    metaSnap.current = auditSnap(meta);
    if (entries.length) {
      setSettings((s) => ({
        ...s,
        priceAudit: [
          ...s.priceAudit,
          ...entries.map((e) => ({
            ...e, at: jalaliNowStr(), user: s.priceUser ?? "",
          })),
        ],
      }));
    }
  }, [meta]);

  // ── فاز E-۵: پروژهٔ جدید از روی این پروژه + بارگذاری پروفایل ──
  // هر دو عملیات، snapshotهای تفاضل را پیش از setState به‌روز می‌کنند تا
  // فیلدهای پاکشده به‌عنوانِ تغییر در سابقهٔ ویرایش ثبت نشوند.
  const onCopyProject = useCallback(() => {
    const next = copyProject(settings, meta);
    settingsSnap.current = auditSnap(next.settings);
    metaSnap.current = auditSnap(next.meta);
    setSettings(next.settings);
    setMeta(next.meta);
  }, [settings, meta]);

  const onLoadProfileText = useCallback((text: string): string[] => {
    const r = loadProjectProfileJson(text);
    if (!r.settings) return r.warns;
    appendAudit(
      r.settings,
      "پروفایل پروژه",
      "load",
      null,
      r.meta ? "بارگذاری پروفایل" : "بارگذاری فایل کناری قدیمی",
      "بارگذاری پروفایل",
      "meta",
    );
    settingsSnap.current = auditSnap(r.settings);
    setSettings(r.settings);
    if (r.meta) {
      metaSnap.current = auditSnap(r.meta);
      setMeta(r.meta);
    }
    return r.warns;
  }, []);

  // ── جداول و مپینگ بارگذاری‌شده ──
  const tables = useMemo(() => files.map((f) => f.table).filter((t) => !!t), [files]);

  const mergedMapping: MappingData | undefined = useMemo(() => {
    const mappingList = files.map((f) => f.mappingData).filter((m): m is MappingData => !!m);
    if (mappingList.length === 0) return undefined;
    return {
      rows: mappingList.flatMap((m) => m.rows),
      format: mappingList.every((m) => m.format === "v2") ? "v2" : "unknown",
      recordCount: mappingList.reduce((s, m) => s + m.recordCount, 0),
      warnings: mappingList.flatMap((m) => m.warnings),
    };
  }, [files]);

  // ── موتور متره — بازمحاسبهٔ زنده با هر تغییر ──
  // اعتبارسنجی تاریخ‌ها (ایراد ۱۲): شروع پیمان ≤ شروع دوره ≤ پایان دوره.
  // در صورت نقض، محاسبه متوقف می‌شود (null) و خطاها در گام تنظیمات نمایش داده می‌شوند.
  const dateErrors = useMemo(() => validateMeta(meta), [meta]);
  const result = useMemo(() => {
    if (!tables.length && !mergedMapping) return null;
    if (dateErrors.length) return null;
    try {
      // فاز E-6 Part C: تاریخ شروع پیمان از meta خوانده می‌شود و در
      // تنظیماتِ ورودیِ موتور قرار می‌گیرد (مثل app.py: s["contract_date"]).
      return computeProject(
        tables as never,
        db,
        { ...settings, contractDate: meta.contractDate },
        mergedMapping,
      );
    } catch (e) {
      console.error("خطای موتور متره:", e);
      return null;
    }
  }, [tables, db, settings, mergedMapping, dateErrors]);

  function loadDemo() {
    const loaded: LoadedFile[] = DEMO_FILES.map((d) => ({
      id: crypto.randomUUID(),
      name: d.name,
      size: d.text.length,
      text: d.text,
      table: parseRevitFile(d.name, d.text),
    }));
    setFiles(loaded);
    setDemoLoaded(true);
    setStep("upload");
  }

  const progress: Record<Step, "done" | "active" | "idle"> = useMemo(() => {
    const order: Step[] = ["home", "fehrest", "upload", "settings", "match", "manual", "reports", "export"];
    const cur = order.indexOf(step);
    const out = {} as Record<Step, "done" | "active" | "idle">;
    order.forEach((s, i) => {
      if (i < cur) out[s] = "done";
      else if (i === cur) out[s] = "active";
      else out[s] = "idle";
    });
    return out;
  }, [step]);

  return (
    <div className="min-h-screen">
      <div className="blueprint-bg app-chrome" />
      <div className="blueprint-grid app-chrome" />

      <div className="flex">
        <Sidebar
          step={step}
          onStep={setStep}
          progress={progress}
          tablesCount={tables.length}
          linesCount={result?.lines.length ?? 0}
          fehrestOk={db.length > 0}
        />

        <main className="flex-1 min-w-0 px-6 lg:px-10 py-8 app-chrome">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 22 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -14 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="max-w-6xl mx-auto"
            >
              {step === "home" && (
                <HomeStep
                  onStep={setStep}
                  onLoadDemo={loadDemo}
                  result={result}
                  fehrestCount={db.length}
                  tablesCount={tables.length}
                  demoLoaded={demoLoaded}
                />
              )}
              {step === "fehrest" && <FehrestStep db={db} setDb={setDb} onNext={() => setStep("upload")} />}
              {step === "upload" && (
                <UploadStep
                  files={files}
                  setFiles={setFiles}
                  onNext={() => setStep("settings")}
                  setDemoLoaded={setDemoLoaded}
                />
              )}
              {step === "settings" && (
                <SettingsStep
                  meta={meta}
                  setMeta={setMeta}
                  settings={settings}
                  setSettings={setSettings}
                  records={result?.records ?? []}
                  onNext={() => setStep("match")}
                />
              )}
              {step === "match" && (
                <MatchStep
                  result={result}
                  settings={settings}
                  setSettings={setSettings}
                  db={db}
                  projectName={meta.projectName}
                />
              )}
              {step === "manual" && (
                <ManualPricesStep
                  result={result}
                  settings={settings}
                  setSettings={setSettings}
                  projectName={meta.projectName}
                  meta={meta}
                  onCopyProject={onCopyProject}
                  onLoadProfileText={onLoadProfileText}
                />
              )}
              {step === "reports" && (
                <ReportsStep
                  result={result}
                  settings={settings}
                  meta={meta}
                  history={history}
                  setHistory={setHistory}
                />
              )}
              {step === "export" && (
                <ExportStep result={result} settings={settings} meta={meta} history={history} />
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* نسخهٔ چاپی صورت‌وضعیت */}
      <PrintReport result={result} settings={settings} meta={meta} history={history} />
    </div>
  );
}
