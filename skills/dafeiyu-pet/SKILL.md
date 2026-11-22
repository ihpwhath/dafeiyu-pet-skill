---
name: dafeiyu-pet
description: >-
  Control, auto-install (first run), and manage the Windows desktop pet
  大肥鱼桌宠 (dafeiyu-pet) across Antigravity, Claude Code, Codex, WorkBuddy,
  CodeBuddy, OpenClaw (小龙虾), and Hermes (爱马仕). Uses the --dev-debug HTTP
  bridge (http://127.0.0.1:9336) with Python or zero-Python PowerShell fallback.
  Triggers on: 大肥鱼, 桌宠, dafeiyu-pet, desktop pet, 动作, 互动, 气泡, 安装.
---

# 大肥鱼桌宠控制 (`dafeiyu-pet`)

通过桌宠内置的 `--dev-debug` 本地 HTTP 调试桥（`http://127.0.0.1:9336/js` 与 `/state`）直接控制动作与气泡。
同时提供两套等效实现，适配不同 AI 客户端与系统环境：
- **Python 版**：[scripts/pet_act.py](./scripts/pet_act.py)（仅用标准库；兼容 **Windows 原生 / Git Bash (MSYS2) / WSL2 Mirrored / WSL2 NAT**）
- **零依赖 PowerShell 版**：[scripts/pet_act.ps1](./scripts/pet_act.ps1)（兼容未安装 Python 的 Windows 环境，如 WorkBuddy / Claude Desktop）

> 以下 `<SKILL_DIR>` 表示本 `SKILL.md` 所在文件夹；Windows 原生无 `python3` 时可改用 `python`、`py -3` 或直接调用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\pet_act.ps1"`。

---

## 1. 首次运行自动安装（仅未安装时触发一次）

当用户首次使用本 Skill 且本机尚未安装大肥鱼桌宠时，执行一次带 `--install --ensure` 的命令即可自动补全安装并拉起 `--dev-debug`：

```bash
# Python（Windows / Git Bash / WSL2 通用）
python3 <SKILL_DIR>/scripts/pet_act.py "点击回应-元气挥手" --say "初次见面，以后请多指教~" --install --ensure

# 或零依赖 PowerShell（Windows 原生无 Python 时）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\pet_act.ps1" "点击回应-元气挥手" -Say "初次见面，以后请多指教~" -Install -Ensure
```

安装逻辑已内置在脚本中，无需改写本 `SKILL.md`：
1. **多路径探测已有安装**：依次检查 `127.0.0.1:9336/state`、运行中进程、`%LOCALAPPDATA%\Programs\大肥鱼桌宠\`、`%LOCALAPPDATA%\Programs\大肥鱼桌宠 Lite\` 以及 Windows `Uninstall` 注册表；**若已安装则直接跳过下载，永不重复安装**。
2. **官方下载源与容灾双备份**：优先查询官方 GitHub Releases（`shenliuyu18/dafeiyu-pet`）获取最新安装包（完整版 `dafeiyu-pet-*-setup.exe`，加 `--lite` / `-Lite` 装 Lite 版），若原仓库 404/不可用或直连超时，自动按序回退官方镜像加速 `https://gh-proxy.org/` 与备份镜像仓库（`ihpwhath/dafeiyu-pet`）。
3. **SHA-256 校验与静默安装**：校验同版本 `SHA256SUMS.txt` 后以 `/S` 静默安装并清理 `%TEMP%` 安装包，在用户缓存目录写入状态标记，随后以 `--dev-debug` 拉起桌宠。
4. **首次之后**：此后所有日常调用均直接访问 `127.0.0.1:9336`，**不再下载、也不再改写 Skill 目录下的任何文件**。

如需一并配置开机自动带 `--dev-debug` 启动（避免重启后端口未监听）：

```bash
python3 <SKILL_DIR>/scripts/pet_act.py --setup-autostart --ensure
```

---

## 2. 日常控制命令

```bash
# 常规收尾触发（推荐用于每轮主对话结束）：离线/全屏/休眠时自动静默跳过并返回 0
python3 <SKILL_DIR>/scripts/pet_act.py "工作状态-雀跃庆祝" --say "搞定啦~" --quiet

# 零 Python 环境等价写法
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\pet_act.ps1" "工作状态-雀跃庆祝" -Say "搞定啦~" -Quiet

# 显式唤醒或切换皮肤 / 喂饭 / 番茄钟 / 诊断
python3 <SKILL_DIR>/scripts/pet_act.py "螃蟹走路" --say "横着走~" --ensure
python3 <SKILL_DIR>/scripts/pet_act.py --status
python3 <SKILL_DIR>/scripts/pet_act.py --api-action feed --ensure
python3 <SKILL_DIR>/scripts/pet_act.py --api-action pomodoro --ensure
python3 <SKILL_DIR>/scripts/pet_act.py --character v3 --say "换新皮肤啦~" --ensure
python3 <SKILL_DIR>/scripts/pet_act.py --doctor
```

---

## 2.5 倒计时与「工作 / 休息」番茄钟集成

基于桌宠原生 `#chip` 倒计时牌与 `setPomodoro` 专注工作状态引擎，在 `--dev-debug` 模式下支持两类计时：

1. **大任务预估倒计时（支持任意秒/分，任务结束即停止）**：
   开始耗时任务（如镜像下载、大型构建、测试套件）时，先预估时间挂上倒计时牌并进入专注工作动画；任务提前完成时调用 `--stop-timer` 立即结束倒计时并撒花庆祝：
   ```bash
   # 开启预估 3 分钟任务倒计时（#chip 显示 ⏳ 镜像中 03:00）
   python3 <SKILL_DIR>/scripts/pet_act.py --countdown 3m --label "镜像中" --say "大任务开始，预计 3 分钟~" --quiet

   # 任务完成（或提前完成）立即停止倒计时并庆祝
   python3 <SKILL_DIR>/scripts/pet_act.py --stop-timer --action "工作状态-雀跃庆祝" --say "大任务顺利完成啦~" --quiet
   ```
   *(也支持 `90s`、`02:30`、`--anim-sec 10`；到达 `00:00` 会自动停止并提示，且不会篡改用户保存的默认番茄钟时长。)*

2. **自定义工作 + 休息周期（如「工作 40 分钟，休息 10 分钟」）**：
   ```bash
   # 单纯工作 40 分钟（走原生 Go 番茄钟，托盘悬浮也会同步显示剩余时间）
   python3 <SKILL_DIR>/scripts/pet_act.py --work 40 --say "开始专注 40 分钟~" --ensure

   # 工作 40 分钟 + 休息 10 分钟（支持任意分钟/秒与多轮循环 --cycles）
   python3 <SKILL_DIR>/scripts/pet_act.py --work 40 --rest 10 --cycles 2 --ensure

   # 零依赖 PowerShell 等价写法
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\pet_act.ps1" -Work 40 -Rest 10 -Cycles 2 -Ensure
   ```
   - 工作阶段显示 `🍅 工作 40:00`，桌宠按设定间隔循环播放 `写代码 / 思考 / 忙碌 / 清点` 动画；
   - 工作结束自动撒花切换为 `☕ 休息 10:00` 并播放轻松动作（`悠闲哼歌`），右键点击桌宠「结束专注」也可随时提前终止。

---

## 3. 大众使用与多场景语义动作映射

根据当前对话的**主题、语气和结果**挑选最贴合的动作，并搭配 4～16 字自然气泡（注意轮换，不要每轮重复同一动作）：

| 使用场景 | 典型用户输入 / 上下文 | 推荐动作（优先轮换） | 气泡风格示例 |
| :--- | :--- | :--- | :--- |
| **情绪陪伴 / 夸奖 / 表白** | 「我喜欢你」「你真棒」「辛苦了」「好无聊」 | `点击回应-害羞惊讶`、`蝴蝶蜜蜂环绕头顶开花`、`凭空生花`、`点击回应-开心跃动`、`点击回应-傲娇生气`、`点击回应-挠痒咯咯笑`、`撸猫` | 「突然说这个…会害羞的啦~」「收到夸奖，开心！」 |
| **编程开发 / 改代码 / 部署** | 写代码、重构、建项目、发版 | `写代码`、`工作状态-忙碌点按`、`工作状态-清点归档`、`轻快记录` | 「键盘冒烟赶工中…」「代码顺利上线！」 |
| **排查 Bug / 深度思考 / 调研** | 定位报错、读源码、对比方案、算法推导 | `工作状态-思考冒泡`、`深度思考碎碎念`、`原地专心玩魔方`、`下五子棋`、`东张西望`、`工作状态-原地踱步张望` | 「让我深思一下线索…」「找到根因啦！」 |
| **任务完成 / 测试全绿 / 喜讯** | 测试通过、Bug 修复、问题解决 | `工作状态-雀跃庆祝`、`放烟花`、`优雅女仆舞`、`轻快摇摆舞`、`可爱宅舞`、`小幅度原地360度旋转展示` | 「全部通过，完美收工~」「撒花庆祝！」 |
| **报错阻塞 / 棘手提醒 / 崩溃** | 构建失败、权限拦截、风险警告、无奈吐槽 | `工作状态-垂头叹气冒汗`、`玩游戏气急败坏`、`被吓一跳`、`打瞌睡被惊醒`、`用鲸鱼尾巴拍打地面` | 「这里卡住了，先别急…」「小心这个坑哦！」 |
| **学习备考 / 论文 / 专注模式** | 背单词、写作业、看文献、开启番茄钟 | `轻快记录`、`工作状态-思考冒泡`、`写代码`、`原地专心玩魔方`、`--api-action pomodoro` | 「专心冲刺这一轮~」「笔记整理好啦！」 |
| **办公总结 / 表格 / 归档清理** | 写周报、整理文件、格式转换、对账 | `工作状态-清点归档`、`轻快记录`、`女仆屈膝礼仪`、`碎碎念-擦桌碎碎念` | 「资料归档整齐啦~」「周报搞定！」 |
| **生活闲聊 / 问候 / 趣味整活** | 打招呼、讲笑话、摸鱼、展示才艺 | `点击回应-元气挥手`、`悠闲哼歌`、`螃蟹走路`、`变鸽子`、`扑克魔术`、`小提琴演奏`、`吹笛子`、`蓝鲸现世`、`鲸鱼吐泡泡特效`、`动物环绕`、`荡秋千`、`骑木马` | 「今天也要元气满满！」「给你变个魔术~」 |
| **吃饭休息 / 摸鱼喝水 / Token 账本** | 点外卖、饿了、查 API 额度/费用、提醒休息 | `吃白饭`、`吃Token`、`涮火锅`、`吃糖葫芦`、`吃大闸蟹`、`吃西瓜`、`吃冰淇淋融化`、`大口吃零食`、`余额-钱袋满溢`、`余额-数金皱眉`、`是啊，吃什么` | 「干饭时间到！」「又炫了一碗 Token~」 |
| **早安 / 熬夜 / 晚安道别** | 早上问好、深夜收尾、下班道别 | `晨间刷牙`、`超大伸懒腰`、`哈欠连天`、`原地小憩沉眠`、`放孔明灯` | 「早安，开始新一天~」「夜深了，早点休息哦」 |
| **节日氛围** | 春节、中秋、端午、圣诞、万圣节、七夕等 | `收红包`、`写福字`、`舞狮头`、`吃饺子`、`吃汤圆`、`吃粽子`、`中秋赏月吃月饼`、`装点圣诞树`、`讨糖南瓜灯`、`堆雪人` | 「节日快乐，好运连连！」 |

> 完整 106 个 `v1` 动作索引与跨版本形象说明见 [v1-actions.md](./references/v1-actions.md)。

---

## 4. 多平台差异与安全边界

- **非侵入原则**：自动收尾调用时**严禁加 `--install`、`--ensure` 或 `--force`**。离线、全屏应用（`fsHidden`）、手动隐藏（`hidden`）或手动哄睡（`!S.awake`）状态下脚本会静默跳过并退出 `0`。
- **仅主对话执行**：在子代理（subagent）与并行 workflow worker 中不要触发桌宠，仅在主对话即将输出最终回复前触发一次。
- **Codex / 沙箱提示**：若运行在只读或断网沙箱（如 Codex 默认 `workspace-write`）中，本机 `127.0.0.1:9336` 可能被沙箱拦截；需按沙箱策略放行或使用 MCP 桥接（见 [troubleshooting.md](./references/troubleshooting.md)）。
- **遇到异常先跑诊断**：`python3 <SKILL_DIR>/scripts/pet_act.py --doctor`（或 `pet_act.ps1 -Doctor`），详细排错见 [troubleshooting.md](./references/troubleshooting.md)。
