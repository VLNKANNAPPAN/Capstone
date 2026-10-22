import { Activity, ExternalLink, Gauge, ShieldAlert, TrendingUp } from "lucide-react";
import { formatPercent } from "../format";
import type { AssetSummary, ContentSummary, StockMetric } from "../types";

interface DemoResearchSummaryProps {
  assets: AssetSummary[];
  metric: StockMetric | null;
  selectedSymbol: string | null;
  news: ContentSummary[];
  onSelectSymbol: (symbol: string) => void;
}

export function DemoResearchSummary({ assets, metric, selectedSymbol, news, onSelectSymbol }: DemoResearchSummaryProps) {
  if (!metric) return null;
  const cards = [
    { icon: TrendingUp, label: "60-day return", value: formatPercent(metric.return_60d_pct), note: (metric.return_60d_pct ?? 0) >= 0 ? "Recent direction was positive." : "Recent direction was negative." },
    { icon: Gauge, label: "RSI (14)", value: metric.rsi_14?.toFixed(1) ?? "—", note: metric.rsi_14 !== null && metric.rsi_14 >= 70 ? "Buying looks stretched." : metric.rsi_14 !== null && metric.rsi_14 <= 30 ? "Selling looks stretched." : "Not at a momentum extreme." },
    { icon: Activity, label: "Sharpe ratio", value: metric.sharpe_252d?.toFixed(2) ?? "—", note: (metric.sharpe_252d ?? 0) >= 1 ? "Strong historical risk-adjusted result." : "Risk-adjusted result is modest or weak." },
    { icon: ShieldAlert, label: "Maximum drawdown", value: formatPercent(metric.max_drawdown_252d_pct), note: "Worst historical peak-to-trough fall." },
  ];

  return <>
    <section className="demo-metric-panel panel">
      <header><div><span className="section-kicker">Four-metric summary</span><h2>{metric.symbol.replace(".NS", "")} · {metric.signal}</h2><p>These measurements describe the stored history. They do not predict the next price.</p></div><label className="asset-select"><span>Choose another company</span><select value={selectedSymbol ?? ""} onChange={(event) => onSelectSymbol(event.target.value)}>{assets.map((asset) => <option value={asset.symbol} key={asset.symbol}>{asset.symbol.replace(".NS", "")} · {asset.name}</option>)}</select></label></header>
      <div className="demo-metric-grid">{cards.map(({ icon: Icon, label, value, note }) => <article key={label}><Icon size={17} /><span>{label}</span><strong>{value}</strong><p>{note}</p></article>)}</div>
      <footer><strong>Simple reading:</strong> {metric.signal === "positive trend" ? "return and trend evidence are constructive, but drawdown still defines the historical pain." : metric.signal === "negative trend" ? "recent direction is weak, so risk matters more than searching for a quick prediction." : "the signals are mixed, so the model avoids forcing a strong conclusion."}</footer>
    </section>
    <section className="demo-news panel">
      <header><div><span className="section-kicker">Context check</span><h2>Linked headlines</h2></div><small>{news.length} stored matches</small></header>
      {news.length ? <div>{news.map((item) => <a href={item.url} target="_blank" rel="noreferrer" key={`${item.source}-${item.external_id}`}><span>{item.source.replaceAll("_", " ")}</span><strong>{item.title}</strong><ExternalLink size={12} /></a>)}</div> : <p>No recent headline is confidently linked to this company. The demo keeps that evidence gap visible instead of inventing context.</p>}
    </section>
  </>;
}
