import type {
  AssetSummary,
  BondCalculation,
  BondLadderProposal,
  BondRefreshResult,
  BondUniverseSnapshot,
  DashboardSnapshot,
  DailyYouTubeDigest,
  FilingRefreshResult,
  FundamentalSnapshot,
  MetricHistory,
  PortfolioProposal,
  PriceSeries,
  ResearchNarrative,
  ResearchSnapshot,
  ThesisEvaluation,
  ThesisVersion
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(
  path: string,
  signal?: AbortSignal,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Accept: "application/json", ...options?.headers },
    signal,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `API request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchResearchSnapshot(
  symbol: string,
  signal?: AbortSignal
): Promise<ResearchSnapshot> {
  return request<ResearchSnapshot>(
    `/api/v1/research/${encodeURIComponent(symbol)}`,
    signal
  );
}

export function prepareResearchSnapshot(
  symbol: string,
  signal?: AbortSignal
): Promise<ResearchSnapshot> {
  return request<ResearchSnapshot>(
    `/api/v1/research/${encodeURIComponent(symbol)}/prepare?refresh_news=true`,
    signal,
    { method: "POST" }
  );
}

export function searchNseCompanies(
  query: string,
  signal?: AbortSignal
): Promise<AssetSummary[]> {
  return request<AssetSummary[]>(
    `/api/v1/companies/search?q=${encodeURIComponent(query)}&limit=12`,
    signal
  );
}

export function generateResearchNarrative(
  symbol: string,
  horizon: "short_term" | "medium_term" | "long_term",
  riskProfile: "conservative" | "balanced" | "aggressive",
  signal?: AbortSignal
): Promise<ResearchNarrative> {
  return request<ResearchNarrative>(
    `/api/v1/research/${encodeURIComponent(symbol)}/explain`,
    signal,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ horizon, risk_profile: riskProfile }),
    }
  );
}

export function createThesisVersion(
  symbol: string,
  cutoffDate: string,
  signal?: AbortSignal
): Promise<ThesisVersion> {
  const cutoff = `${cutoffDate}T23:59:59+05:30`;
  return request<ThesisVersion>(
    `/api/v1/research/${encodeURIComponent(symbol)}/thesis?cutoff=${encodeURIComponent(cutoff)}`,
    signal,
    { method: "POST" }
  );
}

export function fetchThesisVersions(
  symbol: string,
  signal?: AbortSignal
): Promise<ThesisVersion[]> {
  return request<ThesisVersion[]>(
    `/api/v1/research/${encodeURIComponent(symbol)}/thesis/versions?limit=24`,
    signal
  );
}

export function fetchThesisEvaluation(
  thesisId: string,
  signal?: AbortSignal
): Promise<ThesisEvaluation> {
  return request<ThesisEvaluation>(
    `/api/v1/theses/${encodeURIComponent(thesisId)}/evaluation`,
    signal
  );
}

export function fetchFundamentals(
  symbol: string,
  signal?: AbortSignal
): Promise<FundamentalSnapshot> {
  return request<FundamentalSnapshot>(
    `/api/v1/stocks/${encodeURIComponent(symbol)}/fundamentals?limit=12`,
    signal
  );
}

export function refreshFundamentals(
  symbol: string,
  signal?: AbortSignal
): Promise<FilingRefreshResult> {
  return request<FilingRefreshResult>(
    `/api/v1/stocks/${encodeURIComponent(symbol)}/fundamentals/refresh?limit=8`,
    signal,
    { method: "POST" }
  );
}

export function fetchDashboard(signal?: AbortSignal): Promise<DashboardSnapshot> {
  return request<DashboardSnapshot>("/api/v1/dashboard", signal);
}

export function fetchPriceSeries(
  symbol: string,
  signal?: AbortSignal
): Promise<PriceSeries> {
  return request<PriceSeries>(
    `/api/v1/assets/${encodeURIComponent(symbol)}/prices?limit=250`,
    signal
  );
}

export function fetchYouTubeDigest(
  day?: string,
  signal?: AbortSignal
): Promise<DailyYouTubeDigest> {
  const query = day ? `?day=${encodeURIComponent(day)}` : "";
  return request<DailyYouTubeDigest>(`/api/v1/youtube/daily${query}`, signal);
}

export function fetchMetricHistory(
  symbol: string,
  signal?: AbortSignal
): Promise<MetricHistory> {
  return request<MetricHistory>(
    `/api/v1/stocks/${encodeURIComponent(symbol)}/metric-history?window=60&step=5`,
    signal
  );
}

export function proposePortfolio(
  budget: number,
  riskLevel: "conservative" | "balanced" | "aggressive",
  durationMonths: number,
  signal?: AbortSignal
): Promise<PortfolioProposal> {
  return request<PortfolioProposal>("/api/v1/portfolio/propose", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      budget,
      risk_level: riskLevel,
      duration_months: durationMonths,
    }),
  });
}

export function fetchBondUniverse(signal?: AbortSignal): Promise<BondUniverseSnapshot> {
  return request<BondUniverseSnapshot>("/api/v1/bonds", signal);
}

export function refreshBondUniverse(signal?: AbortSignal): Promise<BondRefreshResult> {
  return request<BondRefreshResult>("/api/v1/bonds/refresh", signal, { method: "POST" });
}

export function calculateBond(
  isin: string,
  cleanPrice: number,
  signal?: AbortSignal
): Promise<BondCalculation> {
  return request<BondCalculation>("/api/v1/bonds/calculate", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ isin, clean_price: cleanPrice }),
  });
}

export function proposeBondLadder(
  budget: number,
  horizonYears: number,
  riskLevel: "low" | "medium" | "high",
  signal?: AbortSignal
): Promise<BondLadderProposal> {
  return request<BondLadderProposal>("/api/v1/bonds/ladder", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ budget, horizon_years: horizonYears, risk_level: riskLevel }),
  });
}
