<#
.SYNOPSIS
Zero-Python Windows PowerShell 5.1+ controller & first-run installer for 大肥鱼桌宠 (dafeiyu-pet.exe).
Ideal for WorkBuddy, CodeBuddy, Claude Desktop, or Windows users without Python installed.
#>
param(
    [Parameter(Position = 0)]
    [string]$Action = "",
    [string]$Say = "",
    [int]$Ms = 3500,
    [string]$Character = "",
    [string]$ApiAction = "",
    [string]$Countdown = "",
    [string]$Work = "",
    [string]$Rest = "",
    [int]$Cycles = 1,
    [string]$Label = "",
    [string]$Icon = "",
    [int]$AnimSec = 0,
    [string]$DoneSay = "",
    [string]$DoneAction = "工作状态-雀跃庆祝",
    [switch]$NativePomo,
    [switch]$StopTimer,
    [string]$RawJs = "",
    [string]$Exe = "",
    [switch]$Lite,
    [switch]$Install,
    [switch]$Ensure,
    [switch]$SetupAutostart,
    [switch]$RemoveAutostart,
    [switch]$Doctor,
    [switch]$Force,
    [switch]$Status,
    [switch]$Strict,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$BaseUrl = "http://127.0.0.1:9336"
$ReleaseApi = "https://api.github.com/repos/shenliuyu18/dafeiyu-pet/releases/latest"
$MirrorReleaseApi = "https://api.github.com/repos/ihpwhath/dafeiyu-pet/releases/latest"
$MirrorPrefix = "https://gh-proxy.org/"
$FallbackTag = "v1.5.2"
$FallbackBase = "https://github.com/shenliuyu18/dafeiyu-pet/releases/download/$FallbackTag"
$MirrorRepoBase = "https://github.com/ihpwhath/dafeiyu-pet/releases/download/$FallbackTag"
$WebView2Guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

function Get-PetState {
    try {
        return Invoke-RestMethod -Uri "$BaseUrl/state" -Method Get -TimeoutSec 1
    } catch {
        return $null
    }
}

function ConvertTo-DurationSeconds([string]$Spec, [string]$DefaultUnit = "s") {
    $raw = $Spec.Trim().ToLowerInvariant()
    if (-not $raw) { throw "Empty duration" }
    if ($raw -match '^(\d+):(\d+)$') {
        return [Math]::Max(1, ([int]$matches[1] * 60) + [int]$matches[2])
    }
    if ($raw -match '^\d+(?:\.\d+)?$') {
        $v = [double]$raw
        $mult = if ($DefaultUnit -eq "m") { 60.0 } elseif ($DefaultUnit -eq "h") { 3600.0 } else { 1.0 }
        return [Math]::Max(1, [int][Math]::Round($v * $mult))
    }
    $m = [regex]::Matches($raw, '(\d+(?:\.\d+)?)\s*([hms])')
    if ($m.Count -eq 0) { throw "Invalid duration: $Spec" }
    $sum = 0.0
    foreach ($hit in $m) {
        $n = [double]$hit.Groups[1].Value
        $u = $hit.Groups[2].Value
        $sum += $n * $(if ($u -eq "h") { 3600.0 } elseif ($u -eq "m") { 60.0 } else { 1.0 })
    }
    return [Math]::Max(1, [int][Math]::Round($sum))
}

function New-TimerJs($Phases, [int]$CycleCount, [string]$DoneSayText, [string]$DoneActName, [int]$AnimSecVal) {
    $cfgJson = @{
        phases = $Phases
        cycles = [Math]::Max(1, $CycleCount)
        doneSay = if ($DoneSayText) { $DoneSayText } else { "倒计时完成啦~" }
        doneAction = $DoneActName
        animSec = if ($AnimSecVal -gt 0) { $AnimSecVal } else { $null }
    } | ConvertTo-Json -Compress -Depth 6
    return @"
(() => {
  const cfg = $cfgJson;
  const goRunning = (typeof S !== 'undefined' && S.pomoRunning && (!window.__petSkillTimer || !window.__petSkillTimer.active));
  if (goRunning && typeof api !== 'undefined' && api.action) { api.action('pomodoro'); }
  const launch = () => {
    if (cfg.animSec && typeof applyPomoAnimSec === 'function') { applyPomoAnimSec(cfg.animSec, false); }
    if (!window.__petSkillTimer) {
      const chip = document.getElementById('chip');
      const chipTimeEl = document.getElementById('chip-time');
      const tomatoEl = chip ? chip.querySelector('.tomato') : null;
      const menu = document.getElementById('menu');
      if (chip) chip.style.whiteSpace = 'nowrap';
      const mgr = {
        active: false, interval: null, restAnimTimer: null, phaseIdx: 0, cycleIdx: 0, endsAt: 0, cfg: null,
        stop(sayMsg, actionName, silent) {
          this.active = false;
          if (this.interval) { clearInterval(this.interval); this.interval = null; }
          if (this.restAnimTimer) { clearInterval(this.restAnimTimer); this.restAnimTimer = null; }
          if (tomatoEl) tomatoEl.textContent = '🍅';
          if (typeof setPomodoro === 'function') setPomodoro({ running: false, remaining: 0 });
          if (!silent) {
            if (actionName && typeof playAction === 'function') playAction(actionName);
            else if (typeof playHappy === 'function') playHappy();
            if (typeof burstHearts === 'function') burstHearts(6);
            if (sayMsg && typeof say === 'function') say(sayMsg, 4200);
          }
        },
        render() {
          if (!this.active || !this.cfg) return;
          const p = this.cfg.phases[this.phaseIdx];
          const remMs = Math.max(0, this.endsAt - Date.now());
          if (tomatoEl) tomatoEl.textContent = p.icon || '🍅';
          const clock = typeof fmtClock === 'function' ? fmtClock(remMs) : (Math.ceil(remMs / 1000) + 's');
          const prefix = p.label ? (p.label + ' ') : '';
          if (p.kind === 'rest') {
            if (typeof S !== 'undefined' && S.pomoRunning && typeof setPomodoro === 'function') { setPomodoro({ running: false, remaining: 0 }); }
            if (typeof stage !== 'undefined') stage.classList.remove('focus');
            if (chip) chip.classList.add('show');
            if (chipTimeEl) chipTimeEl.textContent = prefix + clock;
          } else {
            if (typeof setPomodoro === 'function') setPomodoro({ running: true, remaining: remMs });
            if (chipTimeEl && prefix) chipTimeEl.textContent = prefix + clock;
          }
          if (remMs <= 0) this.advance();
        },
        enterPhase(idx) {
          this.phaseIdx = idx;
          const p = this.cfg.phases[idx];
          this.endsAt = Date.now() + p.sec * 1000;
          if (this.restAnimTimer) { clearInterval(this.restAnimTimer); this.restAnimTimer = null; }
          if (p.kind === 'rest') {
            if (typeof setPomodoro === 'function') setPomodoro({ running: false, remaining: 0 });
            if (typeof playHappy === 'function') playHappy();
            if (typeof burstHearts === 'function') burstHearts(5);
            if (p.action && typeof playAction === 'function') playAction(p.action);
            if (p.say && typeof say === 'function') say(p.say, 4000);
            this.restAnimTimer = setInterval(() => {
              if (!this.active) return;
              const cur = this.cfg.phases[this.phaseIdx];
              if (cur && cur.kind === 'rest' && typeof playAction === 'function' && (typeof oneShotPlaying === 'undefined' || !oneShotPlaying)) {
                playAction(cur.action || '悠闲哼歌');
              }
            }, 18000);
          } else {
            if (p.action && typeof playAction === 'function') playAction(p.action);
            if (p.say && typeof say === 'function') say(p.say, 3500);
          }
          this.render();
        },
        advance() {
          if (this.phaseIdx + 1 < this.cfg.phases.length) { this.enterPhase(this.phaseIdx + 1); return; }
          if (this.cycleIdx + 1 < this.cfg.cycles) { this.cycleIdx++; this.enterPhase(0); return; }
          this.stop(this.cfg.doneSay || '倒计时完成啦~', this.cfg.doneAction || '工作状态-雀跃庆祝', false);
        },
        start(c) {
          this.stop(null, null, true);
          this.cfg = c; this.active = true; this.cycleIdx = 0;
          if (typeof wake === 'function') wake();
          this.enterPhase(0);
          this.interval = setInterval(() => this.render(), 500);
        }
      };
      if (menu && !menu.__petSkillTimerHooked) {
        menu.__petSkillTimerHooked = true;
        menu.addEventListener('click', (e) => {
          const btn = e.target && e.target.closest ? e.target.closest('button') : null;
          if (btn && btn.dataset && btn.dataset.act === 'pomodoro' && mgr.active) {
            e.stopImmediatePropagation();
            if (typeof closeMenu === 'function') closeMenu();
            mgr.stop('已手动结束倒计时~', null, false);
          }
        }, true);
      }
      window.__petSkillTimer = mgr;
    }
    window.__petSkillTimer.start(cfg);
  };
  setTimeout(launch, goRunning ? 240 : 0);
})();
"@
}

function Invoke-PetJs([string]$Code) {
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Code)
        $req = [System.Net.HttpWebRequest]::Create("$BaseUrl/js")
        $req.Method = "POST"
        $req.ContentType = "text/plain; charset=utf-8"
        $req.Timeout = 1500
        $req.ContentLength = $bytes.Length
        $stream = $req.GetRequestStream()
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Close()
        $resp = $req.GetResponse()
        $codeInt = [int]$resp.StatusCode
        $resp.Close()
        return ($codeInt -eq 200)
    } catch {
        return $false
    }
}

