import { useEffect, useState } from "react";
import { Activity, AlertTriangle } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchMetricHistory } from "../api";
import type { MetricHistory } from "../types";

const charts: Array<{
  key: "sharpe" | "sortino" | "annualized_volatility_pct" | "maximum_drawdown_pct";
  label: string;
  color: string;
  reference?: number;
}> = [
  { key: "sharpe", label: "Rolling Sharpe", color: "#2256d8", reference: 0 },
  { key: "sortino", label: "Rolling Sortino", color: "#188465", reference: 0 },
  { key: "annualized_volatility_pct", label: "Annualized volatility", color: "#d47d30" },
  { key: "maximum_drawdown_pct", label: "Maximum drawdown", color: "#bd4c46", reference: 0 },
];

export function MetricTrendCharts({ symbol }: { symbol: string | null }) {
  const [history, setHistory] = useState<MetricHistory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    const controller = new AbortController();
    void fetchMetricHistory(symbol, controller.signal).then((next) => { setHistory(next); setError(null); }).catch((caught) => {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(caught instanceof Error ? caught.message : "Metric history failed");
    });
    return () => controller.abort();
  }, [symbol]);

  if (!symbol) return null;
  const data = history?.symbol === symbol ? history.points.map((point) => ({ ...point, date: new Date(point.event_time).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }) })) : [];
  return <section className="metric-trends"><header><div><span className="section-kicker">Rolling risk monitor</span><h2>Four metrics through time</h2><p>Each point uses a trailing 60-session window. These are delayed historical observations, not a live exchange feed.</p></div><Activity size={22} /></header>{error && <div className="metric-chart-error"><AlertTriangle size={16} />{error}</div>}<div className="metric-chart-grid">{charts.map((chart) => <article key={chart.key}><div><strong>{chart.label}</strong><span>{symbol.replace(".NS", "")}</span></div><ResponsiveContainer width="100%" height={190}><LineChart data={data} margin={{ top: 14, right: 14, bottom: 0, left: -20 }}><CartesianGrid stroke="#e7e4dc" vertical={false} /><XAxis dataKey="date" tick={{ fontSize: 8 }} axisLine={false} tickLine={false} minTickGap={25} /><YAxis tick={{ fontSize: 8 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ fontSize: 10 }} />{chart.reference !== undefined && <ReferenceLine y={chart.reference} stroke="#aaa49a" strokeDasharray="4 4" />}<Line type="monotone" dataKey={chart.key} stroke={chart.color} strokeWidth={2} dot={false} connectNulls /></LineChart></ResponsiveContainer></article>)}</div><small>{history?.methodology}</small></section>;
}
