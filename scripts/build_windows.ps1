# Build clipsmith Windows distribution and package as a zip.
# Run from the repo root: .\scripts\build_windows.ps1
#
# Requirements (run once in your venv):
#   pip install pyinstaller
#   pip install -e .

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DIST_DIR  = "dist\clipsmith"
$ZIP_NAME  = "clipsmith-windows-x64.zip"

# --- 1. Build with PyInstaller ---
Write-Host "Building with PyInstaller..." -ForegroundColor Cyan
pyinstaller clipsmith.spec --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# --- 2. Download ffmpeg static build (gyan.dev essentials build) ---
$FFMPEG_URL  = "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip"
$FFMPEG_ZIP  = "ffmpeg_tmp.zip"
$FFMPEG_TMP  = "ffmpeg_tmp"

if (-not (Test-Path "$DIST_DIR\ffmpeg.exe")) {
    Write-Host "Downloading ffmpeg..." -ForegroundColor Cyan
    Invoke-WebRequest $FFMPEG_URL -OutFile $FFMPEG_ZIP
    Expand-Archive $FFMPEG_ZIP -DestinationPath $FFMPEG_TMP -Force
    $ffmpegExe = Get-ChildItem -Recurse $FFMPEG_TMP -Filter "ffmpeg.exe" | Select-Object -First 1
    Copy-Item $ffmpegExe.FullName "$DIST_DIR\ffmpeg.exe"
    Remove-Item $FFMPEG_ZIP, $FFMPEG_TMP -Recurse -Force
    Write-Host "ffmpeg.exe placed in $DIST_DIR" -ForegroundColor Green
} else {
    Write-Host "ffmpeg.exe already present, skipping download." -ForegroundColor DarkGray
}

# --- 3. Add user-facing files ---
Copy-Item ".env.example"    "$DIST_DIR\.env.example"  -Force
Copy-Item "README_user.txt" "$DIST_DIR\README.txt"    -Force

# --- 4. Zip ---
if (Test-Path $ZIP_NAME) { Remove-Item $ZIP_NAME }
Write-Host "Creating $ZIP_NAME..." -ForegroundColor Cyan
Compress-Archive -Path $DIST_DIR -DestinationPath $ZIP_NAME

Write-Host ""
Write-Host "Done: $ZIP_NAME" -ForegroundColor Green
Write-Host "Contents:"
Get-ChildItem $DIST_DIR | Format-Table Name, Length -AutoSize