function Find-PetExe {
    if ($Exe -and (Test-Path -LiteralPath $Exe -PathType Leaf)) { return $Exe }
    if ($env:DAFEIYU_PET_EXE -and (Test-Path -LiteralPath $env:DAFEIYU_PET_EXE -PathType Leaf)) { return $env:DAFEIYU_PET_EXE }

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($pname in @("dafeiyu-pet", "dafeiyu-pet-lite")) {
        $rp = Get-Process -Name $pname -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($rp -and $rp.Path) { $candidates.Add($rp.Path) }
    }

    $localApp = [Environment]::GetFolderPath("LocalApplicationData")
    if ($Lite) {
        $candidates.Add((Join-Path $localApp "Programs\大肥鱼桌宠 Lite\dafeiyu-pet-lite.exe"))
        $candidates.Add((Join-Path $localApp "Programs\大肥鱼桌宠 Lite\dafeiyu-pet.exe"))
        $candidates.Add((Join-Path $localApp "Programs\大肥鱼桌宠\dafeiyu-pet.exe"))
    } else {
        $candidates.Add((Join-Path $localApp "Programs\大肥鱼桌宠\dafeiyu-pet.exe"))
        $candidates.Add((Join-Path $localApp "Programs\大肥鱼桌宠 Lite\dafeiyu-pet-lite.exe"))
        $candidates.Add((Join-Path $localApp "Programs\大肥鱼桌宠 Lite\dafeiyu-pet.exe"))
    }

    $order = if ($Lite) { @("dafeiyu-pet-lite.exe", "dafeiyu-pet.exe") } else { @("dafeiyu-pet.exe", "dafeiyu-pet-lite.exe") }
    foreach ($root in @("HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*")) {
        Get-ItemProperty -Path $root -ErrorAction SilentlyContinue | Where-Object {
            $_.DisplayName -match "大肥鱼|dafeiyu" -or $_.PSChildName -match "dafeiyu|shenliuyu"
        } | ForEach-Object {
            foreach ($prop in @($_.InstallLocation, $_.UninstallString)) {
                if ($prop) {
                    $clean = ($prop -replace '"', "").Trim()
                    $dir = if (Test-Path -LiteralPath $clean -PathType Container) { $clean } else { Split-Path -Parent $clean }
                    if ($dir) {
                        foreach ($n in $order) { $candidates.Add((Join-Path $dir $n)) }
                    }
                }
            }
        }
    }

    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c -PathType Leaf)) { return $c }
    }
    return $null
}

