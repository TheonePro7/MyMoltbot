# MyMoltbot 足彩智能分析系统 - 完整系统说明

## 一、系统概述

MyMoltbot 是一套基于 AI 的足彩赔率分析与智能预测系统，专为中国体育彩票（北单/竞彩）投注场景设计。系统从全球 35 个联赛的 23 万场历史比赛中学习，为每个联赛训练独立的 XGBoost 预测模型，实现"同联赛预测同联赛"。

### 核心能力

| 能力 | 说明 |
|------|------|
| 历史数据 | 231,705 场比赛，170 万条赔率记录 |
| 联赛覆盖 | 35 个联赛独立模型 |
| 北单对接 | 1,330 个中英文球队映射，72.9% 北单比赛覆盖 |
| 串关回测 | 2串1 ROI 94%，3串1 ROI 165%，4串1 ROI 345%（置信度≥60%） |
| 每日推荐 | 自动拉取北单 → 匹配联赛 → 预测 → 生成串关方案 |

### 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 |
| 后端 API | FastAPI + Pydantic |
| 旧版 Web | Flask（模拟投注/盈亏分析） |
| AI 引擎 | XGBoost + scikit-learn + pandas |
| 数据库 | SQLite（零配置，无需安装） |
| 数据源 | football-data.co.uk + The Odds API + 500.com 北单 |

---

## 二、目录结构

```
MyMoltbot/
├── ai/                          # AI 预测模块
│   ├── features.py              # 特征工程（赔率+球队战绩+ELO）
│   ├── team_features.py         # 球队近期战绩特征
│   ├── xgboost_model.py         # XGBoost 模型（训练/保存/加载/预测）
│   ├── backtest.py              # 滚动回测引擎
│   ├── evaluate.py              # 模型评估 + 准确率追踪
│   ├── auto_train.py            # 分联赛自动训练 + 超参优化
│   ├── sim_bet.py               # 模拟下单回测
│   ├── parlay_backtest.py       # 串关模拟回测（2串1/3串1/4串1）
│   ├── daily_recommend.py       # 每日北单推荐
│   └── train.py                 # 一键训练 CLI
│
├── api/                         # FastAPI 后端
│   ├── main.py                  # 入口（端口 8000）
│   ├── schemas.py               # 数据模型
│   └── routers/
│       ├── history.py           # 历史数据 API
│       ├── prediction.py        # 预测 + 评估 API
│       ├── training.py          # 训练成长 API
│       ├── parlay.py            # 串关回测 API
│       └── recommend.py         # 每日推荐 API
│
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # 数据总览
│   │   │   ├── History.tsx          # 历史数据浏览
│   │   │   ├── MatchDetailPage.tsx  # 比赛详情（50+庄家赔率）
│   │   │   ├── Prediction.tsx       # 智能预测
│   │   │   ├── Evaluate.tsx         # 模型评估
│   │   │   ├── TrainingDashboard.tsx # 模型成长大屏
│   │   │   ├── ParlayBacktest.tsx   # 串关回测+详细列表
│   │   │   └── DailyRecommend.tsx   # 每日北单推荐
│   │   ├── services/api.ts      # API 调用层
│   │   └── App.tsx              # 路由 + 导航
│   └── vite.config.ts           # 代理 → 8000
│
├── football_odds/               # 数据采集与分析
│   ├── history_db.py            # SQLite 历史数据库
│   ├── history_csv.py           # football-data.co.uk CSV 下载/解析
│   ├── history_import.py        # 批量导入 CLI
│   ├── odds_api_v2.py           # The Odds API 54 庄家采集
│   ├── bjdc.py                  # 500.com 北单解析
│   ├── bjdc_history_import.py   # 北单历史批量导入
│   ├── jingcai_import.py        # 竞彩+北单导入+预测
│   ├── team_mapping.py          # 中英文球队名映射
│   ├── league_names.py          # 联赛中文名映射
│   ├── jc500.py                 # 500.com 竞彩解析
│   └── analysis.py              # 赔率分析（隐含概率/抽水/去水）
│
├── web/                         # Flask 旧版 Web（模拟投注等）
├── data/                        # 数据文件（.gitignore，需本地生成）
│   ├── history.sqlite3          # 历史数据库
│   ├── models/                  # 训练好的模型（已提交）
│   │   ├── league_E0/           # 英超专属模型
│   │   ├── league_SP1/          # 西甲专属模型
│   │   └── ...                  # 35 个联赛
│   ├── team_name_mapping.json   # 中英文球队名映射（已提交）
│   ├── evaluations.sqlite3      # 评估历史
│   ├── parlay_backtest.sqlite3  # 串关回测明细
│   └── csv_cache/               # CSV 缓存
│
├── tests/                       # 单元测试（31 个）
├── requirements.txt             # Python 依赖
└── AGENTS.md                    # 开发指引
```

---

## 三、本地部署步骤

### 环境要求

- Python 3.12+
- Node.js 18+
- 磁盘 500MB+
- 内存 4GB+

### 1. 克隆代码

```bash
git clone https://github.com/TheonePro7/MyMoltbot.git
cd MyMoltbot
git checkout cursor/development-environment-setup-1c48
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 4. 导入历史数据

```bash
# 五大联赛+小联赛历史（约 10 分钟，13 万场）
python3 -m football_odds.history_import --seasons 20 --leagues all

