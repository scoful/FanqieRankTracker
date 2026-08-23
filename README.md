# 🏆 番茄风向标 · Fanqie Rank Tracker

[![English](https://img.shields.io/badge/lang-English-blue)](README_EN.md)

> 📚 追踪**番茄小说四大赛道榜单**（女频新书 / 女频阅读 / 男频新书 / 男频阅读），每日自动爬取排行数据并结合 AI 生成趋势分析，部署为精美的在线看板。
>
> 基于 [wen1701/FanqieRankTracker](https://github.com/wen1701/FanqieRankTracker) 深度定制的四榜架构 fork。

---

## ✨ 功能概览

| 功能 | 说明 |
|------|------|
| 🕷️ 四榜爬取 | 每日定时抓取女频/男频 × 新书榜/阅读榜共四个榜单，各分类 Top 30 |
| 🔀 榜单切换 | 看板内一键切换四榜，URL 参数可直达（`?channel=female&board=new`） |
| 📊 趋势对比 | 自动对比相邻两天数据：新上榜 / 掉榜 / 排名变化 / 阅读量增长 |
| 🤖 AI 风向分析 | 接入 OpenAI 兼容 API，按分类生成市场趋势速评；prompt 按频道与榜种定制解读侧重 |
| 🧭 类型风向标 | 独立趋势页聚合多日数据，AI 总结综合赛道、具体热门分类和高频题材；未配置 API 时自动规则兜底 |
| 📚 短篇推荐 | 访问时按 99 个题材标签实时读取短故事（依赖外部代理接口） |
| 📡 上游跟随哨兵 | 每日自动检测上游仓库的新功能提交，开 issue 提醒并可选邮件通知，cherry-pick 摘取 |
| 🖥️ 精美看板 | 暗色编辑风格仪表盘，打字机动画、瀑布流书籍卡片与骨架屏加载 |
| 📱 移动适配 | 完整的移动端适配，侧边栏抽屉式菜单 |
| 🔌 数据接口 | 生成静态 JSON 接口，按 `频道/榜种/类型` 三级路径读取最新数据 |
| ⚡ 全自动化 | GitHub Actions + GitHub Pages，零服务器运维 |

---

## 🚀 食用指南

### 前置条件

- **Python 3.9+**
- **Git**
- 一个 GitHub 账号
- （可选）一个 OpenAI 兼容 API 的密钥，用于 AI 分析

### 第一步：Fork 仓库

点击 GitHub 页面右上角的 **Fork** 按钮，将项目 Fork 到你自己的账号下。

### 第二步：开启 GitHub Pages

1. 进入你 Fork 后的仓库 → **Settings** → **Pages**
2. Build and deployment 的 Source 选择 **GitHub Actions**
3. 手动触发一次任一 workflow（或等定时任务），部署完成后看板上线：
   `https://<你的用户名>.github.io/FanqieRankTracker/`

### 第三步：配置 Secrets（可选）

进入仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**。

**AI 分析三件套**：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `API_BASE_URL` | OpenAI 兼容 API 的地址 | `https://api.deepseek.com/v1` |
| `API_KEY` | API 密钥 | `sk-xxxxxxxxxxxxx` |
| `API_MODEL` | 模型名称 | `deepseek-v4-flash` |

> **💡 提示：** 任何 OpenAI 兼容接口均可使用。不配置则自动使用基于规则的摘要替代 AI 分析，**不影响核心功能**。DeepSeek V4 系列会自动关闭思考模式以避免空响应。

**上游跟随邮件通知（可选）**：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `SMTP_HOST` | SMTP 服务器 | `smtp.qq.com` |
| `SMTP_USER` | 发件邮箱（需开启 SMTP 并使用授权码） | `you@qq.com` |
| `SMTP_PASS` | 邮箱授权码（非登录密码） | `xxxxxxxxxxxx` |
| `MAIL_TO` | 收件邮箱 | `you@example.com` |

### 第四步：手动触发首次运行

1. 进入仓库 → **Actions** → 左侧选择 **Daily Fanqie Rank Scraper**
2. 点击右上角 **Run workflow** → **Run workflow**
3. 等待运行完成（四榜全量抓取约 15–25 分钟）

运行成功后，`data/{channel}/{board}/` 目录下会自动生成当日快照，打开 GitHub Pages 链接即可看到看板。

### 第五步：坐等自动更新

GitHub Actions 已配置为 **每天 UTC 00:00（北京时间 08:00）** 自动运行。之后无需任何手动操作，数据和看板会每天自动更新。

- 看板顶部可切换**频道（女频/男频）× 榜种（新书/阅读）**，四榜数据独立采集与构建
- 右上角 **风向标** 进入 `trend.html`，查看综合赛道、具体热门分类和高频题材的近 7 / 14 / 30 日或全部周期趋势
- **Force Update Ranks** workflow 支持手动指定日期与 `channel` / `board` 参数，可单独重爬或重跑某个榜的 AI 摘要

---

## 🔌 最新数据接口

构建脚本会同步生成 GitHub Pages 可直接访问的静态 JSON 接口（路径为 `api/{频道}/{榜种}/`）：

| 类型 | 路径 | 说明 |
|---|---|---|
| 全站索引 | `api/index.json` | 四榜切片列表与更新日期 |
| 类型索引 | `api/female/new/index.json` | 该榜所有分类及对应 URL |
| 全量数据 | `api/female/new/all.json` | 该榜全部分类、趋势和书籍 |
| 单类型数据 | `api/female/new/古风世情.json` | 该榜指定类型的数据 |

示例：

```bash
curl https://<你的用户名>.github.io/FanqieRankTracker/api/male/new/all.json
curl https://<你的用户名>.github.io/FanqieRankTracker/api/female/read/index.json
```

---

## 🔧 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/<你的用户名>/FanqieRankTracker.git
cd FanqieRankTracker

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 运行爬虫（默认全部四榜，每分类 Top 30）
python scrape_fanqie_ranks.py
python scrape_fanqie_ranks.py --channel male          # 仅男频两榜
python scrape_fanqie_ranks.py --channel male --board read  # 仅男频阅读榜

# 5. 构建看板数据（可选，带 AI 分析需设置环境变量）
pip install openai
export API_BASE_URL="https://your-api-endpoint/v1"
export API_KEY="your-api-key"
export API_MODEL="your-model-name"
python scripts/build_latest.py                 # 全部四榜
python scripts/build_latest.py --force --date 2026-08-23 --channel female --board new

# 6. 本地预览前端
python -m http.server 8000
# 打开 http://localhost:8000
```

---

## 📁 项目结构

```
FanqieRankTracker/
├── .github/workflows/
│   ├── scrape.yml              # 每日四榜爬取 + AI 构建 + 部署
│   ├── force_update.yml        # 手动重爬/重跑（支持 channel/board 参数）
│   ├── upstream_watch.yml      # 上游功能哨兵（每日检测 + issue + 邮件）
│   └── pages.yml               # GitHub Pages 部署
├── css/
│   └── style.css               # 暗色编辑风格主题样式（含骨架屏加载）
├── js/
│   ├── boards.js               # 四榜路径与 URL 参数工具
│   ├── app.js                  # 看板渲染（瀑布流 + 打字机动画）
│   ├── trend.js                # 类型风向标页逻辑
│   ├── book.js                 # 作品详情页逻辑
│   └── shorts.js               # 短篇推荐页逻辑
├── scripts/
│   ├── board_config.py         # 四榜配置中心（榜单定义/路径/类型分组/关键词）
│   ├── build_latest.py         # 趋势对比 + AI 分析构建脚本
│   └── upstream_watch.py       # 上游功能检测脚本
├── data/
│   ├── {channel}/{board}/      # 每日原始快照（如 data/female/new/20260823.json）
│   ├── latest/{channel}/{board}.json   # 最新聚合数据（看板数据源）
│   ├── trends/{channel}/{board}/       # 逐日趋势归档
│   ├── market/{channel}/{board}.json   # 全站热点 AI/规则总结
│   └── dates/{channel}/{board}.json    # 可用日期索引
├── api/
│   ├── index.json              # 四榜切片索引
│   └── {channel}/{board}/      # 静态接口（index + all + 按类型拆分）
├── index.html                  # 仪表盘入口页
├── trend.html                  # 类型风向标趋势分析页
├── book.html                   # 作品详情页
├── shorts.html                 # 短篇推荐页
├── scrape_fanqie_ranks.py      # 番茄小说四榜爬虫（Playwright）
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

---

## ⚙️ 工作流程

```
┌────────────────────────────────────────────────────────────────┐
│                GitHub Actions（每日 北京时间 08:00）             │
│                                                                │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐    │
│  │  Playwright    │──▶│  build_latest  │──▶│  git commit   │    │
│  │  四榜爬取       │   │  趋势对比       │   │  自动提交      │    │
│  │  female×male   │   │  + AI 分析      │   │  到 main      │    │
│  │  new × read    │   │  （四榜并行）    │   └───────────────┘    │
│  └───────────────┘   └───────────────┘            │              │
└───────────────────────────────────────────────────┼──────────────┘
                                                    ▼
                                           GitHub Pages 自动部署
                                           用户访问在线看板 🌐

┌────────────────────────────────────────────────────────────────┐
│           Upstream Watch（每日 北京时间 12:00 巡逻）              │
│                                                                │
│  fetch 上游仓库 → 过滤数据噪音 → 新功能提交                        │
│  → 开 issue（含 cherry-pick 指引）→ 可选邮件通知 📧                │
└────────────────────────────────────────────────────────────────┘
```

---

## 📝 常见问题

<details>
<summary><b>Q: Workflow 运行失败怎么办？</b></summary>

检查 Actions 日志中的错误信息。常见原因：
- 番茄小说页面结构变更 → 需要更新爬虫选择器
- Playwright 安装超时 → 尝试重新运行
- 单个榜失败不影响其他三榜（失败隔离 + 断点续爬）

</details>

<details>
<summary><b>Q: 不配置 AI Secret 也能用吗？</b></summary>

可以！系统会自动 fallback 到基于规则的摘要（如"新增3本上榜；《XX》排名上升+5位"）。只是没有 AI 自然语言分析而已。事后配置好 Secrets，可用 **Force Update Ranks** workflow 单独重跑 AI 摘要，无需重新爬取。

</details>

<details>
<summary><b>Q: 怎么跟着上游仓库更新功能？</b></summary>

每日中午的上游哨兵会自动检测上游（wen1701/FanqieRankTracker）的新功能提交并开 issue 提醒。想要的功能按 issue 里的指引 `git cherry-pick` 后关闭 issue 即可；不想要直接关闭，不会重复提醒。**请勿使用 GitHub 的 Sync fork 按钮**——那会把上游的每日数据提交一并拖进来，与四榜数据结构冲突。

</details>

<details>
<summary><b>Q: 短篇推荐为什么是跳转到外部站点？</b></summary>

该功能的数据源是上游部署的 Cloudflare Worker 代理，存在服务端 Origin 白名单限制，fork 站点无法直接读取数据。因此入口直接链接到上游的可用页面（新标签打开），访客体验完整且零维护。后续如上游放开限制，可改回本地页面。

</details>

---

## 📜 License

MIT

---

<p align="center">
  <sub>Made with ☕ and 🤖 — 四榜数据每日自动更新，无需手动维护</sub>
</p>