function Install-Pet {
    $existing = Find-PetExe
    $cacheDir = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "dafeiyu-pet-skill"
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
    $marker = Join-Path $cacheDir "install-state.json"

    if ($existing) {
        if (-not (Test-Path -LiteralPath $marker)) {
            @{ installed = $true; exe = $existing; method = "preexisting" } | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
        }
        return $existing
    }

    $tag = $FallbackTag
    $verNum = $FallbackTag.TrimStart("v")
    $assetName = if ($Lite) { "dafeiyu-pet-lite-$verNum-setup.exe" } else { "dafeiyu-pet-$verNum-setup.exe" }
    $dlUrls = New-Object System.Collections.Generic.List[string]
    $shaUrls = New-Object System.Collections.Generic.List[string]

    foreach ($api in @($ReleaseApi, "$MirrorPrefix$ReleaseApi", $MirrorReleaseApi, "$MirrorPrefix$MirrorReleaseApi")) {
        try {
            $meta = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "dafeiyu-pet-skill/1.0" } -TimeoutSec 10
            foreach ($a in $meta.assets) {
                $burl = [string]$a.browser_download_url
                if (-not $burl) { continue }
                if ($a.name -eq "SHA256SUMS.txt") {
                    if (-not $shaUrls.Contains($burl)) { $shaUrls.Add($burl) }
                } elseif ($a.name -like "*-setup.exe") {
                    $isLiteAsset = ($a.name -like "*-lite-*")
                    if ($isLiteAsset -eq [bool]$Lite) {
                        if ($dlUrls.Count -eq 0) {
                            if ($meta.tag_name) { $tag = [string]$meta.tag_name }
                            $assetName = [string]$a.name
                        }
                        if (-not $dlUrls.Contains($burl)) { $dlUrls.Add($burl) }
                    }
                }
            }
            if ($dlUrls.Count -gt 0 -and $api -like "*ihpwhath*") { break }
        } catch { }
    }
    foreach ($fb in @("$FallbackBase/$assetName", "$MirrorRepoBase/$assetName")) {
        if (-not $dlUrls.Contains($fb)) { $dlUrls.Add($fb) }
    }
    foreach ($fs in @("$FallbackBase/SHA256SUMS.txt", "$MirrorRepoBase/SHA256SUMS.txt")) {
        if (-not $shaUrls.Contains($fs)) { $shaUrls.Add($fs) }
    }

    $expectedSha = $null
    foreach ($su in $shaUrls) {
        foreach ($candSha in @($su, "$MirrorPrefix$su")) {
            try {
                $txt = (Invoke-WebRequest -Uri $candSha -UseBasicParsing -TimeoutSec 10).Content
                foreach ($line in ($txt -split "`r?`n")) {
                    $parts = $line.Trim() -split "\s+"
                    if ($parts.Length -ge 2 -and $parts[1].TrimStart("*") -eq $assetName) {
                        $expectedSha = $parts[0].ToLowerInvariant()
                        break
                    }
                }
                if ($expectedSha) { break }
            } catch { }
        }
        if ($expectedSha) { break }
    }

    $expanded = New-Object System.Collections.Generic.List[string]
    foreach ($u in $dlUrls) {
        if (-not $expanded.Contains($u)) { $expanded.Add($u) }
        if ($u -and -not $u.StartsWith($MirrorPrefix)) {
            $px = "$MirrorPrefix$u"
            if (-not $expanded.Contains($px)) { $expanded.Add($px) }
        }
    }

    $tmpSetup = Join-Path ([IO.Path]::GetTempPath()) $assetName
    $usedUrl = $null
    try {
        foreach ($cand in $expanded) {
            try {
                if (-not $Quiet) { Write-Host "[dafeiyu-pet] Downloading $cand ..." }
                Invoke-WebRequest -Uri $cand -OutFile $tmpSetup -UseBasicParsing -TimeoutSec 120
                if ((Test-Path -LiteralPath $tmpSetup) -and ((Get-Item -LiteralPath $tmpSetup).Length -gt 1000000)) {
                    $usedUrl = $cand
                    break
                }
            } catch { }
        }
        if (-not $usedUrl) { throw "Failed to download installer $assetName" }

        if ($expectedSha) {
            $actualSha = (Get-FileHash -LiteralPath $tmpSetup -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualSha -ne $expectedSha) {
                throw "SHA-256 mismatch: expected $expectedSha, got $actualSha"
            }
        }

        $proc = Start-Process -FilePath $tmpSetup -ArgumentList "/S" -Wait -PassThru
        if ($proc.ExitCode -ne 0) { throw "Installer exited with code $($proc.ExitCode)" }
    } finally {
        if (Test-Path -LiteralPath $tmpSetup) { Remove-Item -LiteralPath $tmpSetup -Force -ErrorAction SilentlyContinue }
    }

    $installed = Find-PetExe
    if (-not $installed) { throw "Installer finished but dafeiyu-pet.exe was not found." }
    @{
        installed = $true
        version = $tag
        variant = if ($Lite) { "lite" } else { "full" }
        exe = $installed
        sourceUrl = $usedUrl
        installedAt = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    } | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
    return $installed
}

