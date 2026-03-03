# GDUT-CLI: 广东工业大学教务系统 Agent 基座 🎓

**GDUT-CLI** 是专为 AI Agent（如 **OpenClaw**）设计的广东工业大学教务系统本地查询引擎。它通过 Playwright 实现自动化登录与反爬验证，并通过标准化的 CLI 接口输出结构化 JSON 数据，让 AI Agent 能轻松接入真实的教务数据。

---

## 🚀 核心特性

- **Agent 原生友好**：全命令支持 `--json` 参数，直接吐出结构化数据，无缝对接 LLM。
- **极强的数据解析鲁棒性**：底层使用一维展平解析法，无视教务老旧系统奇葩的跨行图片嵌套排版，稳定提取键值对。
- **免验证码登录**：内置 Playwright 自动化浏览器，绕过 `reptile.js` 等反爬脚本。
- **持久化与静默会话**：启动复用 Chromium Profile (`~/.gdut/browser_data`) 无感续期，失效时极少打断用户。
- **自然语言级参数映射**：课表查询深度支持 `--date`、`--week`、`--from` 等参数，完美映射 Agent 提取的时间实体。

---

## 🛠️ 开箱即用 (OpenClaw 集成指南)

### 第一步：安装基座
```bash
# 1. 克隆代码并安装依赖
git clone <repository_url>
cd gdut-cli
pip install -e .

# 2. 安装无头浏览器（初次必须执行）
playwright install chromium
```

### 第二步：首次授权登录
Agent 获取数据前，需要主用户进行一次真实的登录授权：
```bash
gdut login
```
*(会弹出内置 Chromium 浏览器，请手动登录。登录成功后关闭窗口，Cookie 自动提取保存。)*

### 第三步：配置 OpenClaw Skill
你可以直接为 OpenClaw 创建一个 **查询教务信息** 的专属 Skill。
👉 **[点击查看完整的 OpenClaw System Prompt 配置模板](docs/OpenClaw_Skill_Prompt.md)**

---

## 📚 核心命令对照 (Agent 调用参考)

### 0. 伴随工具
- `gdut open` *(在浏览器中打开教务系统，自动复用本地已登录状态，供人工查阅)*

### 1. 课表查询 (`gdut schedule`)
**内置周次计算引擎，支持动态时间语义：**
- `gdut schedule --json` *(自动查询**明天**的课)*
- `gdut schedule --date 2026-03-15 --json` *(查询具体日期)*
- `gdut schedule --week 2 --json` *(查询第 2 周完整课表)*
- `gdut schedule --week 2 --day 3 --json` *(查询第 2 周星期三)*
- `gdut schedule --from <日期> --to <日期> --json` *(查询日期范围)*

### 2. 个人信息
- `gdut info --json` *(查询当前用户学籍信息)*

---

## 🏗️ 架构概览

```
├── docs/                        # 教务系统逆向与接口分析文档
│   └── OpenClaw_Skill_Prompt.md # 专属 Agent 提示词配置
├── jw/                          # 核心包
│   ├── cli.py                   # 终端命令入口抽象
│   ├── auth.py                  # Playwright 登录与反检测注入
│   ├── api.py                   # requests 纯接口调用与参数构造
│   ├── parser.py                # Regex + BeautifulSoup 降维提取抵御极其复杂的历史遗留 HTML 表格结构
│   └── display.py               # 终端高质量渲染 (rich) 兼容各语言与缩放特性
└── setup.py
```

如果你希望在 Python 代码中直接调用 SDK 而非子进程 CLI：
```python
from jw.auth import JWAuth
from jw.api import JWClient

# 实例化 Session，断联时会提示重新打开浏览器
client = JWClient(JWAuth().get_session(auto_login=True))
grades_json = client.get_grades()
```
