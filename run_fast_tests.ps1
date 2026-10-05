# run_fast_tests.ps1 — اجرای سریعِ تست‌ها (فاز E-۷ بخش ۴)
#
# نسخهٔ سریعِ run_all_tests.ps1: همهٔ تست‌ها به‌جزِ آزمون‌های «slow»
# (آنهایی که خطِ لولهٔ کاملِ Revit را اجرا می‌کنند). هدف: زیرِ ۳ دقیقه
# برای یک بررسیِ سریعِ سلامت در طولِ توسعه.
#
# چه چیزی را اجرا می‌کند:
#   1) pytest  -m "not slow"      (Python — ۳۰ فایلِ سریع)
#   2) vitest  --config vitest.fast.config.ts   (TypeScript — فایل‌های سریع)
#   3) tsc --noEmit               (نوع‌ها)
#
# چه چیزی را اجرا نمی‌کند: ۳۵ فایلِ slow پایتون + ۳۰ فایلِ slow تایپ‌اسکریپت
# (خطِ لولهٔ کامل، Excel/E2E). برای اجرای کامل run_all_tests.ps1 را ببینید.
#
# نکته: خروجیِ کنسولِ ویندوز فارسی را نشان نمی‌دهد (cp1252)؛ فقط اعداد و
# وضعیت انگلیسی چاپ می‌شوند.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$results = @()

function Step($name, $script) {
    Write-Host ""
    Write-Host "=== $name" -ForegroundColor Cyan
    $out = & $script 2>&1 | Out-String
    $code = $LASTEXITCODE
    $tail = ($out -split "`n" | Select-Object -Last 10) -join "`n"
    Write-Host $tail
    if ($code -ne 0) { Write-Host "  -> FAILED (exit $code)" -ForegroundColor Red }
    else             { Write-Host "  -> OK" -ForegroundColor Green }
    return [pscustomobject]@{ Name = $name; Exit = $code }
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()

$steps = @()
$steps += (Step "1) pytest (Python, not slow)" {
    python -m pytest tests/char_python -q -m "not slow"
})

$steps += (Step "2) vitest (TypeScript, fast config)" {
    npx vitest run --config vitest.fast.config.ts
})

$steps += (Step "3) tsc --noEmit" {
    npx tsc --noEmit
})

$sw.Stop()

# ── خلاصه نهایی ──
Write-Host ""
Write-Host "=== SUMMARY ===" -ForegroundColor Yellow
$failed = 0
foreach ($r in $steps) {
    if ($r.Exit -eq 0) { Write-Host ("{0,-40} OK" -f $r.Name) }
    else { Write-Host ("{0,-40} FAIL (exit {1})" -f $r.Name, $r.Exit) -ForegroundColor Red; $failed++ }
}
Write-Host ""
Write-Host ("duration: {0:N1} s  (target: < 180 s)" -f $sw.Elapsed.TotalSeconds)
if ($failed -eq 0 -and $sw.Elapsed.TotalSeconds -lt 180) {
    Write-Host "FAST SUITE GREEN" -ForegroundColor Green
    exit 0
} else {
    if ($failed -ne 0) { Write-Host "$failed step(s) FAILED" -ForegroundColor Red }
    else { Write-Host "steps OK but over the 3-minute target" -ForegroundColor Yellow }
    exit 1
}