function Ensure-DebugPet([switch]$AllowInstall) {
    $st = Get-PetState
    if ($null -ne $st) { return $st }

    $exePath = Find-PetExe
    if (-not $exePath -and $AllowInstall) { $exePath = Install-Pet }
    if (-not $exePath) { return $null }

    foreach ($pname in @("dafeiyu-pet", "dafeiyu-pet-lite")) {
        $procs = Get-Process -Name $pname -ErrorAction SilentlyContinue
        if ($procs) {
            foreach ($p in $procs) { $p.CloseMainWindow() | Out-Null }
            $sw = [Diagnostics.Stopwatch]::StartNew()
            while ($sw.ElapsedMilliseconds -lt 2500) {
                if (-not (Get-Process -Name $pname -ErrorAction SilentlyContinue)) { break }
                Start-Sleep -Milliseconds 150
            }
            $left = Get-Process -Name $pname -ErrorAction SilentlyContinue
            if ($left) {
                $left | Stop-Process -Force
                Start-Sleep -Milliseconds 400
            }
        }
    }

    Start-Process -FilePath $exePath -ArgumentList "--dev-debug" | Out-Null
    $sw2 = [Diagnostics.Stopwatch]::StartNew()
    while ($sw2.ElapsedMilliseconds -lt 8000) {
        Start-Sleep -Milliseconds 350
        $st = Get-PetState
        if ($null -ne $st -and $st.petInit) { return $st }
    }
    return (Get-PetState)
}

