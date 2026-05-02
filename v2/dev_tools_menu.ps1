$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainDir = Join-Path $root "main"
$pythonExe = Join-Path $mainDir "lib\python_embed\python.exe"
$mainPyw = Join-Path $mainDir "main.pyw"
$launcherExe = Join-Path $root "oldfishVDL.exe"
$ffmpegExe = Join-Path $mainDir "lib\ffmpeg-7.1.1-essentials_build\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
$ffprobeExe = Join-Path $mainDir "lib\ffmpeg-7.1.1-essentials_build\ffmpeg-7.1.1-essentials_build\bin\ffprobe.exe"
$settingsJson = Join-Path $mainDir "main\settings.json"
$ytCacheJson = Join-Path $mainDir "main\ytdlp_version_cache.json"
$launcherLog = Join-Path $mainDir "launcher.log"
$thumbCache = Join-Path $mainDir "thumb_cache"
$downloadsDir = Join-Path $mainDir "downloads"

if (!(Test-Path -LiteralPath $pythonExe)) {
  Write-Host "[ERROR] Embedded python not found:"
  Write-Host $pythonExe
  Read-Host "Press Enter to exit" | Out-Null
  exit 1
}

function Show-Menu {
  param(
    [string]$Title,
    [array]$Items
  )

  $index = 0
  while ($true) {
    Clear-Host
    Write-Host "======================================="
    Write-Host " $Title"
    Write-Host "======================================="
    Write-Host ""
    for ($i = 0; $i -lt $Items.Count; $i++) {
      if ($i -eq $index) { Write-Host ("> " + $Items[$i].Label) } else { Write-Host ("  " + $Items[$i].Label) }
    }
    Write-Host ""
    Write-Host "Use Up/Down, Enter=select, Esc=back"
    try {
      $key = [Console]::ReadKey($true)
      switch ($key.Key) {
        "UpArrow" { if ($index -gt 0) { $index-- } else { $index = $Items.Count - 1 } }
        "DownArrow" { if ($index -lt ($Items.Count - 1)) { $index++ } else { $index = 0 } }
        "Enter" { return $Items[$index].Id }
        "Escape" { return "back" }
      }
    } catch {
      Write-Host ""
      for ($j = 0; $j -lt $Items.Count; $j++) {
        Write-Host ("[{0}] {1}" -f ($j + 1), $Items[$j].Label)
      }
      $raw = Read-Host "No interactive console. Enter number"
      $num = 0
      if ([int]::TryParse($raw, [ref]$num) -and $num -ge 1 -and $num -le $Items.Count) {
        return $Items[$num - 1].Id
      }
      return "back"
    }
  }
}

function Pause-Done { Read-Host "Press Enter to continue" | Out-Null }
function Confirm-Action([string]$msg) { return (Read-Host $msg) -match "^(?i:y|yes)$" }

function Run-Console([string]$flags) {
  Push-Location $mainDir
  try {
    Write-Host "[RUN] Console mode $flags"
    if ([string]::IsNullOrWhiteSpace($flags)) { & $pythonExe $mainPyw } else { & $pythonExe $mainPyw $flags }
    Write-Host "[DONE] Exit code: $LASTEXITCODE"
  } finally {
    Pop-Location
  }
  Pause-Done
}

function Run-ConsoleDebug {
  Push-Location $mainDir
  try {
    Write-Host "[RUN] Console mode + DEBUG"
    $env:OLDFISH_LOG_LEVEL = "DEBUG"
    & $pythonExe $mainPyw
    Write-Host "[DONE] Exit code: $LASTEXITCODE"
  } finally {
    Remove-Item Env:OLDFISH_LOG_LEVEL -ErrorAction SilentlyContinue
    Pop-Location
  }
  Pause-Done
}

function Run-Launcher([string]$flags) {
  if (!(Test-Path -LiteralPath $launcherExe)) {
    Write-Host "[ERROR] Launcher not found:"
    Write-Host $launcherExe
    Pause-Done
    return
  }
  Write-Host "[RUN] Launcher mode $flags"
  if ([string]::IsNullOrWhiteSpace($flags)) {
    Start-Process -FilePath $launcherExe | Out-Null
  } else {
    Start-Process -FilePath $launcherExe -ArgumentList $flags | Out-Null
  }
  Write-Host "[INFO] Launcher started."
  Pause-Done
}

