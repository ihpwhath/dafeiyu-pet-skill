#!/usr/bin/env python3
"""Cross-environment controller and first-run installer for 大肥鱼桌宠 (dafeiyu-pet.exe).

Supports:
- Windows native Python
- Git Bash / MSYS2 / Cygwin on Windows
- WSL2 Mirrored networking (direct http://127.0.0.1:9336)
- WSL2 NAT networking (automatic fallback via Windows curl.exe)
- First-run auto-install from GitHub Releases (+ gh-proxy.org fallback & SHA-256 check)
- Autostart migration for both v1.4.x (HKCU Run) and v1.5.x+ (Scheduled Task)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:9336"
GITHUB_RELEASE_API = "https://api.github.com/repos/shenliuyu18/dafeiyu-pet/releases/latest"
MIRROR_RELEASE_API = "https://api.github.com/repos/ihpwhath/dafeiyu-pet/releases/latest"
GITHUB_MIRROR_PREFIX = "https://gh-proxy.org/"
FALLBACK_VERSION = "v1.5.2"
FALLBACK_DIRECT_BASE = f"https://github.com/shenliuyu18/dafeiyu-pet/releases/download/{FALLBACK_VERSION}"
MIRROR_DIRECT_BASE = f"https://github.com/ihpwhath/dafeiyu-pet/releases/download/{FALLBACK_VERSION}"
WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def is_windows_native() -> bool:
    return os.name == "nt"


def is_msys() -> bool:
    return (
        os.name != "nt"
        and (
            sys.platform in ("msys", "cygwin")
            or bool(os.environ.get("MSYSTEM"))
            or "cygwin" in platform.system().lower()
            or "mingw" in platform.system().lower()
        )
    )


def is_wsl() -> bool:
    if os.name == "nt" or is_msys():
        return False
    rel = platform.release().lower()
    return "microsoft" in rel or "wsl" in rel or Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists()


def env_kind() -> str:
    if is_windows_native():
        return "windows-native"
    if is_msys():
        return "msys-gitbash"
    if is_wsl():
        return "wsl2"
    return sys.platform


def find_powershell() -> str | None:
    if is_windows_native():
        return shutil.which("powershell.exe") or shutil.which("pwsh.exe") or "powershell.exe"
    if is_msys():
        for candidate in (
            shutil.which("powershell.exe"),
            shutil.which("powershell"),
            "/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            shutil.which("pwsh.exe"),
        ):
            if candidate and Path(candidate).exists():
                return candidate
    if is_wsl():
        for candidate in (
            shutil.which("powershell.exe"),
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            shutil.which("pwsh.exe"),
            "/mnt/c/Program Files/PowerShell/7/pwsh.exe",
        ):
            if candidate and Path(candidate).exists():
                return candidate
    return None


def find_win_curl() -> str | None:
    if is_windows_native():
        return shutil.which("curl.exe")
    if is_msys():
        for candidate in (
            shutil.which("curl.exe"),
            "/c/Windows/System32/curl.exe",
        ):
            if candidate and Path(candidate).exists():
                return candidate
    if is_wsl():
        for candidate in (
            shutil.which("curl.exe"),
            "/mnt/c/Windows/System32/curl.exe",
        ):
            if candidate and Path(candidate).exists():
                return candidate
    return None


def to_win_path(posix_path: Path) -> str:
    s = str(posix_path)
    if is_windows_native():
        return s
    if is_msys():
        cyg = shutil.which("cygpath")
        if cyg:
            return subprocess.run([cyg, "-w", s], capture_output=True, text=True, check=True).stdout.strip()
        if len(s) >= 3 and s[0] == "/" and s[2] == "/":
            return f"{s[1].upper()}:\\{s[3:].replace('/', '\\')}"
        return s
    if is_wsl():
        return subprocess.run(["wslpath", "-w", s], capture_output=True, text=True, check=True).stdout.strip()
    return s


def to_posix_path(win_path: str) -> Path:
    if is_windows_native():
        return Path(win_path)
    if is_msys():
        cyg = shutil.which("cygpath")
        if cyg:
            out = subprocess.run([cyg, "-u", win_path], capture_output=True, text=True, check=True).stdout.strip()
            return Path(out)
        if len(win_path) >= 2 and win_path[1] == ":":
            drive = win_path[0].lower()
            rest = win_path[2:].replace("\\", "/")
            return Path(f"/{drive}{rest}")
        return Path(win_path)
    if is_wsl():
        out = subprocess.run(["wslpath", "-u", win_path], capture_output=True, text=True, check=True).stdout.strip()
        return Path(out)
    return Path(win_path)


def run_powershell(script: str, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    ps_bin = find_powershell()
    if not ps_bin:
        raise RuntimeError("powershell.exe not found; Windows, Git Bash, or WSL2 interop is required.")
    wrapped = (
        "$OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        + script
    )
    encoded = base64.b64encode(wrapped.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        [ps_bin, "-NoProfile", "-NonInteractive", "-InputFormat", "None", "-EncodedCommand", encoded],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def cache_dir() -> Path:
    if is_windows_native():
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    d = base / "dafeiyu-pet-skill"
    d.mkdir(parents=True, exist_ok=True)
    return d


def install_marker_path() -> Path:
    return cache_dir() / "install-state.json"


def _win_curl_request(method: str, path: str, body: str | None = None, timeout: float = 1.5) -> tuple[int, str] | None:
    curl_exe = find_win_curl()
    if not curl_exe:
        return None
    cmd = [
        curl_exe,
        "-sS",
        "--max-time",
        str(max(1, int(round(timeout)))),
        "-w",
        "\n%{http_code}",
        "-X",
        method,
        f"{BASE_URL}{path}",
    ]
    stdin_data = None
    if body is not None:
        cmd.extend(["-H", "Content-Type: text/plain; charset=utf-8", "--data-binary", "@-"])
        stdin_data = body.encode("utf-8")
    try:
        res = subprocess.run(cmd, input=stdin_data, capture_output=True, timeout=timeout + 2.0, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    out = res.stdout.decode("utf-8", errors="replace")
    parts = out.rsplit("\n", 1)
    if len(parts) != 2:
        return None
    try:
        code = int(parts[1].strip())
    except ValueError:
        return None
    return code, parts[0]


def get_state(timeout: float = 0.45, force_win_bridge: bool = False) -> dict | None:
    """Fetch JSON from /state. Falls back to Windows curl.exe under WSL2 NAT mode."""
    if not force_win_bridge:
        req = urllib.request.Request(f"{BASE_URL}/state", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass

    if is_wsl() or force_win_bridge:
        bridged = _win_curl_request("GET", "/state", timeout=max(1.0, timeout))
        if bridged and bridged[0] == 200:
            try:
                return json.loads(bridged[1])
            except ValueError:
                return None
    return None


def post_js(js_code: str, timeout: float = 1.0, force_win_bridge: bool = False) -> bool:
    """Execute JS in the pet WebView2 window via POST /js."""
    if not force_win_bridge:
        req = urllib.request.Request(
            f"{BASE_URL}/js",
            data=js_code.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

    if is_wsl() or force_win_bridge:
        bridged = _win_curl_request("POST", "/js", body=js_code, timeout=max(1.5, timeout))
        return bool(bridged and bridged[0] == 200)
    return False


def find_pet_exe(explicit_exe: str | None = None, prefer_lite: bool = False) -> str | None:
    """Locate installed dafeiyu-pet.exe (or lite) dynamically across any Windows user profile."""
    env_exe = explicit_exe or os.environ.get("DAFEIYU_PET_EXE")
    if env_exe:
        return env_exe

    order_names = (
        ["dafeiyu-pet-lite.exe", "dafeiyu-pet.exe"]
        if prefer_lite
        else ["dafeiyu-pet.exe", "dafeiyu-pet-lite.exe"]
    )
    ps_script = f"""
