param([string]$Dir = "$env:TEMP\cc-shots")

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) {
    Write-Error "Panoda görsel yok. Önce Win+Shift+S ile ekran görüntüsü al, sonra bu scripti çalıştır."
    exit 1
}

if (-not (Test-Path $Dir)) { New-Item -ItemType Directory -Path $Dir -Force | Out-Null }

$img  = [System.Windows.Forms.Clipboard]::GetImage()
$path = Join-Path $Dir ("shot-{0}.png" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$img.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)

# path'i panoya geri koy (Claude'a Ctrl+V ile yapıştırılabilsin)
Set-Clipboard -Value $path
Write-Output $path
