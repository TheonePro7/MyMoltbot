import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Typography, Spin } from 'antd';
import { DatabaseOutlined, LineChartOutlined, GlobalOutlined } from '@ant-design/icons';
import { getStats } from '../services/api';

const { Title } = Typography;

export default function Dashboard() {
  const [stats, setStats] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats().then(r => { setStats(r.data); setLoading(false); });
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!stats) return null;

  const columns = [
    { title: '联赛代码', dataIndex: 'division', key: 'division', width: 100 },
    { title: '国家', dataIndex: 'country', key: 'country', width: 120 },
    { title: '联赛名称', dataIndex: 'league_name', key: 'league_name' },
    {
      title: '比赛数',
      dataIndex: 'match_count',
      key: 'match_count',
      sorter: (a: any, b: any) => a.match_count - b.match_count,
      render: (v: number) => v.toLocaleString(),
    },
    { title: '赛季范围', key: 'range', render: (_: any, r: any) => `${r.first_season} ~ ${r.last_season}` },
  ];

  return (
    <div>
      <Title level={2}>数据总览</Title>
      <Row gutter={[24, 24]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card hoverable>
            <Statistic title="历史比赛总数" value={stats.total_matches} prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#1677ff', fontSize: 32 }} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable>
            <Statistic title="欧赔记录" value={stats.total_odds_records} prefix={<LineChartOutlined />}
              valueStyle={{ color: '#52c41a', fontSize: 32 }} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card hoverable>
            <Statistic title="亚盘记录" value={stats.total_asian_records} prefix={<GlobalOutlined />}
              valueStyle={{ color: '#fa8c16', fontSize: 32 }} />
          </Card>
        </Col>
      </Row>

      <Card title="各联赛数据">
        <Table dataSource={stats.by_division} columns={columns} rowKey="division"
          pagination={false} size="middle" />
      </Card>
    </div>
  );
}
