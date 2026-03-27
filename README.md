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

### 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

**说明**：本工具仅做数学层面的赔率解读与多源对比，不构成投注建议；真实预测需结合球队数据、伤病、模型等。
