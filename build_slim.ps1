# RocoFlower slim onefile build script
# Uses a clean CPython 3.10 virtualenv to avoid Anaconda/MKL bloat.

param(
    [switch]$Clean = $false,
    [switch]$Verbose = $false,
    [string]$PythonExe = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$EntryPoint = "main_window.py"
$IconFile = "favicon.ico"
$OutputFileName = "RocoFlower-slim.exe"
$VenvDir = Join-Path $ProjectRoot ".venv-slim"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$CacheDir = Join-Path $ProjectRoot "nuitka_cache_slim"
$UpxDir = "C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\UPX.UPX_Microsoft.Winget.Source_8wekyb3d8bbwe\upx-5.1.1-win64"

$RequiredPackages = @(
    "pip",
    "setuptools",
    "wheel",
    "PyQt5",
    "pywin32",
    "cryptography",
    "opencv-python-headless",
    "nuitka",
    "ordered-set",
    "zstandard"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RocoFlower Slim Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path (Join-Path $ProjectRoot $EntryPoint))) {
    Write-Host "[Error] Entry file not found: $EntryPoint" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot $IconFile))) {
    Write-Host "[Error] Icon file not found: $IconFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "[Error] CPython 3.10 not found: $PythonExe" -ForegroundColor Red
    Write-Host "        Pass -PythonExe with a valid python.exe path." -ForegroundColor Yellow
    exit 1
}

if ($Clean) {
    Write-Host "[Clean] Removing old slim build files..." -ForegroundColor Yellow
    $pathsToRemove = @(
        $VenvDir,
        (Join-Path $ProjectRoot $OutputFileName),
        (Join-Path $ProjectRoot "main_window.build"),
        (Join-Path $ProjectRoot "main_window.dist"),
        (Join-Path $ProjectRoot "main_window.onefile-build"),
        $CacheDir
    )
    foreach ($path in $pathsToRemove) {
        if (Test-Path $path) {
            Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $path" -ForegroundColor Gray
        }
    }
    Write-Host ""
}

Write-Host "[Config] Slim Build Info:" -ForegroundColor Green
Write-Host "  Project Dir: $ProjectRoot"
Write-Host "  Python Exe : $PythonExe"
Write-Host "  Venv Dir   : $VenvDir"
Write-Host "  Output File: $OutputFileName"
Write-Host "  Cache Dir  : $CacheDir"
Write-Host ""

if (-not (Test-Path $VenvPython)) {
    Write-Host "[Env] Creating virtualenv..." -ForegroundColor Green
    & $PythonExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Error] Virtualenv creation failed" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

Write-Host "[Env] Installing minimal build dependencies..." -ForegroundColor Green
& $VenvPython -m pip install --upgrade @RequiredPackages
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Error] Dependency installation failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

$env:NUITKA_CACHE_DIR = $CacheDir
Write-Host "[Env] Setting cache directory: $CacheDir" -ForegroundColor Green
if (Test-Path $UpxDir) {
    $env:PATH = "$UpxDir;$env:PATH"
    Write-Host "[Env] UPX detected: $UpxDir" -ForegroundColor Green
}
Write-Host ""

$outputPath = Join-Path $ProjectRoot $OutputFileName
if (Test-Path $outputPath) {
    Remove-Item -Path $outputPath -Force -ErrorAction SilentlyContinue
}

$nuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$IconFile",
    "--enable-plugin=pyqt5",
    "--enable-plugin=upx",
    "--output-filename=$OutputFileName",
    "--assume-yes-for-downloads",
    "--lto=yes",
    "--jobs=1",
    "--python-flag=no_docstrings",
    "--nofollow-import-to=tkinter",
    "--nofollow-import-to=unittest",
    "--nofollow-import-to=test",
    "--nofollow-import-to=tests",
    "--nofollow-import-to=setuptools",
    "--nofollow-import-to=pip",
    "--nofollow-import-to=pandas",
    "--nofollow-import-to=matplotlib",
    "--nofollow-import-to=scipy",
    "--nofollow-import-to=PIL",
    "--include-module=pythoncom",
    "--include-module=pywintypes",
    "--include-module=win32com.client",
    "--include-module=win32gui",
    "--include-module=win32con",
    "--include-module=win32api",
    "--include-module=win32ui",
    "--include-data-dir=img=img",
    $EntryPoint
)

if ($Verbose) {
    $nuitkaArgs += "--show-progress"
    $nuitkaArgs += "--show-memory"
}

Write-Host "[Build] Starting slim onefile compilation..." -ForegroundColor Green
Write-Host ""

$startTime = Get-Date
try {
    & $VenvPython $nuitkaArgs
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host "[Error] Nuitka execution failed: $_" -ForegroundColor Red
    exit 1
}
$endTime = Get-Date
$duration = $endTime - $startTime

if ($exitCode -ne 0) {
    Write-Host "[Error] Slim build failed with exit code: $exitCode" -ForegroundColor Red
    exit $exitCode
}

if (-not (Test-Path $outputPath)) {
    Write-Host "[Error] Build finished but output file not found: $outputPath" -ForegroundColor Red
    exit 1
}

$fileSize = (Get-Item $outputPath).Length / 1MB

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Slim Build Success!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output File: $outputPath"
Write-Host "File Size : $([math]::Round($fileSize, 2)) MB"
Write-Host "Build Time: $($duration.ToString('hh\:mm\:ss'))"
Write-Host ""
Write-Host "[Note] Distribute license.key next to $OutputFileName" -ForegroundColor Cyan
