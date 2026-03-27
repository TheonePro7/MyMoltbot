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

### 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

**说明**：本工具仅做数学层面的赔率解读与多源对比，不构成投注建议；真实预测需结合球队数据、伤病、模型等。