$preferLite = {'$true' if prefer_lite else '$false'}
$candidates = New-Object System.Collections.Generic.List[string]

foreach ($pname in @('dafeiyu-pet', 'dafeiyu-pet-lite')) {{
    $rp = Get-Process -Name $pname -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($rp -and $rp.Path) {{ $candidates.Add($rp.Path) }}
}}

$localApp = [Environment]::GetFolderPath('LocalApplicationData')
$stdPaths = if ($preferLite) {{
    @(
        (Join-Path $localApp 'Programs\\大肥鱼桌宠 Lite\\dafeiyu-pet-lite.exe'),
        (Join-Path $localApp 'Programs\\大肥鱼桌宠 Lite\\dafeiyu-pet.exe'),
        (Join-Path $localApp 'Programs\\大肥鱼桌宠\\dafeiyu-pet.exe')
    )
}} else {{
    @(
        (Join-Path $localApp 'Programs\\大肥鱼桌宠\\dafeiyu-pet.exe'),
        (Join-Path $localApp 'Programs\\大肥鱼桌宠 Lite\\dafeiyu-pet-lite.exe'),
        (Join-Path $localApp 'Programs\\大肥鱼桌宠 Lite\\dafeiyu-pet.exe')
    )
}}
foreach ($p in $stdPaths) {{ $candidates.Add($p) }}

foreach ($root in @('HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*', 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*')) {{
    Get-ItemProperty -Path $root -ErrorAction SilentlyContinue | Where-Object {{
        $_.DisplayName -match '大肥鱼|dafeiyu' -or $_.PSChildName -match 'dafeiyu|shenliuyu'
    }} | ForEach-Object {{
        foreach ($prop in @($_.InstallLocation, $_.UninstallString)) {{
            if ($prop) {{
                $clean = ($prop -replace '"', '').Trim()
                $dir = if (Test-Path -LiteralPath $clean -PathType Container) {{ $clean }} else {{ Split-Path -Parent $clean }}
                if ($dir) {{
                    foreach ($exeName in @({','.join(repr(n) for n in order_names)})) {{
                        $candidates.Add((Join-Path $dir $exeName))
                    }}
                }}
            }}
        }}
    }}
}}

