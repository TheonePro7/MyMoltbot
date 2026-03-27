import { useEffect, useState } from 'react';
import { Card, Table, Button, InputNumber, Input, Typography, Spin, Space, Tag, message, Descriptions, Row, Col, Statistic, Alert } from 'antd';
import { ExperimentOutlined, HistoryOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Title, Text } = Typography;

interface EvalRecord {
  id: string;
  run_at: string;
  description: string;
  n_matches: number;
  accuracy: number;
  accuracy_home: number;
  accuracy_draw: number;
  accuracy_away: number;
  high_conf_accuracy: number;
  high_conf_count: number;
}

interface EvalResult {
  run_id: string;
  n_matches: number;
  n_skipped_no_odds: number;
  train_size: number;
  test_date_range: string;
  accuracy: number;
  accuracy_home: number;
  accuracy_draw: number;
  accuracy_away: number;
  high_conf_accuracy: number;
  high_conf_count: number;
  pred_distribution: Record<string, number>;
  actual_distribution: Record<string, number>;
  by_division: { division: string; matches: number; accuracy: number }[];
  by_confidence: { bin: string; matches: number; accuracy: number }[];
}

export default function Evaluate() {
  const [history, setHistory] = useState<EvalRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [matchCount, setMatchCount] = useState(2000);
  const [desc, setDesc] = useState('');
  const [latestResult, setLatestResult] = useState<EvalResult | null>(null);

  const loadHistory = () => {
    setLoading(true);
    axios.get('/api/prediction/eval-history').then(r => {
      setHistory(r.data);
      setLoading(false);
    });
  };

  useEffect(() => { loadHistory(); }, []);

  const runEval = () => {
    setRunning(true);
    message.loading({ content: `正在评估最近 ${matchCount} 场比赛...`, key: 'eval', duration: 0 });
    axios.get('/api/prediction/evaluate', { params: { matches: matchCount, desc }, timeout: 120000 })
      .then(r => {
        setLatestResult(r.data);
        message.success({ content: '评估完成！', key: 'eval' });
        loadHistory();
        setRunning(false);
      })
      .catch(e => {
        message.error({ content: `评估失败: ${e.response?.data?.detail || e.message}`, key: 'eval' });
        setRunning(false);
      });
  };

  const historyColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    { title: '时间', dataIndex: 'run_at', key: 'time', width: 180,
      render: (v: string) => v?.slice(0, 19) },
    { title: '描述', dataIndex: 'description', key: 'desc',
      render: (v: string) => v || <Text type="secondary">(无)</Text> },
    { title: '场数', dataIndex: 'n_matches', key: 'n', width: 80 },
    { title: '准确率', dataIndex: 'accuracy', key: 'acc', width: 100,
      render: (v: number) => <Text strong style={{ color: v >= 0.55 ? '#52c41a' : '#fa8c16' }}>{(v * 100).toFixed(1)}%</Text> },
    { title: '主胜', dataIndex: 'accuracy_home', key: 'ah', width: 80,
      render: (v: number) => `${(v * 100).toFixed(1)}%` },
    { title: '平', dataIndex: 'accuracy_draw', key: 'ad', width: 80,
      render: (v: number) => `${(v * 100).toFixed(1)}%` },
    { title: '客胜', dataIndex: 'accuracy_away', key: 'aa', width: 80,
      render: (v: number) => `${(v * 100).toFixed(1)}%` },
    { title: '高置信', key: 'hc', width: 100,
      render: (_: any, r: EvalRecord) => `${(r.high_conf_accuracy * 100).toFixed(1)}% (${r.high_conf_count})` },
  ];

  const prev = history.length >= 2 ? history[1] : null;

  return (
    <div>
      <Title level={2}>模型评估</Title>
      <Alert message="对最近 N 场已结束的比赛做预测（假装不知道结果），对比实际结果计算准确率。每次评估都会保存记录，方便对比改动效果。"
        type="info" showIcon style={{ marginBottom: 16 }} />

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>评估场数：</span>
          <InputNumber min={100} max={5000} value={matchCount} onChange={v => setMatchCount(v || 2000)} />
          <span>描述：</span>
          <Input placeholder="如：基线模型 / 新增亚盘特征" value={desc} onChange={e => setDesc(e.target.value)}
            style={{ width: 250 }} />
          <Button type="primary" icon={<ExperimentOutlined />} loading={running} onClick={runEval}>
            开始评估
          </Button>
        </Space>
      </Card>

      {latestResult && (
        <Card title="最新评估结果" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={6}>
              <Statistic title="总准确率" value={latestResult.accuracy * 100} precision={1} suffix="%"
                valueStyle={{ color: '#1677ff', fontSize: 28 }}
                prefix={prev ? (latestResult.accuracy > prev.accuracy ? <ArrowUpOutlined style={{color:'#52c41a'}}/> : <ArrowDownOutlined style={{color:'#f5222d'}}/>) : undefined} />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic title="主胜" value={latestResult.accuracy_home * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic title="平局" value={latestResult.accuracy_draw * 100} precision={1} suffix="%" />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic title="客胜" value={latestResult.accuracy_away * 100} precision={1} suffix="%" />
            </Col>
          </Row>
          <Descriptions column={3} size="small" style={{ marginTop: 16 }}>
            <Descriptions.Item label="评估场数">{latestResult.n_matches}</Descriptions.Item>
            <Descriptions.Item label="训练集">{latestResult.train_size} 场</Descriptions.Item>
            <Descriptions.Item label="日期范围">{latestResult.test_date_range}</Descriptions.Item>
            <Descriptions.Item label="高置信(≥50%)">{(latestResult.high_conf_accuracy * 100).toFixed(1)}% ({latestResult.high_conf_count}场)</Descriptions.Item>
          </Descriptions>

          {latestResult.by_confidence && latestResult.by_confidence.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Text strong>按置信度区间：</Text>
              <Table dataSource={latestResult.by_confidence} size="small" pagination={false} rowKey="bin"
                style={{ marginTop: 8 }}
                columns={[
                  { title: '置信度区间', dataIndex: 'bin', key: 'bin' },
                  { title: '场数', dataIndex: 'matches', key: 'n' },
                  { title: '准确率', dataIndex: 'accuracy', key: 'acc',
                    render: (v: number) => <Tag color={v >= 0.6 ? 'green' : v >= 0.5 ? 'blue' : 'default'}>{(v * 100).toFixed(1)}%</Tag> },
                ]} />
            </div>
          )}
        </Card>
      )}

      <Card title={<span><HistoryOutlined /> 历史评估记录</span>}>
        <Table dataSource={history} columns={historyColumns} rowKey="id" loading={loading}
          size="middle" pagination={false} />
      </Card>
    </div>
  );
}