function Set-AutostartConfig([bool]$Enable) {
    if ($null -ne (Get-PetState)) {
        Invoke-PetJs "if (typeof applyAutoStart === 'function') applyAutoStart('0', true);" | Out-Null
        Start-Sleep -Milliseconds 400
    }
    $startupDir = [Environment]::GetFolderPath("Startup")
    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    foreach ($vn in @("大肥鱼桌宠", "大肥鱼桌宠 Lite", "com.dafeiyu.desktop-pet")) {
        Remove-ItemProperty -Path $runKey -Name $vn -ErrorAction SilentlyContinue
    }
    foreach ($tn in @("大肥鱼桌宠", "大肥鱼桌宠 Lite")) {
        & schtasks.exe /Delete /TN $tn /F 2>$null | Out-Null
    }

    $roaming = [Environment]::GetFolderPath("ApplicationData")
    foreach ($dn in @("dafeiyu-desktop-pet", "dafeiyu-desktop-pet-lite")) {
        $sf = Join-Path $roaming "$dn\dafeiyu-state.json"
        if (Test-Path -LiteralPath $sf) {
            try {
                $obj = Get-Content -LiteralPath $sf -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($null -ne $obj.autoStart -and $obj.autoStart -eq $true) {
                    $obj.autoStart = $false
                    if ($null -ne $obj.highPriority) { $obj.highPriority = $false }
                    $obj | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $sf -Encoding UTF8
                }
            } catch { }
        }
    }

    if (-not $Enable) {
        foreach ($ln in @("大肥鱼桌宠.lnk", "大肥鱼桌宠 Lite.lnk")) {
            $lp = Join-Path $startupDir $ln
            if (Test-Path -LiteralPath $lp) { Remove-Item -LiteralPath $lp -Force }
        }
        return "autostart_removed"
    }

    $exePath = Find-PetExe
    if (-not $exePath) { throw "dafeiyu-pet.exe not found; run with -Install first." }
    $lnkFile = if ($exePath -match "lite") { "大肥鱼桌宠 Lite.lnk" } else { "大肥鱼桌宠.lnk" }
    $lnkPath = Join-Path $startupDir $lnkFile
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnkPath)
    $sc.TargetPath = $exePath
    $sc.Arguments = "--dev-debug"
    $sc.WorkingDirectory = Split-Path -Parent $exePath
    $sc.Description = "大肥鱼桌宠 (--dev-debug)"
    $sc.Save()
    return $lnkPath
}

