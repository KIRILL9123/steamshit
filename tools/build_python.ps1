$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$PythonDir = "$ProjectRoot\python_sidecar"
$BinariesDir = "$ProjectRoot\src-tauri\binaries"

Write-Host "Building Python Sidecar..."

Set-Location $PythonDir

# Activate virtual environment if exists, otherwise assume uv or pip is available
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "Syncing dependencies with uv..."
    uv sync
    Write-Host "Running PyInstaller via uv..."
    uv run pyinstaller --clean --noconfirm --onefile --name python_sidecar --hidden-import awpy src/cs2_sidecar/__main__.py
} else {
    if (Test-Path "$PythonDir\.venv\Scripts\Activate.ps1") {
        . "$PythonDir\.venv\Scripts\Activate.ps1"
    }

    # Install PyInstaller
    Write-Host "Installing PyInstaller..."
    pip install pyinstaller

    # Build
    Write-Host "Running PyInstaller..."
    pyinstaller --clean --noconfirm --onefile --name python_sidecar --hidden-import awpy src/cs2_sidecar/__main__.py
}

if (-Not (Test-Path $BinariesDir)) {
    New-Item -ItemType Directory -Force -Path $BinariesDir
}

# Target triple for Windows x64 MSVC (default for Tauri on Windows)
$TargetName = "python_sidecar-x86_64-pc-windows-msvc.exe"
$SourceExe = "$PythonDir\dist\python_sidecar.exe"
$DestExe = "$BinariesDir\$TargetName"

Write-Host "Copying $SourceExe to $DestExe..."
Copy-Item -Path $SourceExe -Destination $DestExe -Force

Write-Host "Done! Python sidecar built successfully."
