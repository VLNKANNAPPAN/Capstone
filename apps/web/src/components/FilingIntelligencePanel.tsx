import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, ExternalLink, FileSearch, LoaderCircle, RefreshCw } from "lucide-react";
import { fetchFundamentals, refreshFundamentals } from "../api";
import type { FundamentalFact, FundamentalSnapshot } from "../types";

interface FilingIntelligencePanelProps {
  symbol: string | null;
}

const preferredMetricGroups = [
  ["revenue", "total_income"],
  ["net_profit_parent", "net_profit"],
  ["ebitda_margin_pct"],
  ["operating_margin_pct"],
  ["basic_eps"],
  ["interest_coverage"],
];

function formatFact(fact: FundamentalFact | undefined) {
  if (!fact || fact.value === null) return "Not available";
  if (fact.unit === "INR") return `₹${(fact.value / 10_000_000).toLocaleString("en-IN", { maximumFractionDigits: 2 })} cr`;
  if (fact.unit === "percent") return `${fact.value.toFixed(2)}%`;
  if (fact.unit === "ratio") return `${fact.value.toFixed(2)}x`;
  return fact.value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function FilingIntelligencePanel({ symbol }: FilingIntelligencePanelProps) {
  const [data, setData] = useState<FundamentalSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (activeSymbol: string, signal?: AbortSignal) => {
    setLoading(true);
    try {
      setData(await fetchFundamentals(activeSymbol, signal));
      setError(null);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught instanceof Error ? caught.message : "Fundamental facts could not be loaded");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!symbol) return;
    const controller = new AbortController();
    setData(null);
    void load(symbol, controller.signal);
    return () => controller.abort();
  }, [symbol]);

  const latest = useMemo(() => {
    if (!data?.periods.length) return null;
    const latestPeriods = data.periods.filter((item) => item.period_end === data.latest_period_end);
    return latestPeriods.find((item) => item.basis === data.latest_basis) ?? latestPeriods[0] ?? null;
  }, [data]);
  const metricMap = useMemo(
    () => new Map(latest?.metrics.map((item) => [item.metric, item]) ?? []),
    [latest]
  );
  const metrics = preferredMetricGroups
    .map((names) => names.map((name) => metricMap.get(name)).find(Boolean))
    .filter((item): item is FundamentalFact => Boolean(item));

  const refresh = async () => {
    if (!symbol) return;
    setRefreshing(true);
    setError(null);
    try {
      const result = await refreshFundamentals(symbol);
      await load(symbol);
      if (result.failed_documents && !result.parsed_documents && !result.cached_documents) {
        setError(result.warnings[0] ?? "No supported XBRL filing could be parsed");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Filing extraction failed");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <section className="filing-intelligence panel">
      <div className="filing-intelligence-head">
        <div><span className="section-kicker">Indian filing intelligence</span><h2>Structured facts from exchange XBRL</h2><p>Every value retains its filing, period, basis, source concept and formula.</p></div>
        <button type="button" disabled={!symbol || refreshing} onClick={() => void refresh()}>
          {refreshing ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}
          {refreshing ? "Extracting…" : "Refresh filings"}
        </button>
      </div>
      {error && <div className="filing-error"><AlertCircle size={15} />{error}</div>}
      {loading && !data && <div className="filing-empty"><LoaderCircle className="spin" /> Loading normalized filing facts…</div>}
      {data && !latest && !loading && (
        <div className="filing-empty"><FileSearch size={22} /><strong>No parsed XBRL facts yet.</strong><span>Use Refresh filings to parse the latest supported NSE documents.</span></div>
      )}
      {data && latest && (
        <>
          <div className="filing-summary-line">
            <div><strong>{symbol?.replace(".NS", "")}</strong><span>{latest.period_end} · {latest.basis} · {latest.audited === null ? "audit status unavailable" : latest.audited ? "audited" : "unaudited"}</span></div>
            <div><strong>{data.period_count}</strong><span>parsed periods</span></div>
            <div><strong>{latest.revision_number}</strong><span>filing revision</span></div>
            <a href={latest.source_url} target="_blank" rel="noreferrer">Official filing <ExternalLink size={12} /></a>
          </div>
          <div className="filing-metric-grid">
            {metrics.map((fact) => (
              <article key={fact.metric} title={fact.evidence_id}>
                <span>{fact.metric.replaceAll("_", " ")}</span>
                <strong>{formatFact(fact)}</strong>
                <small>{fact.derived ? `Derived · ${fact.formula}` : fact.source_concept}</small>
              </article>
            ))}
          </div>
          <div className="filing-insights">
            <section><h3>Deterministic insights</h3>{data.insights.map((insight) => (
              <article className={`filing-insight insight-${insight.severity}`} key={insight.insight_id}>
                {insight.severity === "positive" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                <div><strong>{insight.title}</strong><p>{insight.detail}</p></div>
              </article>
            ))}</section>
            <section><h3>Coverage and limitations</h3>{Object.entries(data.coverage).map(([key, ready]) => (
              <div className="filing-coverage-row" key={key}><span>{key.replaceAll("_", " ")}</span><b className={ready ? "is-ready" : "is-missing"}>{ready ? "available" : "missing"}</b></div>
            ))}<p>{data.methodology}</p></section>
          </div>
        </>
      )}
    </section>
  );
}
