Add-Type -AssemblyName System.Drawing

$iconDir = "C:\Users\kyrylo\Documents\steamshit\src-tauri\icons"

function New-Icon($path, $size) {
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    $rect = New-Object System.Drawing.Rectangle 0, 0, $size, $size
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush $rect, ([System.Drawing.Color]::FromArgb(14, 15, 18)), ([System.Drawing.Color]::FromArgb(40, 45, 60)), 45
    $g.FillRectangle($brush, $rect)

    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 140, 0)), ([single]($size / 12))
    $cx = [int]($size / 2)
    $r = [int]($size * 0.3)
    $g.DrawEllipse($pen, $cx - $r, $cx - $r, $r * 2, $r * 2)
    $g.DrawLine($pen, $cx, $cx - $r, $cx, $cx + $r)
    $g.DrawLine($pen, $cx - $r, $cx, $cx + $r, $cx)

    $innerBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(0, 194, 255))
    $ir = [int]($size / 16)
    if ($ir -lt 1) { $ir = 1 }
    $g.FillEllipse($innerBrush, $cx - $ir, $cx - $ir, $ir * 2, $ir * 2)

    $g.Dispose()
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "Created $path"
}

New-Icon "$iconDir\32x32.png" 32
New-Icon "$iconDir\128x128.png" 128
New-Icon "$iconDir\128x128@2x.png" 256
New-Icon "$iconDir\icon.png" 512

# Build .ico from 256x256 via Bitmap.GetHicon()
$bmp = [System.Drawing.Bitmap]::FromFile("$iconDir\128x128@2x.png")
$hicon = $bmp.GetHicon()
$ico = [System.Drawing.Icon]::FromHandle($hicon)
$fs = [System.IO.File]::Create("$iconDir\icon.ico")
$ico.Save($fs)
$fs.Close()
$bmp.Dispose()
Write-Host "Created $iconDir\icon.ico"

# icns placeholder (Tauri 2 may want this on macOS — just a copy for now)
Copy-Item "$iconDir\icon.png" "$iconDir\icon.icns" -Force
Write-Host "Created $iconDir\icon.icns (placeholder)"

Get-ChildItem $iconDir | Select-Object Name, Length
