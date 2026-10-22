import { useState } from "react";
import { AlertTriangle, LoaderCircle, ShieldCheck, WalletCards } from "lucide-react";
import { proposePortfolio } from "../api";
import type { PortfolioProposal } from "../types";

type RiskLevel = "conservative" | "balanced" | "aggressive";

const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const number = (value: number | null, suffix = "") =>
  value === null ? "—" : `${value.toFixed(2)}${suffix}`;

export function DemoPortfolioBuilder() {
  const [budget, setBudget] = useState(100000);
  const [risk, setRisk] = useState<RiskLevel>("balanced");
  const [duration, setDuration] = useState(12);
  const [proposal, setProposal] = useState<PortfolioProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const build = async () => {
    setLoading(true);
    setError(null);
    try {
      setProposal(await proposePortfolio(budget, risk, duration));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Portfolio could not be created");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="demo-portfolio">
      <section className="demo-portfolio-controls panel">
        <div>
          <span className="section-kicker">Three inputs</span>
          <h3>Tell the model what you can invest</h3>
          <p>The demo ranks stored stocks, limits concentration and buys whole shares. It does not place trades.</p>
        </div>
        <div className="portfolio-form">
          <label>Budget (₹)<input min="10000" step="5000" type="number" value={budget} onChange={(event) => setBudget(Number(event.target.value))} /></label>
          <label>Risk<select value={risk} onChange={(event) => setRisk(event.target.value as RiskLevel)}><option value="conservative">Conservative</option><option value="balanced">Balanced</option><option value="aggressive">Aggressive</option></select></label>
          <label>Duration<select value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value="6">6 months</option><option value="12">12 months</option><option value="24">24 months</option><option value="36">36 months</option></select></label>
          <button className="generate-button" disabled={loading || budget < 10000} onClick={() => void build()} type="button">{loading ? <LoaderCircle className="spin" size={17} /> : <WalletCards size={17} />}{loading ? "Building…" : "Create demo portfolio"}</button>
        </div>
      </section>

      {error && <div className="error-banner"><AlertTriangle size={17} />{error}</div>}
      {!proposal && !loading && <section className="demo-empty panel"><WalletCards size={28} /><div><strong>No portfolio generated yet</strong><p>Use the three inputs above. The result will show only the allocation and its most important risk checks.</p></div></section>}

      {proposal && <>
        <section className="demo-result-summary">
          <div><span>Invested</span><strong>{rupees.format(proposal.invested_amount)}</strong><small>{rupees.format(proposal.cash_remaining)} cash remains</small></div>
          <div><span>Model range</span><strong>{proposal.expectation.low_return_pct.toFixed(1)}% to {proposal.expectation.high_return_pct.toFixed(1)}%</strong><small>{proposal.expectation.confidence_score}/100 confidence</small></div>
          <div><span>Risk-adjusted return</span><strong>{number(proposal.weighted_sharpe)}</strong><small>Weighted Sharpe ratio</small></div>
          <div><span>Diversification</span><strong>{proposal.diversification.sector_count} sectors</strong><small>{proposal.holdings.length} holdings</small></div>
        </section>

        <section className="demo-allocation panel">
          <header><div><span className="section-kicker">Suggested allocation</span><h3>Where the budget goes</h3></div><small>{proposal.risk_level} · {proposal.duration_months} months</small></header>
          <div className="demo-holdings">
            {proposal.holdings.map((holding) => <article key={holding.symbol}>
              <div><strong>{holding.symbol.replace(".NS", "")}</strong><span>{holding.name}</span></div>
              <div className="demo-weight-track"><i style={{ width: `${Math.min(holding.weight_pct * 2.5, 100)}%` }} /></div>
              <div><strong>{holding.weight_pct.toFixed(1)}%</strong><span>{rupees.format(holding.invested_amount)}</span></div>
            </article>)}
          </div>
        </section>

        <section className="demo-explanation panel">
          <ShieldCheck size={22} />
          <div><span className="section-kicker">How to explain this result</span><h3>Score, diversify, then fit the budget</h3><ol><li>Stocks are ranked using return, volatility, downside risk and trend metrics.</li><li>Sector caps and correlation checks prevent one industry from dominating.</li><li>Whole-share quantities are fitted to the budget and unused cash stays visible.</li></ol><p>The expected-return range is based on historical observations. It is not a guarantee or investment advice.</p></div>
        </section>
      </>}
    </div>
  );
}
