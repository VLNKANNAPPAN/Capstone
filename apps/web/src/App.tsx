import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Boxes, Database, Layers3, Newspaper } from "lucide-react";
import { fetchDashboard, fetchPriceSeries } from "./api";
import { ActivityTable } from "./components/ActivityTable";
import { BondDesk } from "./components/BondDesk";
import { ContentPanel } from "./components/ContentPanel";
import { ContextExplainer } from "./components/ContextExplainer";
import { FilingList } from "./components/FilingList";
import { FilingIntelligencePanel } from "./components/FilingIntelligencePanel";
import { Header } from "./components/Header";
import { MarketAnalyticsPanel } from "./components/MarketAnalyticsPanel";
import { MetricAcademy } from "./components/MetricAcademy";
import { MetricTrendCharts } from "./components/MetricTrendCharts";
import { PortfolioBuilder } from "./components/PortfolioBuilder";
import { PriceChart } from "./components/PriceChart";
import { QualityPanel } from "./components/QualityPanel";
import { ResearchWorkbench } from "./components/ResearchWorkbench";
import { SourcePanel } from "./components/SourcePanel";
import { StatCard } from "./components/StatCard";
import { YouTubeBriefing } from "./components/YouTubeBriefing";
import { formatCount, relativeTime } from "./format";
import type { DashboardSnapshot, PriceSeries } from "./types";