function Clean-PyCache {
  Write-Host "[CLEAN] __pycache__ ..."
  Get-ChildItem -Path $mainDir -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
  Write-Host "[DONE] __pycache__ cleaned."
}

function Clean-ThumbCache {
  Write-Host "[CLEAN] thumb_cache ..."
  if (Test-Path -LiteralPath $thumbCache) {
    Get-ChildItem -Path $thumbCache -Force -ErrorAction SilentlyContinue |
      Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[DONE] thumb_cache cleaned."
  } else {
    Write-Host "[INFO] thumb_cache not found."
  }
}

function Clean-YtCache {
  Write-Host "[CLEAN] ytdlp_version_cache.json ..."
  if (Test-Path -LiteralPath $ytCacheJson) {
    Remove-Item -LiteralPath $ytCacheJson -Force -ErrorAction SilentlyContinue
    Write-Host "[DONE] ytdlp cache removed."
  } else {
    Write-Host "[INFO] ytdlp cache not found."
  }
}

function Clean-Downloads {
  Write-Host "[CLEAN] downloads ..."
  if (Test-Path -LiteralPath $downloadsDir) {
    Get-ChildItem -Path $downloadsDir -Force -ErrorAction SilentlyContinue |
      Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[DONE] downloads cleaned."
  } else {
    Write-Host "[INFO] downloads folder not found."
  }
}

function Reset-Settings {
  Push-Location $mainDir
  try {
    Write-Host "[RESET] settings.json ..."
    & $pythonExe -c "import json, sys; from pathlib import Path; sys.path.insert(0, '.'); from scripts.config.constants import DEFAULT_SETTINGS; p=Path('main') / 'settings.json'; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=2), encoding='utf-8')"
    if ($LASTEXITCODE -ne 0) {
      Write-Host "[ERROR] Failed to reset settings.json"
      return
    }
    Write-Host "[DONE] settings.json reset."
  } catch {
    Write-Host "[ERROR] Failed to reset settings.json"
  } finally {
    Pop-Location
  }
}

function Reset-AllFactory {
  Write-Host "[RESET] Factory reset start ..."
  Clean-PyCache
  Clean-ThumbCache
  Clean-YtCache
  Clean-Downloads
  Reset-Settings
  Write-Host "[DONE] Factory reset completed."
}

function Show-EnvInfo {
  Clear-Host
  Write-Host "========================"
  Write-Host " Environment Info"
  Write-Host "========================"
  Write-Host ""
  Write-Host "[Python]"
  & $pythonExe -V
  & $pythonExe -c "import sys; print(sys.executable)"
  Write-Host ""
  Write-Host "[FFmpeg]"
  if (Test-Path -LiteralPath $ffmpegExe) { (& $ffmpegExe -version)[0] } else { Write-Host "ffmpeg.exe not found" }
  if (Test-Path -LiteralPath $ffprobeExe) { (& $ffprobeExe -version)[0] } else { Write-Host "ffprobe.exe not found" }
  Write-Host ""
  Write-Host "[yt-dlp]"
  & $pythonExe -m yt_dlp --version
  Write-Host ""
  Write-Host "[PyQt]"
  & $pythonExe -c "mods=[('PyQt6','PyQt6.QtCore'),('PyQt5','PyQt5.QtCore'),('PySide6','PySide6.QtCore')]; ok=False
for name,mod in mods:
    try:
        m=__import__(mod, fromlist=['*'])
        pyqt_ver=getattr(m,'PYQT_VERSION_STR',None)
        qt_ver=getattr(m,'QT_VERSION_STR',None)
        if pyqt_ver and qt_ver:
            print(name, pyqt_ver, 'Qt', qt_ver)
        elif qt_ver:
            print(name, 'Qt', qt_ver)
        else:
            print(name, 'installed')
        ok=True
        break
    except Exception:
        pass
if not ok:
    print('Not found: PyQt6/PyQt5/PySide6')"
  Write-Host ""
  Write-Host "[Required Files]"
  @(
    @{N="python.exe"; P=$pythonExe},
    @{N="main.pyw"; P=$mainPyw},
    @{N="oldfishVDL.exe"; P=$launcherExe},
    @{N="settings.json"; P=$settingsJson},
    @{N="launcher.log"; P=$launcherLog}
  ) | ForEach-Object {
    if (Test-Path -LiteralPath $_.P) { Write-Host "[OK] $($_.N)" } else { Write-Host "[MISSING] $($_.N) ($($_.P))" }
  }
  Pause-Done
}

