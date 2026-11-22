#!/usr/bin/env bash
set -euo pipefail

# One-click installer for dafeiyu-pet-skill across Antigravity, Claude Code,
# Codex CLI, WorkBuddy, CodeBuddy, OpenClaw (小龙虾), and Hermes (爱马仕).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/dafeiyu-pet"

TARGET="auto"
WITH_RULES=0
SETUP_PET=0
SETUP_AUTOSTART=0
LITE=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]
  --target <list>     Comma-separated: auto, all, antigravity, claude, codex,
                      workbuddy, codebuddy, openclaw, hermes (default: auto)
  --with-rules        Append non-intrusive end-of-turn pet reaction rules to
                      each target agent's global AGENTS.md / CLAUDE.md
  --setup-pet         First-run check: auto-install dafeiyu-pet.exe if missing
                      and launch --dev-debug mode
  --setup-autostart   Configure Windows Startup shortcut with --dev-debug
  --lite              Prefer dafeiyu-pet Lite variant when installing
  --dry-run           Show planned actions without modifying files
  -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-auto}"; shift 2 ;;
    --with-rules) WITH_RULES=1; shift ;;
    --setup-pet) SETUP_PET=1; shift ;;
    --setup-autostart) SETUP_AUTOSTART=1; shift ;;
    --lite) LITE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

# Detect Windows user profile path too when running in WSL2
WIN_USER_HOME=""
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null || [[ -e /proc/sys/fs/binfmt_misc/WSLInterop ]]; then
  PS_BIN="$(command -v powershell.exe || echo /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe)"
  if [[ -x "$PS_BIN" ]]; then
    RAW_WIN_HOME="$("$PS_BIN" -NoProfile -NonInteractive -InputFormat None -Command '[Environment]::GetFolderPath("UserProfile")' < /dev/null 2>/dev/null | tr -d '\r\n' || true)"
    if [[ -n "$RAW_WIN_HOME" ]]; then
      WIN_USER_HOME="$(wslpath -u "$RAW_WIN_HOME" 2>/dev/null || true)"
    fi
  fi
fi

RULE_START="<!-- dafeiyu-pet-skill:start -->"
RULE_END="<!-- dafeiyu-pet-skill:end -->"

append_rule_if_missing() {
  local rule_file="$1"
  local script_ref="$2"
  local skill_ref="$3"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] Would append auto-reaction rule to: $rule_file"
    return
  fi

  mkdir -p "$(dirname "$rule_file")"
  touch "$rule_file"
  if grep -qF "$RULE_START" "$rule_file"; then
    echo "  Rule already present in: $rule_file"
    return
  fi

  cat >> "$rule_file" <<EOF

