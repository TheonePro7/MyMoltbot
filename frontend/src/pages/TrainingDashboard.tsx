import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Typography, Spin, Tag, Progress, Empty } from 'antd';
import { RiseOutlined, ExperimentOutlined, TrophyOutlined, LineChartOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Title, Text } = Typography;

interface TimelineItem {
  run_index: number;
  run_id: string;
  run_at: string;
  description: string;
  accuracy: number;
  accuracy_home: number;
  accuracy_draw: number;
  accuracy_away: number;
  high_conf_accuracy: number;
  n_matches: number;
  best_so_far: number;
}

interface LeagueItem {
  division: string;
  name: string;
  matches: number;
  accuracy: number;
}

export default function TrainingDashboard() {
  const [growth, setGrowth] = useState<any>(null);
  const [leagues, setLeagues] = useState<LeagueItem[]>([]);
  const [simHistory, setSimHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      axios.get('/api/training/growth'),
      axios.get('/api/training/league-comparison'),
      axios.get('/api/training/sim-history'),
    ]).then(([g, l, s]) => {
      setGrowth(g.data);
      setLeagues(l.data.leagues);
      setSimHistory(s.data.runs);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const timeline: TimelineItem[] = growth?.timeline || [];
  const latest = timeline.length > 0 ? timeline[timeline.length - 1] : null;
  const first = timeline.length > 0 ? timeline[0] : null;
  const improvement = growth?.improvement || 0;

  const leagueColumns = [
    { title: '联赛', dataIndex: 'name', key: 'name', render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: '代码', dataIndex: 'division', key: 'div', width: 70 },
    { title: '场数', dataIndex: 'matches', key: 'matches', width: 80 },
    {
      title: '准确率', dataIndex: 'accuracy', key: 'acc', width: 150,
      sorter: (a: any, b: any) => a.accuracy - b.accuracy,
      defaultSortOrder: 'descend' as const,
      render: (v: number) => (
        <span>
          <Progress percent={v} size="small" strokeColor={v >= 65 ? '#52c41a' : v >= 55 ? '#1677ff' : '#fa8c16'} style={{ width: 80, marginRight: 8 }} />
          <Text strong style={{ color: v >= 65 ? '#52c41a' : v >= 55 ? '#1677ff' : '#fa8c16' }}>{v.toFixed(1)}%</Text>
        </span>
      ),
    },
  ];

  const historyColumns = [
    { title: '序号', dataIndex: 'run_index', key: 'idx', width: 60 },
    { title: '时间', dataIndex: 'run_at', key: 'time', width: 170, render: (v: string) => v?.slice(0, 19) },
    { title: '描述', dataIndex: 'description', key: 'desc', render: (v: string) => v || <Text type="secondary">-</Text> },
    { title: '场数', dataIndex: 'n_matches', key: 'n', width: 80 },
    {
      title: '准确率', dataIndex: 'accuracy', key: 'acc', width: 100,
      render: (v: number, _: any, idx: number) => {
        const prev = idx > 0 ? timeline[idx - 1]?.accuracy : v;
        const diff = v - prev;
        return (
          <span>
            <Text strong style={{ color: v >= 60 ? '#52c41a' : '#fa8c16' }}>{v.toFixed(1)}%</Text>
            {idx > 0 && diff !== 0 && (
              <Text style={{ fontSize: 12, marginLeft: 4, color: diff > 0 ? '#52c41a' : '#f5222d' }}>
                {diff > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{Math.abs(diff).toFixed(1)}
              </Text>
            )}
          </span>
        );
      },
    },
    { title: '主胜', dataIndex: 'accuracy_home', key: 'ah', width: 70, render: (v: number) => `${v.toFixed(1)}%` },
    { title: '平局', dataIndex: 'accuracy_draw', key: 'ad', width: 70, render: (v: number) => `${v.toFixed(1)}%` },
    { title: '客胜', dataIndex: 'accuracy_away', key: 'aa', width: 70, render: (v: number) => `${v.toFixed(1)}%` },
    { title: '高置信', dataIndex: 'high_conf_accuracy', key: 'hc', width: 80, render: (v: number) => <Text strong>{v.toFixed(1)}%</Text> },
    { title: '最佳', dataIndex: 'best_so_far', key: 'best', width: 70, render: (v: number) => <Tag color="gold">{v.toFixed(1)}%</Tag> },
  ];

  return (
    <div>
      <Title level={2}><RiseOutlined /> 模型自我成长</Title>

      {/* 核心指标 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={6}>
          <Card hoverable>
            <Statistic title="训练次数" value={growth?.total_runs || 0} prefix={<ExperimentOutlined />}
              valueStyle={{ color: '#1677ff', fontSize: 32 }} />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card hoverable>
            <Statistic title="最新准确率" value={latest?.accuracy || 0} suffix="%" precision={1}
              prefix={<LineChartOutlined />} valueStyle={{ color: '#52c41a', fontSize: 32 }} />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card hoverable>
            <Statistic title="历史最佳" value={growth?.best_accuracy || 0} suffix="%" precision={1}
              prefix={<TrophyOutlined />} valueStyle={{ color: '#faad14', fontSize: 32 }} />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card hoverable>
            <Statistic title="成长幅度" value={improvement} suffix="%" precision={1}
              prefix={improvement >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              valueStyle={{ color: improvement >= 0 ? '#52c41a' : '#f5222d', fontSize: 32 }} />
          </Card>
        </Col>
      </Row>

      {/* 各联赛对比 */}
      <Card title="各联赛准确率对比" style={{ marginBottom: 24 }}>
        {leagues.length > 0 ? (
          <Table dataSource={leagues} columns={leagueColumns} rowKey="division"
            pagination={false} size="middle" />
        ) : (
          <Empty description="暂无联赛对比数据" />
        )}
      </Card>

      {/* 训练历史 */}
      <Card title="训练历史记录（准确率变化）">
        {timeline.length > 0 ? (
          <Table dataSource={timeline} columns={historyColumns} rowKey="run_id"
            pagination={false} size="middle" scroll={{ y: 400 }} />
        ) : (
          <Empty description="暂无训练记录。运行 python3 -m ai.evaluate 生成评估记录。" />
        )}
      </Card>

      {/* 模拟下单历史 */}
      {simHistory.length > 0 && (
        <Card title="模拟下单历史" style={{ marginTop: 24 }}>
          <Table dataSource={simHistory} rowKey="id" size="middle" pagination={false}
            columns={[
              { title: '时间', dataIndex: 'run_at', key: 't', width: 170, render: (v: string) => v?.slice(0, 19) },
              { title: '描述', dataIndex: 'description', key: 'd' },
              { title: '下注', dataIndex: 'n_bets', key: 'nb', width: 70 },
              { title: '命中', dataIndex: 'n_wins', key: 'nw', width: 70 },
              { title: '命中率', dataIndex: 'win_rate', key: 'wr', width: 80, render: (v: number) => `${(v * 100).toFixed(1)}%` },
              { title: 'ROI', dataIndex: 'roi_pct', key: 'roi', width: 80,
                render: (v: number) => <Text strong style={{ color: v > 0 ? '#52c41a' : '#f5222d' }}>{v.toFixed(1)}%</Text> },
              { title: '利润', dataIndex: 'profit', key: 'p', width: 100,
                render: (v: number) => <Text style={{ color: v > 0 ? '#52c41a' : '#f5222d' }}>¥{v.toFixed(0)}</Text> },
            ]} />
        </Card>
      )}
    </div>
  );
}
