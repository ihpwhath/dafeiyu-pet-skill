# 常见 Bug 枚举与根因解决方案（14 类全覆盖）

先运行自检诊断命令定位原因：

```bash
# Python 版
python3 <SKILL_DIR>/scripts/pet_act.py --doctor

# 或零依赖 PowerShell 版
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\pet_act.ps1" -Doctor
```

---

## Bug 1：WSL2 下桌宠开着，`curl http://127.0.0.1:9336/state` 却提示 Connection Refused

- **原因**：WSL2 默认采用 **NAT 网络模式**，Linux 里的 `127.0.0.1` 与 Windows 宿主机 `127.0.0.1` 隔离，而 `dafeiyu-pet.exe` 只监听 Windows 本机 `127.0.0.1:9336`。仅开启了 `networkingMode=mirrored` 的机器才可从 Linux 直接连 `127.0.0.1`。
- **对策**：`pet_act.py` 在 `urllib` 直连失败后会自动识别 WSL2 并经 Windows 原生 `C:\Windows\System32\curl.exe` 通过标准输入（`--data-binary @-`）跨端请求 `127.0.0.1:9336`。若仍不通，检查 `/proc/sys/fs/binfmt_misc/WSLInterop` 是否开启。

---

## Bug 2：运行了 `dafeiyu-pet.exe --dev-debug`，端口 9336 依然没起来

- **原因**：大肥鱼桌宠使用 Windows 全局单实例互斥锁（`Global\dafeiyu-desktop-pet-wails` / Lite 为 `Global\dafeiyu-desktop-pet-wails-lite`）。如果电脑上已经运行着一个**未带 `--dev-debug`** 的实例，第二个带 `--dev-debug` 启动的进程会直接退出。
- **对策**：不要手动叠开第二个进程，直接运行 `pet_act.py --ensure`（或 `pet_act.ps1 -Ensure`）：脚本会先发 `CloseMainWindow()` 优雅退出旧实例，确认完全退出后再带 `--dev-debug` 拉起新实例。

---

## Bug 3：改了注册表 `HKCU\...\Run` 加 `--dev-debug`，重启电脑后参数又丢了（甚至双开抢占）

- **原因**：
  - **v1.4.x**：内置「开机自启」每次启动都会把 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\大肥鱼桌宠` 覆盖为无参路径；
  - **v1.5.2+**：内置「开机自启」改用 **Windows 登录计划任务**（`大肥鱼桌宠` / `大肥鱼桌宠 Lite`，参数 `--autostart`），它在 `Startup` 文件夹之前由 Task Scheduler 拉起并抢占单实例互斥锁，导致 `Startup\*.lnk` 的 `--dev-debug` 启动被拒。
- **对策**：运行一次 `pet_act.py --setup-autostart --ensure`（或 `pet_act.ps1 -SetupAutostart -Ensure`），会自动关闭内置 `autoStart`、清理 `HKCU Run` 与同名计划任务，并创建带 `--dev-debug` 的 `Startup\大肥鱼桌宠.lnk`。
- ⚠️ **注意**：之后不要在桌宠设置界面重新勾选「开机自启」。

---

## Bug 4：在 `Startup` 文件夹旁放了 `README.txt` / `README.md`，结果每次开机自动弹记事本

- **原因**：Windows 登录时会自动执行/打开 `shell:startup` **根目录**下的所有普通文件。
- **对策**：若要在启动目录旁留说明，务必放到**子文件夹**（如 `Startup\大肥鱼桌宠-README\README.md`），Windows 启动扫描不会递归子目录。

---

## Bug 5：中文动作名或气泡文字出现乱码（`????`）或前端 JS 报语法错误

- **原因**：
  1. 从 WSL / Git Bash 直接把中文参数拼到 `powershell.exe -Command "..."` 时会经过 Windows ANSI (GBK) 代码页转换导致乱码；
  2. 气泡文本里包含单引号 `'`、双引号 `"` 或换行 `\n` 会破坏 JS 字符串语法。
- **对策**：`pet_act.py` 对所有 PowerShell 调用强制使用 **UTF-16LE Base64 (`-EncodedCommand`)**，对所有 HTTP `/js` 请求体采用二进制 UTF-8 流 + `json.dumps` 严格转义。

---

## Bug 6：GitHub 直连超时 / 资产名带版本号导致 404 / 下载损坏

- **原因**：国内直连 `github.com` 容易超时；官网安装包文件名带版本号（如 `dafeiyu-pet-1.5.2-setup.exe`），写死无版本号链接会 404；上游仓库若被删库或迁移也会导致下载失败。
- **对策**：`--install` 动态读取 `/releases/latest` 资产列表，并内置 **上游 `shenliuyu18/dafeiyu-pet` → `gh-proxy.org` → 备份镜像 `ihpwhath/dafeiyu-pet`** 多级回退，静默安装前强制校验 `SHA256SUMS.txt`；校验失败自动删除残缺文件并中止。

