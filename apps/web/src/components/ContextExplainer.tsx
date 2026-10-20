import { ArrowRight, CheckCircle2, CircleAlert, Scale } from "lucide-react";
import { formatMoney, formatPercent } from "../format";
import type { AssetSummary, StockMetric } from "../types";

interface ContextExplainerProps {
  assets: AssetSummary[];
  metric: StockMetric | null;
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
}

type EvidenceTone = "support" | "caution" | "neutral";

interface Evidence {
  label: string;
  value: string;
  explanation: string;
  tone: EvidenceTone;
}

function evidenceFor(metric: StockMetric): Evidence[] {
  const momentum = metric.return_60d_pct;
  const trend = metric.distance_sma20_pct;
  const rsi = metric.rsi_14;
  const sharpe = metric.sharpe_252d;
  const cvar = metric.cvar_95_daily_pct;
  const drawdown = metric.max_drawdown_252d_pct;

  return [
    {
      label: "Momentum",
      value: formatPercent(momentum),
      explanation: (momentum ?? 0) >= 0 ? "Price gained over 60 trading days." : "Price lost ground over 60 trading days.",
      tone: (momentum ?? 0) >= 0 ? "support" : "caution"
    },
    {
      label: "Short trend",
      value: formatPercent(trend),
      explanation: (trend ?? 0) >= 0 ? "Price is above its 20-day average." : "Price is below its 20-day average.",
      tone: (trend ?? 0) >= 0 ? "support" : "caution"
    },
    {
      label: "RSI 14",
      value: rsi?.toFixed(1) ?? "—",
      explanation: rsi !== null && rsi <= 30 ? "Selling is historically stretched." : rsi !== null && rsi >= 70 ? "Buying is historically stretched." : "Recent buying and selling are not at an extreme.",
      tone: rsi !== null && (rsi <= 30 || rsi >= 70) ? "caution" : "neutral"
    },
    {
      label: "Sharpe",
      value: sharpe?.toFixed(2) ?? "—",
      explanation: sharpe !== null && sharpe >= 1 ? "Return has compensated well for variability." : sharpe !== null && sharpe < 0 ? "Return did not compensate for variability." : "Risk-adjusted return is modest.",
      tone: sharpe !== null && sharpe >= 1 ? "support" : sharpe !== null && sharpe < 0 ? "caution" : "neutral"
    },
    {
      label: "Tail loss",
      value: formatPercent(cvar),
      explanation: "Average result during the worst 5% of daily returns.",
      tone: cvar !== null && cvar <= -3 ? "caution" : "neutral"
    },
    {
      label: "Max drawdown",
      value: formatPercent(drawdown),
      explanation: "Largest peak-to-trough decline in the available one-year window.",
      tone: drawdown !== null && drawdown <= -20 ? "caution" : "neutral"
    }
  ];
}

function conclusion(metric: StockMetric): string {
  switch (metric.signal) {
    case "positive trend":
      return "Momentum and the short-term trend agree on strength. Risk measures still determine whether that strength has been efficient.";
    case "negative trend":
      return "Momentum and the short-term trend agree on weakness. This is a warning state, not a prediction that prices must keep falling.";
    case "oversold":
      return "Recent selling has been unusually intense. A rebound is possible, but trend and risk evidence do not yet confirm one.";
    case "extended":
      return "Recent buying has been unusually intense. Strength is visible, but chasing an extended move can increase timing risk.";
    default:
      return "The indicators disagree, so the responsible conclusion is mixed rather than forcing a bullish or bearish label.";
  }
}

export function ContextExplainer({ assets, metric, selectedSymbol, onSelectSymbol }: ContextExplainerProps) {
  if (!metric) return null;
  const evidence = evidenceFor(metric);

  return (
    <section className="context-panel">
      <div className="context-topline">
        <div>
          <span className="section-kicker">From evidence to context</span>
          <h2>Why is {metric.symbol.replace(".NS", "")} labelled “{metric.signal}”?</h2>
        </div>
        <label className="asset-select">
          <span>Explain another stock</span>
          <select value={selectedSymbol ?? ""} onChange={(event) => onSelectSymbol(event.target.value)}>
            {assets.map((asset) => <option value={asset.symbol} key={asset.symbol}>{asset.symbol.replace(".NS", "")} · {asset.name}</option>)}
          </select>
        </label>
      </div>

      <div className="reason-chain" aria-label="How the context is assembled">
        <span>Return & trend</span><ArrowRight size={16} /><span>Risk & downside</span><ArrowRight size={16} /><strong>{metric.signal}</strong>
      </div>

      <div className="evidence-grid">
        {evidence.map((item) => (
          <article className={`evidence-item evidence-${item.tone}`} key={item.label}>
            {item.tone === "support" ? <CheckCircle2 size={17} /> : item.tone === "caution" ? <CircleAlert size={17} /> : <Scale size={17} />}
            <div><span>{item.label}</span><strong>{item.value}</strong><p>{item.explanation}</p></div>
          </article>
        ))}
      </div>

      <div className="context-conclusion">
        <div><span>Observed close</span><strong>{formatMoney(metric.close, metric.currency)}</strong></div>
        <p>{conclusion(metric)}</p>
      </div>
      <p className="context-disclaimer">This label summarizes historical evidence. It is not a buy, sell, or price forecast.</p>
    </section>
  );
}
