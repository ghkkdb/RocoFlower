# RocoFlower Nuitka Build Script
# Package Python application into a single executable

param(
    [switch]$Clean = $false,
    [switch]$Verbose = $false,
    [switch]$Onefile = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$OutputFileName = "RocoFlower.exe"
$IconFile = "favicon.ico"
$EntryPoint = "main_window.py"
$CacheDir = Join-Path $ProjectRoot "nuitka_cache"
$UpxDir = "C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\UPX.UPX_Microsoft.Winget.Source_8wekyb3d8bbwe\upx-5.1.1-win64"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RocoFlower Nuitka Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($Clean) {
    Write-Host "[Clean] Removing old build files..." -ForegroundColor Yellow
    $buildDirs = @(
        "main_window.build",
        "main_window.dist",
        "main_window.onefile-build",
        $OutputFileName
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

if (Test-Path $UpxDir) {
    $env:PATH = "$UpxDir;$env:PATH"
    Write-Host "[Env] UPX detected: $UpxDir" -ForegroundColor Green
    Write-Host ""
}

$outputPath = Join-Path $ProjectRoot $OutputFileName
if (Test-Path $outputPath) {
    Write-Host "[Clean] Removing previous output: $OutputFileName" -ForegroundColor Yellow
    try {
        Remove-Item -Path $outputPath -Force
    } catch {
        Write-Host "[Error] Failed to remove existing output. Close any running copy of $OutputFileName and try again." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

Write-Host "[Build] Starting Nuitka compilation..." -ForegroundColor Green
Write-Host ""

$nuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$IconFile",
    "--enable-plugin=pyqt5",
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
    "--noinclude-dlls=qt5network_conda.dll",
    "--noinclude-dlls=qt5pdf_conda.dll",
    "--noinclude-dlls=qt5quick_conda.dll",
    "--noinclude-dlls=qt5qml_conda.dll",
    "--noinclude-dlls=qt5qmlmodels_conda.dll",
    "--noinclude-dlls=qt5websockets_conda.dll",
    "--noinclude-dlls=qt5multimedia_conda.dll",
    "--noinclude-dlls=qt5printsupport_conda.dll",
    "--noinclude-dlls=qt5svg_conda.dll",
    "--noinclude-dlls=qt5dbus_conda.dll",
    $EntryPoint
)

if ($Onefile) {
    $nuitkaArgs += "--onefile"
    $nuitkaArgs += "--enable-plugin=upx"
    $nuitkaArgs += "--output-filename=$OutputFileName"
} else {
    $nuitkaArgs += "--output-filename=$OutputFileName"
}

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
    $exePath = if ($Onefile) { $outputPath } else { Join-Path $ProjectRoot "main_window.dist\$OutputFileName" }
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
        $tempDirs = @("main_window.build")
        if ($Onefile) {
            $tempDirs += "main_window.onefile-build"
            $tempDirs += "main_window.dist"
        }
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