foreach ($c in $candidates) {{
    if ($c -and (Test-Path -LiteralPath $c -PathType Leaf)) {{
        Write-Output $c
        exit 0
    }}
}}
exit 1
"""
    try:
        res = run_powershell(ps_script, timeout=12.0)
    except RuntimeError:
        return None
    if res.returncode == 0:
        found = res.stdout.strip().splitlines()
        if found:
            return found[0].strip()
    return None


def _http_get_bytes(url: str, timeout: float = 25.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "dafeiyu-pet-skill/1.0",
            "Accept": "application/vnd.github+json,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _download_with_fallback(urls: list[str], dest: Path, timeout: float = 90.0) -> str:
    """Download from ordered URL candidates (upstream direct, gh-proxy, GitHub mirror)."""
    errors: list[str] = []
    expanded: list[str] = []
    for u in urls:
        if u and u not in expanded:
            expanded.append(u)
        if u and not u.startswith(GITHUB_MIRROR_PREFIX):
            proxied = f"{GITHUB_MIRROR_PREFIX}{u}"
            if proxied not in expanded:
                expanded.append(proxied)

    for candidate_url in expanded:
        try:
            req = urllib.request.Request(candidate_url, headers={"User-Agent": "dafeiyu-pet-skill/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as f:
                shutil.copyfileobj(resp, f)
            if dest.exists() and dest.stat().st_size > 1_000_000:
                return candidate_url
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate_url}: {exc}")

        curl_exe = find_win_curl()
        if curl_exe:
            try:
                win_dest = to_win_path(dest)
                res = subprocess.run(
                    [curl_exe, "-fL", "--max-time", str(int(timeout)), "-o", win_dest, candidate_url],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and dest.exists() and dest.stat().st_size > 1_000_000:
                    return candidate_url
                errors.append(f"curl.exe {candidate_url}: exit {res.returncode}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"curl.exe {candidate_url}: {exc}")

    raise RuntimeError("Download failed:\n  " + "\n  ".join(errors))


def _resolve_release_assets(prefer_lite: bool = False) -> tuple[str, str, list[str], str | None]:
    """Return (tag, asset_name, ordered_download_urls, expected_sha256)."""
    tag = FALLBACK_VERSION
    asset_name = (
        f"dafeiyu-pet-lite-{FALLBACK_VERSION.lstrip('v')}-setup.exe"
        if prefer_lite
        else f"dafeiyu-pet-{FALLBACK_VERSION.lstrip('v')}-setup.exe"
    )
    download_urls: list[str] = []
    sha_urls: list[str] = []

    for api_url in (
        GITHUB_RELEASE_API,
        f"{GITHUB_MIRROR_PREFIX}{GITHUB_RELEASE_API}",
        MIRROR_RELEASE_API,
        f"{GITHUB_MIRROR_PREFIX}{MIRROR_RELEASE_API}",
    ):
        try:
            meta = json.loads(_http_get_bytes(api_url, timeout=10.0).decode("utf-8"))
            found_tag = str(meta.get("tag_name") or tag)
            assets = meta.get("assets") or []
            for a in assets:
                name = str(a.get("name") or "")
                burl = str(a.get("browser_download_url") or "")
                if not burl:
                    continue
                if name == "SHA256SUMS.txt":
                    if burl not in sha_urls:
                        sha_urls.append(burl)
                elif name.endswith("-setup.exe"):
                    is_lite_asset = "-lite-" in name
                    if is_lite_asset == prefer_lite:
                        if not download_urls:
                            tag = found_tag
                            asset_name = name
                        if burl not in download_urls:
                            download_urls.append(burl)
            if download_urls and "ihpwhath/dafeiyu-pet" in api_url:
                break
        except Exception:  # noqa: BLE001
            continue

    for fallback_url in (f"{FALLBACK_DIRECT_BASE}/{asset_name}", f"{MIRROR_DIRECT_BASE}/{asset_name}"):
        if fallback_url not in download_urls:
            download_urls.append(fallback_url)
    for fallback_sha in (f"{FALLBACK_DIRECT_BASE}/SHA256SUMS.txt", f"{MIRROR_DIRECT_BASE}/SHA256SUMS.txt"):
        if fallback_sha not in sha_urls:
            sha_urls.append(fallback_sha)

    expected_sha: str | None = None
    for su in sha_urls:
        for cand in (su, f"{GITHUB_MIRROR_PREFIX}{su}"):
            try:
                text = _http_get_bytes(cand, timeout=10.0).decode("utf-8", errors="replace")
                for line in text.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1].lstrip("*") == asset_name:
                        expected_sha = parts[0].lower()
                        break
                if expected_sha:
                    break
            except Exception:  # noqa: BLE001
                continue
        if expected_sha:
            break

    return tag, asset_name, download_urls, expected_sha


def install_pet(prefer_lite: bool = False, quiet: bool = False) -> str:
    """Download, verify SHA-256, and silently install 大肥鱼桌宠 on first run."""
    existing = find_pet_exe(prefer_lite=prefer_lite)
    if existing:
        marker = install_marker_path()
        if not marker.exists():
            marker.write_text(
                json.dumps({"installed": True, "exe": existing, "method": "preexisting"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return existing

    if not find_powershell():
        raise RuntimeError("Windows environment (native, Git Bash, or WSL2) is required to install dafeiyu-pet.exe.")

    tag, asset_name, urls, expected_sha = _resolve_release_assets(prefer_lite=prefer_lite)
    if not quiet:
        print(f"[dafeiyu-pet] First-run install: fetching {asset_name} ({tag})...", file=sys.stderr)

    if is_windows_native():
        dl_dir = Path(os.environ.get("TEMP") or cache_dir())
        installer_path = dl_dir / asset_name
        win_installer_path = str(installer_path)
    else:
        win_temp = run_powershell("[IO.Path]::GetTempPath()", timeout=8.0).stdout.strip()
        installer_path = to_posix_path(win_temp) / asset_name
        win_installer_path = str(Path(win_temp) / asset_name).replace("/", "\\")

    try:
        used_url = _download_with_fallback(urls, installer_path, timeout=120.0)
        if expected_sha:
            h = hashlib.sha256()
            with installer_path.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            actual_sha = h.hexdigest().lower()
            if actual_sha != expected_sha:
                raise RuntimeError(f"SHA-256 mismatch for {asset_name}: expected {expected_sha}, got {actual_sha}")

        if not quiet:
            print(f"[dafeiyu-pet] Installing silently via {win_installer_path} /S ...", file=sys.stderr)
        ps_install = f"""
