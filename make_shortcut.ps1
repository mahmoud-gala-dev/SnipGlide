$ErrorActionPreference = "Stop"
$desktop = [Environment]::GetFolderPath("Desktop")
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$pythonwPath = Join-Path $baseDir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonwPath)) {
    $pythonwPath = "pythonw.exe"
}

$appScript = Join-Path $baseDir "app.py"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut((Join-Path $desktop "SnipGlide Pro.lnk"))
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = "`"$appScript`""
$shortcut.WorkingDirectory = $baseDir
$shortcut.IconLocation = (Join-Path $baseDir "snipglide\assets\icon.ico")
$shortcut.Description = "SnipGlide Pro - Text Expander & Smart Chat Notes"
$shortcut.Save()

Write-Host "SnipGlide Pro Desktop Shortcut created/updated successfully on Desktop (No CMD window)!"
