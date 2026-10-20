import { BarChart3 } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { formatDateTime, formatMoney } from "../format";
import type { AssetSummary, PriceSeries } from "../types";

interface PriceChartProps {
  assets: AssetSummary[];
  selectedSymbol: string | null;
  series: PriceSeries | null;
  onSelectSymbol: (symbol: string) => void;
}

export function PriceChart({ assets, selectedSymbol, series, onSelectSymbol }: PriceChartProps) {
  const selectedAsset = assets.find((asset) => asset.symbol === selectedSymbol);
  const data = (series?.points ?? []).map((point) => ({
    ...point,
    tick: new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(
      new Date(point.event_time)
    )
  }));

  return (
    <section className="panel price-panel">
      <div className="panel-heading chart-heading">
        <div>
          <span className="section-kicker">Point-in-time series</span>
          <h2>{selectedSymbol ? `${selectedSymbol} price history` : "Price history"}</h2>
        </div>
        <label className="asset-select">
          <span>Asset</span>
          <select
            value={selectedSymbol ?? ""}
            onChange={(event) => onSelectSymbol(event.target.value)}
            disabled={assets.length === 0}
          >
            {assets.length === 0 && <option value="">No assets</option>}
            {assets.map((asset) => (
              <option value={asset.symbol} key={asset.symbol}>
                {asset.symbol} {asset.name ? `· ${asset.name}` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      {data.length > 0 ? (
        <>
          <div className="chart-summary">
            <div>
              <span>Latest close</span>
              <strong>{formatMoney(data[data.length - 1].close, selectedAsset?.currency)}</strong>
            </div>
            <div>
              <span>Observations</span>
              <strong>{data.length.toLocaleString()}</strong>
            </div>
            <div>
              <span>Last available</span>
              <strong>{formatDateTime(data[data.length - 1].available_at)}</strong>
            </div>
          </div>
          <div className="chart-wrap" aria-label={`${selectedSymbol} closing price chart`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 20, right: 6, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.24} />
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis
                  dataKey="tick"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                  minTickGap={28}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                  width={55}
                />
                <Tooltip
                  cursor={{ stroke: "var(--muted)", strokeDasharray: "4 4" }}
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    borderRadius: 8,
                    color: "var(--ink)"
                  }}
                  formatter={(value) => [formatMoney(Number(value ?? 0)), "Close"]}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke="var(--accent)"
                  strokeWidth={2.5}
                  fill="url(#priceFill)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <div className="empty-chart">
          <div className="empty-icon">
            <BarChart3 size={30} />
          </div>
          <strong>No normalized price bars yet</strong>
          <p>
            Run the Indian research bootstrap or a configured provider backfill. Valid bars
            will appear here on the next polling cycle.
          </p>
          <code>capstone-data seed-india-research</code>
        </div>
      )}
    </section>
  );
}
