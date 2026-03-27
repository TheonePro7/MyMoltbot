import { useEffect, useState } from 'react';
import { Card, Table, Tag, Progress, Typography, Spin, Space, Tooltip } from 'antd';
import { TrophyOutlined } from '@ant-design/icons';
import { getPredictions } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

const labelMap: Record<string, { text: string; color: string }> = {
  H: { text: '主胜', color: 'green' },
  D: { text: '平局', color: 'orange' },
  A: { text: '客胜', color: 'red' },
};

export default function Prediction() {
  const [preds, setPreds] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getPredictions().then(r => { setPreds(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const columns = [
    { title: '日期', dataIndex: 'match_date', key: 'date', width: 120 },
    { title: '联赛', dataIndex: 'division', key: 'div', width: 70,
      render: (v: string) => <Tag>{v}</Tag> },
    { title: '主队', dataIndex: 'home_team', key: 'home' },
    { title: '客队', dataIndex: 'away_team', key: 'away' },
    {
      title: '主胜概率', key: 'ph', width: 110,
      render: (_: any, r: PredictionItem) => (
        <Progress percent={Math.round(r.prob_home * 100)} size="small"
          strokeColor={r.pred_label === 'H' ? '#52c41a' : '#d9d9d9'} />
      ),
    },
    {
      title: '平局概率', key: 'pd', width: 110,
      render: (_: any, r: PredictionItem) => (
        <Progress percent={Math.round(r.prob_draw * 100)} size="small"
          strokeColor={r.pred_label === 'D' ? '#fa8c16' : '#d9d9d9'} />
      ),
    },
    {
      title: '客胜概率', key: 'pa', width: 110,
      render: (_: any, r: PredictionItem) => (
        <Progress percent={Math.round(r.prob_away * 100)} size="small"
          strokeColor={r.pred_label === 'A' ? '#f5222d' : '#d9d9d9'} />
      ),
    },
    {
      title: '预测', key: 'pred', width: 100,
      render: (_: any, r: PredictionItem) => {
        const info = labelMap[r.pred_label] || { text: r.pred_label, color: 'default' };
        return <Tag color={info.color} icon={<TrophyOutlined />}>{info.text}</Tag>;
      },
    },
    {
      title: '置信度', key: 'conf', width: 100, sorter: (a: PredictionItem, b: PredictionItem) => a.confidence - b.confidence,
      defaultSortOrder: 'descend' as const,
      render: (_: any, r: PredictionItem) => {
        const pct = Math.round(r.confidence * 100);
        const color = pct >= 80 ? '#52c41a' : pct >= 60 ? '#1677ff' : pct >= 50 ? '#fa8c16' : '#999';
        return <Text strong style={{ color }}>{pct}%</Text>;
      },
    },
  ];

  const highConf = preds.filter(p => p.confidence >= 0.6);

  return (
    <div>
      <Title level={2}>智能预测</Title>

      {highConf.length > 0 && (
        <Card title={<span><TrophyOutlined style={{ color: '#faad14' }} /> 高置信度推荐（≥60%）</span>}
          style={{ marginBottom: 16 }} bodyStyle={{ padding: '12px 16px' }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            {highConf.slice(0, 8).map(p => {
              const info = labelMap[p.pred_label] || { text: p.pred_label, color: 'default' };
              return (
                <Card key={p.match_id} size="small" hoverable
                  onClick={() => navigate(`/history/${p.match_id}`)}
                  style={{ borderLeft: `4px solid ${info.color === 'green' ? '#52c41a' : info.color === 'red' ? '#f5222d' : '#fa8c16'}` }}>
                  <Space>
                    <Tag>{p.division}</Tag>
                    <Text type="secondary">{p.match_date}</Text>
                    <Text strong>{p.home_team} vs {p.away_team}</Text>
                    <Tag color={info.color} icon={<TrophyOutlined />}>{info.text}</Tag>
                    <Text strong style={{ color: '#1677ff' }}>{Math.round(p.confidence * 100)}%</Text>
                  </Space>
                </Card>
              );
            })}
          </Space>
        </Card>
      )}

      <Card title={`全部预测（${preds.length} 场）`}>
        <Table dataSource={preds} columns={columns} rowKey="match_id" size="middle"
          onRow={r => ({ onClick: () => navigate(`/history/${r.match_id}`), style: { cursor: 'pointer' } })}
          pagination={{ pageSize: 20, showTotal: t => `共 ${t} 场` }} />
      </Card>
    </div>
  );
}
