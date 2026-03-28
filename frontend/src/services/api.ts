import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

export interface LeagueStat {
  division: string;
  country: string | null;
  league_name: string | null;
  match_count: number;
  first_season: string | null;
  last_season: string | null;
}

export interface DashboardStats {
  total_matches: number;
  total_odds_records: number;
  total_asian_records: number;
  by_division: LeagueStat[];
}

export interface MatchItem {
  match_id: number;
  division: string;
  season: string;
  match_date: string;
  home_team: string;
  away_team: string;
  fthg: number | null;
  ftag: number | null;
  ftr: string | null;
  b365_h: number | null;
  b365_d: number | null;
  b365_a: number | null;
  ps_h: number | null;
  ps_d: number | null;
  ps_a: number | null;
  ah_handicap: number | null;
}

export interface MatchListResponse {
  matches: MatchItem[];
  total: number;
  page: number;
  total_pages: number;
}

export interface OddsRecord {
  bookmaker: string;
  is_closing: number;
  home_odds: number | null;
  draw_odds: number | null;
  away_odds: number | null;
  overround: number | null;
}

export interface AsianOddsRecord {
  bookmaker: string;
  is_closing: number;
  handicap: number | null;
  home_odds: number | null;
  away_odds: number | null;
}

export interface OURecord {
  bookmaker: string;
  is_closing: number;
  over_odds: number | null;
  under_odds: number | null;
}

export interface MatchDetail {
  match_id: number;
  division: string;
  season: string;
  match_date: string;
  match_time: string | null;
  home_team: string;
  away_team: string;
  fthg: number | null;
  ftag: number | null;
  ftr: string | null;
  hthg: number | null;
  htag: number | null;
  referee: string | null;
  home_shots: number | null;
  away_shots: number | null;
  home_sot: number | null;
  away_sot: number | null;
  home_corners: number | null;
  away_corners: number | null;
  home_fouls: number | null;
  away_fouls: number | null;
  home_yellows: number | null;
  away_yellows: number | null;
  home_reds: number | null;
  away_reds: number | null;
  odds_1x2: OddsRecord[];
  odds_asian: AsianOddsRecord[];
  odds_ou25: OURecord[];
}

export interface PredictionItem {
  match_id: number;
  home_team: string;
  away_team: string;
  match_date: string;
  division: string;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  pred_label: string;
  confidence: number;
}

export const getStats = () => api.get<DashboardStats>('/history/stats');
export const getMatches = (params: { division?: string; season?: string; page?: number; page_size?: number }) =>
  api.get<MatchListResponse>('/history/matches', { params });
export const getMatchDetail = (id: number) => api.get<MatchDetail>(`/history/matches/${id}`);
export const getPredictions = () => api.get<PredictionItem[]>('/prediction/upcoming');
export const getModelInfo = () => api.get('/prediction/model-info');
