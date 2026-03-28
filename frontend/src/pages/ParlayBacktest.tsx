import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Typography, Spin, Tag, Descriptions, Collapse, Space, Alert } from 'antd';
import { DollarOutlined, TrophyOutlined, LineChartOutlined, FireOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Title, Text } = Typography;

interface ParlayRun {
  id: string;
  run_at: string;
  parlay_type: string;
  min_confidence: number;
  n_parlays: number;
  n_wins: number;
  total_staked: number;
  total_payout: number;
  profit: number;
  roi_pct: number;
  details: any;
}

export default function ParlayBacktest() {
  const [runs, setRuns] = useState<ParlayRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('/api/parlay/results').then(r => {
      setRuns(r.data.runs);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  // 按策略分组
  const strategies: Record<string, ParlayRun[]> = {};
  for (const r of runs) {
    const key = `${r.parlay_type}_${Math.round(r.min_confidence * 100)}`;
    if (!strategies[key]) strategies[key] = [];
    strategies[key].push(r);
  }

  // 取最新一轮的数据
  const latest = runs.length > 0 ? runs[0].run_at?.slice(0, 19) : '';
  const latestRuns = runs.filter(r => r.run_at?.startsWith(latest?.slice(0, 16) || ''));

  // 按置信度分组展示
  const confGroups: Record<string, ParlayRun[]> = {};
  for (const r of latestRuns) {
    const conf = `${Math.round(r.min_confidence * 100)}%`;
    if (!confGroups[conf]) confGroups[conf] = [];
    confGroups[conf].push(r);
  }

  const renderRoiColor = (v: number) => v > 50 ? '#52c41a' : v > 0 ? '#1677ff' : '#f5222d';

  return (
    <div>
      <Title level={2}><DollarOutlined /> 北单串关回测</Title>
      <Alert message="基于联赛专属模型预测北单比赛，模拟2串1/3串1/4串1串关投注的历史回测结果。每注2元。"
        type="info" showIcon style={{ marginBottom: 16 }} />

      {Object.entries(confGroups).sort().map(([conf, groupRuns]) => (
        <Card key={conf} title={<span><FireOutlined style={{ color: '#fa8c16' }} /> 置信度 ≥{conf}</span>}
          style={{ marginBottom: 24 }}>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {groupRuns.map(r => (
              <Col xs={24} sm={12} md={6} key={r.id}>
                <Card size="small" hoverable
                  style={{ borderLeft: `4px solid ${renderRoiColor(r.roi_pct)}` }}>
                  <Statistic title={r.parlay_type}
                    value={r.roi_pct} precision={1} suffix="%"
                    prefix={<LineChartOutlined />}
                    valueStyle={{ color: renderRoiColor(r.roi_pct), fontSize: 28 }} />
                  <div style={{ marginTop: 8, fontSize: 13, color: '#666' }}>
                    <div>{r.n_parlays}注 | 命中{r.n_wins} | 率{((r.n_wins || 0) / (r.n_parlays || 1) * 100).toFixed(1)}%</div>
                    <div>投入¥{r.total_staked?.toFixed(0)} → 回报¥{r.total_payout?.toFixed(0)}</div>
                    <div style={{ color: r.profit > 0 ? '#52c41a' : '#f5222d', fontWeight: 'bold' }}>
                      {r.profit > 0 ? '+' : ''}¥{r.profit?.toFixed(0)}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          {/* 月度统计（展开查看） */}
          {groupRuns.filter(r => r.details?.monthly?.length > 0).slice(0, 1).map(r => (
            <Collapse key={`monthly_${r.id}`} ghost
              items={[{
                key: '1',
                label: `${r.parlay_type} 月度明细`,
                children: (
                  <Table size="small" pagination={false} rowKey="month"
                    dataSource={r.details.monthly}
                    columns={[
                      { title: '月份', dataIndex: 'month', key: 'm' },
                      { title: '注数', dataIndex: 'parlays', key: 'p' },
                      { title: '命中', dataIndex: 'wins', key: 'w' },
                      { title: '投入', dataIndex: 'staked', key: 's', render: (v: number) => `¥${v.toFixed(0)}` },
                      { title: '回报', dataIndex: 'payout', key: 'po', render: (v: number) => `¥${v.toFixed(0)}` },
                      { title: '利润', dataIndex: 'profit', key: 'pr',
                        render: (v: number) => <Text style={{ color: v > 0 ? '#52c41a' : '#f5222d' }}>¥{v.toFixed(0)}</Text> },
                      { title: 'ROI', dataIndex: 'roi', key: 'r',
                        render: (v: number) => <Text strong style={{ color: renderRoiColor(v) }}>{v.toFixed(1)}%</Text> },
                    ]} />
                ),
              }]} />
          ))}

          {/* 命中案例 */}
          {groupRuns.filter(r => r.details?.sample_wins?.length > 0).slice(0, 1).map(r => (
            <Collapse key={`wins_${r.id}`} ghost
              items={[{
                key: '1',
                label: `${r.parlay_type} 命中案例（${r.details.sample_wins.length}个）`,
                children: (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {r.details.sample_wins.slice(0, 5).map((w: any, i: number) => (
                      <Card size="small" key={i}
                        style={{ borderLeft: '3px solid #52c41a' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <div>
                            {w.legs.map((leg: any, j: number) => (
                              <div key={j} style={{ marginBottom: 4 }}>
                                <Tag color="blue">{leg.league}</Tag>
                                <Text>{leg.home} vs {leg.away}</Text>
                                <Tag color="green">{leg.pred === 'H' ? '主胜' : leg.pred === 'D' ? '平' : '客胜'}</Tag>
                                <Text type="secondary">SP:{leg.odds?.toFixed(2)} 比分:{leg.score}</Text>
                                {leg.correct ? <Tag color="green">✓</Tag> : <Tag color="red">✗</Tag>}
                              </div>
                            ))}
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div><Text strong>总赔率: {w.total_odds?.toFixed(2)}</Text></div>
                            <div><Text style={{ color: '#52c41a', fontWeight: 'bold' }}>
                              ¥{w.stake} → ¥{w.payout?.toFixed(2)}</Text></div>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </Space>
                ),
              }]} />
          ))}
        </Card>
      ))}

      {/* 详细投注列表 */}
      <ParlayDetailList />

      {runs.length === 0 && (
        <Card>
          <Text type="secondary">暂无回测数据。运行 <code>python3 -m ai.parlay_backtest</code> 生成数据。</Text>
        </Card>
      )}
    </div>
  );
}

function ParlayDetailList() {
  const [details, setDetails] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [parlayType, setParlayType] = useState('2串1');
  const [conf, setConf] = useState(60);
  const [onlyWins, setOnlyWins] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadDetails = () => {
    setLoading(true);
    axios.get('/api/parlay/details', {
      params: { parlay_type: parlayType, min_confidence: conf, page, page_size: 20, only_wins: onlyWins }
    }).then(r => {
      setDetails(r.data.details);
      setTotal(r.data.total);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { loadDetails(); }, [page, parlayType, conf, onlyWins]);

  return (
    <Card title="详细投注列表" style={{ marginTop: 24 }}>
      <Space style={{ marginBottom: 16 }} wrap>
        {['2串1', '3串1', '4串1'].map(t => (
          <Tag key={t} color={parlayType === t ? 'blue' : 'default'} style={{ cursor: 'pointer', padding: '4px 12px' }}
            onClick={() => { setParlayType(t); setPage(1); }}>{t}</Tag>
        ))}
        <span>置信度:</span>
        {[50, 60, 70].map(c => (
          <Tag key={c} color={conf === c ? 'green' : 'default'} style={{ cursor: 'pointer', padding: '4px 8px' }}
            onClick={() => { setConf(c); setPage(1); }}>≥{c}%</Tag>
        ))}
        <Tag color={onlyWins ? 'gold' : 'default'} style={{ cursor: 'pointer', padding: '4px 8px' }}
          onClick={() => { setOnlyWins(!onlyWins); setPage(1); }}>{onlyWins ? '只看命中 ✓' : '全部'}</Tag>
        <Text type="secondary">共 {total} 注</Text>
      </Space>

      <Table dataSource={details} rowKey="id" loading={loading} size="small"
        pagination={{ current: page, total, pageSize: 20, onChange: p => setPage(p), showTotal: t => `共${t}注` }}
        expandable={{
          expandedRowRender: (record: any) => (
            <Table dataSource={record.legs} rowKey={(_, i) => String(i)} size="small" pagination={false}
              columns={[
                { title: '联赛', dataIndex: 'league', key: 'lg', width: 70, render: (v: string) => <Tag color="blue">{v}</Tag> },
                { title: '主队', dataIndex: 'home', key: 'h' },
                { title: '客队', dataIndex: 'away', key: 'a' },
                { title: '预测', dataIndex: 'pred', key: 'p', width: 60,
                  render: (v: string) => <Tag color={v === 'H' ? 'green' : v === 'A' ? 'red' : 'orange'}>{v === 'H' ? '主胜' : v === 'D' ? '平' : '客胜'}</Tag> },
                { title: '比分', dataIndex: 'score', key: 's', width: 60 },
                { title: '结果', dataIndex: 'correct', key: 'c', width: 50,
                  render: (v: boolean) => v ? <Tag color="green">✓</Tag> : <Tag color="red">✗</Tag> },
                { title: 'SP', dataIndex: 'odds', key: 'o', width: 60, render: (v: number) => v?.toFixed(2) },
                { title: '置信度', dataIndex: 'confidence', key: 'cf', width: 70,
                  render: (v: number) => `${Math.round(v * 100)}%` },
              ]} />
          ),
        }}
        columns={[
          { title: '日期', dataIndex: 'parlay_date', key: 'd', width: 110 },
          { title: '结果', dataIndex: 'is_win', key: 'w', width: 60,
            render: (v: number) => v ? <Tag color="green">命中</Tag> : <Tag color="red">未中</Tag> },
          { title: '总赔率', dataIndex: 'total_odds', key: 'o', width: 80,
            render: (v: number) => <Text strong>{v?.toFixed(2)}</Text> },
          { title: '投入', dataIndex: 'stake', key: 's', width: 60, render: (v: number) => `¥${v}` },
          { title: '回报', dataIndex: 'payout', key: 'p', width: 80,
            render: (v: number) => <Text style={{ color: v > 0 ? '#52c41a' : '#999' }}>¥{v?.toFixed(2)}</Text> },
          { title: '比赛', key: 'legs', render: (_: any, r: any) => (
            <Space size={4} wrap>
              {r.legs?.map((leg: any, i: number) => (
                <Tag key={i} color={leg.correct ? 'green' : 'red'}>
                  {leg.home} vs {leg.away} {leg.pred === 'H' ? '主' : leg.pred === 'D' ? '平' : '客'} {leg.score}
                </Tag>
              ))}
            </Space>
          )},
        ]} />
    </Card>
  );
}
