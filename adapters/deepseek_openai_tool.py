#!/usr/bin/env python3
"""OpenAI / DeepSeek Function Calling adapter & runnable example for 大肥鱼桌宠.

Works with any OpenAI-compatible Chat Completions endpoint (DeepSeek API,
OpenAI GPT, OpenRouter, local vLLM/Ollama). Uses only Python stdlib.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "dafeiyu-pet" / "scripts"))

import pet_act  # noqa: E402

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "pet_react",
            "description": "在回复用户时控制桌面上的大肥鱼桌宠做出贴合语境的动作与气泡台词。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "动作名称，例如：写代码、工作状态-思考冒泡、工作状态-雀跃庆祝、"
                            "工作状态-垂头叹气冒汗、点击回应-害羞惊讶、点击回应-开心跃动、"
                            "点击回应-元气挥手、优雅女仆舞、轻快摇摆舞、螃蟹走路、吃Token、撸猫、原地小憩沉眠"
                        ),
                    },
                    "say": {
                        "type": "string",
                        "description": "气泡台词，4~16字中文，贴合当前对话语气",
                    },
                },
                "required": ["action", "say"],
            },
        },
    }
]


def execute_tool_call(name: str, arguments_json: str) -> str:
    """Execute an OpenAI/DeepSeek tool call locally against 大肥鱼桌宠."""
    if name != "pet_react":
        return json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False)
    args = json.loads(arguments_json or "{}")
    st = pet_act.get_state()
    if st is None:
        return json.dumps({"ok": False, "status": "offline"}, ensure_ascii=False)
    if st.get("hidden") or st.get("fsHidden"):
        return json.dumps({"ok": True, "status": "skipped_hidden"}, ensure_ascii=False)
    js = pet_act.build_js(
        action=args.get("action"),
        say_text=args.get("say"),
        ms=3500,
        character=None,
        api_action=None,
        force=False,
    )
    ok = pet_act.post_js(js)
    return json.dumps({"ok": ok}, ensure_ascii=False)


def chat_with_pet(prompt: str) -> str:
    """Example DeepSeek / OpenAI loop. Set OPENAI_API_KEY (or DEEPSEEK_API_KEY) & OPENAI_BASE_URL."""
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set DEEPSEEK_API_KEY or OPENAI_API_KEY before calling chat_with_pet().")
    base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or ("https://api.deepseek.com/v1" if os.environ.get("DEEPSEEK_API_KEY") else "https://api.openai.com/v1")
    ).rstrip("/")
    model = os.environ.get("PET_MODEL") or ("deepseek-chat" if "deepseek" in base_url else "gpt-4o-mini")

    messages: list[dict] = [
        {
            "role": "system",
            "content": "你是一个友好的桌面助手。每次回复用户前，调用一次 pet_react 让大肥鱼桌宠做出贴合对话语义的动作与气泡。",
        },
        {"role": "user", "content": prompt},
    ]

    for _ in range(3):
        body = json.dumps({"model": model, "messages": messages, "tools": OPENAI_TOOLS}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return msg.get("content") or ""
        for tc in tool_calls:
            fn = tc["function"]
            out = execute_tool_call(fn["name"], fn.get("arguments") or "{}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
    return ""


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        print(json.dumps({"tools": OPENAI_TOOLS}, ensure_ascii=False))
        raise SystemExit(0)
    user_q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "今天代码一次性编译通过了！"
    print(chat_with_pet(user_q))