$RULE_START
## Desktop Pet Reaction (\`dafeiyu-pet\`)
- At the end of every **main-conversation** turn (skip inside subagents, background workflows, or if the user asks not to touch the pet), right before giving your final reply, trigger an action and short 4–16 char Chinese bubble matching the turn's topic/outcome via:
  \`python3 "$script_ref" "<action>" --say "<text>" --quiet\` (or \`powershell.exe -ExecutionPolicy Bypass -File "${script_ref%.py}.ps1" "<action>" -Say "<text>" -Quiet\`)
- Consult \`$skill_ref\` for scenario-to-action mappings and vary choices naturally.
- Never pass \`--install\`, \`--ensure\`, or \`--force\` on automatic end-of-turn reactions so offline/fullscreen/sleeping states are respected with zero error or delay.
$RULE_END
EOF
  echo "  Updated global rule: $rule_file"
}

install_to_dir() {
  local label="$1"
  local dest_skill="$2"
  local rule_file="${3:-}"

  echo "[$label] -> $dest_skill"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] Would copy $SKILL_SRC to $dest_skill"
  else
    mkdir -p "$dest_skill"
    cp -r "$SKILL_SRC"/. "$dest_skill"/
    chmod +x "$dest_skill/scripts/pet_act.py" || true
  fi

  if [[ "$WITH_RULES" -eq 1 && -n "$rule_file" ]]; then
    append_rule_if_missing "$rule_file" "$dest_skill/scripts/pet_act.py" "$dest_skill/SKILL.md"
  fi
}

declare -A SELECTED
if [[ "$TARGET" == "all" ]]; then
  for k in antigravity claude codex workbuddy codebuddy openclaw hermes; do SELECTED[$k]=1; done
elif [[ "$TARGET" == "auto" ]]; then
  [[ -d "$HOME/.gemini" ]] && SELECTED[antigravity]=1
  [[ -d "$HOME/.claude" ]] && SELECTED[claude]=1
  [[ -d "$HOME/.codex" ]] && SELECTED[codex]=1
  [[ -d "$HOME/.workbuddy" ]] && SELECTED[workbuddy]=1
  [[ -d "$HOME/.codebuddy" ]] && SELECTED[codebuddy]=1
  [[ -d "$HOME/.openclaw" ]] && SELECTED[openclaw]=1
  [[ -d "$HOME/.hermes" ]] && SELECTED[hermes]=1
  if [[ -n "$WIN_USER_HOME" ]]; then
    [[ -d "$WIN_USER_HOME/.claude" ]] && SELECTED[claude_win]=1
    [[ -d "$WIN_USER_HOME/.codex" ]] && SELECTED[codex_win]=1
    [[ -d "$WIN_USER_HOME/.workbuddy" ]] && SELECTED[workbuddy_win]=1
    [[ -d "$WIN_USER_HOME/.codebuddy" ]] && SELECTED[codebuddy_win]=1
    [[ -d "$WIN_USER_HOME/.openclaw" ]] && SELECTED[openclaw_win]=1
    [[ -d "$WIN_USER_HOME/.hermes" ]] && SELECTED[hermes_win]=1
  fi
  if [[ ${#SELECTED[@]} -eq 0 ]]; then
    SELECTED[antigravity]=1
  fi
else
  IFS=',' read -ra LIST <<< "$TARGET"
  for item in "${LIST[@]}"; do
    SELECTED["$item"]=1
  done
fi

[[ -n "${SELECTED[antigravity]:-}" ]] && install_to_dir "Antigravity" "$HOME/.gemini/config/skills/dafeiyu-pet" "$HOME/.gemini/config/AGENTS.md"
[[ -n "${SELECTED[claude]:-}" ]] && install_to_dir "Claude Code" "$HOME/.claude/skills/dafeiyu-pet" "$HOME/.claude/CLAUDE.md"
[[ -n "${SELECTED[codex]:-}" ]] && install_to_dir "Codex CLI" "$HOME/.codex/skills/dafeiyu-pet" "$HOME/.codex/AGENTS.md"
[[ -n "${SELECTED[workbuddy]:-}" ]] && install_to_dir "WorkBuddy" "$HOME/.workbuddy/skills/dafeiyu-pet" "$HOME/.workbuddy/AGENTS.md"
[[ -n "${SELECTED[codebuddy]:-}" ]] && install_to_dir "CodeBuddy" "$HOME/.codebuddy/skills/dafeiyu-pet" "$HOME/.codebuddy/CODEBUDDY.md"
[[ -n "${SELECTED[openclaw]:-}" ]] && install_to_dir "OpenClaw (小龙虾)" "$HOME/.openclaw/workspace/skills/dafeiyu-pet" "$HOME/.openclaw/workspace/AGENTS.md"
[[ -n "${SELECTED[hermes]:-}" ]] && install_to_dir "Hermes (爱马仕)" "$HOME/.hermes/skills/dafeiyu-pet" "$HOME/.hermes/AGENTS.md"

if [[ -n "$WIN_USER_HOME" ]]; then
  [[ -n "${SELECTED[claude_win]:-}" ]] && install_to_dir "Claude Code (Windows)" "$WIN_USER_HOME/.claude/skills/dafeiyu-pet" "$WIN_USER_HOME/.claude/CLAUDE.md"
  [[ -n "${SELECTED[codex_win]:-}" ]] && install_to_dir "Codex (Windows)" "$WIN_USER_HOME/.codex/skills/dafeiyu-pet" "$WIN_USER_HOME/.codex/AGENTS.md"
  [[ -n "${SELECTED[workbuddy_win]:-}" ]] && install_to_dir "WorkBuddy (Windows)" "$WIN_USER_HOME/.workbuddy/skills/dafeiyu-pet" "$WIN_USER_HOME/.workbuddy/AGENTS.md"
  [[ -n "${SELECTED[codebuddy_win]:-}" ]] && install_to_dir "CodeBuddy (Windows)" "$WIN_USER_HOME/.codebuddy/skills/dafeiyu-pet" "$WIN_USER_HOME/.codebuddy/CODEBUDDY.md"
  [[ -n "${SELECTED[openclaw_win]:-}" ]] && install_to_dir "OpenClaw (Windows)" "$WIN_USER_HOME/.openclaw/workspace/skills/dafeiyu-pet" "$WIN_USER_HOME/.openclaw/workspace/AGENTS.md"
  [[ -n "${SELECTED[hermes_win]:-}" ]] && install_to_dir "Hermes (Windows)" "$WIN_USER_HOME/.hermes/skills/dafeiyu-pet" "$WIN_USER_HOME/.hermes/AGENTS.md"
fi

if [[ "$DRY_RUN" -eq 0 && ( "$SETUP_PET" -eq 1 || "$SETUP_AUTOSTART" -eq 1 ) ]]; then
  PY_FLAGS=()
  [[ "$LITE" -eq 1 ]] && PY_FLAGS+=(--lite)
  [[ "$SETUP_PET" -eq 1 ]] && PY_FLAGS+=(--install --ensure)
  [[ "$SETUP_AUTOSTART" -eq 1 ]] && PY_FLAGS+=(--setup-autostart --ensure)
  python3 "$SKILL_SRC/scripts/pet_act.py" "点击回应-元气挥手" --say "安装配好啦，请多关照~" "${PY_FLAGS[@]}"
fi

echo "Done."
