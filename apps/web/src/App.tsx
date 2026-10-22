import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Boxes, Database, Layers3, Newspaper } from "lucide-react";
import { fetchDashboard, fetchPriceSeries } from "./api";
import { ActivityTable } from "./components/ActivityTable";
import { DemoGuide } from "./components/DemoGuide";
import { DemoPortfolioBuilder } from "./components/DemoPortfolioBuilder";
import { DemoResearchSummary } from "./components/DemoResearchSummary";
import { Header } from "./components/Header";
import { PriceChart } from "./components/PriceChart";
import { QualityPanel } from "./components/QualityPanel";
import { SourcePanel } from "./components/SourcePanel";
import { StatCard } from "./components/StatCard";
import { formatCount, relativeTime } from "./format";
import type { DashboardSnapshot, PriceSeries } from "./types";

const POLL_INTERVAL_MS = 5000;
const validPages = new Set(["overview", "research", "portfolio", "learn", "pipeline"]);

function readPage() {
  const candidate = window.location.hash.replace(/^#\/?/, "") || "overview";
  return validPages.has(candidate) ? candidate : "overview";
}

function PageHeading({ number, kicker, title, description }: { number: string; kicker: string; title: string; description: string }) {
  return (
    <div className="section-heading page-heading">
      <span>{number}</span>
      <div><p>{kicker}</p><h2>{title}</h2><small>{description}</small></div>
    </div>
  );
}

export default function App() {
  const [, setPage] = useState(readPage);
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [series, setSeries] = useState<PriceSeries | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const activePage = readPage();

  useEffect(() => {
    const onRoute = () => {
      setPage(readPage());
      window.scrollTo({ top: 0, behavior: "smooth" });
    };
    const onRouteLink = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest('a[href^="#/"]') : null;
      const route = target?.getAttribute("href")?.replace(/^#\//, "");
      if (route && validPages.has(route)) {
        event.preventDefault();
        window.location.hash = `/${route}`;
        setPage(route);
      }
    };
    window.addEventListener("hashchange", onRoute);
    document.addEventListener("click", onRouteLink);
    if (!window.location.hash || window.location.hash === "#overview") window.location.hash = "/overview";
    return () => {
      window.removeEventListener("hashchange", onRoute);
      document.removeEventListener("click", onRouteLink);
    };
  }, []);

  const loadDashboard = useCallback(async (signal?: AbortSignal) => {
    try {
      const nextSnapshot = await fetchDashboard(signal);
      setSnapshot(nextSnapshot);
      setError(null);
      setSelectedSymbol((current) => {
        if (current) return current;
        return nextSnapshot.latest_prices[0]?.symbol ?? nextSnapshot.assets[0]?.symbol ?? null;
      });
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught instanceof Error ? caught.message : "Unable to load dashboard");
      }
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const initialLoad = window.setTimeout(() => void loadDashboard(controller.signal), 0);
    const timer = window.setInterval(() => void loadDashboard(), POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
    };
  }, [loadDashboard]);

  useEffect(() => {
    if (!selectedSymbol) return;
    const controller = new AbortController();
    void fetchPriceSeries(selectedSymbol, controller.signal)
      .then(setSeries)
      .catch((caught) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Unable to load price series");
        }
      });
    return () => controller.abort();
  }, [selectedSymbol, snapshot?.generated_at]);

  const rejectedRecords = useMemo(
    () => snapshot?.recent_runs.reduce((sum, run) => sum + run.rejected_count, 0) ?? 0,
    [snapshot]
  );
  const counts = snapshot?.counts;
  const selectedMetric = useMemo(
    () => snapshot?.market_analytics.stocks.find((stock) => stock.symbol === selectedSymbol) ?? null,
    [selectedSymbol, snapshot]
  );
  const refreshNow = () => {
    setRefreshing(true);
    void loadDashboard().finally(() => setRefreshing(false));
  };

  return (
    <div className="app-shell">
      <Header connected={Boolean(snapshot) && !error} refreshing={refreshing} generatedAt={snapshot?.generated_at ?? null} onRefresh={refreshNow} currentPage={activePage} />
      <main className="page-main">
        {error && <div className="error-banner" role="alert"><AlertTriangle size={18} /><span>{error}. Confirm the API is running.</span></div>}

        {activePage === "overview" && (
          <>
            <section className="demo-stage-banner"><span>Presentation build</span><strong>Focused scope · working prototype · explainable outputs</strong><p>The full research platform remains safely available on the main branch.</p></section>
            <section className="hero-section">
              <div className="hero-copy"><span className="section-kicker">An explainable Indian market prototype</span><h2>Data to metrics.<br />Metrics to decisions.</h2><p>A focused demonstration of four connected capabilities: normalized data, company analysis, portfolio construction and investor education.</p><div className="hero-actions"><a href="#/research">Explore a company</a><a href="#/portfolio">Build a portfolio</a></div></div>
              <div className="hero-note"><Layers3 size={20} /><div><strong>One clear demo story</strong><span>Collect reliable records, calculate transparent metrics, combine the signals and show the limits.</span></div></div>
            </section>
            <section className="stats-grid" aria-label="Dataset overview">
              <StatCard label="Tracked assets" value={formatCount(counts?.assets ?? 0)} detail="Indian research universe" icon={Boxes} tone="blue" />
              <StatCard label="Normalized bars" value={formatCount(counts?.price_bars ?? 0)} detail="Point-in-time OHLCV records" icon={Database} tone="mint" />
              <StatCard label="Context records" value={formatCount((counts?.news_items ?? 0) + (counts?.video_items ?? 0) + (counts?.corporate_disclosures ?? 0) + (counts?.macro_observations ?? 0))} detail="News, videos, filings and macro" icon={Newspaper} tone="amber" />
              <StatCard label="Quality queue" value={formatCount(counts?.quality_issues ?? 0)} detail={`${rejectedRecords.toLocaleString()} rejected in recent runs`} icon={AlertTriangle} tone={counts?.quality_issues ? "rose" : "blue"} />
            </section>
            <section className="demo-story panel"><span>01 · Acquire</span><i /><span>02 · Normalize</span><i /><span>03 · Measure</span><i /><span>04 · Explain</span></section>
            <section className="overview-modules">
              <a href="#/research"><span>01</span><strong>Company explorer</strong><p>Price history, four key signals and linked news.</p></a>
              <a href="#/portfolio"><span>02</span><strong>Portfolio builder</strong><p>Budget, risk and duration become a diversified model.</p></a>
              <a href="#/learn"><span>03</span><strong>Metric guide</strong><p>Learn the four measurements used in the demo.</p></a>
              <a href="#/pipeline"><span>04</span><strong>Data status</strong><p>Show where the records came from and when they arrived.</p></a>
            </section>
          </>
        )}

        {activePage === "research" && <section className="module-section route-section"><PageHeading number="01" kicker="Explore" title="Understand one company at a time" description="Choose a company, inspect its price record and read four transparent metrics before looking at linked news." /><div className="demo-research-flow"><span>Choose company</span><i>→</i><span>Inspect price</span><i>→</i><span>Read metrics</span><i>→</i><span>Check context</span></div><PriceChart assets={snapshot?.assets ?? []} selectedSymbol={selectedSymbol} series={series} onSelectSymbol={setSelectedSymbol} /><DemoResearchSummary assets={snapshot?.assets ?? []} metric={selectedMetric} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} news={snapshot?.recent_content.filter((item) => item.content_type === "news" && (!selectedSymbol || item.symbols.includes(selectedSymbol))).slice(0, 6) ?? []} /></section>}

        {activePage === "portfolio" && <section className="module-section route-section"><PageHeading number="02" kicker="Allocate" title="Build a simple model portfolio" description="Use three understandable constraints and inspect the resulting allocation, risk estimate and diversification checks." /><DemoPortfolioBuilder /></section>}

        {activePage === "learn" && <section className="module-section route-section"><PageHeading number="03" kicker="Learn" title="Four metrics used in the demo" description="A compact guide to momentum, RSI, Sharpe ratio and maximum drawdown—enough to explain the model without hiding its limitations." /><DemoGuide /></section>}

        {activePage === "pipeline" && <section className="module-section route-section"><PageHeading number="04" kicker="Status" title="Show that the data is real" description="A small operational view for demonstrating source provenance, freshness and quality without exposing the full admin console." /><div className="pipeline-grid"><SourcePanel sources={snapshot?.sources ?? []} /><section className="panel freshness-panel"><div className="panel-heading"><div><span className="section-kicker">Storage state</span><h2>Freshness</h2></div><Database size={20} /></div><div className="freshness-body"><strong>{relativeTime(snapshot?.latest_ingested_at ?? null)}</strong><p>Most recent raw provider record received.</p><dl><div><dt>Raw revisions</dt><dd>{formatCount(counts?.raw_records ?? 0)}</dd></div><div><dt>Price bars</dt><dd>{formatCount(counts?.price_bars ?? 0)}</dd></div><div><dt>Storage</dt><dd>SQL database</dd></div></dl></div></section><ActivityTable runs={snapshot?.recent_runs.slice(0, 5) ?? []} /><QualityPanel issues={snapshot?.quality_issues.slice(0, 5) ?? []} /></div></section>}
      </main>
    </div>
  );
}
