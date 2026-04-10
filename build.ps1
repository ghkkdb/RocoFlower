# RocoFlower Nuitka Build Script
# Package Python application into a single executable

param(
    [switch]$Clean = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$OutputFileName = "RocoFlower.exe"
$IconFile = "favicon.ico"
$EntryPoint = "main_window.py"
$CacheDir = Join-Path $ProjectRoot "nuitka_cache"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RocoFlower Nuitka Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($Clean) {
    Write-Host "[Clean] Removing old build files..." -ForegroundColor Yellow
    $buildDirs = @(
        "main_window.build",
        "main_window.dist", 
        "main_window.onefile-build"
    )
    foreach ($dir in $buildDirs) {
        $path = Join-Path $ProjectRoot $dir
        if (Test-Path $path) {
            Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $dir" -ForegroundColor Gray
        }
    }
    Write-Host ""
}

Write-Host "[Config] Project Info:" -ForegroundColor Green
Write-Host "  Project Dir: $ProjectRoot"
Write-Host "  Entry Point: $EntryPoint"
Write-Host "  Output File: $OutputFileName"
Write-Host "  Icon File: $IconFile"
Write-Host "  Cache Dir: $CacheDir"
Write-Host ""

if (-not (Test-Path (Join-Path $ProjectRoot $EntryPoint))) {
    Write-Host "[Error] Entry file not found: $EntryPoint" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot $IconFile))) {
    Write-Host "[Error] Icon file not found: $IconFile" -ForegroundColor Red
    exit 1
}

$env:NUITKA_CACHE_DIR = $CacheDir
Write-Host "[Env] Setting cache directory: $CacheDir" -ForegroundColor Green
Write-Host ""

Write-Host "[Build] Starting Nuitka compilation..." -ForegroundColor Green
Write-Host ""

$nuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$IconFile",
    "--enable-plugin=pyqt5",
    "--output-filename=$OutputFileName",
    "--assume-yes-for-downloads",
    "--nofollow-import-to=tkinter",
    "--nofollow-import-to=unittest",
    "--nofollow-import-to=test",
    "--nofollow-import-to=tests",
    "--nofollow-import-to=email",
    "--nofollow-import-to=html",
    "--nofollow-import-to=xml",
    "--nofollow-import-to=xmlrpc",
    "--nofollow-import-to=multiprocessing",
    "--nofollow-import-to=concurrent",
    "--nofollow-import-to=asyncio",
    "--nofollow-import-to=distutils",
    "--nofollow-import-to=setuptools",
    "--nofollow-import-to=pip",
    "--nofollow-import-to=site-packages",
    "--include-module=win32gui",
    "--include-module=win32con",
    "--include-module=win32api",
    $EntryPoint
)

if ($Verbose) {
    $nuitkaArgs += "--show-progress"
    $nuitkaArgs += "--show-memory"
}

$startTime = Get-Date

try {
    & python $nuitkaArgs
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host "[Error] Nuitka execution failed: $_" -ForegroundColor Red
    exit 1
}

$endTime = Get-Date
$duration = $endTime - $startTime

if ($exitCode -eq 0) {
    $exePath = Join-Path $ProjectRoot $OutputFileName
    if (Test-Path $exePath) {
        $fileSize = (Get-Item $exePath).Length / 1MB
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  Build Success!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Output File: $exePath"
        Write-Host "File Size: $([math]::Round($fileSize, 2)) MB"
        Write-Host "Build Time: $($duration.ToString('hh\:mm\:ss'))"
        Write-Host ""
        
        Write-Host "[Clean] Removing temporary build directories..." -ForegroundColor Yellow
        $tempDirs = @("main_window.build", "main_window.dist", "main_window.onefile-build")
        foreach ($dir in $tempDirs) {
            $path = Join-Path $ProjectRoot $dir
            if (Test-Path $path) {
                Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host "  Temporary files cleaned" -ForegroundColor Gray
        Write-Host ""
        
        Write-Host "[Tip] Run $OutputFileName to test the application" -ForegroundColor Cyan
    } else {
        Write-Host "[Warning] Build completed but output file not found" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "[Error] Build failed with exit code: $exitCode" -ForegroundColor Red
    Write-Host "Please check error messages and try again" -ForegroundColor Yellow
    exit $exitCode
}
