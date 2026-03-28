import { useEffect, useState } from 'react';
import { Card, Table, Tag, Typography, Spin, Space, Input, Button, Row, Col, Statistic, Alert, Collapse, Descriptions } from 'antd';
import { ThunderboltOutlined, TrophyOutlined, ReloadOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Title, Text } = Typography;

const predColor: Record<string, string> = { H: 'green', D: 'orange', A: 'red' };
const predText: Record<string, string> = { H: '主胜', D: '平', A: '客胜' };

export default function DailyRecommend() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [expect, setExpect] = useState('');
  const [confidence, setConfidence] = useState(0.6);

  const load = (exp?: string) => {
    setLoading(true);
    const params: any = { confidence };
    if (exp) params.expect = exp;
    axios.get('/api/recommend/daily', { params, timeout: 60000 })
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const predictions = data?.predictions || [];
  const highConf = predictions.filter((p: any) => p.confidence >= confidence);

  const matchColumns = [
    { title: '场次', dataIndex: 'match_num', key: 'num', width: 60 },
    { title: '联赛', dataIndex: 'league', key: 'lg', width: 70, render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: '时间', dataIndex: 'kickoff', key: 'time', width: 70 },
    { title: '主队', dataIndex: 'home_team', key: 'home' },
    { title: '让球', dataIndex: 'handicap', key: 'hc', width: 50, align: 'center' as const },
    { title: '客队', dataIndex: 'away_team', key: 'away' },
    { title: '预测', key: 'pred', width: 70,
      render: (_: any, r: any) => <Tag color={predColor[r.pred_label]}>{r.pred_text}</Tag> },
    { title: '置信度', key: 'conf', width: 80, sorter: (a: any, b: any) => a.confidence - b.confidence,
      defaultSortOrder: 'descend' as const,
      render: (_: any, r: any) => {
        const pct = Math.round(r.confidence * 100);
        return <Text strong style={{ color: pct >= 70 ? '#52c41a' : pct >= 60 ? '#1677ff' : '#999' }}>{pct}%</Text>;
      } },
    { title: '北单SP', key: 'sp', width: 120,
      render: (_: any, r: any) => (
        <span>
          <Text type={r.pred_label === 'H' ? undefined : 'secondary'}>{r.sp_h?.toFixed(2)}</Text>/
          <Text type={r.pred_label === 'D' ? undefined : 'secondary'}>{r.sp_d?.toFixed(2)}</Text>/
          <Text type={r.pred_label === 'A' ? undefined : 'secondary'}>{r.sp_a?.toFixed(2)}</Text>
        </span>
      ) },
    { title: '比分', dataIndex: 'score', key: 'score', width: 60,
      render: (v: string | null) => v || <Tag>未赛</Tag> },
  ];

  return (
    <div>
      <Title level={2}><ThunderboltOutlined /> 每日北单推荐</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <span>期号：</span>
          <Input placeholder="如 26039（空=当期）" value={expect} onChange={e => setExpect(e.target.value)}
            style={{ width: 150 }} />
          <Button type="primary" icon={<ReloadOutlined />} loading={loading}
            onClick={() => load(expect || undefined)}>拉取推荐</Button>
        </Space>
      </Card>

      {loading && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}

      {data && !loading && (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={8}><Card><Statistic title="北单总场数" value={data.total_matches} /></Card></Col>
            <Col xs={8}><Card><Statistic title="可预测" value={data.predictable} /></Card></Col>
            <Col xs={8}><Card><Statistic title={`高置信(≥${Math.round(confidence*100)}%)`} value={data.high_confidence}
              valueStyle={{ color: '#52c41a' }} /></Card></Col>
          </Row>

          {/* 串关推荐 */}
          {Object.entries(data.parlays || {}).map(([name, parlays]: [string, any]) => (
            <Card key={name} title={<span><TrophyOutlined style={{ color: '#faad14' }} /> {name} 推荐方案</span>}
              style={{ marginBottom: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {parlays.map((p: any, i: number) => (
                  <Card key={i} size="small" hoverable
                    style={{ borderLeft: '4px solid #1677ff' }}>
                    <Row justify="space-between" align="middle">
                      <Col flex="auto">
                        {p.legs.map((leg: any, j: number) => (
                          <div key={j} style={{ marginBottom: 4 }}>
                            <Tag color="blue">{leg.league}</Tag>
                            <Text strong>{leg.home_team}</Text>
                            <Text type="secondary"> vs </Text>
                            <Text strong>{leg.away_team}</Text>
                            <Tag color={predColor[leg.pred_label]} style={{ marginLeft: 8 }}>{leg.pred_text}</Tag>
                            <Text type="secondary" style={{ marginLeft: 4 }}>
                              置信{Math.round(leg.confidence * 100)}% SP:{leg.pred_sp?.toFixed(2)}
                            </Text>
                          </div>
                        ))}
                      </Col>
                      <Col>
                        <div style={{ textAlign: 'right' }}>
                          <div><Text strong>总赔率: {p.total_odds}</Text></div>
                          <div><Text style={{ color: '#1677ff', fontSize: 18, fontWeight: 'bold' }}>
                            ¥2 → ¥{p.potential_payout}</Text></div>
                        </div>
                      </Col>
                    </Row>
                  </Card>
                ))}
              </Space>
            </Card>
          ))}

          {/* 全部预测列表 */}
          <Card title={`全部可预测比赛（${predictions.length}场）`}>
            <Table dataSource={predictions} columns={matchColumns} rowKey="match_num"
              size="small" pagination={false}
              rowClassName={(r: any) => r.confidence >= confidence ? 'high-conf-row' : ''} />
          </Card>
        </>
      )}
    </div>
  );
}
