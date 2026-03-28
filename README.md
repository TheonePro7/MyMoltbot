# MyMoltbot

## 足彩赔率分析

根据欧赔（十进制赔率，如 2.10）做 **1X2（主胜/平/客胜）** 分析：

- **隐含概率**：\(1 / \text{赔率}\)
- **抽水（overround）**：三结果隐含概率之和减 1
- **去水（比例法）**：各结果隐含概率除以总和，得到和为 1 的「公平概率」估计（常用简化假设）
- **多庄对比**：赔率区间、哪家给出最高赔、多庄去水后概率的简单平均（粗共识）

### 使用方式

```bash
python3 main.py analyze examples/matches_sample.json
python3 main.py compare examples/matches_sample.json
python3 main.py compare examples/matches_sample.json --json-out
```

数据格式见 `examples/matches_sample.json`。也可在代码中调用 `football_odds` 包。

### Web 演示（浏览器）

```bash
pip install -r requirements.txt
python3 -m web.app
```

浏览器打开 <http://127.0.0.1:5000>。

**数据源（页面顶部切换）**

| 参数 | 说明 |
|------|------|
| 默认 `?source=jc500` | 抓取 [500 网竞彩](https://trade.500.com/jczq/) 当日 **真实开售 SP**（胜平负 + 让球胜平负两行）；日期可用 `?date=YYYY-MM-DD` |
| `?source=odds_api` | [The Odds API](https://the-odds-api.com/) 多庄 **h2h 十进制**；需环境变量 **`ODDS_API_KEY`**，可选 `ODDS_SPORT_KEY`（默认 `soccer_epl`）、`ODDS_REGIONS`（默认 `eu`）、`ODDS_MAX_MATCHES`（默认 30） |
| `?source=file` | 本地 JSON，默认 `examples/matches_sample.json`；路径用环境变量 `FOOTBALL_ODDS_DATA` |

远程访问可设置 `HOST=0.0.0.0`（注意防火墙与安全）。**The Odds API 为境外庄家数据，与体彩竞彩开售赔率不是同一来源。**

### The Odds API：Key 放在哪，Agent 才能调到真实数据？

**不要**在聊天里粘贴 Key。正确做法是：把 Key 放在 **运行 `python` 的那台机器、进程能读到的环境** 里——在 Cursor 里让我跑命令时，通常就是 **当前工作区所在环境**。

| 方式 | 说明 |
|------|------|
| **项目根目录 `.env`（推荐）** | 复制 `.env.example` → `.env`，写一行 `ODDS_API_KEY=...`。已接入 `python-dotenv`，`python3 -m web.app` 会自动加载。文件已被 `.gitignore` 忽略，不会进 Git。**你在本机或 SSH 远端保存后，我在同一仓库里执行终端命令时就能读到。** |
| **Cursor / 系统环境变量** | 在 Cursor 的 *Settings → Environment variables*（或你系统的用户环境变量）里增加 `ODDS_API_KEY`。对该工作区启动的终端、Agent 命令生效。 |
| **仅当前终端** | `export ODDS_API_KEY='...'` 后再运行程序；适合临时测试。 |

**说明**：没有 Key 时，仍可用 **500 网竞彩（`source=jc500`）** 拉真实 SP，不依赖 The Odds API。若要做 **境外多庄** 联调，必须把 Key 配在上述任一位置，而不是发在对话里。

### 完整 Web 功能（拉取到本地后）

导航栏包含：

| 页面 | 说明 |
|------|------|
| **赔率分析** | 竞彩真实 SP / Odds API / 本地 JSON |
| **简易预测** | 按官方 SP 去水后概率最大项（基线对照） |
| **模拟投注** | 勾选场次、**胆**、最多 **5 种**过关（几串几）、每子注默认 **2 元**、倍数 |
| **方案与盈亏** | SQLite 账本（默认 `data/sim_bets.sqlite3`，可用 `SIM_BET_DB`） |
| **赛果录入** | 填写 90 分钟比分或从页面导入，用于结算 |

生产环境建议设置 `FLASK_SECRET_KEY`。

### 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

**说明**：本工具仅做数学层面的赔率解读与多源对比，不构成投注建议；真实预测需结合球队数据、伤病、模型等。