$p = Start-Process -FilePath "{win_installer_path}" -ArgumentList "/S" -Wait -PassThru
exit $p.ExitCode
"""
        res = run_powershell(ps_install, timeout=120.0)
        if res.returncode != 0:
            raise RuntimeError(f"Installer exited with code {res.returncode}: {res.stderr.strip()}")
    finally:
        if installer_path.exists():
            try:
                installer_path.unlink()
            except OSError:
                pass

    installed_exe = find_pet_exe(prefer_lite=prefer_lite)
    if not installed_exe:
        raise RuntimeError("Installer finished, but dafeiyu-pet.exe was not found in expected install paths.")

    install_marker_path().write_text(
        json.dumps(
            {
                "installed": True,
                "version": tag,
                "variant": "lite" if prefer_lite else "full",
                "exe": installed_exe,
                "sourceUrl": used_url,
                "installedAt": int(time.time()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return installed_exe


def ensure_debug_pet(
    explicit_exe: str | None = None,
    prefer_lite: bool = False,
    allow_install: bool = False,
    wait_sec: float = 8.0,
    quiet: bool = False,
) -> dict | None:
    """Ensure dafeiyu-pet is running with --dev-debug and /state responds."""
    state = get_state(timeout=0.45)
    if state is not None:
        return state

    exe_path = find_pet_exe(explicit_exe=explicit_exe, prefer_lite=prefer_lite)
    if not exe_path and allow_install:
        exe_path = install_pet(prefer_lite=prefer_lite, quiet=quiet)
    if not exe_path:
        return None

    ps_launch = f"""
$exePath = "{exe_path}"
if (-not (Test-Path -LiteralPath $exePath)) {{
    Write-Error "Executable not found: $exePath"
    exit 1
}}
foreach ($pname in @('dafeiyu-pet', 'dafeiyu-pet-lite')) {{
    $procs = Get-Process -Name $pname -ErrorAction SilentlyContinue
    if ($procs) {{
        foreach ($p in $procs) {{ $p.CloseMainWindow() | Out-Null }}
        $sw = [Diagnostics.Stopwatch]::StartNew()
        while ($sw.ElapsedMilliseconds -lt 2500) {{
            if (-not (Get-Process -Name $pname -ErrorAction SilentlyContinue)) {{ break }}
            Start-Sleep -Milliseconds 150
        }}
        $left = Get-Process -Name $pname -ErrorAction SilentlyContinue
        if ($left) {{
            $left | Stop-Process -Force
            Start-Sleep -Milliseconds 400
        }}
    }}
}}
Start-Process -FilePath $exePath -ArgumentList "--dev-debug" | Out-Null
"""
    res = run_powershell(ps_launch, timeout=20.0)
    if res.returncode != 0:
        return None

    deadline = time.monotonic() + wait_sec
    while time.monotonic() < deadline:
        time.sleep(0.35)
        state = get_state(timeout=0.6)
        if state is not None and state.get("petInit"):
            return state
    return get_state(timeout=0.6)


def setup_autostart(enable: bool = True, explicit_exe: str | None = None, prefer_lite: bool = False) -> str:
    """Configure Windows Startup .lnk with --dev-debug and clean conflicting Run/Scheduled Task entries."""
    if get_state(timeout=0.4) is not None:
        post_js("if (typeof applyAutoStart === 'function') applyAutoStart('0', true);", timeout=1.0)
        time.sleep(0.4)

    exe_path = find_pet_exe(explicit_exe=explicit_exe, prefer_lite=prefer_lite)
    if enable and not exe_path:
        raise RuntimeError("dafeiyu-pet.exe not found; pass --install first.")

    ps_script = f"""
$enable = {'$true' if enable else '$false'}
$exePath = "{exe_path or ''}"
$startupDir = [Environment]::GetFolderPath('Startup')
$lnkNames = @('大肥鱼桌宠.lnk', '大肥鱼桌宠 Lite.lnk')

$runKey = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run'
foreach ($valName in @('大肥鱼桌宠', '大肥鱼桌宠 Lite', 'com.dafeiyu.desktop-pet')) {{
    Remove-ItemProperty -Path $runKey -Name $valName -ErrorAction SilentlyContinue
}}
foreach ($taskName in @('大肥鱼桌宠', '大肥鱼桌宠 Lite')) {{
    & schtasks.exe /Delete /TN $taskName /F 2>$null | Out-Null
}}

$roaming = [Environment]::GetFolderPath('ApplicationData')
foreach ($dirName in @('dafeiyu-desktop-pet', 'dafeiyu-desktop-pet-lite')) {{
    $sf = Join-Path $roaming "$dirName\\dafeiyu-state.json"
    if (Test-Path -LiteralPath $sf) {{
        try {{
            $obj = Get-Content -LiteralPath $sf -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($null -ne $obj.autoStart -and $obj.autoStart -eq $true) {{
                $obj.autoStart = $false
                if ($null -ne $obj.highPriority) {{ $obj.highPriority = $false }}
                $obj | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $sf -Encoding UTF8
            }}
        }} catch {{}}
    }}
}}

if (-not $enable) {{
    foreach ($ln in $lnkNames) {{
        $lp = Join-Path $startupDir $ln
        if (Test-Path -LiteralPath $lp) {{ Remove-Item -LiteralPath $lp -Force }}
    }}
    Write-Output "autostart_removed"
    exit 0
}}

$isLite = ($exePath -match 'lite')
$lnkFile = if ($isLite) {{ '大肥鱼桌宠 Lite.lnk' }} else {{ '大肥鱼桌宠.lnk' }}
$lnkPath = Join-Path $startupDir $lnkFile
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnkPath)
$sc.TargetPath = $exePath
$sc.Arguments = "--dev-debug"
$sc.WorkingDirectory = Split-Path -Parent $exePath
$sc.Description = "大肥鱼桌宠 (--dev-debug)"
$sc.Save()
Write-Output $lnkPath
"""
    res = run_powershell(ps_script, timeout=15.0)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"Failed with exit code {res.returncode}")
    return res.stdout.strip()


def run_doctor(explicit_exe: str | None = None, prefer_lite: bool = False) -> dict:
    """Collect diagnostic checks for environment, installation, WebView2, networking, and autostart."""
    ek = env_kind()
    ps_bin = find_powershell()
    curl_bin = find_win_curl()
    exe_path = find_pet_exe(explicit_exe=explicit_exe, prefer_lite=prefer_lite)
    direct_state = None
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/state"), timeout=0.4) as r:
            direct_state = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        direct_state = None
    bridge_state = get_state(timeout=1.0, force_win_bridge=True) if is_wsl() else direct_state

    win_diag: dict = {}
    if ps_bin:
        ps = f"""
