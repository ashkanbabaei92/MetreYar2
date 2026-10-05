// ─────────────────────────────────────────────────────────────
// پروژهٔ نمونهٔ نمایشی (دمو): زیرمجموعهٔ کوچک‌شده‌ای از خروجی‌های Schedule
// نرم‌افزار Revit (ساختمان مسکونی اسکلت بتنی). این دادهٔ کامل پروژهٔ مرجع
// نیست — فایل‌های واقعی data/export revit را آپلود کنید.
// ─────────────────────────────────────────────────────────────

export interface DemoFile {
  name: string;
  text: string;
}

export const DEMO_FILES: DemoFile[] = [
  {
    name: "جدول ریزمتره بتن مگر.txt",
    text: `"جدول ریزمتره بتن مگر - Lean Concrete Schedule","",""
"Mark","Family and Type","Volume"
"","",""
"LC-01","Foundation Slab: 100mm Foundation Slab","18.65 m³"`,
  },
  {
    name: "جدول ریزمتره حجم بتن سازه‌ای.txt",
    text: `"جدول ریزمتره حجم بتن سازه‌ای - Structural Concrete Schedule","","",""
"Category","Family and Type","Material: Name","Material: Volume"
"","","",""
"Floors","Floor: Slab20","CONCRETE","13.95 m³"
"Floors","Floor: Slab_Topping_50mm","CONCRETE","2.58 m³"
"Stairs","Cast-In-Place Stair: Monolithic Stair IRAN","CONCRETE","4.21 m³"
"Stairs: Runs","Monolithic Run: 25 mm Nosing","CONCRETE","4.21 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X50-14F16","CONCRETE","11.76 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X50-14F18","CONCRETE","9.59 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X55-14F18","CONCRETE","6.50 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X55-16F18","CONCRETE","4.89 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X60-16F18","CONCRETE","1.73 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X60-18F18","CONCRETE","0.88 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X60-20F20","CONCRETE","6.35 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C45X60-24F20","CONCRETE","3.46 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C50X60-20F20","CONCRETE","2.91 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C50X60-24F20","CONCRETE","2.89 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C50X60-24F22","CONCRETE","1.79 m³"
"Structural Columns","M_Concrete-Rectangular-Column: C50X70-28F22","CONCRETE","1.30 m³"
"Structural Columns","M_Concrete-Square-Column: C40-8F16","CONCRETE","1.71 m³"
"Structural Columns","M_Concrete-Square-Column: C45-12F16","CONCRETE","10.62 m³"
"Structural Columns","M_Concrete-Square-Column: C45-12F18","CONCRETE","4.79 m³"
"Structural Framing","M_Concrete-Rectangular Beam: B40X40","CONCRETE","2.26 m³"
"Structural Framing","M_Concrete-Rectangular Beam: B45X45","CONCRETE","1.30 m³"
"Structural Framing","M_Concrete-Rectangular Beam: B45X50","CONCRETE","41.37 m³"
"Structural Framing","M_Concrete-Rectangular Beam: B45X55","CONCRETE","85.65 m³"
"Structural Framing","M_Concrete-Rectangular Beam: B50X50","CONCRETE","11.80 m³"
"Structural Framing","M_Concrete-Rectangular Beam: B50X55","CONCRETE","25.78 m³"
"Grand total: 245","","","264.25 m³"`,
  },
  {
    name: "جدول ریزمتره قالب‌بندی سازه.txt",
    text: `"جدول ریزمتره قالب‌بندی سازه - Superstructure Formwork Schedule","","",""
"Category","Family and Type","Material: Name","Material: Area"
"","","",""
"Stairs: Runs","Monolithic Run: 25 mm Nosing","CONCRETE","41 m²"
"Structural Columns"," ","CONCRETE","670 m²"
"Structural Framing"," ","CONCRETE","1472 m²"
"Grand total: 236","","","2184 m²"`,
  },
  {
    name: "جدول قالب‌بندی پی.txt",
    text: `"جدول قالب‌بندی پی - Foundation Formwork Schedule","","","",""
"Family and Type","Mark","Length","Width","Formwork Area"
"","","","",""
"Wall Foundation: WF_A_1800x900","L(1-2) L(1-2)","13471.04 mm","1800.00 mm","24.25 m²"
"Wall Foundation: WF_A_1800x900","L(2-3)","13429.25 mm","1800.00 mm","24.17 m²"
"Wall Foundation: WF_A_1800x900","L(3-4)","13345.17 mm","1800.00 mm","24.02 m²"
"Wall Foundation: WF_A_1800x900","L(5-6)","13297.72 mm","1800.00 mm","23.94 m²"
"Wall Foundation: WF_B_2000x900","T(A-B)-1","2400.00 mm","2000.00 mm","4.32 m²"
"Wall Foundation: WF_B_2000x900","T(A-B)-2","6650.38 mm","2000.00 mm","11.97 m²"
"Wall Foundation: WF_B_2000x900","T(A-B)-3","3878.10 mm","2000.00 mm","6.98 m²"
"Wall Foundation: WF_A_1800x900","T(B-C)-1","2400.00 mm","1800.00 mm","4.32 m²"
"Wall Foundation: WF_A_1800x900","T(B-C)-2","6650.00 mm","1800.00 mm","11.97 m²"
"Wall Foundation: WF_A_1800x900","T(B-C)-3","4084.60 mm","1800.00 mm","7.35 m²"
"Wall Foundation: WF_A_1800x900","T(C-D)-1","2400.00 mm","1800.00 mm","4.32 m²"
"Wall Foundation: WF_A_1800x900","T(C-D)-2","6650.00 mm","1800.00 mm","11.97 m²"
"Wall Foundation: WF_A_1800x900","T(C-D)-3","4290.64 mm","1800.00 mm","7.72 m²"
"Grand total: 13","","","",""`,
  },
  {
    name: "جدول ریزمتره سقف تیرچه بلوک.txt",
    text: `"جدول ریزمتره سقف تیرچه بلوک - Joist Floor Schedule","","","","","",""
"Family and Type","Mark","Reference Level","Length","Count","Volume","Comments","Description"
"","","","","","","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5697.49 mm","1","0.64 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5702.86 mm","1","0.64 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5708.24 mm","1","0.64 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5713.62 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5718.99 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5724.37 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5727.63 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5735.12 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5740.50 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5745.87 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5751.25 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5756.62 mm","1","0.65 m³","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Story1","5762.00 mm","1","0.11 m³","",""
"Grand total: 13","","","74484.56 mm","13","7.88 m³","",""`,
  },
  {
    name: "جدول متره بتن پاشنه و یونولیت.txt",
    text: `"جدول متره بتن پاشنه و یونولیت - Joist Concrete & EPS Block Schedule","","","",""
"Family and Type","Mark","Material: Name","Material: Volume","Structural Usage"
"","","","",""
"تیرچه و یونولیت222: Joist","JST-ST1","بتن پاشنه تیرچه","0.34 m³","Joist"
"بتن پاشنه تیرچه: 13","","","0.34 m³",""
"تیرچه و یونولیت222: Joist","JST-ST1","یونولیت","7.49 m³","Joist"
"یونولیت: 13","","","7.49 m³",""
"Grand total: 26","","","7.84 m³",""`,
  },
  {
    name: "جدول ریزمتره آرماتورهای تیرچه.txt",
    text: `"جدول ریزمتره آرماتورهای تیرچه - Joist Rebar Schedule","","","","",""
"Family and Type","Mark","Material: Name","Material: Volume","وزن کل آرماتور (kg)","Structural Usage"
"","","","","","",""
"تیرچه و یونولیت222: Joist","JST-ST1","Rebar - Φ8","0.02 m³","129.42779","Joist"
"Rebar - Φ8: 13","","","0.02 m³","129.42779",""
"تیرچه و یونولیت222: Joist","JST-ST1","Rebar - Φ10","0.02 m³","137.761047","Joist"
"Rebar - Φ10: 13","","","0.02 m³","137.761047",""
"تیرچه و یونولیت222: Joist","JST-ST1","Rebar - Φ12","0.01 m³","66.125303","Joist"
"Rebar - Φ12: 13","","","0.01 m³","66.125303",""
"Grand total: 39","","","0.04 m³","333.31414",""`,
  },
  {
    name: "جدول ریزمتره آرماتورهای اتصال تیرچه.txt",
    text: `"جدول ریزمتره آرماتورهای اتصال تیرچه - Joist Connection Rebar Schedule","",""
"Mark","Length","وزن آرماتورهای اتصال (kg)"
"","",""
"JST-ST1","5697.49 mm","7.62"
"JST-ST1","5702.86 mm","7.62"
"JST-ST1","5708.24 mm","7.63"
"JST-ST1","5713.62 mm","7.63"
"JST-ST1","5718.99 mm","7.64"
"JST-ST1","5724.37 mm","7.64"
"JST-ST1","5727.63 mm","7.65"
"JST-ST1","5735.12 mm","7.65"
"JST-ST1","5740.50 mm","7.66"
"JST-ST1","5745.87 mm","7.66"
"JST-ST1","5751.25 mm","7.67"
"JST-ST1","5756.62 mm","7.68"
"JST-ST1","5762.00 mm","7.68"
"Grand total: 13","","99.43"`,
  },
  {
    name: "جدول ریزمتره آرماتور (بخش نمونه).txt",
    text: `"جدول ریزمتره آرماتورها - Rebar Schedule","","","","","","","","",""
"Mark","Bar Type","Bar Diameter","Rebar Shape","Material","Count","Spacing","Total Bar Length","Volume","Total Weight"
"","","","","","","","","","",""
"STR-ST1-Starter-F","Φ16","16 mm","Rebar Shape 11","IR-Rebar-Fy4000","7","200 mm","76.580 m","0.0154 m³","120.87 kg"
"STR-ST1-Starter-F","Φ16","16 mm","Rebar Shape 11","IR-Rebar-Fy4000","7","200 mm","17.290 m","0.0035 m³","27.29 kg"
"STR-ST1-TR-B","Φ14","14 mm","M_00","IR-Rebar-Fy4000","43","200 mm","54.410 m","0.0084 m³","65.75 kg"
"STR-ST1-TR-T","Φ14","14 mm","M_00","IR-Rebar-Fy4000","44","200 mm","55.740 m","0.0086 m³","67.36 kg"
"TM-8","A-I-8mm","8 mm","M_00","IR-Rebar-Fy2400","43"," ","318.230 m","0.0160 m³","125.57 kg"
"TR(1-2)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"
"TR(1-2)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"
"TR(2-3)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"
"TR(2-3)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","68","200 mm","140.080 m","0.0216 m³","169.27 kg"
"TR(3-4)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","59","200 mm","121.540 m","0.0187 m³","146.87 kg"
"TR(3-4)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","67","200 mm","138.020 m","0.0212 m³","166.79 kg"
"TR(4-5)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","67","200 mm","138.020 m","0.0212 m³","166.79 kg"
"TR(4-5)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","67","200 mm","138.020 m","0.0212 m³","166.79 kg"
"TR(A-B)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","233.160 m","0.0359 m³","281.75 kg"
"TR(A-B)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","233.160 m","0.0359 m³","281.75 kg"
"TR(B-C)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","95","200 mm","195.700 m","0.0301 m³","236.49 kg"
"TR(B-C)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","86","200 mm","177.160 m","0.0273 m³","214.08 kg"
"TR(C-D)-B","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","212.180 m","0.0327 m³","256.40 kg"
"TR(C-D)-T","Φ14","14 mm","M_02","IR-Rebar-Fy4000","103","200 mm","212.180 m","0.0327 m³","256.40 kg"
"Grand total","","","","","","2315","","7720.800 m","1.5289 m³","12001.91 kg"`,
  },
];

export const DEMO_PROJECT_META = {
  name: "پروژهٔ مسکونی نمونه (دمو) — اسکلت بتنی",
  discipline: "رشته ابنیه — مقطع اسکلت و سفت‌کاری",
  note: "زیرمجموعهٔ نمایشی خروجی‌های Revit / Dynamo — دادهٔ کامل پروژهٔ مرجع نیست؛ برای پروژهٔ واقعی فایل‌های export revit را آپلود کنید.",
};
