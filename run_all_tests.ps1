# run_all_tests.ps1 — اجرای کل تست‌های خودکار متره‌یار ۳.۰
#
# پشت سر هم اجرا می‌کند: pytest (Python) + vitest (TypeScript) +
# tsc --noEmit + vite build. در پایان خلاصهٔ pass/fail هر مرحله و
# اعداد مرجع فعلی (baseTotal / grandTotal) را چاپ می‌کند.
#
# خروجی مورد انتظار روی دادهٔ مرجع (تنظیمات پیش‌فرض):
#   Python  : 894 passed + 1 xfailed (895) / 80 files
#   TS      : 843 passed + 1 expected fail (844) / 75 files
#   tsc     : no errors
#   vite    : build ok
#   totals  : baseTotal = 23218381337.01 / grandTotal = 31391251567.64
#             (۱۷ خط — مرحلهٔ ۱۱: بدون ضریب پرت؛ مرحلهٔ ۱۳: ایراد ۱/۲/۳/۴ —
#              زنجیرهٔ مالی: base × ۱ (طبقات ناقص) × ۱٫۳ × ۱٫۰۴ (گرگان) + ۰
#              = gross؛ شاخص تعدیل دورهٔ مبنا)
#
# این اسکریپت همهٔ تست‌ها را اجرا می‌کند (حتیِ slowها). برای اجرای سریعِ
# زیرِ ۳ دقیقه run_fast_tests.ps1 را ببینید.
#
# نکته: خروجی کنسول ویندوز فارسی را نشان نمی‌دهد (cp1252)؛ فقط
# اعداد و وضعیت انگلیسی چاپ می‌شوند. برای گزارش فارسی، ACCEPTANCE.md
# را ببینید.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$results = @()

function Step($name, $script) {
    Write-Host ""
    Write-Host "=== $name" -ForegroundColor Cyan
    $out = & $script 2>&1 | Out-String
    $code = $LASTEXITCODE
    $tail = ($out -split "`n" | Select-Object -Last 6) -join "`n"
    Write-Host $tail
    if ($code -ne 0) { Write-Host "  -> FAILED (exit $code)" -ForegroundColor Red }
    else             { Write-Host "  -> OK" -ForegroundColor Green }
    return [pscustomobject]@{ Name = $name; Exit = $code }
}

$steps = @()
$steps += (Step "1) pytest (Python)" {
    python -m pytest tests/char_python -q
})

$steps += (Step "2) vitest (TypeScript)" {
    npx vitest run
})

$steps += (Step "3) tsc --noEmit" {
    npx tsc --noEmit
})

$steps += (Step "4) vite build" {
    npx vite build
})

# ── 5) اعداد مرجع فعلی (از موتور واقعی) ──
Write-Host ""
Write-Host "=== 5) reference totals (real engine, default settings)" -ForegroundColor Cyan
$code = @'
import os, sys, warnings
warnings.filterwarnings("ignore")
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
sys.path.insert(0, ".")
from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)
revit = "data/export revit"
tables = []
for f in sorted(os.listdir(revit)):
    if f.endswith(".txt"):
        with open(os.path.join(revit, f), "r", encoding="utf-8-sig") as fh:
            tables.append(RevitScheduleParser.parse(f, fh.read()))
res = []
for root, _d, fs in os.walk("data/dynamo"):
    for fn in sorted(fs):
        if fn.endswith(".txt"):
            with open(os.path.join(root, fn), "rb") as fh:
                res.append(DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
map_df = DynamoMappingParser.merge_formats(res)
r = TechnicalOfficeEngine(_default_fehrest_db(), default_settings()).compute(tables, map_df)
print(f"lines={len(r['lines'])} baseTotal={r['base_total']:.2f} grandTotal={r['grand_total']:.2f}")
'@
$tmp = Join-Path $env:TEMP "metreyar_totals.py"
[IO.File]::WriteAllText($tmp, $code, [Text.Encoding]::UTF8)
$totals = & python $tmp 2>$null | Out-String
Write-Host $totals.Trim()
Remove-Item $tmp -Force

# ── خلاصه نهایی ──
Write-Host ""
Write-Host "=== SUMMARY ===" -ForegroundColor Yellow
$failed = 0
foreach ($r in $steps) {
    if ($r.Exit -eq 0) { Write-Host ("{0,-30} OK" -f $r.Name) }
    else { Write-Host ("{0,-30} FAIL (exit {1})" -f $r.Name, $r.Exit) -ForegroundColor Red; $failed++ }
}
Write-Host ""
if ($failed -eq 0) {
    Write-Host "ALL GREEN" -ForegroundColor Green
    exit 0
} else {
    Write-Host "$failed step(s) FAILED" -ForegroundColor Red
    exit 1
}
