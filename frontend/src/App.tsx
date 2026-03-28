import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, ConfigProvider, theme } from 'antd';
import { DashboardOutlined, DatabaseOutlined, ExperimentOutlined, ShoppingCartOutlined, BarChartOutlined, RiseOutlined } from '@ant-design/icons';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import MatchDetailPage from './pages/MatchDetailPage';
import Prediction from './pages/Prediction';
import Evaluate from './pages/Evaluate';
import TrainingDashboard from './pages/TrainingDashboard';
import ParlayBacktest from './pages/ParlayBacktest';
import DailyRecommend from './pages/DailyRecommend';

const { Header, Content, Footer } = Layout;

function AppMenu() {
  const location = useLocation();
  const path = location.pathname;
  let selected = '/';
  if (path.startsWith('/history')) selected = '/history';
  if (path.startsWith('/prediction')) selected = '/prediction';
  if (path.startsWith('/evaluate')) selected = '/evaluate';
  if (path.startsWith('/growth')) selected = '/growth';
  if (path.startsWith('/recommend')) selected = '/recommend';
  if (path.startsWith('/parlay')) selected = '/parlay';

  return (
    <Menu theme="dark" mode="horizontal" selectedKeys={[selected]} style={{ flex: 1 }}
      items={[
        { key: '/', icon: <DashboardOutlined />, label: <Link to="/">数据总览</Link> },
        { key: '/history', icon: <DatabaseOutlined />, label: <Link to="/history">历史数据</Link> },
        { key: '/prediction', icon: <ExperimentOutlined />, label: <Link to="/prediction">智能预测</Link> },
        { key: '/evaluate', icon: <BarChartOutlined />, label: <Link to="/evaluate">模型评估</Link> },
        { key: '/growth', icon: <RiseOutlined />, label: <Link to="/growth">模型成长</Link> },
        { key: '/recommend', icon: <ExperimentOutlined />, label: <Link to="/recommend">每日推荐</Link> },
        { key: '/parlay', icon: <DashboardOutlined />, label: <Link to="/parlay">串关回测</Link> },
        { key: 'sim', icon: <ShoppingCartOutlined />, label: <a href="http://localhost:5000/bet" target="_blank" rel="noreferrer">模拟投注</a> },
      ]}
    />
  );
}

export default function App() {
  return (
    <ConfigProvider theme={{
      algorithm: theme.defaultAlgorithm,
      token: { colorPrimary: '#1677ff', borderRadius: 8 },
    }}>
      <BrowserRouter>
        <Layout style={{ minHeight: '100vh' }}>
          <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
            <div style={{ color: '#fff', fontSize: 20, fontWeight: 700, marginRight: 32, whiteSpace: 'nowrap' }}>
              ⚽ MyMoltbot
            </div>
            <AppMenu />
          </Header>
          <Content style={{ padding: '24px 48px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/history" element={<History />} />
              <Route path="/history/:id" element={<MatchDetailPage />} />
              <Route path="/prediction" element={<Prediction />} />
              <Route path="/evaluate" element={<Evaluate />} />
              <Route path="/growth" element={<TrainingDashboard />} />
              <Route path="/recommend" element={<DailyRecommend />} />
              <Route path="/parlay" element={<ParlayBacktest />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: 'center', color: '#999' }}>
            MyMoltbot 足彩赔率分析与智能预测系统
          </Footer>
        </Layout>
      </BrowserRouter>
    </ConfigProvider>
  );
}