if ($Doctor) {
    $st = Get-PetState
    $exePath = Find-PetExe
    $wv2 = $false
    foreach ($k in @(
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$WebView2Guid",
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$WebView2Guid",
        "HKCU:\Software\Microsoft\EdgeUpdate\Clients\$WebView2Guid"
    )) {
        if (Test-Path $k) {
            $v = (Get-ItemProperty $k -ErrorAction SilentlyContinue).pv
            if ($v) { $wv2 = $v; break }
        }
    }
    $procs = @(Get-CimInstance Win32_Process -Filter "Name = 'dafeiyu-pet.exe' or Name = 'dafeiyu-pet-lite.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        @{ pid = $_.ProcessId; name = $_.Name; cmd = $_.CommandLine }
    })
    $startupDir = [Environment]::GetFolderPath("Startup")
    $lnks = @(Get-ChildItem -LiteralPath $startupDir -Filter "*大肥鱼*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    @{
        environment = "windows-powershell"
        installedExe = $exePath
        online = ($null -ne $st)
        webview2Version = $wv2
        runningProcesses = $procs
        startupShortcuts = $lnks
        stateSummary = if ($st) { @{ variant = $st.variant; petInit = $st.petInit; hidden = $st.hidden; fsHidden = $st.fsHidden; pomoRunning = $st.pomoRunning } } else { $null }
    } | ConvertTo-Json -Depth 4
    exit 0
}

if ($SetupAutostart) {
    if ($Install -and -not (Find-PetExe)) { Install-Pet | Out-Null }
    $resPath = Set-AutostartConfig -Enable $true
    if (-not $Quiet) { Write-Output $resPath }
    if ($Ensure) { Ensure-DebugPet | Out-Null }
    exit 0
}

if ($RemoveAutostart) {
    $resMsg = Set-AutostartConfig -Enable $false
    if (-not $Quiet) { Write-Output $resMsg }
    exit 0
}

