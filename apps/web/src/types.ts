export interface DatasetCounts {
  assets: number;
  price_bars: number;
  filings: number;
  raw_records: number;
  quality_issues: number;
  news_items: number;
  social_items: number;
  video_items: number;
  corporate_disclosures: number;
  macro_observations: number;
  bond_securities: number;
  yield_curve_points: number;
}

export interface BondSecurity {
  isin: string;
  issuer: string;
  security_name: string;
  bond_type: "corporate" | "government" | "treasury_bill" | "sdl";
  coupon_rate_pct: number | null;
  coupon_frequency: number;
  issue_date: string | null;
  maturity_date: string;
  face_value: number;
  issue_price: number | null;
  rating: string | null;
  rating_agency: string | null;
  rating_outlook: string | null;
  secured: boolean | null;
  seniority: string | null;
  callable: boolean;
  puttable: boolean;
  sector: string | null;
  status: string;
  source: string;
  source_url: string;
  available_at: string;
}

export interface YieldCurvePoint {
  curve_date: string;
  tenor_years: number;
  yield_pct: number;
  source: string;
  source_url: string;
  available_at: string;
}

export interface BondRiskSummary {
  isin: string;
  years_to_maturity: number;
  annual_coupon_amount: number | null;
  benchmark_yield_pct: number | null;
  coupon_minus_benchmark_pct: number | null;
  rating_band: "sovereign" | "high" | "medium" | "low" | "unrated";
  liquidity_status: "unknown" | "metadata_only" | "traded" | "model_valued";
  risk_flags: string[];
}

export interface BondUniverseSnapshot {
  generated_at: string;
  curve_date: string | null;
  curve: YieldCurvePoint[];
  securities: BondSecurity[];
  risk: BondRiskSummary[];
  source_notes: string[];
  methodology: string;
}

export interface BondRefreshResult {
  curve_points: number;
  securities: number;
  source_date: string | null;
  warnings: string[];
}

export interface BondCalculation {
  isin: string;
  settlement_date: string;
  clean_price: number;
  current_yield_pct: number | null;
  ytm_pct: number | null;
  macaulay_duration_years: number | null;
  modified_duration_years: number | null;
  convexity: number | null;
  dv01: number | null;
  accrued_interest_included: boolean;
  scenarios: Array<{ shift_bps: number; repriced_clean_price: number; price_change_pct: number }>;
  warnings: string[];
  methodology: string;
}

export interface BondLadderProposal {
  generated_at: string;
  budget: number;
  horizon_years: number;
  risk_level: string;
  curve_date: string;
  buckets: Array<{
    label: string;
    tenor_years: number;
    allocation_pct: number;
    amount: number;
    indicative_yield_pct: number;
    duration_proxy_years: number;
  }>;
  weighted_indicative_yield_pct: number;
  weighted_duration_proxy_years: number;
  warnings: string[];
  methodology: string;
}

export interface AssetSummary {
  symbol: string;
  name: string | null;
  asset_type: string;
  exchange: string | null;
  currency: string;
  cik: string | null;
  active: boolean;
}

export interface SourceSummary {
  source: string;
  dataset: string;
  record_count: number;
  latest_available_at: string | null;
  latest_ingested_at: string | null;
  latest_run_status: string | null;
}

export interface RunSummary {
  run_id: string;
  source: string;
  dataset: string;
  partition_key: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  raw_count: number;
  accepted_count: number;
  rejected_count: number;
  error_message: string | null;
}

export interface QualityIssueSummary {
  issue_id: string;
  source: string;
  dataset: string;
  partition_key: string;
  natural_key: string | null;
  code: string;
  message: string;
  severity: string;
  detected_at: string;
}

export interface FilingSummary {
  symbol: string;
  form: string;
  accession_number: string;
  filing_date: string;
  report_date: string | null;
  available_at: string;
  source_url: string;
}

export interface LatestPrice {
  symbol: string;
  timeframe: string;
  event_time: string;
  available_at: string;
  close: number;
  volume: number;
  source: string;
}