# 北单历史（约 8 分钟，3.5 万场）
python3 -m football_odds.bjdc_history_import
```

### 5. 配置 API Key（可选）

```bash
cp .env.example .env
# 编辑 .env，填入 ODDS_API_KEY（The Odds API，免费申请）
# 不填也可以用，只是无法拉取实时多庄家赔率
```

### 6. 训练模型（可选，已有预训练模型）

```bash
# 如果想重新训练全部联赛（约 15 分钟）
python3 -m ai.auto_train --mode league
```

### 7. 启动服务

```bash
# 终端 1：FastAPI 后端（端口 8000）
python3 -m api.main

# 终端 2：React 前端（端口 3000）
cd frontend && npm run dev

# 终端 3（可选）：Flask 旧版（端口 5000，模拟投注功能）
HOST=0.0.0.0 python3 -m web.app
```

### 8. 访问

- 前端主界面：**http://localhost:3000**
- API 文档：**http://localhost:8000/docs**
- 旧版界面：**http://localhost:5000**

---

## 四、前端页面说明

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 数据总览 | 统计卡片（比赛数/赔率数/亚盘数）+ 联赛表格 |
| `/history` | 历史数据 | 按联赛/赛季筛选，点击进入比赛详情 |
| `/history/:id` | 比赛详情 | 50+ 庄家赔率表 + 亚盘 + 大小球 + 比赛统计 |
| `/prediction` | 智能预测 | 未赛比赛预测（概率+置信度+推荐） |
| `/recommend` | 每日推荐 | 拉取北单 → 预测 → 2/3/4串1推荐方案 |
| `/parlay` | 串关回测 | ROI 卡片 + 详细投注列表（可展开看每注明细） |
| `/evaluate` | 模型评估 | 对已结束比赛做"盲测"，追踪准确率 |
| `/growth` | 模型成长 | 训练次数/准确率变化/联赛对比/模拟下单历史 |

---

## 五、命令行工具

### 数据导入

```bash
# 导入欧洲联赛历史（football-data.co.uk）
python3 -m football_odds.history_import --seasons 20 --leagues all
python3 -m football_odds.history_import --stats

# 导入北单历史（500.com）
python3 -m football_odds.bjdc_history_import
python3 -m football_odds.bjdc_history_import --stats

# 采集实时赔率（The Odds API，54 庄家/场）
python3 -m football_odds.odds_api_v2
python3 -m football_odds.odds_api_v2 --all-leagues

# 导入当日竞彩+北单
python3 -m football_odds.jingcai_import --predict
```

### AI 训练与评估

```bash
# 一键训练（通用模型）
python3 -m ai.train --backtest

# 按联赛分别训练
python3 -m ai.auto_train --mode league

# 自动超参优化
python3 -m ai.auto_train --mode optimize

# 模型评估
python3 -m ai.evaluate --matches 2000 --desc "描述"
python3 -m ai.evaluate --history

# 模拟下单
python3 -m ai.sim_bet --matches 2000 --confidence 0.6

# 串关回测
python3 -m ai.parlay_backtest --matches 3000

# 每日推荐
python3 -m ai.daily_recommend
python3 -m ai.daily_recommend --expect 26039
```

---

## 六、数据说明

### 数据规模

| 数据 | 数量 |
|------|------|
| 总比赛 | 231,705 场 |
| 欧赔记录 | 1,717,004 条 |
| 亚盘记录 | 598,002 条 |
| 北单历史 | 35,034 场（140 期） |
| 联赛模型 | 35 个 |
| 球队映射 | 1,330 个 |

### 联赛覆盖

**主要联赛（football-data.co.uk，2006-2026）**：
英超、英冠、英甲、英乙、西甲、西乙、德甲、德乙、意甲、意乙、法甲、法乙、荷甲、比甲、葡超、土超、希腊超、苏超、苏冠

**额外联赛（football-data.co.uk，2012-2026）**：
阿甲、奥甲、巴甲、中超、丹超、芬超、爱超、J联赛、墨超、挪超、波甲、罗甲、俄超、瑞超、瑞士超、美职

### 时间说明

所有时间统一转换为**北京时间**（UTC+8），原始当地时间保留在 `match_time` 字段。

---

## 七、串关回测结果

基于最近 1,447 场可预测的北单比赛，每注 2 元：

| 策略 | 置信度≥50% | 置信度≥60% | 置信度≥70% |
|------|:---:|:---:|:---:|
| 单关命中率 | 65.1% | **73.1%** | **81.8%** |
| 单关 ROI | 28.9% | 35.4% | 41.2% |
| 2串1 ROI | 79.2% | **94.3%** | **104.3%** |
| 3串1 ROI | 132.0% | **165.5%** | **203.7%** |
| 4串1 ROI | 248.1% | **345.7%** | **418.1%** |

### 推荐投注策略

- **只在置信度 ≥60% 时下注**
- 优先选择有联赛专属模型的比赛（准确率更高）
- 串关不超过 4 串 1（串关越多风险越大）
- 单注金额固定，不追加

---

## 八、注意事项

1. **模型不是万能的**：足球比赛有随机性，任何模型都不能保证 100% 准确
2. **回测 ≠ 实战**：回测结果是历史模拟，实际投注可能有差异
3. **平局难预测**：平局是所有预测模型的弱点，模型倾向于少预测平局
4. **数据需要持续更新**：定期运行导入脚本保持数据新鲜
5. **赛后统计不能用于赛前预测**：射门、角球等数据只有赛后才有，模型的赛前预测完全基于赔率和球队战绩