---

## Bug 7：首次安装完或精简版 Windows 启动时白屏 / 无法渲染

- **原因**：桌宠基于 Wails v2 + Microsoft Edge WebView2，部分精简版 / LTSC 系统未预装 WebView2 Runtime。
- **对策**：运行 `--doctor` 检查 `webview2Version`。若为 `false`，先安装微软 Evergreen WebView2 Runtime 再运行 `--ensure`。

---

## Bug 8：非默认安装路径（装在 D 盘）或仅安装了 Lite 版找不到程序

- **原因**：硬编码 `C:\Users\<用户名>\AppData\Local\Programs\...` 换盘或换用户即失效。
- **对策**：脚本动态读取 `%LOCALAPPDATA%`，检索完整版与 Lite 版目录、运行中进程路径以及 `HKCU`/`HKLM` `Uninstall` 注册表项；也可通过 `--exe` 或环境变量 `DAFEIYU_PET_EXE` 指定任意路径。

---

## Bug 9：多子代理并行时桌宠抽搐抢动作，或桌宠离线导致 AI 任务报错

- **原因**：全局 `AGENTS.md` / `CLAUDE.md` 会被子代理继承；离线返回非 0 退出码会让 Agent 误判失败并反复重试。
- **对策**：常规收尾不加 `--strict`/`--ensure`，脚本在离线/全屏/休眠时默认静默跳过并返回 `0`；规则中限定**仅主对话最终回复前执行一次**。

---

## Bug 10：用户在全屏看视频 / 打游戏，或手动哄睡 / 番茄钟期间被打断

- **原因**：不判断状态直接调用 `playAction` 会唤醒睡眠或干扰全屏。
- **对策**：脚本执行前检查 `/state` 的 `hidden`、`fsHidden` 以及前端 `S.awake === false`，命中即跳过（显式传 `--force` 才强制执行）。

---

## Bug 11：强杀进程导致系统托盘留下幽灵图标

- **原因**：`Stop-Process -Force` 不会触发 `beforeClose()` -> `stopTray()`。
- **对策**：`--ensure` 优先调用 `CloseMainWindow()` 正常保存状态并注销托盘图标，仅超时 2.5 秒未退出时兜底强杀。

---

## Bug 12：Windows 用户没装 Python，或 `python3` 触发微软商店弹窗

- **原因**：Windows 10/11 默认把 `python3` 别名指向 Microsoft Store 占位符（返回码 49/9009），且部分纯办公用户（如 WorkBuddy 用户）根本没装 Python。
- **对策**：本 Skill 同目录自带纯 PowerShell 5.1 脚本 [pet_act.ps1](../scripts/pet_act.ps1)，零外部依赖，Windows 10/11 开箱即用；`SKILL.md` 与 `install.ps1` 均提供了 PowerShell 调用路径。

---

## Bug 13：Claude Code / Codex 在 Windows Git Bash (MSYS2) 下报 `wslpath: command not found` 或 `/mnt/c` 不存在

- **原因**：Git Bash / MINGW64 的盘符挂载在 `/c/...` 而非 `/mnt/c/...`，路径转换命令是 `cygpath` 而非 `wslpath`。
- **对策**：`pet_act.py` 专门区分 `windows-native`、`msys-gitbash` 与 `wsl2` 三种 Windows 运行态，自动选用 `cygpath` / `/c/Windows/...` 或 `wslpath` / `/mnt/c/Windows/...`。

---

## Bug 14：Codex 沙箱拦截本机请求 / OpenClaw 未刷新 Skill 列表

- **原因**：
  1. **Codex CLI**：默认 `workspace-write` 沙箱可能禁止访问 `127.0.0.1` 或调用外部 PowerShell 进程；需在执行提示批准或配置中允许本地回环/MCP 工具（或使用 `adapters/mcp_server.py` 经由宿主进程桥接）。
  2. **OpenClaw（小龙虾）**：新复制进去的 Skill 需执行 `openclaw gateway restart` 或通过 `openclaw skills list` 确认已载入；若 OpenClaw 跑在 Docker 容器内，需把桌宠宿主访问映射到宿主机地址或改用宿主机端执行。
  3. **Hermes（爱马仕）**：Skill 安装在 `~/.hermes/skills/dafeiyu-pet/` 后可用 `skills_list()` 或 `/dafeiyu-pet` 斜杠命令直接验证是否生效。
