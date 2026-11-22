# dafeiyu-pet-skill

<div align="center">

**让市面上主流 AI 编程助手与桌面 Agent 真正“活”起来的标准桌面伙伴 Skill**  
直连 [大肥鱼桌宠 (shenliuyu18/dafeiyu-pet)](https://github.com/shenliuyu18/dafeiyu-pet) 底层 HTTP 调试桥 · 零模拟点击 · 首次自动补全安装 · 适配 7 大主流生态

</div>

---

## 为什么做这个项目？

市面上的 AI 工具百花齐放——**Antigravity、Claude / Claude Code、GPT / Codex CLI、WorkBuddy / CodeBuddy、OpenClaw（小龙虾）、Hermes（爱马仕）、DeepSeek 生态**——它们大多遵循相似的 `SKILL.md` / Tool / Rule 思路，但**底层执行环境与接入机制各有差异**：

- 有的跑在 **WSL2**（默认 NAT 网络隔离了 `127.0.0.1`），有的跑在 **Git Bash (MSYS2)**，有的跑在 **Windows 原生命令行**；
- 有的用户电脑上**根本没装 Python**（直接调 `python3` 会弹微软商店）；
- 有的靠 `SKILL.md` + `AGENTS.md` / `CLAUDE.md` 自动触发，有的靠 **MCP Server**（Claude Desktop / Cherry Studio / Cursor），有的靠 **OpenAI / DeepSeek Function Calling**；
- 新用户第一次装 Skill 时，电脑里可能还没装大肥鱼桌宠本体。

本仓库把这些差异全部拉平，做成了可直接克隆、一键安装、开箱即用的标准发行版。

---

## 核心特性

1. **首次运行自动补全安装，之后不再改写 Skill**
   - 内置官方 GitHub Releases（`shenliuyu18/dafeiyu-pet`）动态解析、官方备用镜像仓库（`ihpwhath/dafeiyu-pet`）防删库回退、国内加速 `https://gh-proxy.org/` 自动容灾、**SHA-256 哈希校验** 与 NSIS `/S` 静默安装。
   - **仅在未检测到桌宠时触发一次**，安装状态写入用户缓存目录，**永不修改 Skill 目录自身文件**。
2. **直连底层接口，毫秒级响应，零模拟点击**
   - 通过桌宠官方 `--dev-debug` 监听的 `http://127.0.0.1:9336/js` 与 `/state` 直接调用前端动作与气泡接口，不抢鼠标焦点、不弹右键菜单。
3. **双引擎脚本 + 双扩展适配器**
   - [skills/dafeiyu-pet/scripts/pet_act.py](./skills/dafeiyu-pet/scripts/pet_act.py)：纯 Python 3 标准库，自动适配 **Windows 原生 / Git Bash (MSYS2) / WSL2 Mirrored / WSL2 NAT**。
   - [skills/dafeiyu-pet/scripts/pet_act.ps1](./skills/dafeiyu-pet/scripts/pet_act.ps1)：纯 PowerShell 5.1，**零 Python 依赖**，Windows 10/11 开箱即用。
   - [adapters/mcp_server.py](./adapters/mcp_server.py)：零依赖标准 `stdio` MCP Server（适配 Claude Desktop、Cherry Studio、Cursor、Antigravity MCP 等）。
   - [adapters/deepseek_openai_tool.py](./adapters/deepseek_openai_tool.py)：DeepSeek / OpenAI GPT Function Calling 完整 Schema 与开箱示例。
4. **大众化全场景语义匹配**
   - 覆盖 106 个 `v1` 动作与 `v2`–`v9` / `GPT 娘` 多形象：编程开发、排查 Bug、测试通过、报错预警、情绪陪伴（夸奖/表白/害羞/傲娇）、番茄钟学习、办公归档、饮食/Token 账本、早晚问候、传统节日等。
5. **14 类常见 Bug 逐一攻破 + 一键 `--doctor` 诊断**
   - 解决单实例互斥锁冲突、`v1.4.x` `HKCU Run` 与 `v1.5.2+` 计划任务自启抢占、`Startup` 根目录放 README 开机弹记事本、CJK 乱码、托盘幽灵图标、全屏/睡眠打扰等全部坑点。

---

## 主流平台适配矩阵（7 大生态全覆盖）

| 平台 / 客户端 | Skill 目录 | 全局常驻规则文件 | 执行与适配要点 |
| :--- | :--- | :--- | :--- |
| **Antigravity (AGY)** | `~/.gemini/config/skills/dafeiyu-pet/` | `~/.gemini/config/AGENTS.md` | 常跑在 WSL2 中；`pet_act.py` 自动兼容 NAT（`curl.exe` 桥接）与 Mirrored 网络，PowerShell 全走 UTF-16LE `-EncodedCommand` |
| **Claude Code** | `~/.claude/skills/dafeiyu-pet/` | `~/.claude/CLAUDE.md` | Windows 下常在 Git Bash (`MSYS2`) 中运行；脚本自动识别 `cygpath` 与 `/c/...` 盘符；也支持在 Claude Desktop 挂载 `adapters/mcp_server.py` |
| **GPT / Codex CLI** | `~/.codex/skills/dafeiyu-pet/` | `~/.codex/AGENTS.md` | 同时兼容 Windows 原生与 WSL2；若开启严格沙箱限制了 `127.0.0.1` 或子进程，可改走 MCP 适配器或放行本机回环 |
| **WorkBuddy / CodeBuddy** | `~/.workbuddy/skills/dafeiyu-pet/`<br>`~/.codebuddy/skills/dafeiyu-pet/` | `~/.workbuddy/AGENTS.md`<br>`~/.codebuddy/CODEBUDDY.md` | 针对纯 Windows 办公电脑可能无 Python 的场景，内置纯 PowerShell 5.1 版 `pet_act.ps1`，并在 `SKILL.md` description 中保留完整中英文触发词 |
| **OpenClaw（小龙虾）** | `~/.openclaw/workspace/skills/dafeiyu-pet/` | `~/.openclaw/workspace/AGENTS.md` | 符合 OpenClaw `SKILL.md` 规范；安装后可用 `openclaw skills list` 查看，必要时执行 `openclaw gateway restart` 刷新 |
| **Hermes（爱马仕）** | `~/.hermes/skills/dafeiyu-pet/` | `~/.hermes/AGENTS.md` | 符合 Nous Research Hermes `SKILL.md` 规范，支持按需 `skill_view` 与 `/dafeiyu-pet` 斜杠调用 |
| **DeepSeek / 通用 API & GUI 客户端** | `.agents/skills/dafeiyu-pet/`（OpenCode/Cline/Roo） | `.clinerules` / System Prompt | 提供 `adapters/mcp_server.py`（Cherry Studio / Cline / Cursor）与 `adapters/deepseek_openai_tool.py`（DeepSeek API / OpenAI SDK Function Calling） |

---

## 快速安装与使用

### 第一步：安装 Skill 到你的 AI 客户端

#### 方式 1：标准 `skills` CLI

```bash
npx skills add ihpwhath/dafeiyu-pet-skill
```

#### 方式 2：仓库内置一键安装脚本（推荐）

脚本会自动探测本机已安装的 **Antigravity / Claude / Codex / WorkBuddy / CodeBuddy / OpenClaw / Hermes**（包括 WSL2 里的 Windows 用户目录），一键复制 Skill 并可选写入「每轮自动做动作」规则：

**Windows PowerShell：**

```powershell
# 1) 仅安装 Skill 到所有已检测到的客户端
.\install.ps1

# 2) 全套配齐：安装 Skill + 写入每轮自动反应规则 + 首次自动安装桌宠 + 配置开机自启 --dev-debug
.\install.ps1 -WithRules -SetupPet -SetupAutostart
```

**WSL2 / Git Bash / Linux：**

```bash
# 查看将安装到哪些目录（预览模式）
./install.sh --target auto --with-rules --dry-run

# 全套一键配置
./install.sh --target auto --with-rules --setup-pet --setup-autostart
```

> 可指定单个或多个目标，例如 `--target antigravity,claude,openclaw,hermes` 或 `--target all`。

---

### 第二步：首次自动补全大肥鱼桌宠（如已跳过 `-SetupPet`）

如果用户电脑上还没有大肥鱼桌宠，或者当前是以普通模式启动的，首次运行一次：

```bash
# Python
python3 skills/dafeiyu-pet/scripts/pet_act.py "点击回应-元气挥手" --say "初次见面，请多关照~" --install --ensure

# 或零依赖 PowerShell（无需安装 Python）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\skills\dafeiyu-pet\scripts\pet_act.ps1" "点击回应-元气挥手" -Say "初次见面，请多关照~" -Install -Ensure
```

**配置开机自动带 `--dev-debug` 启动（建议只执行一次）：**

```bash
python3 skills/dafeiyu-pet/scripts/pet_act.py --setup-autostart --ensure
```

> **提示**：该命令会自动关闭桌宠自带的自启项（同时清理 `v1.4.x` 注册表 `Run` 键与 `v1.5.2+` 登录计划任务），并在 Windows `Startup` 目录创建带 `--dev-debug` 参数的快捷方式。配置后请勿在桌宠设置界面里重新打开「开机自启」。

---

### 第三步：接入 MCP / DeepSeek / GPT（非 `SKILL.md` 客户端）

#### MCP 客户端（Claude Desktop / Cherry Studio / Cursor）

在对应客户端的 MCP 配置中添加（纯 Python 标准库，无需 `pip install`）：

```json
{
  "mcpServers": {
    "dafeiyu-pet": {
      "command": "python",
      "args": ["/你的绝对路径/dafeiyu-pet-skill/adapters/mcp_server.py"]
    }
  }
}
```

可用 MCP 工具：`pet_react`、`pet_status`、`pet_install_or_ensure`、`pet_doctor`。

#### DeepSeek / OpenAI GPT Function Calling

```bash
export DEEPSEEK_API_KEY="sk-..."
python3 adapters/deepseek_openai_tool.py "今天代码一次性编译通过了！"
```

详见 [adapters/deepseek_openai_tool.py](./adapters/deepseek_openai_tool.py)。

---

## 「每轮对话结束自动做动作」规则模板

大多数 Agent 的 `SKILL.md` 采用按需加载（只有提到桌宠时才会激活）。如果你想让 AI 在**每一次日常对话结束后**都自动匹配语境做动作，只需在对应全局规则文件（`AGENTS.md` / `CLAUDE.md` / `CODEBUDDY.md`，使用 `install.sh --with-rules` 或 `install.ps1 -WithRules` 可自动写入）加入：

```markdown
## Desktop Pet Reaction (`dafeiyu-pet`)
- At the end of every **main-conversation** turn (skip inside subagents, background workflows, or if the user asks not to touch the pet), right before giving your final reply, trigger an action and short 4–16 char Chinese bubble matching the turn's topic/outcome via:
  `python3 "<SKILL_DIR>/scripts/pet_act.py" "<action>" --say "<text>" --quiet`
- Consult `<SKILL_DIR>/SKILL.md` for semantic scenario-to-action mappings and vary choices naturally.
- Never pass `--install`, `--ensure`, or `--force` on automatic end-of-turn reactions so offline/fullscreen/sleeping states are respected with zero error or delay.
```

---

## 日常常用指令速查

```bash
# 查看桌宠实时状态 JSON
python3 skills/dafeiyu-pet/scripts/pet_act.py --status

# 触发特定动作 + 气泡
python3 skills/dafeiyu-pet/scripts/pet_act.py "优雅女仆舞" --say "任务全部完成啦~"

# 喂一碗白饭 / 切换睡眠 / 开启番茄钟
python3 skills/dafeiyu-pet/scripts/pet_act.py --api-action feed --ensure
python3 skills/dafeiyu-pet/scripts/pet_act.py --api-action pomodoro --ensure

# 切换形象皮肤（v1~v5、gpt 等）
python3 skills/dafeiyu-pet/scripts/pet_act.py --character v3 --say "换新形象啦~" --ensure

# 大任务预估倒计时 & 完成即停
python3 skills/dafeiyu-pet/scripts/pet_act.py --countdown 3m --label "构建中" --say "预计 3 分钟~"
python3 skills/dafeiyu-pet/scripts/pet_act.py --stop-timer --action "工作状态-雀跃庆祝" --say "任务完成啦~"

# 工作 40 分钟 + 休息 10 分钟（番茄钟循环）
python3 skills/dafeiyu-pet/scripts/pet_act.py --work 40 --rest 10 --cycles 2 --ensure

# 全面环境体检与故障排查
python3 skills/dafeiyu-pet/scripts/pet_act.py --doctor
```

---

## 诊断与常见 Bug 一览

遇到任何问题先运行 `--doctor`，脚本会一次性输出环境类型（`windows-native` / `msys-gitbash` / `wsl2`）、`curl.exe` 与 `powershell.exe` 可用性、安装路径、WebView2 Runtime 版本、运行进程参数、注册表/计划任务/启动快捷方式冲突情况以及双网络连通性。

完整 14 类 Bug 的根因与解决方案见 [troubleshooting.md](./skills/dafeiyu-pet/references/troubleshooting.md)，包括：
1. WSL2 NAT 模式 `127.0.0.1` 隔离
2. 单实例互斥锁导致 `--dev-debug` 拉起失败
3. `v1.4.x` 注册表 `Run` 与 `v1.5.2+` 登录计划任务自启抢占
4. `Startup` 根目录放 `README` 导致开机弹记事本
5. 中文 GBK 乱码与 JS 引号注入报错
6. GitHub 直连超时、资产名版本化 404 与 SHA-256 校验
7. WebView2 Runtime 缺失白屏
8. 非默认盘符与 Lite 版路径识别
9. 子代理并发抢动作与离线报错中断
10. 全屏应用 / 手动休眠打扰
11. 强杀进程残留系统托盘幽灵图标
12. Windows 无 Python / `python3` 弹微软商店
13. Git Bash (MSYS2) `/c/` 与 `cygpath` 路径差异
14. Codex 沙箱限制与 OpenClaw Gateway 刷新

---

## 目录结构

```text
dafeiyu-pet-skill/
├── README.md
├── LICENSE
├── install.ps1
├── install.sh
├── adapters/
│   ├── mcp_server.py
│   └── deepseek_openai_tool.py
└── skills/
    └── dafeiyu-pet/
        ├── SKILL.md
        ├── scripts/
        │   ├── pet_act.py
        │   └── pet_act.ps1
        └── references/
            ├── v1-actions.md
            └── troubleshooting.md
```

## 致谢与备份

- 桌宠本体（上游官方）：[shenliuyu18/dafeiyu-pet](https://github.com/shenliuyu18/dafeiyu-pet)（MIT License）
- 桌宠镜像仓库（防删库备份，含 `v1.5.2` 安装包）：[ihpwhath/dafeiyu-pet](https://github.com/ihpwhath/dafeiyu-pet)
- 本 Skill 仓库：[ihpwhath/dafeiyu-pet-skill](https://github.com/ihpwhath/dafeiyu-pet-skill)