while ($true) {
  $mainChoice = Show-Menu "oldfishVDL Dev Tools Main Menu v1.0.0" @(
    @{Id="run"; Label="Run App"},
    @{Id="maint"; Label="Maintenance"},
    @{Id="env"; Label="Environment Info"},
    @{Id="quit"; Label="Exit"}
  )

  switch ($mainChoice) {
    "run" {
      while ($true) {
        $runChoice = Show-Menu "Run App" @(
          @{Id="r1"; Label="Console mode (normal)"},
          @{Id="r2"; Label="Console mode + DEBUG"},
          @{Id="r3"; Label="Console mode + --safe"},
          @{Id="r4"; Label="Console mode + --no-gpu"},
          @{Id="r5"; Label="Console mode + --require-admin"},
          @{Id="r6"; Label="Launcher normal"},
          @{Id="r7"; Label="Launcher --safe"},
          @{Id="r8"; Label="Launcher --no-gpu"},
          @{Id="r9"; Label="Launcher --require-admin"},
          @{Id="back"; Label="Back"}
        )
        if ($runChoice -eq "back") { break }
        switch ($runChoice) {
          "r1" { Run-Console "" }
          "r2" { Run-ConsoleDebug }
          "r3" { Run-Console "--safe" }
          "r4" { Run-Console "--no-gpu" }
          "r5" { Run-Console "--require-admin" }
          "r6" { Run-Launcher "" }
          "r7" { Run-Launcher "--safe" }
          "r8" { Run-Launcher "--no-gpu" }
          "r9" { Run-Launcher "--require-admin" }
          default { continue }
        }
      }
    }
    "maint" {
      while ($true) {
        $m = Show-Menu "Maintenance" @(
          @{Id="m1"; Label="Clean __pycache__"},
          @{Id="m2"; Label="Clean thumb_cache"},
          @{Id="m3"; Label="Clean ytdlp_version_cache.json"},
          @{Id="m4"; Label="Clean downloads"},
          @{Id="m5"; Label="Clean all (cache only)"},
          @{Id="m6"; Label="Reset settings.json"},
          @{Id="sep"; Label="------------------------------"},
          @{Id="m7"; Label="Reset all (Factory reset)"},
          @{Id="back"; Label="Back"}
        )
        if ($m -eq "back") { break }
        switch ($m) {
          "m1" { if (Confirm-Action "Confirm clean __pycache__? (y/N)") { Clean-PyCache; Pause-Done } }
          "m2" { if (Confirm-Action "Confirm clean thumb_cache? (y/N)") { Clean-ThumbCache; Pause-Done } }
          "m3" { if (Confirm-Action "Confirm clean ytdlp_version_cache.json? (y/N)") { Clean-YtCache; Pause-Done } }
          "m4" { if (Confirm-Action "Confirm clean downloads? (y/N)") { Clean-Downloads; Pause-Done } }
          "m5" {
            if (Confirm-Action "Confirm clean all cache items? (y/N)") {
              Clean-PyCache
              Clean-ThumbCache
              Clean-YtCache
              Pause-Done
            }
          }
          "m6" { if (Confirm-Action "Confirm reset settings.json? (y/N)") { Reset-Settings; Pause-Done } }
          "m7" { if (Confirm-Action "Confirm FACTORY RESET (delete files + reset settings)? (y/N)") { Reset-AllFactory; Pause-Done } }
          "sep" { continue }
          default { continue }
        }
      }
    }
    "env" { Show-EnvInfo }
    "quit" { break }
    default { break }
  }
}

exit 0
