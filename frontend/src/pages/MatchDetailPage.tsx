import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Table, Tag, Spin, Button, Typography, Row, Col, Statistic } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getMatchDetail } from '../services/api';

const { Title } = Typography;

export default function MatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [match, setMatch] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      getMatchDetail(Number(id)).then(r => { setMatch(r.data); setLoading(false); });
    }
  }, [id]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!match) return <div>比赛不存在</div>;

  const ftrLabel: Record<string, string> = { H: '主胜', D: '平', A: '客胜' };

  const oddsColumns = [
    { title: '庄家', dataIndex: 'bookmaker', key: 'bm', width: 160 },
    { title: '类型', key: 'type', width: 70,
      render: (_: any, r: any) => <Tag color={r.is_closing ? 'green' : 'blue'}>{r.is_closing ? '终盘' : '初盘'}</Tag> },
    { title: '主胜', dataIndex: 'home_odds', key: 'h', render: (v: number | null) => v?.toFixed(2) || '-' },
    { title: '平局', dataIndex: 'draw_odds', key: 'd', render: (v: number | null) => v?.toFixed(2) || '-' },
    { title: '客胜', dataIndex: 'away_odds', key: 'a', render: (v: number | null) => v?.toFixed(2) || '-' },
    { title: '抽水%', dataIndex: 'overround', key: 'or', width: 80,
      render: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
  ];

  const ahColumns = [
    { title: '庄家', dataIndex: 'bookmaker', key: 'bm', width: 160 },
    { title: '类型', key: 'type', width: 70,
      render: (_: any, r: any) => <Tag color={r.is_closing ? 'green' : 'blue'}>{r.is_closing ? '终盘' : '初盘'}</Tag> },
    { title: '盘口', dataIndex: 'handicap', key: 'hc', render: (v: number | null) => v ?? '-' },
    { title: '主队水位', dataIndex: 'home_odds', key: 'h', render: (v: number | null) => v?.toFixed(2) || '-' },
    { title: '客队水位', dataIndex: 'away_odds', key: 'a', render: (v: number | null) => v?.toFixed(2) || '-' },
  ];

  const ouColumns = [
    { title: '庄家', dataIndex: 'bookmaker', key: 'bm', width: 160 },
    { title: '类型', key: 'type', width: 70,
      render: (_: any, r: any) => <Tag color={r.is_closing ? 'green' : 'blue'}>{r.is_closing ? '终盘' : '初盘'}</Tag> },
    { title: '大 2.5', dataIndex: 'over_odds', key: 'ov', render: (v: number | null) => v?.toFixed(2) || '-' },
    { title: '小 2.5', dataIndex: 'under_odds', key: 'un', render: (v: number | null) => v?.toFixed(2) || '-' },
  ];

  const hasStats = match.home_shots != null;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>返回</Button>

      <Card style={{ marginBottom: 16 }}>
        <Title level={3}>{match.home_team} vs {match.away_team}</Title>
        <Descriptions column={{ xs: 1, sm: 2, md: 4 }} size="small">
          <Descriptions.Item label="北京时间">{match.match_date} {(match as any).match_time_bj || match.match_time || ''}</Descriptions.Item>
          <Descriptions.Item label="联赛">{match.division} ({match.season})</Descriptions.Item>
          <Descriptions.Item label="比分">
            {match.fthg != null ? (
              <span><strong>{match.fthg}:{match.ftag}</strong> <Tag>{ftrLabel[match.ftr || ''] || match.ftr}</Tag></span>
            ) : '未赛'}
          </Descriptions.Item>
          {match.referee && <Descriptions.Item label="裁判">{match.referee}</Descriptions.Item>}
        </Descriptions>
      </Card>

      {hasStats && (
        <Card title="比赛统计" style={{ marginBottom: 16 }} size="small">
          <Row gutter={16}>
            {[
              ['射门', match.home_shots, match.away_shots],
              ['射正', match.home_sot, match.away_sot],
              ['角球', match.home_corners, match.away_corners],
              ['犯规', match.home_fouls, match.away_fouls],
              ['黄牌', match.home_yellows, match.away_yellows],
              ['红牌', match.home_reds, match.away_reds],
            ].map(([label, h, a]) => (
              <Col xs={12} sm={8} md={4} key={label as string}>
                <Statistic title={label as string} value={`${h ?? '-'} : ${a ?? '-'}`}
                  valueStyle={{ fontSize: 18, textAlign: 'center' }} />
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {match.odds_1x2.length > 0 && (
        <Card title={`欧赔 1X2（${match.odds_1x2.length} 条记录）`} style={{ marginBottom: 16 }}>
          <Table dataSource={match.odds_1x2} columns={oddsColumns}
            rowKey={(r, i) => `${r.bookmaker}-${r.is_closing}-${i}`}
            pagination={false} size="small" scroll={{ y: 500 }}
            rowClassName={r => r.is_closing ? 'closing-row' : ''} />
        </Card>
      )}

      {match.odds_ou25.length > 0 && (
        <Card title={`大小球 2.5（${match.odds_ou25.length} 条记录）`} style={{ marginBottom: 16 }}>
          <Table dataSource={match.odds_ou25} columns={ouColumns}
            rowKey={(r, i) => `ou-${r.bookmaker}-${r.is_closing}-${i}`}
            pagination={false} size="small" />
        </Card>
      )}

      {match.odds_asian.length > 0 && (
        <Card title={`亚盘（${match.odds_asian.length} 条记录）`}>
          <Table dataSource={match.odds_asian} columns={ahColumns}
            rowKey={(r, i) => `ah-${r.bookmaker}-${r.is_closing}-${i}`}
            pagination={false} size="small" />
        </Card>
      )}
    </div>
  );
}
