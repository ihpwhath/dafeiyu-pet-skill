#!/usr/bin/env python3
"""Zero-dependency stdio MCP server for 大肥鱼桌宠 (dafeiyu-pet).

Compatible with Claude Desktop, Cursor, Cherry Studio, Antigravity, OpenClaw,
Hermes, and any MCP client using standard JSON-RPC 2.0 over stdio.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "skills" / "dafeiyu-pet" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import pet_act  # noqa: E402

SERVER_INFO = {"name": "dafeiyu-pet", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "pet_react",
        "description": (
            "Trigger a context-matching animation and speech bubble on 大肥鱼桌宠 "
            "(dafeiyu-pet.exe). Respects fullscreen/hidden/sleep states unless force=true."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Animation name, e.g. 写代码, 工作状态-思考冒泡, 工作状态-雀跃庆祝, 点击回应-害羞惊讶, 螃蟹走路, 吃Token, 优雅女仆舞",
                },
                "say": {"type": "string", "description": "Short Chinese speech bubble text (4-16 chars)"},
                "ms": {"type": "integer", "default": 3500, "description": "Bubble duration in milliseconds"},
                "character": {"type": "string", "description": "Optional skin id (v1..v5, gpt, etc.)"},
                "api_action": {"type": "string", "description": "Optional built-in action: feed, sleep, pomodoro"},
                "ensure": {"type": "boolean", "default": False, "description": "Launch/restart --dev-debug if offline"},
                "force": {"type": "boolean", "default": False, "description": "Override hidden/sleep checks"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "pet_status",
        "description": "Query live state JSON from 大肥鱼桌宠 (/state).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "pet_install_or_ensure",
        "description": "First-run auto-install from GitHub Releases (if missing) and ensure --dev-debug is running.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lite": {"type": "boolean", "default": False, "description": "Install Lite variant if missing"},
                "setup_autostart": {"type": "boolean", "default": False, "description": "Also configure Startup .lnk with --dev-debug"},
            },
        },
    },
    {
        "name": "pet_doctor",
        "description": "Run diagnostics for Windows/WSL2/GitBash networking, WebView2, autostart conflicts, and process status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "pet_timer",
        "description": (
            "Start a task countdown (arbitrary seconds/minutes), a Pomodoro work/rest cycle "
            "(e.g. work='40m', rest='10m'), or stop the active timer when a task finishes early."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "countdown": {"type": "string", "description": "Task countdown, e.g. '90s', '3m', '02:30'"},
                "work": {"type": "string", "description": "Work duration, e.g. '40' or '40m'"},
                "rest": {"type": "string", "description": "Optional rest duration, e.g. '10' or '10m'"},
                "cycles": {"type": "integer", "default": 1, "description": "Number of work+rest cycles"},
                "label": {"type": "string", "description": "Short chip label, e.g. '镜像中' or '工作'"},
                "icon": {"type": "string", "description": "Chip emoji icon (default ⏳ or 🍅)"},
                "say": {"type": "string", "description": "Optional speech bubble text"},
                "done_say": {"type": "string", "description": "Bubble text when timer completes"},
                "stop": {"type": "boolean", "default": False, "description": "Stop active countdown/Pomodoro"},
                "ensure": {"type": "boolean", "default": False, "description": "Start --dev-debug if offline"},
            },
        },
    },
]


def _reply(msg_id: object, result: dict | None = None, error: dict | None = None) -> None:
    payload: dict = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result or {}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle_tool_call(name: str, args: dict) -> dict:
    if name == "pet_status":
        st = pet_act.get_state()
        return _text_result(json.dumps(st, ensure_ascii=False, indent=2) if st else "offline")

    if name == "pet_doctor":
        return _text_result(json.dumps(pet_act.run_doctor(), ensure_ascii=False, indent=2))

    if name == "pet_timer":
        ensure = bool(args.get("ensure", False))
        st = pet_act.ensure_debug_pet(quiet=True) if ensure else pet_act.get_state()
        if st is None:
            return _text_result("offline (pass ensure=true)", is_error=ensure)
        if args.get("stop"):
            js = pet_act.build_stop_timer_js(args.get("say"), None)
            ok = pet_act.post_js(js)
            return _text_result("ok" if ok else "failed", is_error=not ok)
        if args.get("countdown"):
            sec = pet_act.parse_duration(str(args["countdown"]), default_unit="s")
            phases = [{
                "kind": "task",
                "sec": sec,
                "label": args.get("label") or "",
                "icon": args.get("icon") or "⏳",
                "action": "写代码",
                "say": args.get("say") or "",
            }]
            js = pet_act.build_timer_js(phases=phases, cycles=int(args.get("cycles") or 1), done_say=args.get("done_say"))
            ok = pet_act.post_js(js)
            return _text_result("ok" if ok else "failed", is_error=not ok)
        if args.get("work") or args.get("rest"):
            w_sec = pet_act.parse_duration(str(args["work"]), default_unit="m") if args.get("work") else 0
            r_sec = pet_act.parse_duration(str(args["rest"]), default_unit="m") if args.get("rest") else 0
            phases = []
            if w_sec > 0:
                phases.append({
                    "kind": "work",
                    "sec": w_sec,
                    "label": args.get("label") or ("工作" if r_sec > 0 else ""),
                    "icon": args.get("icon") or "🍅",
                    "action": "写代码",
                    "say": args.get("say") or f"开始专注 {max(1, w_sec // 60)} 分钟~",
                })
            if r_sec > 0:
                phases.append({
                    "kind": "rest",
                    "sec": r_sec,
                    "label": "休息",
                    "icon": "☕",
                    "action": "悠闲哼歌",
                    "say": f"工作结束，休息 {max(1, r_sec // 60)} 分钟啦~",
                })
            js = pet_act.build_timer_js(phases=phases, cycles=int(args.get("cycles") or 1), done_say=args.get("done_say"))
            ok = pet_act.post_js(js)
            return _text_result("ok" if ok else "failed", is_error=not ok)
        return _text_result("Specify countdown, work/rest, or stop=true", is_error=True)

    if name == "pet_install_or_ensure":
        lite = bool(args.get("lite", False))
        if not pet_act.find_pet_exe(prefer_lite=lite):
            pet_act.install_pet(prefer_lite=lite, quiet=True)
        if args.get("setup_autostart"):
            pet_act.setup_autostart(enable=True, prefer_lite=lite)
        st = pet_act.ensure_debug_pet(prefer_lite=lite, allow_install=False, quiet=True)
        return _text_result(json.dumps({"online": st is not None, "state": st}, ensure_ascii=False))

    if name == "pet_react":
        ensure = bool(args.get("ensure", False))
        force = bool(args.get("force", False))
        st = pet_act.ensure_debug_pet(quiet=True) if ensure else pet_act.get_state()
        if st is None:
            return _text_result("offline (pass ensure=true or run pet_install_or_ensure)", is_error=ensure)
        if not force and (st.get("hidden") or st.get("fsHidden")):
            return _text_result("skipped (hidden or fullscreen active)")
        js = pet_act.build_js(
            action=args.get("action"),
            say_text=args.get("say"),
            ms=int(args.get("ms") or 3500),
            character=args.get("character"),
            api_action=args.get("api_action"),
            force=force,
        )
        ok = pet_act.post_js(js)
        return _text_result("ok" if ok else "failed", is_error=not ok)

    return _text_result(f"Unknown tool: {name}", is_error=True)


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _reply(None, error={"code": -32700, "message": f"Parse error: {exc}"})
            continue

        msg_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        if method == "initialize":
            _reply(
                msg_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                },
            )
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            _reply(msg_id, {})
        elif method == "tools/list":
            _reply(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            try:
                res = handle_tool_call(str(params.get("name") or ""), params.get("arguments") or {})
            except Exception as exc:  # noqa: BLE001
                res = _text_result(f"Error: {exc}", is_error=True)
            _reply(msg_id, res)
        elif msg_id is not None:
            _reply(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