$startupDir = [Environment]::GetFolderPath('Startup')
$wv2 = $false
foreach ($k in @(
    "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{WEBVIEW2_GUID}",
    "HKLM:\\SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{WEBVIEW2_GUID}",
    "HKCU:\\Software\\Microsoft\\EdgeUpdate\\Clients\\{WEBVIEW2_GUID}"
)) {{
    if (Test-Path $k) {{
        $v = (Get-ItemProperty $k -ErrorAction SilentlyContinue).pv
        if ($v) {{ $wv2 = $v; break }}
    }}
}}

$procs = @(Get-CimInstance Win32_Process -Filter "Name = 'dafeiyu-pet.exe' or Name = 'dafeiyu-pet-lite.exe'" -ErrorAction SilentlyContinue | ForEach-Object {{
    @{{ pid = $_.ProcessId; name = $_.Name; cmd = $_.CommandLine }}
}})

$runEntries = @()
$rk = Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue
foreach ($vn in @('大肥鱼桌宠', '大肥鱼桌宠 Lite', 'com.dafeiyu.desktop-pet')) {{
    if ($rk -and $null -ne $rk.$vn) {{ $runEntries += "$vn=$($rk.$vn)" }}
}}

$tasks = @()
foreach ($tn in @('大肥鱼桌宠', '大肥鱼桌宠 Lite')) {{
    & schtasks.exe /Query /TN $tn 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {{ $tasks += $tn }}
}}

$lnks = @(Get-ChildItem -LiteralPath $startupDir -Filter '*大肥鱼*' -ErrorAction SilentlyContinue | ForEach-Object {{ $_.FullName }})

