import { Activity, TrendingUp } from "lucide-react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { formatMoney, formatPercent } from "../format";
import type { MarketAnalytics } from "../types";

interface MarketAnalyticsPanelProps {
  analytics: MarketAnalytics;
}

export function MarketAnalyticsPanel({ analytics }: MarketAnalyticsPanelProps) {
  const plotData = analytics.stocks
    .filter(
      (stock) => stock.return_60d_pct !== null && stock.volatility_20d_pct !== null
    )
    .map((stock) => ({
      symbol: stock.symbol.replace(".NS", ""),
      momentum: stock.return_60d_pct,
      risk: stock.volatility_20d_pct
    }));

  return (
    <section className="panel analytics-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Decision context</span>
          <h2>20-stock market monitor</h2>
        </div>
        <Activity size={20} />
      </div>

      {analytics.stocks.length > 0 ? (
        <>
          <div className="breadth-strip">
            <div><span>Coverage</span><strong>{analytics.breadth.covered_assets}</strong></div>
            <div><span>Positive 60D</span><strong>{analytics.breadth.positive_60d}</strong></div>
            <div><span>Above SMA20</span><strong>{analytics.breadth.above_sma20}</strong></div>
            <div><span>Median Sharpe</span><strong>{analytics.breadth.median_sharpe_252d?.toFixed(2) ?? "—"}</strong></div>
            <div><span>Median CVaR 95</span><strong>{formatPercent(analytics.breadth.median_cvar_95_daily_pct)}</strong></div>
          </div>

          <div className="analytics-chart" aria-label="Sixty-day momentum versus annualized volatility">
            <div className="chart-caption">
              <div><span className="section-kicker">Risk–momentum map</span><h3>60-day momentum vs volatility</h3></div>
              <small>Upper-left combines stronger momentum with lower realized risk.</small>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <ScatterChart margin={{ top: 14, right: 20, bottom: 18, left: 2 }}>
                <CartesianGrid stroke="var(--chart-grid)" />
                <XAxis
                  type="number"
                  dataKey="risk"
                  name="Annualized volatility"
                  unit="%"
                  tick={{ fill: "var(--muted)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  label={{ value: "20D annualized volatility (%)", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 10 }}
                />
                <YAxis
                  type="number"
                  dataKey="momentum"
                  name="60-day momentum"
                  unit="%"
                  tick={{ fill: "var(--muted)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={50}
                />
                <Tooltip
                  cursor={{ stroke: "var(--muted)", strokeDasharray: "4 4" }}
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" }}
                />
                <Scatter data={plotData} fill="var(--accent)" name="Stocks" isAnimationActive={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          <div className="table-scroll metrics-table-wrap">
            <table>
              <thead><tr><th>Stock</th><th>Close</th><th>Momentum 60D</th><th>Vs SMA20</th><th>RSI 14</th><th>Volatility 20D</th><th>Sharpe 1Y</th><th>Sortino 1Y</th><th>CVaR 95 daily</th><th>Max DD 1Y</th><th>Context</th></tr></thead>
              <tbody>
                {analytics.stocks.map((stock) => (
                  <tr key={stock.symbol}>
                    <td><span className="table-strong">{stock.symbol.replace(".NS", "")}</span><small>{stock.name}</small></td>
                    <td>{formatMoney(stock.close, stock.currency)}</td>
                    <td className={(stock.return_60d_pct ?? 0) >= 0 ? "metric-positive" : "metric-negative"}>{formatPercent(stock.return_60d_pct)}</td>
                    <td>{formatPercent(stock.distance_sma20_pct)}</td>
                    <td>{stock.rsi_14?.toFixed(1) ?? "—"}</td>
                    <td>{formatPercent(stock.volatility_20d_pct)}</td>
                    <td className={(stock.sharpe_252d ?? 0) >= 0 ? "metric-positive" : "metric-negative"}>{stock.sharpe_252d?.toFixed(2) ?? "—"}</td>
                    <td className={(stock.sortino_252d ?? 0) >= 0 ? "metric-positive" : "metric-negative"}>{stock.sortino_252d?.toFixed(2) ?? "—"}</td>
                    <td className="metric-negative">{formatPercent(stock.cvar_95_daily_pct)}</td>
                    <td className="metric-negative">{formatPercent(stock.max_drawdown_252d_pct)}</td>
                    <td><span className={`signal-chip signal-${stock.signal.replaceAll(" ", "-")}`}>{stock.signal}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="methodology-note">{analytics.methodology}</p>
        </>
      ) : (
        <div className="compact-empty analytics-empty">
          <TrendingUp size={24} />
          <p>Seed the research universe to calculate transparent market metrics.</p>
          <code>capstone-data seed-india-research</code>
        </div>
      )}
    </section>
  );
}
