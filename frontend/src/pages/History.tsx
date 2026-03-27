import { useEffect, useState } from 'react';
import { Card, Table, Select, Input, Space, Tag, Typography } from 'antd';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getMatches, getStats, MatchItem, LeagueStat } from '../services/api';

const { Title } = Typography;

const ftrColor: Record<string, string> = { H: 'green', D: 'orange', A: 'red' };
const ftrLabel: Record<string, string> = { H: '主胜', D: '平', A: '客胜' };

export default function History() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const [division, setDivision] = useState(searchParams.get('division') || '');
  const [season, setSeason] = useState(searchParams.get('season') || '');
  const [leagues, setLeagues] = useState<LeagueStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats().then(r => setLeagues(r.data.by_division));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: any = { page, page_size: 30 };
    if (division) params.division = division;
    if (season) params.season = season;
    getMatches(params).then(r => {
      setMatches(r.data.matches);
      setTotal(r.data.total);
      setLoading(false);
    });
    const sp: any = {};
    if (division) sp.division = division;
    if (season) sp.season = season;
    if (page > 1) sp.page = String(page);
    setSearchParams(sp, { replace: true });
  }, [page, division, season]);

  const columns = [
    { title: '日期', dataIndex: 'match_date', key: 'date', width: 120 },
    { title: '联赛', dataIndex: 'division', key: 'div', width: 70,
      render: (v: string) => <Tag>{v}</Tag> },
    { title: '主队', dataIndex: 'home_team', key: 'home' },
    {
      title: '比分', key: 'score', width: 100, align: 'center' as const,
      render: (_: any, r: MatchItem) => {
        if (r.fthg == null) return <Tag>未赛</Tag>;
        return (
          <span>
            <strong>{r.fthg}:{r.ftag}</strong>{' '}
            <Tag color={ftrColor[r.ftr || ''] || 'default'}>{ftrLabel[r.ftr || ''] || r.ftr}</Tag>
          </span>
        );
      },
    },
    { title: '客队', dataIndex: 'away_team', key: 'away' },
    { title: 'B365 主', key: 'b365h', width: 80, render: (_: any, r: MatchItem) => r.b365_h?.toFixed(2) || '-' },
    { title: 'B365 平', key: 'b365d', width: 80, render: (_: any, r: MatchItem) => r.b365_d?.toFixed(2) || '-' },
    { title: 'B365 客', key: 'b365a', width: 80, render: (_: any, r: MatchItem) => r.b365_a?.toFixed(2) || '-' },
    { title: '亚盘', key: 'ah', width: 70, render: (_: any, r: MatchItem) => r.ah_handicap ?? '-' },
  ];

  return (
    <div>
      <Title level={2}>历史数据</Title>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select style={{ width: 200 }} placeholder="选择联赛" allowClear value={division || undefined}
            onChange={v => { setDivision(v || ''); setPage(1); }}>
            {leagues.map(l => (
              <Select.Option key={l.division} value={l.division}>
                {l.division} - {l.league_name} ({l.match_count.toLocaleString()})
              </Select.Option>
            ))}
          </Select>
          <Input placeholder="赛季 如 2526" style={{ width: 140 }} value={season}
            onChange={e => { setSeason(e.target.value); setPage(1); }} allowClear />
          <span style={{ color: '#999' }}>共 {total.toLocaleString()} 场</span>
        </Space>
      </Card>

      <Table dataSource={matches} columns={columns} rowKey="match_id" loading={loading}
        size="middle" onRow={r => ({ onClick: () => navigate(`/history/${r.match_id}`), style: { cursor: 'pointer' } })}
        pagination={{ current: page, total, pageSize: 30, showSizeChanger: false,
          onChange: p => setPage(p), showTotal: t => `共 ${t.toLocaleString()} 场` }} />
    </div>
  );
}