if ($Install) {
    $inst = Install-Pet
    if (-not $Quiet) { Write-Output "installed: $inst" }
    if (-not $Ensure -and -not $Action -and -not $Say -and -not $RawJs -and -not $Status) { exit 0 }
}

$state = if ($Ensure -or $Install) { Ensure-DebugPet -AllowInstall:$Install } else { Get-PetState }

if ($Status) {
    if ($null -eq $state) {
        if (-not $Quiet) { Write-Output "offline" }
        if ($Strict -or $Ensure) { exit 1 } else { exit 0 }
    }
    $state | ConvertTo-Json -Compress -Depth 4
    exit 0
}

if ($null -eq $state) {
    if (-not $Quiet) { Write-Output "pet debug server offline (run with -Ensure, or -Install -Ensure on first setup)" }
    if ($Strict -or $Ensure -or $Install) { exit 1 } else { exit 0 }
}

if (-not $Force -and ($state.hidden -or $state.fsHidden)) {
    if (-not $Quiet) { Write-Output "skipped (pet hidden or fullscreen active)" }
    exit 0
}

$hasTimer = [bool]($StopTimer -or $Countdown -or $Work -or $Rest)
if (-not $hasTimer -and -not $Action -and -not $Say -and -not $Character -and -not $ApiAction -and -not $RawJs) {
    if (-not $Quiet) { Write-Output "ready" }
    exit 0
}