const POLL_INTERVAL_MS = 5000;
const validPages = new Set(["overview", "research", "portfolio", "bonds", "market", "analysis", "learn", "evidence", "pipeline"]);

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
            <section className="hero-section">
              <div className="hero-copy"><span className="section-kicker">A learning-first Indian market workspace</span><h2>Understand the evidence.<br />Then form a view.</h2><p>Explore normalized market, exchange, RBI, news and video data. Every context label remains connected to inspectable evidence.</p><div className="hero-actions"><a href="#/research">Open research desk</a><a href="#/learn">Start the short course</a></div></div>
              <div className="hero-note"><Layers3 size={20} /><div><strong>No black-box conclusions</strong><span>Metrics are calculated first. AI is only used to explain supplied evidence.</span></div></div>
            </section>
            <section className="stats-grid" aria-label="Dataset overview">
              <StatCard label="Tracked assets" value={formatCount(counts?.assets ?? 0)} detail="Indian research universe" icon={Boxes} tone="blue" />
              <StatCard label="Normalized bars" value={formatCount(counts?.price_bars ?? 0)} detail="Point-in-time OHLCV records" icon={Database} tone="mint" />
              <StatCard label="Context records" value={formatCount((counts?.news_items ?? 0) + (counts?.video_items ?? 0) + (counts?.corporate_disclosures ?? 0) + (counts?.macro_observations ?? 0))} detail="News, videos, filings and macro" icon={Newspaper} tone="amber" />
              <StatCard label="Quality queue" value={formatCount(counts?.quality_issues ?? 0)} detail={`${rejectedRecords.toLocaleString()} rejected in recent runs`} icon={AlertTriangle} tone={counts?.quality_issues ? "rose" : "blue"} />
            </section>
            <section className="overview-modules">
              <a href="#/research"><span>01</span><strong>Research desk</strong><p>Evidence ledger and Groq brief.</p></a>
              <a href="#/portfolio"><span>02</span><strong>Portfolio lab</strong><p>Budget, risk and horizon constraints.</p></a>
              <a href="#/bonds"><span>03</span><strong>Bond desk</strong><p>Yield curve, bond terms and rate risk.</p></a>
              <a href="#/market"><span>04</span><strong>Market record</strong><p>Price history and normalized observations.</p></a>
              <a href="#/learn"><span>05</span><strong>Metric University</strong><p>Equity and bond lessons with scenarios.</p></a>
              <a href="#/evidence"><span>06</span><strong>Daily evidence</strong><p>News, filings and YouTube desk.</p></a>
              <a href="#/pipeline"><span>07</span><strong>Admin console</strong><p>Freshness, sources and quality.</p></a>
            </section>
          </>
        )}

        {activePage === "research" && <section className="module-section route-section"><PageHeading number="01" kicker="Research" title="From evidence to an explainable view" description="Inspect deterministic facts first, then ask Groq to translate the exact evidence into scenarios and thesis breakers." /><ResearchWorkbench assets={snapshot?.assets ?? []} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} /></section>}

        {activePage === "portfolio" && <section className="module-section route-section"><PageHeading number="02" kicker="Allocate" title="Build a constraint-aware model portfolio" description="Turn budget, risk tolerance and time horizon into a transparent educational allocation—without promising future returns." /><PortfolioBuilder /></section>}

        {activePage === "bonds" && <section className="module-section route-section"><PageHeading number="03" kicker="Fixed income" title="Inspect yield, cash flow and rate risk" description="Use official sovereign curve data and public corporate-bond terms without confusing coupons, model values or database listings with executable returns." /><BondDesk /></section>}

        {activePage === "market" && <section className="module-section route-section"><PageHeading number="02" kicker="Observe" title="Start with the price record" description="Choose a stock and inspect what actually happened before interpreting indicators." /><PriceChart assets={snapshot?.assets ?? []} selectedSymbol={selectedSymbol} series={series} onSelectSymbol={setSelectedSymbol} /></section>}

        {activePage === "analysis" && snapshot?.market_analytics && <section className="module-section route-section"><PageHeading number="03" kicker="Interpret" title="Build context from several signals" description="Momentum, trend, tail risk and market breadth are read together; no single indicator gets the final word." /><ContextExplainer assets={snapshot.assets} metric={selectedMetric} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} /><MetricTrendCharts symbol={selectedSymbol} /><MarketAnalyticsPanel analytics={snapshot.market_analytics} /></section>}

        {activePage === "learn" && <section className="module-section route-section course-page"><PageHeading number="05" kicker="Learn" title="Metric University" description="A five-module short course covering equity metrics, fixed income, worked examples, charts and scenario practice." /><MetricAcademy /></section>}

        {activePage === "evidence" && <section className="module-section route-section"><PageHeading number="05" kicker="Broaden" title="Company and market evidence" description="Combine exchange filings, linked news and the daily YouTube desk without confusing metadata with full article or transcript analysis." /><FilingIntelligencePanel symbol={selectedSymbol} /><YouTubeBriefing /><div className="evidence-layout"><ContentPanel items={snapshot?.recent_content.filter((item) => item.content_type !== "video") ?? []} newsCount={counts?.news_items ?? 0} socialCount={counts?.social_items ?? 0} /><FilingList filings={snapshot?.recent_filings ?? []} /></div></section>}

        {activePage === "pipeline" && <section className="module-section route-section"><PageHeading number="06" kicker="Admin" title="Verify the pipeline" description="Cross-check provider status, ingestion history, storage freshness and rejected records behind the product." /><div className="pipeline-grid"><SourcePanel sources={snapshot?.sources ?? []} /><section className="panel freshness-panel"><div className="panel-heading"><div><span className="section-kicker">Storage state</span><h2>Freshness</h2></div><Database size={20} /></div><div className="freshness-body"><strong>{relativeTime(snapshot?.latest_ingested_at ?? null)}</strong><p>Most recent raw provider record received.</p><dl><div><dt>Raw revisions</dt><dd>{formatCount(counts?.raw_records ?? 0)}</dd></div><div><dt>YouTube</dt><dd>{formatCount(counts?.video_items ?? 0)}</dd></div><div><dt>Storage</dt><dd>SQL database</dd></div></dl></div></section><ActivityTable runs={snapshot?.recent_runs ?? []} /><QualityPanel issues={snapshot?.quality_issues ?? []} /></div></section>}
      </main>
    </div>
  );
}
