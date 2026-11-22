<#
.SYNOPSIS
Windows one-click installer for dafeiyu-pet-skill across Antigravity, Claude Code,
Codex CLI, WorkBuddy, CodeBuddy, OpenClaw (小龙虾), and Hermes (爱马仕).
#>
param(
    [ValidateSet("auto", "all", "antigravity", "claude", "codex", "workbuddy", "codebuddy", "openclaw", "hermes")]
    [string[]]$Target = @("auto"),
    [switch]$WithRules,
    [switch]$SetupPet,
    [switch]$SetupAutostart,
    [switch]$Lite,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillSrc = Join-Path $RepoRoot "skills\dafeiyu-pet"
$UserHome = [Environment]::GetFolderPath("UserProfile")

$TargetsMap = @{
    antigravity = @{ Label = "Antigravity";       Detect = (Join-Path $UserHome ".gemini");    Skill = (Join-Path $UserHome ".gemini\config\skills\dafeiyu-pet");          Rule = (Join-Path $UserHome ".gemini\config\AGENTS.md") }
    claude      = @{ Label = "Claude Code";       Detect = (Join-Path $UserHome ".claude");    Skill = (Join-Path $UserHome ".claude\skills\dafeiyu-pet");                 Rule = (Join-Path $UserHome ".claude\CLAUDE.md") }
    codex       = @{ Label = "Codex CLI / GPT";   Detect = (Join-Path $UserHome ".codex");     Skill = (Join-Path $UserHome ".codex\skills\dafeiyu-pet");                  Rule = (Join-Path $UserHome ".codex\AGENTS.md") }
    workbuddy   = @{ Label = "WorkBuddy";         Detect = (Join-Path $UserHome ".workbuddy"); Skill = (Join-Path $UserHome ".workbuddy\skills\dafeiyu-pet");              Rule = (Join-Path $UserHome ".workbuddy\AGENTS.md") }
    codebuddy   = @{ Label = "CodeBuddy";         Detect = (Join-Path $UserHome ".codebuddy"); Skill = (Join-Path $UserHome ".codebuddy\skills\dafeiyu-pet");              Rule = (Join-Path $UserHome ".codebuddy\CODEBUDDY.md") }
    openclaw    = @{ Label = "OpenClaw (小龙虾)"; Detect = (Join-Path $UserHome ".openclaw");  Skill = (Join-Path $UserHome ".openclaw\workspace\skills\dafeiyu-pet");     Rule = (Join-Path $UserHome ".openclaw\workspace\AGENTS.md") }
    hermes      = @{ Label = "Hermes (爱马仕)";   Detect = (Join-Path $UserHome ".hermes");    Skill = (Join-Path $UserHome ".hermes\skills\dafeiyu-pet");                 Rule = (Join-Path $UserHome ".hermes\AGENTS.md") }
}

$Selected = New-Object System.Collections.Generic.List[string]
if ($Target -contains "all") {
    foreach ($k in $TargetsMap.Keys) { $Selected.Add($k) }
} elseif ($Target -contains "auto") {
    foreach ($k in $TargetsMap.Keys) {
        if (Test-Path -LiteralPath $TargetsMap[$k].Detect) { $Selected.Add($k) }
    }
    if ($Selected.Count -eq 0) { $Selected.Add("antigravity") }
} else {
    foreach ($t in $Target) { if ($TargetsMap.ContainsKey($t)) { $Selected.Add($t) } }
}

$RuleStart = "<!-- dafeiyu-pet-skill:start -->"
$RuleEnd = "<!-- dafeiyu-pet-skill:end -->"

foreach ($k in $Selected) {
    $cfg = $TargetsMap[$k]
    Write-Host "[$($cfg.Label)] -> $($cfg.Skill)"
    if ($DryRun) {
        Write-Host "  [dry-run] Would copy $SkillSrc -> $($cfg.Skill)"
    } else {
        New-Item -ItemType Directory -Force -Path $cfg.Skill | Out-Null
        Copy-Item -Path "$SkillSrc\*" -Destination $cfg.Skill -Recurse -Force
    }

    if ($WithRules) {
        $psScript = Join-Path $cfg.Skill "scripts\pet_act.ps1"
        $skillMd = Join-Path $cfg.Skill "SKILL.md"
        if ($DryRun) {
            Write-Host "  [dry-run] Would append auto-reaction rule to $($cfg.Rule)"
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $cfg.Rule) | Out-Null
            if (-not (Test-Path -LiteralPath $cfg.Rule)) { New-Item -ItemType File -Path $cfg.Rule | Out-Null }
            $existing = Get-Content -LiteralPath $cfg.Rule -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
            if ($existing -and $existing.Contains($RuleStart)) {
                Write-Host "  Rule already present in $($cfg.Rule)"
            } else {
                $snippet = @"

$RuleStart
## Desktop Pet Reaction (``dafeiyu-pet``)
- At the end of every **main-conversation** turn (skip inside subagents, background workflows, or if the user asks not to touch the pet), right before giving your final reply, trigger an action and short 4–16 char Chinese bubble matching the turn's topic/outcome via:
  ``powershell.exe -ExecutionPolicy Bypass -File "$psScript" "<action>" -Say "<text>" -Quiet`` (or ``python "$($cfg.Skill)\scripts\pet_act.py" "<action>" --say "<text>" --quiet``)
- Consult ``$skillMd`` for scenario-to-action mappings and vary choices naturally.
- Never pass ``-Install``/``--install``, ``-Ensure``/``--ensure``, or ``-Force``/``--force`` on automatic end-of-turn reactions so offline/fullscreen/sleeping states are respected with zero error or delay.
$RuleEnd
"@
                Add-Content -LiteralPath $cfg.Rule -Value $snippet -Encoding UTF8
                Write-Host "  Updated global rule: $($cfg.Rule)"
            }
        }
    }
}

if (-not $DryRun -and ($SetupPet -or $SetupAutostart)) {
    $psRunner = Join-Path $SkillSrc "scripts\pet_act.ps1"
    $psArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $psRunner, "点击回应-元气挥手", "-Say", "安装配好啦，请多关照~")
    if ($Lite) { $psArgs += "-Lite" }
    if ($SetupPet) { $psArgs += @("-Install", "-Ensure") }
    if ($SetupAutostart) { $psArgs += @("-SetupAutostart", "-Ensure") }
    & powershell.exe @psArgs
}

Write-Host "Done."