if ($RawJs) {
    $js = $RawJs
} elseif ($StopTimer) {
    $sayJson = if ($Say) { $Say | ConvertTo-Json -Compress } else { "null" }
    $actJson = if ($Action) { $Action | ConvertTo-Json -Compress } else { "null" }
    $js = @"
(() => {
  const sayMsg = $sayJson;
  const actName = $actJson;
  if (window.__petSkillTimer && window.__petSkillTimer.active) {
    window.__petSkillTimer.stop(sayMsg, actName, false);
    return;
  }
  if (typeof S !== 'undefined' && S.pomoRunning && typeof api !== 'undefined' && api.action) {
    api.action('pomodoro');
    setTimeout(() => {
      if (actName && typeof playAction === 'function') playAction(actName);
      if (sayMsg && typeof say === 'function') say(sayMsg, 3800);
    }, 160);
    return;
  }
  if (actName && typeof playAction === 'function') playAction(actName);
  if (sayMsg && typeof say === 'function') say(sayMsg, 3500);
})();
"@
} elseif ($Countdown) {
    $sec = ConvertTo-DurationSeconds $Countdown "s"
    $phases = @(@{
        kind = "task"
        sec = $sec
        label = $Label
        icon = if ($Icon) { $Icon } else { "⏳" }
        action = if ($Action) { $Action } else { "写代码" }
        say = $Say
    })
    $js = New-TimerJs -Phases $phases -CycleCount $Cycles -DoneSayText $(if ($DoneSay) { $DoneSay } else { "预估时间到啦~" }) -DoneActName $DoneAction -AnimSecVal $AnimSec
} elseif ($Work -or $Rest) {
    $workSec = if ($Work) { ConvertTo-DurationSeconds $Work "m" } else { 0 }
    $restSec = if ($Rest) { ConvertTo-DurationSeconds $Rest "m" } else { 0 }
    $useNative = $NativePomo -or ($workSec -ge 300 -and $workSec -le 7200 -and ($workSec % 60 -eq 0) -and $restSec -eq 0 -and $Cycles -eq 1 -and -not $Label -and -not $Icon)
    if ($useNative -and $workSec -gt 0) {
        $wMin = [Math]::Max(5, [Math]::Min(120, [int]($workSec / 60)))
        $sayLine = if ($Say) { "if (typeof say === 'function') say($($Say | ConvertTo-Json -Compress), 3500);" } else { "" }
        $animLine = if ($AnimSec -gt 0) { "if (typeof applyPomoAnimSec === 'function') applyPomoAnimSec($AnimSec, true);" } else { "" }
        $js = @"
(() => {
  if (window.__petSkillTimer && window.__petSkillTimer.active) { window.__petSkillTimer.stop(null, null, true); }
  if (typeof wake === 'function') wake();
  if (typeof applyPomoMin === 'function') applyPomoMin($wMin, true);
  $animLine
  const startNow = () => {
    if (typeof S !== 'undefined' && !S.pomoRunning && typeof api !== 'undefined' && api.action) { api.action('pomodoro'); }
    $sayLine
  };
  if (typeof S !== 'undefined' && S.pomoRunning && typeof api !== 'undefined' && api.action) {
    api.action('pomodoro'); setTimeout(startNow, 260);
  } else { setTimeout(startNow, 80); }
})();
"@
    } else {
        $phases = New-Object System.Collections.Generic.List[object]
        if ($workSec -gt 0) {
            $phases.Add(@{
                kind = "work"
                sec = $workSec
                label = if ($Label) { $Label } elseif ($restSec -gt 0) { "工作" } else { "" }
                icon = if ($Icon) { $Icon } else { "🍅" }
                action = if ($Action) { $Action } else { "写代码" }
                say = if ($Say) { $Say } else { "开始专注 $([Math]::Max(1, [int]($workSec / 60))) 分钟~" }
            })
        }
        if ($restSec -gt 0) {
            $rLbl = if ($restSec -ge 60) { "$([Math]::Max(1, [int]($restSec / 60))) 分钟" } else { "$restSec 秒" }
            $phases.Add(@{
                kind = "rest"
                sec = $restSec
                label = if ($workSec -gt 0 -or -not $Label) { "休息" } else { $Label }
                icon = "☕"
                action = "悠闲哼歌"
                say = "工作结束，休息 $rLbl啦~"
            })
        }
        $js = New-TimerJs -Phases $phases.ToArray() -CycleCount $Cycles -DoneSayText $(if ($DoneSay) { $DoneSay } else { "本轮工作与休息完成啦~" }) -DoneActName $DoneAction -AnimSecVal $AnimSec
    }
} else {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("(() => {")
    if (-not $Force) { $lines.Add("  if (typeof S !== 'undefined' && S.awake === false) return;") }
    if ($Character) {
        $cJson = $Character | ConvertTo-Json -Compress
        $lines.Add("  if (typeof applyCharacter === 'function') applyCharacter($cJson, true);")
    }
    if ($ApiAction) {
        $aJson = $ApiAction | ConvertTo-Json -Compress
        $lines.Add("  if (typeof api !== 'undefined' && api.action) api.action($aJson);")
    }
    if ($Action) {
        $actJson = $Action | ConvertTo-Json -Compress
        $lines.Add("  if (typeof playAction === 'function') {")
        $lines.Add("    const act = $actJson;")
        $lines.Add("    const ch = typeof charNow === 'function' ? charNow() : { kind: 'video' };")
        $lines.Add("    if (ch.kind !== 'video' || typeof HAS === 'undefined' || HAS.has(act)) { playAction(act); }")
        $lines.Add("    else if (typeof ANIM !== 'undefined' && Array.isArray(ANIM.clicks) && ANIM.clicks.length) { playAction(ANIM.clicks[0]); }")
        $lines.Add("  }")
    }
    if ($Say) {
        $sayJson = $Say | ConvertTo-Json -Compress
        $lines.Add("  if (typeof say === 'function') say($sayJson, $Ms);")
    }
    $lines.Add("})();")
    $js = $lines -join "`n"
}

$ok = Invoke-PetJs $js
if (-not $Quiet) { Write-Output ($(if ($ok) { "ok" } else { "failed" })) }
if ($ok) { exit 0 } elseif ($Strict -or $Ensure -or $Install) { exit 1 } else { exit 0 }
