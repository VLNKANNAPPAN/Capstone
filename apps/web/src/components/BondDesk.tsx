import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  ArrowDownUp,
  Calculator,
  ExternalLink,
  Landmark,
  Layers3,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  calculateBond,
  fetchBondUniverse,
  proposeBondLadder,
  refreshBondUniverse,
} from "../api";
import type {
  BondCalculation,
  BondLadderProposal,
  BondSecurity,
  BondUniverseSnapshot,
} from "../types";

const money = (value: number) => `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const metric = (value: number | null, suffix = "") => value === null ? "Unavailable" : `${value.toFixed(2)}${suffix}`;

export function BondDesk() {
  const [data, setData] = useState<BondUniverseSnapshot | null>(null);
  const [selectedIsin, setSelectedIsin] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [rating, setRating] = useState("all");
  const [cleanPrice, setCleanPrice] = useState(1000);
  const [calculation, setCalculation] = useState<BondCalculation | null>(null);
  const [budget, setBudget] = useState(100000);
  const [horizon, setHorizon] = useState(5);
  const [risk, setRisk] = useState<"low" | "medium" | "high">("low");
  const [ladder, setLadder] = useState<BondLadderProposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (signal?: AbortSignal) => {
    try {
      const next = await fetchBondUniverse(signal);
      setData(next);
      setSelectedIsin((current) => current ?? next.securities[0]?.isin ?? null);
      if (selectedIsin === null && next.securities[0]) {
        setCleanPrice(next.securities[0].issue_price ?? next.securities[0].face_value);
      }
      setError(null);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught instanceof Error ? caught.message : "Bond data could not be loaded");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    void fetchBondUniverse(controller.signal)
      .then((next) => {
        setData(next);
        setSelectedIsin(next.securities[0]?.isin ?? null);
        if (next.securities[0]) {
          setCleanPrice(next.securities[0].issue_price ?? next.securities[0].face_value);
        }
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Bond data could not be loaded");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const riskMap = useMemo(
    () => new Map(data?.risk.map((item) => [item.isin, item]) ?? []),
    [data]
  );
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (data?.securities ?? []).filter((item) => {
      const bondRisk = riskMap.get(item.isin);
      const textMatches = !term || `${item.issuer} ${item.isin} ${item.security_name}`.toLowerCase().includes(term);
      const ratingMatches = rating === "all" || bondRisk?.rating_band === rating;
      return textMatches && ratingMatches;
    });
  }, [data, query, rating, riskMap]);
  const selected = data?.securities.find((item) => item.isin === selectedIsin) ?? null;
  const selectedRisk = selected ? riskMap.get(selected.isin) : undefined;
  const curve = useMemo(() => {
    const points = data?.curve ?? [];
    return points.filter((_, index) => index % Math.max(1, Math.floor(points.length / 45)) === 0);
  }, [data]);

  const refresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const result = await refreshBondUniverse();
      await load();
      if (result.warnings.length) setError(result.warnings.join(" "));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Public bond refresh failed");
      setRefreshing(false);
    }
  };

  const runCalculation = async () => {
    if (!selected) return;
    setWorking(true);
    setError(null);
    try {
      setCalculation(await calculateBond(selected.isin, cleanPrice));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Bond calculation failed");
    } finally {
      setWorking(false);
    }
  };

  const buildLadder = async () => {
    setWorking(true);
    setError(null);
    try {
      setLadder(await proposeBondLadder(budget, horizon, risk));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Bond ladder failed");
    } finally {
      setWorking(false);
    }
  };

  if (loading) return <div className="bond-loading"><LoaderCircle className="spin" />Loading fixed-income evidence…</div>;

  return (
    <div className="bond-desk">
      {error && <div className="bond-alert"><AlertTriangle size={16} />{error}</div>}
      <section className="bond-source-strip">
        <div><Landmark size={20} /><span><strong>Official public sources</strong><small>CCIL sovereign curve · SEBI-backed Bond Central terms</small></span></div>
        <div><strong>{data?.curve_date ?? "No curve"}</strong><small>latest curve date</small></div>
        <div><strong>{data?.securities.length ?? 0}</strong><small>reference securities</small></div>
        <button type="button" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}{refreshing ? "Refreshing…" : "Refresh sources"}</button>
      </section>

      <section className="bond-curve panel">
        <header><div><span className="section-kicker">Sovereign benchmark</span><h2>Indian zero-coupon yield curve</h2><p>A term-structure benchmark, not a list of executable prices.</p></div><ArrowDownUp size={22} /></header>
        {curve.length ? <ResponsiveContainer width="100%" height={300}>
          <LineChart data={curve} margin={{ top: 24, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid stroke="#e3e2dc" vertical={false} />
            <XAxis dataKey="tenor_years" tick={{ fontSize: 9 }} label={{ value: "Tenor (years)", position: "insideBottomRight", offset: -2, fontSize: 9 }} />
            <YAxis domain={["dataMin - 0.2", "dataMax + 0.2"]} tick={{ fontSize: 9 }} tickFormatter={(value) => Number(value).toFixed(2)} unit="%" />
            <Tooltip formatter={(value) => [`${Number(value).toFixed(4)}%`, "Zero rate"]} labelFormatter={(value) => `${value} years`} />
            <Line type="monotone" dataKey="yield_pct" stroke="#2256d8" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer> : <div className="bond-empty">Refresh public sources to load the latest CCIL curve.</div>}
        <footer>{data?.source_notes[0]}</footer>
      </section>

      <section className="bond-browser panel">
        <header><div><span className="section-kicker">Corporate bond reference desk</span><h2>Search terms before judging return</h2></div><ShieldCheck size={22} /></header>
        <div className="bond-filters">
          <label>Issuer, ISIN or security<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search stored bonds" /></label>
          <label>Credit band<select value={rating} onChange={(event) => setRating(event.target.value)}><option value="all">All ratings</option><option value="high">High grade</option><option value="medium">Medium</option><option value="low">Low</option><option value="unrated">Unrated</option></select></label>
        </div>
        <div className="bond-browser-grid">
          <div className="bond-list">
            {filtered.map((item) => <button className={item.isin === selectedIsin ? "is-active" : ""} type="button" key={item.isin} onClick={() => { setSelectedIsin(item.isin); setCalculation(null); setCleanPrice(item.issue_price ?? item.face_value); }}>
              <span><strong>{item.issuer}</strong><small>{item.isin} · matures {item.maturity_date}</small></span>
              <span><b>{metric(item.coupon_rate_pct, "%")}</b><small>{item.rating ?? "Unrated"}</small></span>
            </button>)}
            {!filtered.length && <div className="bond-empty">No stored bond matches these filters.</div>}
          </div>
          {selected ? <BondDetail security={selected} risk={selectedRisk} /> : <div className="bond-empty">Select a bond to inspect its terms.</div>}
        </div>
      </section>

      {selected && <section className="bond-tools-grid">
        <div className="bond-calculator panel">
          <header><Calculator size={18} /><div><span className="section-kicker">Price-to-risk calculator</span><h2>Calculate from a price you provide</h2></div></header>
          <label>Clean price<input type="number" min="0.01" step="0.01" value={cleanPrice} onChange={(event) => setCleanPrice(Number(event.target.value))} /></label>
          <button type="button" disabled={working || cleanPrice <= 0} onClick={() => void runCalculation()}>Calculate YTM and rate risk</button>
          {calculation && <div className="bond-calc-result">
            <div><span>YTM</span><strong>{metric(calculation.ytm_pct, "%")}</strong></div><div><span>Current yield</span><strong>{metric(calculation.current_yield_pct, "%")}</strong></div><div><span>Modified duration</span><strong>{metric(calculation.modified_duration_years, "y")}</strong></div><div><span>DV01</span><strong>{calculation.dv01 === null ? "Unavailable" : money(calculation.dv01)}</strong></div>
            <div className="bond-scenarios">{calculation.scenarios.map((item) => <span key={item.shift_bps}><small>{item.shift_bps > 0 ? "+" : ""}{item.shift_bps} bps</small><b className={item.price_change_pct >= 0 ? "positive" : "negative"}>{item.price_change_pct > 0 ? "+" : ""}{item.price_change_pct.toFixed(2)}%</b></span>)}</div>
            <p>{calculation.methodology}</p>
          </div>}
        </div>

        <div className="bond-ladder panel">
          <header><Layers3 size={18} /><div><span className="section-kicker">Cash-flow planning</span><h2>Build a maturity-bucket ladder</h2></div></header>
          <div className="bond-ladder-form"><label>Budget<input type="number" min="10000" value={budget} onChange={(event) => setBudget(Number(event.target.value))} /></label><label>Horizon<select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>{[1,3,5,10,15,20,30].map((year) => <option value={year} key={year}>{year} years</option>)}</select></label><label>Rate-risk tolerance<select value={risk} onChange={(event) => setRisk(event.target.value as "low" | "medium" | "high")}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label></div>
          <button type="button" disabled={working || budget < 10000} onClick={() => void buildLadder()}>Create model ladder</button>
          {ladder && <div className="ladder-result"><div className="ladder-head"><span><small>Indicative curve yield</small><strong>{ladder.weighted_indicative_yield_pct.toFixed(2)}%</strong></span><span><small>Duration proxy</small><strong>{ladder.weighted_duration_proxy_years.toFixed(2)}y</strong></span></div>{ladder.buckets.map((item) => <div className="ladder-row" key={item.label}><span><strong>{item.label}</strong><small>{item.indicative_yield_pct.toFixed(2)}% indicative</small></span><span><b>{money(item.amount)}</b><small>{item.allocation_pct.toFixed(1)}%</small></span></div>)}<p>{ladder.warnings[0]}</p></div>}
        </div>
      </section>}

      <section className="bond-boundary"><AlertTriangle size={16} /><p><strong>Research boundary:</strong> A coupon is not a return forecast, a rating is not a guarantee, and a database record is not proof of liquidity. Verify the offer document, current rating, executable price, cash-flow schedule, tax treatment and platform eligibility before any investment.</p></section>
    </div>
  );
}

function BondDetail({ security, risk }: { security: BondSecurity; risk: BondUniverseSnapshot["risk"][number] | undefined }) {
  return <article className="bond-detail">
    <div className="bond-detail-title"><span className="rating-chip">{security.rating ?? "Unrated"}</span><h3>{security.security_name}</h3><p>{security.issuer}</p></div>
    <dl><div><dt>ISIN</dt><dd>{security.isin}</dd></div><div><dt>Coupon</dt><dd>{metric(security.coupon_rate_pct, "%")}</dd></div><div><dt>Face value</dt><dd>{money(security.face_value)}</dd></div><div><dt>Maturity</dt><dd>{security.maturity_date}</dd></div><div><dt>Security</dt><dd>{security.secured === null ? "Not stated" : security.secured ? "Secured" : "Unsecured"}</dd></div><div><dt>Liquidity</dt><dd>{risk?.liquidity_status.replaceAll("_", " ") ?? "unknown"}</dd></div><div><dt>G-Sec benchmark</dt><dd>{metric(risk?.benchmark_yield_pct ?? null, "%")}</dd></div><div><dt>Coupon − benchmark</dt><dd>{metric(risk?.coupon_minus_benchmark_pct ?? null, "%")}</dd></div></dl>
    <div className="bond-risk-flags">{risk?.risk_flags.map((flag) => <p key={flag}><AlertTriangle size={12} />{flag}</p>)}</div>
    <a href={security.source_url} target="_blank" rel="noreferrer">Inspect source record <ExternalLink size={12} /></a>
  </article>;
}