@{{
    webview2Version = $wv2
    runningProcesses = $procs
    hkcuRunEntries = $runEntries
    scheduledTasks = $tasks
    startupShortcuts = $lnks
}} | ConvertTo-Json -Compress -Depth 4
"""
        res = run_powershell(ps, timeout=12.0)
        if res.returncode == 0 and res.stdout.strip():
            try:
                win_diag = json.loads(res.stdout.strip())
            except ValueError:
                win_diag = {"raw": res.stdout.strip()}

    return {
        "environment": ek,
        "powershell": ps_bin,
        "winCurl": curl_bin,
        "installedExe": exe_path,
        "installMarkerExists": install_marker_path().exists(),
        "directLoopbackOnline": direct_state is not None,
        "winBridgeOnline": bridge_state is not None,
        "wslMode": "mirrored" if (is_wsl() and direct_state is not None) else ("nat-or-offline" if is_wsl() else "n/a"),
        "stateSummary": (
            {
                "variant": (direct_state or bridge_state).get("variant"),
                "petInit": (direct_state or bridge_state).get("petInit"),
                "hidden": (direct_state or bridge_state).get("hidden"),
                "fsHidden": (direct_state or bridge_state).get("fsHidden"),
                "pomoRunning": (direct_state or bridge_state).get("pomoRunning"),
            }
            if (direct_state or bridge_state)
            else None
        ),
        "windows": win_diag,
    }


def parse_duration(spec: str, default_unit: str = "s") -> int:
    """Parse duration like '90', '90s', '40m', '1h30m', or '02:30' into integer seconds."""
    raw = spec.strip().lower()
    if not raw:
        raise ValueError("Empty duration")
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) == 2:
            return max(1, int(round(float(parts[0]) * 60 + float(parts[1]))))
        if len(parts) == 3:
            return max(1, int(round(float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2]))))
    m_plain = re.fullmatch(r"\d+(?:\.\d+)?", raw)
    if m_plain:
        val = float(raw)
        mult = 60.0 if default_unit == "m" else (3600.0 if default_unit == "h" else 1.0)
        return max(1, int(round(val * mult)))
    tokens = re.findall(r"(\d+(?:\.\d+)?)\s*([hms])", raw)
    if not tokens or "".join(f"{v}{u}" for v, u in tokens) != re.sub(r"\s+", "", raw):
        raise ValueError(f"Invalid duration format: {spec!r}")
    total = 0.0
    for val_s, unit in tokens:
        val = float(val_s)
        total += val * (3600.0 if unit == "h" else (60.0 if unit == "m" else 1.0))
    return max(1, int(round(total)))


def build_timer_js(
    phases: list[dict],
    cycles: int = 1,
    done_say: str | None = None,
    done_action: str = "工作状态-雀跃庆祝",
    anim_sec: int | None = None,
) -> str:
    """Build JS for managing countdown / work-rest cycles directly inside the pet WebView2."""
    cfg = {
        "phases": phases,
        "cycles": max(1, int(cycles)),
        "doneSay": done_say or "倒计时完成啦~",
        "doneAction": done_action,
        "animSec": anim_sec,
    }
    cfg_json = json.dumps(cfg, ensure_ascii=False)
    return f"""(() => {{
  const cfg = {cfg_json};
  const goRunning = (typeof S !== 'undefined' && S.pomoRunning && (!window.__petSkillTimer || !window.__petSkillTimer.active));
  if (goRunning && typeof api !== 'undefined' && api.action) {{
    api.action('pomodoro');
  }}
  const launch = () => {{
    if (cfg.animSec && typeof applyPomoAnimSec === 'function') {{
      applyPomoAnimSec(cfg.animSec, false);
    }}
    if (!window.__petSkillTimer) {{
      const chip = document.getElementById('chip');
      const chipTimeEl = document.getElementById('chip-time');
      const tomatoEl = chip ? chip.querySelector('.tomato') : null;
      const menu = document.getElementById('menu');
      if (chip) chip.style.whiteSpace = 'nowrap';
      const mgr = {{
        active: false,
        interval: null,
        restAnimTimer: null,
        phaseIdx: 0,
        cycleIdx: 0,
        endsAt: 0,
        cfg: null,
        stop(sayMsg, actionName, silent) {{
          this.active = false;
          if (this.interval) {{ clearInterval(this.interval); this.interval = null; }}
          if (this.restAnimTimer) {{ clearInterval(this.restAnimTimer); this.restAnimTimer = null; }}
          if (tomatoEl) tomatoEl.textContent = '🍅';
          if (typeof setPomodoro === 'function') setPomodoro({{ running: false, remaining: 0 }});
          if (!silent) {{
            if (actionName && typeof playAction === 'function') playAction(actionName);
            else if (typeof playHappy === 'function') playHappy();
            if (typeof burstHearts === 'function') burstHearts(6);
            if (sayMsg && typeof say === 'function') say(sayMsg, 4200);
          }}
        }},
        render() {{
          if (!this.active || !this.cfg) return;
          const p = this.cfg.phases[this.phaseIdx];
          const remMs = Math.max(0, this.endsAt - Date.now());
          if (tomatoEl) tomatoEl.textContent = p.icon || '🍅';
          const clock = typeof fmtClock === 'function' ? fmtClock(remMs) : `${{Math.ceil(remMs / 1000)}}s`;
          const prefix = p.label ? `${{p.label}} ` : '';
          if (p.kind === 'rest') {{
            if (typeof S !== 'undefined' && S.pomoRunning && typeof setPomodoro === 'function') {{
              setPomodoro({{ running: false, remaining: 0 }});
            }}
            if (typeof stage !== 'undefined') stage.classList.remove('focus');
            if (chip) chip.classList.add('show');
            if (chipTimeEl) chipTimeEl.textContent = prefix + clock;
          }} else {{
            if (typeof setPomodoro === 'function') setPomodoro({{ running: true, remaining: remMs }});
            if (chipTimeEl && prefix) chipTimeEl.textContent = prefix + clock;
          }}
          if (remMs <= 0) this.advance();
        }},
        enterPhase(idx) {{
          this.phaseIdx = idx;
          const p = this.cfg.phases[idx];
          this.endsAt = Date.now() + p.sec * 1000;
          if (this.restAnimTimer) {{ clearInterval(this.restAnimTimer); this.restAnimTimer = null; }}
          if (p.kind === 'rest') {{
            if (typeof setPomodoro === 'function') setPomodoro({{ running: false, remaining: 0 }});
            if (typeof playHappy === 'function') playHappy();
            if (typeof burstHearts === 'function') burstHearts(5);
            if (p.action && typeof playAction === 'function') playAction(p.action);
            if (p.say && typeof say === 'function') say(p.say, 4000);
            this.restAnimTimer = setInterval(() => {{
              if (!this.active) return;
              const cur = this.cfg.phases[this.phaseIdx];
              if (cur && cur.kind === 'rest' && typeof playAction === 'function' && (typeof oneShotPlaying === 'undefined' || !oneShotPlaying)) {{
                playAction(cur.action || '悠闲哼歌');
              }}
            }}, 18000);
          }} else {{
            if (p.action && typeof playAction === 'function') playAction(p.action);
            if (p.say && typeof say === 'function') say(p.say, 3500);
          }}
          this.render();
        }},
        advance() {{
          if (this.phaseIdx + 1 < this.cfg.phases.length) {{
            this.enterPhase(this.phaseIdx + 1);
            return;
          }}
          if (this.cycleIdx + 1 < this.cfg.cycles) {{
            this.cycleIdx++;
            this.enterPhase(0);
            return;
          }}
          const ds = this.cfg.doneSay || '倒计时完成啦~';
          const da = this.cfg.doneAction || '工作状态-雀跃庆祝';
          this.stop(ds, da, false);
        }},
        start(c) {{
          this.stop(null, null, true);
          this.cfg = c;
          this.active = true;
          this.cycleIdx = 0;
          if (typeof wake === 'function') wake();
          this.enterPhase(0);
          this.interval = setInterval(() => this.render(), 500);
        }}
      }};
      if (menu && !menu.__petSkillTimerHooked) {{
        menu.__petSkillTimerHooked = true;
        menu.addEventListener('click', (e) => {{
          const btn = e.target && e.target.closest ? e.target.closest('button') : null;
          if (btn && btn.dataset && btn.dataset.act === 'pomodoro' && mgr.active) {{
            e.stopImmediatePropagation();
            if (typeof closeMenu === 'function') closeMenu();
            mgr.stop('已手动结束倒计时~', null, false);
          }}
        }}, true);
      }}
      window.__petSkillTimer = mgr;
    }}
    window.__petSkillTimer.start(cfg);
  }};
  setTimeout(launch, goRunning ? 240 : 0);
}})();"""


def build_native_pomo_js(work_min: int, anim_sec: int | None, say_text: str | None) -> str:
    """Start the built-in Go Pomodoro timer (5..120 min) via --dev-debug /js."""
    say_line = f"  if (typeof say === 'function') say({json.dumps(say_text, ensure_ascii=False)}, 3500);" if say_text else ""
    anim_line = f"  if (typeof applyPomoAnimSec === 'function') applyPomoAnimSec({int(anim_sec)}, true);" if anim_sec else ""
    return f"""(() => {{
  if (window.__petSkillTimer && window.__petSkillTimer.active) {{
    window.__petSkillTimer.stop(null, null, true);
  }}
  if (typeof wake === 'function') wake();
  if (typeof applyPomoMin === 'function') applyPomoMin({int(work_min)}, true);
{anim_line}
  const startNow = () => {{
    if (typeof S !== 'undefined' && !S.pomoRunning && typeof api !== 'undefined' && api.action) {{
      api.action('pomodoro');
    }}
{say_line}
  }};
  if (typeof S !== 'undefined' && S.pomoRunning && typeof api !== 'undefined' && api.action) {{
    api.action('pomodoro');
    setTimeout(startNow, 260);
  }} else {{
    setTimeout(startNow, 80);
  }}
}})();"""


def build_stop_timer_js(say_text: str | None, action: str | None) -> str:
    """Stop any running countdown or Pomodoro timer cleanly."""
    say_json = json.dumps(say_text, ensure_ascii=False)
    act_json = json.dumps(action, ensure_ascii=False)
    return f"""(() => {{
  const sayMsg = {say_json};
  const actName = {act_json};
  if (window.__petSkillTimer && window.__petSkillTimer.active) {{
    window.__petSkillTimer.stop(sayMsg, actName, false);
    return;
  }}
  if (typeof S !== 'undefined' && S.pomoRunning && typeof api !== 'undefined' && api.action) {{
    api.action('pomodoro');
    setTimeout(() => {{
      if (actName && typeof playAction === 'function') playAction(actName);
      if (sayMsg && typeof say === 'function') say(sayMsg, 3800);
    }}, 160);
    return;
  }}
  if (actName && typeof playAction === 'function') playAction(actName);
  if (sayMsg && typeof say === 'function') say(sayMsg, 3500);
}})();"""


def build_js(
    action: str | None,
    say_text: str | None,
    ms: int,
    character: str | None,
    api_action: str | None,
    force: bool,
) -> str:
    """Build a self-contained, syntax-safe JS snippet for /js."""
    parts: list[str] = ["(() => {"]
    if not force:
        parts.append("  if (typeof S !== 'undefined' && S.awake === false) return;")
    if character:
        parts.append(
            f"  if (typeof applyCharacter === 'function') applyCharacter({json.dumps(character)}, true);"
        )
    if api_action:
        parts.append(
            f"  if (typeof api !== 'undefined' && api.action) api.action({json.dumps(api_action)});"
        )
    if action:
        act_json = json.dumps(action, ensure_ascii=False)
        parts.append(
            f"""  if (typeof playAction === 'function') {{
    const act = {act_json};
    const ch = typeof charNow === 'function' ? charNow() : {{ kind: 'video' }};
    if (ch.kind !== 'video' || typeof HAS === 'undefined' || HAS.has(act)) {{
      playAction(act);
    }} else if (typeof ANIM !== 'undefined' && Array.isArray(ANIM.clicks) && ANIM.clicks.length) {{
      playAction(ANIM.clicks[0]);
    }}
  }}"""
        )
    if say_text:
        say_json = json.dumps(say_text, ensure_ascii=False)
        parts.append(f"  if (typeof say === 'function') say({say_json}, {int(ms)});")
    parts.append("})();")
    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control & auto-install 大肥鱼桌宠 (dafeiyu-pet.exe)")
    parser.add_argument("action", nargs="?", help="Animation/action name, e.g. 螃蟹走路")
    parser.add_argument("--action", dest="action_opt", help="Optional flag alias for action name")
    parser.add_argument("--say", dest="say_text", help="Optional speech bubble text")
    parser.add_argument("--ms", type=int, default=3500, help="Bubble duration in milliseconds")
    parser.add_argument("--character", help="Switch character skin (e.g. v1, v2, v3, v4, v5, gpt, claude, gemini...)")
    parser.add_argument("--api-action", help="Invoke window.pet.action(name), e.g. feed/sleep/pomodoro")
    parser.add_argument("--countdown", help="Start task countdown (e.g. 90s, 3m, 02:30, or bare seconds)")
    parser.add_argument("--work", help="Start work focus timer (bare number = minutes, e.g. 40 or 40m)")
    parser.add_argument("--rest", help="Rest duration after work phase (bare number = minutes, e.g. 10 or 10m)")
    parser.add_argument("--cycles", type=int, default=1, help="Number of work+rest cycles (default: 1)")
    parser.add_argument("--label", help="Short label shown on countdown chip, e.g. 镜像中 / 工作")
    parser.add_argument("--icon", help="Emoji icon shown on countdown chip (default ⏳ or 🍅)")
    parser.add_argument("--anim-sec", type=int, help="Work animation interval in seconds (5..120)")
    parser.add_argument("--done-say", help="Bubble text shown when countdown finishes naturally")
    parser.add_argument("--done-action", default="工作状态-雀跃庆祝", help="Action played when countdown finishes")
    parser.add_argument("--native-pomo", action="store_true", help="Force built-in Go Pomodoro (5..120m)")
    parser.add_argument("--stop-timer", action="store_true", help="Stop active countdown or Pomodoro immediately")
    parser.add_argument("--raw-js", help="Execute raw JS directly on /js")
    parser.add_argument("--exe", help="Explicit path to dafeiyu-pet.exe")
    parser.add_argument("--lite", action="store_true", help="Prefer Lite variant when locating or installing")
    parser.add_argument("--install", action="store_true", help="Download & silently install 大肥鱼桌宠 if missing (first-run)")
    parser.add_argument("--ensure", action="store_true", help="Launch/restart pet in --dev-debug mode if offline")
    parser.add_argument("--setup-autostart", action="store_true", help="Configure Windows Startup .lnk with --dev-debug")
    parser.add_argument("--remove-autostart", action="store_true", help="Remove Windows Startup .lnk and autostart tasks")
    parser.add_argument("--doctor", action="store_true", help="Print full environment & bug diagnostics JSON")
    parser.add_argument("--force", action="store_true", help="Run even if hidden/fsHidden/sleeping")
    parser.add_argument("--status", action="store_true", help="Print /state JSON and exit")
    parser.add_argument("--strict", action="store_true", help="Return non-zero exit code if offline/failed")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    action_name = args.action or args.action_opt

    if args.doctor:
        print(json.dumps(run_doctor(explicit_exe=args.exe, prefer_lite=args.lite), ensure_ascii=False, indent=2))
        return 0

    if args.setup_autostart:
        if args.install and not find_pet_exe(explicit_exe=args.exe, prefer_lite=args.lite):
            install_pet(prefer_lite=args.lite, quiet=args.quiet)
        out = setup_autostart(enable=True, explicit_exe=args.exe, prefer_lite=args.lite)
        if not args.quiet:
            print(out)
        if args.ensure:
            ensure_debug_pet(explicit_exe=args.exe, prefer_lite=args.lite, allow_install=False, quiet=args.quiet)
        return 0

    if args.remove_autostart:
        out = setup_autostart(enable=False, explicit_exe=args.exe, prefer_lite=args.lite)
        if not args.quiet:
            print(out)
        return 0

    if args.install:
        exe = install_pet(prefer_lite=args.lite, quiet=args.quiet)
        if not args.quiet:
            print(f"installed: {exe}")
        if not args.ensure and not action_name and not args.say_text and not args.raw_js and not args.status:
            return 0

    if args.ensure or args.install:
        state = ensure_debug_pet(
            explicit_exe=args.exe,
            prefer_lite=args.lite,
            allow_install=args.install,
            quiet=args.quiet,
        )
    else:
        state = get_state()

    if args.status:
        if state is None:
            if not args.quiet:
                print("offline")
            return 1 if (args.strict or args.ensure) else 0
        print(json.dumps(state, ensure_ascii=False))
        return 0

    if state is None:
        if not args.quiet:
            print("pet debug server offline (run with --ensure, or --install --ensure on first setup)")
        return 1 if (args.strict or args.ensure or args.install) else 0

    if not args.force and (state.get("hidden") or state.get("fsHidden")):
        if not args.quiet:
            print("skipped (pet hidden or fullscreen active)")
        return 0

    has_timer_cmd = bool(args.stop_timer or args.countdown or args.work or args.rest)
    if not has_timer_cmd and not action_name and not args.say_text and not args.character and not args.api_action and not args.raw_js:
        if not args.quiet:
            print("ready")
        return 0

    if args.raw_js:
        js = args.raw_js
    elif args.stop_timer:
        js = build_stop_timer_js(args.say_text, action_name)
    elif args.countdown:
        sec = parse_duration(args.countdown, default_unit="s")
        phases = [
            {
                "kind": "task",
                "sec": sec,
                "label": args.label or "",
                "icon": args.icon or "⏳",
                "action": action_name or "写代码",
                "say": args.say_text or "",
            }
        ]
        js = build_timer_js(
            phases=phases,
            cycles=args.cycles,
            done_say=args.done_say or "预估时间到啦~",
            done_action=args.done_action,
            anim_sec=args.anim_sec,
        )
    elif args.work or args.rest:
        work_sec = parse_duration(args.work, default_unit="m") if args.work else 0
        rest_sec = parse_duration(args.rest, default_unit="m") if args.rest else 0
        use_native = (
            args.native_pomo
            or (
                work_sec >= 300
                and work_sec <= 7200
                and work_sec % 60 == 0
                and rest_sec == 0
                and args.cycles == 1
                and not args.label
                and not args.icon
            )
        )
        if use_native and work_sec > 0:
            work_min = max(5, min(120, work_sec // 60))
            js = build_native_pomo_js(work_min, args.anim_sec, args.say_text)
        else:
            phases = []
            if work_sec > 0:
                phases.append(
                    {
                        "kind": "work",
                        "sec": work_sec,
                        "label": args.label or ("工作" if rest_sec > 0 else ""),
                        "icon": args.icon or "🍅",
                        "action": action_name or "写代码",
                        "say": args.say_text or f"开始专注 {max(1, work_sec // 60)} 分钟~",
                    }
                )
            if rest_sec > 0:
                rest_min_label = max(1, rest_sec // 60) if rest_sec >= 60 else rest_sec
                rest_unit = "分钟" if rest_sec >= 60 else "秒"
                phases.append(
                    {
                        "kind": "rest",
                        "sec": rest_sec,
                        "label": "休息" if work_sec > 0 or not args.label else args.label,
                        "icon": "☕",
                        "action": "悠闲哼歌",
                        "say": f"工作结束，休息 {rest_min_label} {rest_unit}啦~",
                    }
                )
            js = build_timer_js(
                phases=phases,
                cycles=args.cycles,
                done_say=args.done_say or "本轮工作与休息完成啦~",
                done_action=args.done_action,
                anim_sec=args.anim_sec,
            )
    else:
        js = build_js(
            action=action_name,
            say_text=args.say_text,
            ms=args.ms,
            character=args.character,
            api_action=args.api_action,
            force=args.force,
        )
    ok = post_js(js)
    if not args.quiet:
        print("ok" if ok else "failed")
    return 0 if ok else (1 if (args.strict or args.ensure or args.install) else 0)


if __name__ == "__main__":
    sys.exit(main())
