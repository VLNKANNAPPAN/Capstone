import { useState } from "react";
import { AlertTriangle, BrainCircuit, LoaderCircle, WalletCards } from "lucide-react";
import { proposePortfolio } from "../api";
import type { PortfolioProposal } from "../types";

type RiskLevel = "conservative" | "balanced" | "aggressive";

const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

function display(value: number | null, suffix = "") {
  return value === null ? "—" : `${value.toFixed(2)}${suffix}`;
}

export function PortfolioBuilder() {
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
      setError(caught instanceof Error ? caught.message : "Portfolio proposal failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="portfolio-builder">
      <section className="portfolio-controls">
        <div>
          <span className="section-kicker">Educational model portfolio</span>
          <h3>Set the constraints, then inspect the evidence</h3>
          <p>
            Nine factors, sector caps and pairwise correlation shape the allocation. One compact
            Groq call explains the fixed result; it cannot change the weights.
          </p>
        </div>
        <div className="portfolio-form">
          <label>Budget (₹)<input min="1000" step="1000" type="number" value={budget} onChange={(event) => setBudget(Number(event.target.value))} /></label>
          <label>Risk level<select value={risk} onChange={(event) => setRisk(event.target.value as RiskLevel)}><option value="conservative">Conservative</option><option value="balanced">Balanced</option><option value="aggressive">Aggressive</option></select></label>
          <label>Duration (months)<input min="1" max="120" type="number" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
          <button className="generate-button" disabled={loading || budget <= 0} onClick={() => void build()} type="button">{loading ? <LoaderCircle className="spin" size={17} /> : <WalletCards size={17} />}{loading ? "Building…" : "Build model portfolio"}</button>
        </div>
      </section>

      {error && <div className="error-banner"><AlertTriangle size={17} />{error}</div>}
      {!proposal && !loading && <div className="portfolio-empty"><WalletCards size={27} /><div><strong>Your constraints come first.</strong><p>The result uses whole shares, keeps cash visible and shows the exact metrics behind every candidate.</p></div></div>}

      {proposal && (
        <>
          <section className="portfolio-expectation">
            <div className="expectation-copy">
              <span className="section-kicker">Historical model estimate · {proposal.expectation.horizon_months} months</span>
              <h3>Expected return range</h3>
              <p>This range blends the observed portfolio path with a conservative long-run prior. It is an uncertainty estimate, not a guaranteed probability interval.</p>
            </div>
            <div className="expectation-range">
              <article><span>Lower model case</span><strong>{proposal.expectation.low_return_pct.toFixed(1)}%</strong><small>{rupees.format(proposal.expectation.low_value)}</small></article>
              <article className="expectation-central"><span>Central estimate</span><strong>{proposal.expectation.central_return_pct.toFixed(1)}%</strong><small>{rupees.format(proposal.expectation.central_value)}</small></article>
              <article><span>Upper model case</span><strong>+{proposal.expectation.high_return_pct.toFixed(1)}%</strong><small>{rupees.format(proposal.expectation.high_value)}</small></article>
            </div>
            <div className="expectation-confidence">
              <div><strong>{proposal.expectation.confidence_score}/100</strong><span>{proposal.expectation.confidence_label} model confidence</span></div>
              <div className="confidence-track"><span style={{ width: `${proposal.expectation.confidence_score}%` }} /></div>
              <small>Based on {proposal.expectation.observation_count} common daily observations, metric coverage, sector breadth and concentration.</small>
            </div>
          </section>
          <section className="portfolio-summary">
            <div><span>Invested</span><strong>{rupees.format(proposal.invested_amount)}</strong></div>
            <div><span>Cash left</span><strong>{rupees.format(proposal.cash_remaining)}</strong></div>
            <div><span>Weighted Sharpe</span><strong>{display(proposal.weighted_sharpe)}</strong></div>
            <div><span>Weighted Sortino</span><strong>{display(proposal.weighted_sortino)}</strong></div>
            <div><span>Volatility</span><strong>{display(proposal.weighted_volatility_pct, "%")}</strong></div>
            <div><span>Max drawdown</span><strong>{display(proposal.weighted_maximum_drawdown_pct, "%")}</strong></div>
          </section>
          <section className="portfolio-construction-grid">
            <article className="portfolio-diversification">
              <header><span className="section-kicker">Diversification controls</span><h3>{proposal.diversification.sector_count} industries represented</h3></header>
              <div className="diversification-stats"><div><span>Effective holdings</span><strong>{proposal.diversification.effective_holdings.toFixed(1)}</strong></div><div><span>Avg. correlation</span><strong>{display(proposal.diversification.average_pairwise_correlation)}</strong></div><div><span>Sector cap</span><strong>{proposal.diversification.maximum_sector_weight_pct.toFixed(0)}%</strong></div></div>
              <div className="sector-bars">{Object.entries(proposal.diversification.sector_allocations_pct).map(([sector, weight]) => <div key={sector}><span>{sector}</span><div><i style={{ width: `${Math.min(weight, 100)}%` }} /></div><strong>{weight.toFixed(1)}%</strong></div>)}</div>
            </article>
            <article className="portfolio-factors">
              <header><span className="section-kicker">Decision recipe</span><h3>Nine weighted signals</h3></header>
              <div>{Object.entries(proposal.factor_weights_pct).sort((left, right) => right[1] - left[1]).map(([factor, weight]) => <div key={factor}><span>{factor}</span><div><i style={{ width: `${weight * 3.2}%` }} /></div><strong>{weight.toFixed(0)}%</strong></div>)}</div>
              <small>Weights change with risk level and duration. Fundamental factors remain excluded until audited statement data is connected.</small>
            </article>
          </section>
          <section className="portfolio-holdings">
            <header><div><span className="section-kicker">Proposed allocation</span><h3>{proposal.holdings.length} evidence-ranked holdings</h3></div><small>{proposal.risk_level} · {proposal.duration_months} months</small></header>
            <div className="holding-table-wrap"><table><thead><tr><th>Company</th><th>Industry</th><th>Shares</th><th>Allocation</th><th>60D return</th><th>Sharpe</th><th>Sortino</th><th>Volatility</th><th>Drawdown</th></tr></thead><tbody>{proposal.holdings.map((holding) => <tr key={holding.symbol}><td><strong>{holding.symbol.replace(".NS", "")}</strong><span>{holding.name}</span></td><td>{holding.sector}</td><td>{holding.shares}</td><td>{holding.weight_pct.toFixed(1)}%<small>{rupees.format(holding.invested_amount)}</small></td><td>{display(holding.return_60d_pct, "%")}</td><td>{display(holding.sharpe)}</td><td>{display(holding.sortino)}</td><td>{display(holding.volatility_pct, "%")}</td><td>{display(holding.maximum_drawdown_pct, "%")}</td></tr>)}</tbody></table></div>
          </section>
          {proposal.ai_narrative && <section className="portfolio-ai"><BrainCircuit size={23} /><div><span className="section-kicker">One-call Groq explanation</span><h3>{proposal.ai_narrative.summary}</h3><div className="portfolio-ai-grid"><article><strong>Allocation logic</strong><ul>{proposal.ai_narrative.allocation_logic.map((item) => <li key={item}>{item}</li>)}</ul></article><article><strong>Key risks</strong><ul>{proposal.ai_narrative.key_risks.map((item) => <li key={item}>{item}</li>)}</ul></article><article><strong>Monitor</strong><ul>{proposal.ai_narrative.monitoring_triggers.map((item) => <li key={item}>{item}</li>)}</ul></article></div><p>{proposal.ai_narrative.disclaimer}</p></div></section>}
          <section className="portfolio-warnings"><AlertTriangle size={18} /><div>{proposal.warnings.map((warning) => <p key={warning}>{warning}</p>)}<small>{proposal.methodology}</small></div></section>
        </>
      )}
    </div>
  );
}