export interface DashboardSnapshot {
  generated_at: string;
  latest_ingested_at: string | null;
  counts: DatasetCounts;
  assets: AssetSummary[];
  sources: SourceSummary[];
  latest_prices: LatestPrice[];
  recent_runs: RunSummary[];
  quality_issues: QualityIssueSummary[];
  recent_filings: FilingSummary[];
  market_analytics: MarketAnalytics;
  recent_content: ContentSummary[];
}

export interface PricePoint {
  event_time: string;
  available_at: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceSeries {
  symbol: string;
  timeframe: string | null;
  cutoff: string;
  points: PricePoint[];
}

export interface StockMetric {
  symbol: string;
  name: string | null;
  currency: string;
  as_of: string;
  close: number;
  return_20d_pct: number | null;
  return_60d_pct: number | null;
  volatility_20d_pct: number | null;
  max_drawdown_252d_pct: number | null;
  sharpe_252d: number | null;
  sortino_252d: number | null;
  cvar_95_daily_pct: number | null;
  distance_sma20_pct: number | null;
  rsi_14: number | null;
  average_volume_20d: number | null;
  observation_count: number;
  signal: string;
}

export interface MarketAnalytics {
  methodology: string;
  breadth: {
    covered_assets: number;
    positive_20d: number;
    positive_60d: number;
    above_sma20: number;
    median_return_20d_pct: number | null;
    median_volatility_20d_pct: number | null;
    median_sharpe_252d: number | null;
    median_cvar_95_daily_pct: number | null;
  };
  stocks: StockMetric[];
}

export interface ContentSummary {
  source: string;
  external_id: string;
  content_type: string;
  title: string;
  url: string;
  published_at: string;
  available_at: string;
  symbols: string[];
  sentiment_score: number | null;
}

export interface YouTubeVideo {
  video_id: string;
  channel_name: string;
  channel_handle: string;
  language: string | null;
  source_type: string;
  priority: number;
  title: string;
  summary: string | null;
  url: string;
  published_at: string;
  duration: string | null;
  view_count: number | null;
  like_count: number | null;
  symbols: string[];
}

export interface ChannelVideoDigest {
  channel_name: string;
  channel_handle: string;
  language: string | null;
  source_type: string;
  priority: number;
  video_count: number;
  summary: string;
  videos: YouTubeVideo[];
}

export interface DailyYouTubeDigest {
  date: string;
  timezone: string;
  generated_at: string;
  total_videos: number;
  covered_channels: number;
  configured_channels: number;
  headline: string;
  summary: string;
  channels: ChannelVideoDigest[];
  recommended_videos: Array<{
    video: YouTubeVideo;
    relevance_score: number;
    why_recommended: string;
    flashpoints: string[];
  }>;
  stock_research_ideas: Array<{
    symbol: string;
    mention_count: number;
    context: string;
    evidence_titles: string[];
  }>;
  methodology: string;
}

export interface MetricHistoryPoint {
  event_time: string;
  sharpe: number | null;
  sortino: number | null;
  annualized_volatility_pct: number | null;
  maximum_drawdown_pct: number | null;
}

export interface MetricHistory {
  symbol: string;
  timeframe: string;
  window: number;
  points: MetricHistoryPoint[];
  methodology: string;
}

export interface PortfolioHolding {
  symbol: string;
  name: string | null;
  sector: string;
  shares: number;
  price: number;
  invested_amount: number;
  weight_pct: number;
  evidence_score: number;
  signal: string;
  sharpe: number | null;
  sortino: number | null;
  volatility_pct: number | null;
  maximum_drawdown_pct: number | null;
  return_60d_pct: number | null;
  news_headlines: string[];
  rationale: string;
}

export interface PortfolioProposal {
  generated_at: string;
  budget: number;
  invested_amount: number;
  cash_remaining: number;
  risk_level: string;
  duration_months: number;
  objective: string;
  holdings: PortfolioHolding[];
  weighted_sharpe: number | null;
  weighted_sortino: number | null;
  weighted_volatility_pct: number | null;
  weighted_maximum_drawdown_pct: number | null;
  expectation: {
    horizon_months: number;
    low_return_pct: number;
    central_return_pct: number;
    high_return_pct: number;
    low_value: number;
    central_value: number;
    high_value: number;
    confidence_score: number;
    confidence_label: string;
    observation_count: number;
    assumptions: string[];
  };
  diversification: {
    sector_count: number;
    sector_allocations_pct: Record<string, number>;
    effective_holdings: number;
    average_pairwise_correlation: number | null;
    maximum_sector_weight_pct: number;
  };
  factor_weights_pct: Record<string, number>;
  ai_narrative: {
    summary: string;
    allocation_logic: string[];
    key_risks: string[];
    monitoring_triggers: string[];
    disclaimer: string;
  } | null;
  warnings: string[];
  methodology: string;
}

export interface TechnicalSnapshot {
  symbol: string;
  timeframe: string;
  cutoff: string;
  as_of: string;
  source: string;
  observation_count: number;
  close: number;
  returns: {
    one_day_pct: number | null;
    twenty_day_pct: number | null;
    sixty_day_pct: number | null;
    ninety_day_pct: number | null;
  };
  trend: {
    sma_20: number | null;
    sma_50: number | null;
    sma_200: number | null;
    ema_20: number | null;
    distance_sma_20_pct: number | null;
    distance_52_week_high_pct: number | null;
  };
  momentum: {
    rsi_14: number | null;
    macd: number | null;
    macd_signal: number | null;
    macd_histogram: number | null;
  };
  risk: {
    annualized_volatility_30d_pct: number | null;
    annualized_volatility_90d_pct: number | null;
    atr_14: number | null;
    max_drawdown_252d_pct: number | null;
    sharpe_252d: number | null;
    sortino_252d: number | null;
    cvar_95_daily_pct: number | null;
  };
  liquidity: {
    average_volume_20d: number | null;
    volume_ratio_20d: number | null;
  };
  signal: string;
  methodology: string;
}

export interface ResearchEvidence {
  evidence_id: string;
  category: string;
  title: string;
  detail: string;
  direction: "supporting" | "contradicting" | "neutral" | "risk";
  source_type: string;
  source_id: string;
  source_url: string | null;
  observed_at: string;
  freshness: "fresh" | "recent" | "aging" | "stale";
}

export interface ResearchClaim {
  claim_id: string;
  claim_type: string;
  claim: string;
  evidence_ids: string[];
  confidence: number;
  status: "supported" | "mixed" | "caution" | "insufficient_data";
}

export interface ResearchSnapshot {
  symbol: string;
  company_name: string | null;
  exchange: string | null;
  currency: string;
  generated_at: string;
  cutoff: string;
  technical: TechnicalSnapshot;
  evidence: ResearchEvidence[];
  claims: ResearchClaim[];
  coverage: {
    price_history: boolean;
    technical_metrics: boolean;
    news: boolean;
    fundamentals: boolean;
    macro: boolean;
    video: boolean;
    social: boolean;
    missing: string[];
  };
  methodology: string;
}

export interface NarrativeEvidence {
  title: string;
  explanation: string;
  evidence_ids: string[];
}

export interface ScenarioNarrative {
  label: string;
  assumptions: string[];
  interpretation: string;
}

export interface ResearchNarrative {
  analysis_id: string;
  symbol: string;
  model: string;
  prompt_version: string;
  snapshot_hash: string;
  generated_at: string;
  narrative: {
    executive_summary: string;
    what_is_happening: string;
    why_it_matters: string;
    supporting_evidence: NarrativeEvidence[];
    contradicting_evidence: NarrativeEvidence[];
    key_risks: string[];
    assumptions: string[];
    thesis_breakers: string[];
    bull_case: ScenarioNarrative;
    base_case: ScenarioNarrative;
    bear_case: ScenarioNarrative;
    confidence: number;
    data_gaps: string[];
    disclaimer: string;
  };
}

export interface ThesisBreaker {
  rule_id: string;
  label: string;
  metric: string;
  operator: "lt" | "lte" | "gt" | "gte";
  threshold: number;
  current_value: number | null;
  breached: boolean;
  severity: "monitor" | "material" | "critical";
  interpretation: string;
}

export interface ThesisChange {
  field: string;
  label: string;
  previous_value: number | string | boolean | null;
  current_value: number | string | boolean | null;
  delta: number | null;
  material: boolean;
  interpretation: string;
}

export interface ThesisVersion {
  thesis_id: string;
  symbol: string;
  version_number: number;
  cutoff: string;
  as_of: string;
  created_at: string;
  previous_version_id: string | null;
  snapshot_hash: string;
  state: "constructive" | "neutral" | "cautious" | "at_risk";
  confidence: number;
  evidence_coverage_pct: number;
  metrics: {
    close: number;
    signal: string;
    return_60d_pct: number | null;
    distance_sma_20_pct: number | null;
    rsi_14: number | null;
    volatility_30d_pct: number | null;
    maximum_drawdown_252d_pct: number | null;
    sharpe_252d: number | null;
    cvar_95_daily_pct: number | null;
  };
  breakers: ThesisBreaker[];
  changes: ThesisChange[];
  contradictions: Array<{
    contradiction_id: string;
    contradiction_type: string;
    severity: "low" | "medium" | "high";
    summary: string;
    supporting_evidence_ids: string[];
    contradicting_evidence_ids: string[];
    interpretation: string;
  }>;
  sensitivity: Array<{
    scenario_id: string;
    removed_category: string;
    baseline_confidence: number;
    perturbed_confidence: number;
    confidence_delta: number;
    remaining_evidence_count: number;
    fragile: boolean;
    interpretation: string;
  }>;
  methodology_version: string;
  methodology: string;
}

export interface ThesisEvaluation {
  thesis_id: string;
  symbol: string;
  version_number: number;
  thesis_cutoff: string;
  thesis_as_of: string;
  evaluated_at: string;
  expected_direction: "positive" | "negative" | "undirected";
  outcomes: Array<{
    horizon_trading_days: number;
    available: boolean;
    end_date: string | null;
    realized_return_pct: number | null;
    realized_direction: "positive" | "negative" | "flat" | "unavailable";
    thesis_aligned: boolean | null;
  }>;
  scored_horizons: number;
  aligned_horizons: number;
  directional_accuracy: number | null;
  methodology: string;
}

export interface FundamentalFact {
  metric: string;
  value: number | null;
  text_value: string | null;
  unit: string | null;
  source_concept: string;
  derived: boolean;
  formula: string | null;
  evidence_id: string;
}

export interface FundamentalPeriod {
  document_id: string;
  filing_external_id: string;
  period_start: string | null;
  period_end: string | null;
  basis: string;
  audited: boolean | null;
  taxonomy: string;
  source_url: string;
  available_at: string;
  revision_number: number;
  metrics: FundamentalFact[];
}

export interface FundamentalSnapshot {
  symbol: string;
  generated_at: string;
  cutoff: string;
  period_count: number;
  latest_period_end: string | null;
  latest_basis: string | null;
  periods: FundamentalPeriod[];
  insights: Array<{
    insight_id: string;
    kind: "growth" | "profitability" | "quality" | "risk" | "data_quality";
    severity: "positive" | "neutral" | "caution";
    title: string;
    detail: string;
    evidence_ids: string[];
  }>;
  coverage: Record<string, boolean>;
  methodology: string;
}

export interface FilingRefreshResult {
  symbol: string;
  considered_filings: number;
  downloaded_documents: number;
  cached_documents: number;
  parsed_documents: number;
  failed_documents: number;
  normalized_facts: number;
  warnings: string[];
}
