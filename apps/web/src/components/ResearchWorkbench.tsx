import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  LoaderCircle,
  Search,
  ShieldAlert,
  Sparkles,
  GitCompareArrows,
} from "lucide-react";
import {
  createThesisVersion,
  fetchThesisEvaluation,
  fetchThesisVersions,
  generateResearchNarrative,
  prepareResearchSnapshot,
  searchNseCompanies,
} from "../api";
import type {
  AssetSummary,
  ResearchEvidence,
  ResearchNarrative,
  ResearchSnapshot,
  ScenarioNarrative,
  ThesisVersion,
  ThesisEvaluation,
} from "../types";

interface ResearchWorkbenchProps {
  assets: AssetSummary[];
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
}

type Horizon = "short_term" | "medium_term" | "long_term";
type RiskProfile = "conservative" | "balanced" | "aggressive";

const coverageLabels: Array<[keyof ResearchSnapshot["coverage"], string]> = [
  ["price_history", "Price history"],
  ["technical_metrics", "Technical metrics"],
  ["news", "Linked news"],
  ["fundamentals", "Fundamentals"],
  ["macro", "Macro"],
  ["video", "YouTube"],
  ["social", "Social"],
];

function metric(value: number | null, suffix = "%") {
  return value === null ? "Not available" : `${value.toFixed(2)}${suffix}`;
}

function EvidenceRow({ item }: { item: ResearchEvidence }) {
  const body = (
    <>
      <span className={`evidence-direction direction-${item.direction}`} />
      <div>
        <div className="evidence-meta">
          <span>{item.category.replaceAll("_", " ")}</span>
          <span>{item.freshness}</span>
        </div>
        <strong>{item.title}</strong>
        <p>{item.detail}</p>
        <code>{item.evidence_id}</code>
      </div>
      {item.source_url && <ExternalLink size={14} />}
    </>
  );
  return item.source_url ? (
    <a className="research-evidence-row" href={item.source_url} target="_blank" rel="noreferrer">
      {body}
    </a>
  ) : (
    <div className="research-evidence-row">{body}</div>
  );
}

function ScenarioCard({ scenario, tone }: { scenario: ScenarioNarrative; tone: string }) {
  return (
    <article className={`scenario-card scenario-${tone}`}>
      <span>{scenario.label}</span>
      <p>{scenario.interpretation}</p>
      <ul>{scenario.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
    </article>
  );
}

export function ResearchWorkbench({
  assets,
  selectedSymbol,
  onSelectSymbol,
}: ResearchWorkbenchProps) {
  const [snapshot, setSnapshot] = useState<ResearchSnapshot | null>(null);
  const [narrative, setNarrative] = useState<ResearchNarrative | null>(null);
  const [horizon, setHorizon] = useState<Horizon>("medium_term");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("balanced");
  const [loadedSymbol, setLoadedSymbol] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [companyQuery, setCompanyQuery] = useState("");
  const [companyOpen, setCompanyOpen] = useState(false);
  const [companyMatches, setCompanyMatches] = useState<AssetSummary[]>(assets.slice(0, 12));
  const [companySearching, setCompanySearching] = useState(false);
  const [selectedOption, setSelectedOption] = useState<AssetSummary | null>(null);
  const [replayDate, setReplayDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [thesisVersions, setThesisVersions] = useState<ThesisVersion[]>([]);
  const [activeThesis, setActiveThesis] = useState<ThesisVersion | null>(null);
  const [thesisEvaluation, setThesisEvaluation] = useState<ThesisEvaluation | null>(null);
  const [thesisLoading, setThesisLoading] = useState(false);
  const selectedAsset = selectedOption?.symbol === selectedSymbol
    ? selectedOption
    : assets.find((item) => item.symbol === selectedSymbol);
  const selectedCompanyLabel = selectedAsset
    ? `${selectedAsset.name ?? selectedAsset.symbol} (${selectedAsset.symbol.replace(".NS", "")})`
    : selectedSymbol?.replace(".NS", "") ?? "";

  useEffect(() => {
    const next = assets.find((item) => item.symbol === selectedSymbol);
    if (next) setSelectedOption(next);
  }, [assets, selectedSymbol]);

  useEffect(() => {
    if (!companyOpen) return;
    const query = companyQuery.trim();
    if (!query) {
      setCompanyMatches(assets.slice(0, 12));
      setCompanySearching(false);
      return;
    }
    const controller = new AbortController();
    setCompanySearching(true);
    const timer = window.setTimeout(() => {
      void searchNseCompanies(query, controller.signal)
        .then((matches) => {
          setCompanyMatches(matches);
          setError(null);
        })
        .catch((caught) => {
          if (!(caught instanceof DOMException && caught.name === "AbortError")) {
            setError(caught instanceof Error ? caught.message : "NSE company search failed");
          }
        })
        .finally(() => setCompanySearching(false));
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [assets, companyOpen, companyQuery]);

  useEffect(() => {
    if (!selectedSymbol) return;
    const controller = new AbortController();
    setLoadedSymbol(null);
    setSnapshot(null);
    void prepareResearchSnapshot(selectedSymbol, controller.signal)
      .then((nextSnapshot) => {
        setSnapshot(nextSnapshot);
        setLoadedSymbol(selectedSymbol);
        setError(null);
      })
      .catch((caught) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setLoadedSymbol(selectedSymbol);
          setError(caught instanceof Error ? caught.message : "Research snapshot failed");
        }
      });
    return () => controller.abort();
  }, [selectedSymbol]);

  useEffect(() => {
    if (!activeThesis) {
      setThesisEvaluation(null);
      return;
    }
    const controller = new AbortController();
    void fetchThesisEvaluation(activeThesis.thesis_id, controller.signal)
      .then(setThesisEvaluation)
      .catch((caught) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setThesisEvaluation(null);
        }
      });
    return () => controller.abort();
  }, [activeThesis]);

  useEffect(() => {
    if (!selectedSymbol) return;
    const controller = new AbortController();
    setActiveThesis(null);
    void fetchThesisVersions(selectedSymbol, controller.signal)
      .then((versions) => {
        setThesisVersions(versions);
        setActiveThesis(versions[0] ?? null);
      })
      .catch((caught) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setThesisVersions([]);
          setActiveThesis(null);
        }
      });
    return () => controller.abort();
  }, [selectedSymbol]);

  const evidenceById = useMemo(
    () => new Map(snapshot?.evidence.map((item) => [item.evidence_id, item]) ?? []),
    [snapshot]
  );
  const loadingSnapshot = Boolean(selectedSymbol) && loadedSymbol !== selectedSymbol;
  const activeNarrative = narrative?.symbol === selectedSymbol ? narrative : null;

  const generate = async () => {
    if (!selectedSymbol) return;
    setGenerating(true);
    setError(null);
    try {
      setNarrative(
        await generateResearchNarrative(selectedSymbol, horizon, riskProfile)
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI synthesis failed");
    } finally {
      setGenerating(false);
    }
  };

  const chooseCompany = (asset: AssetSummary) => {
    setSelectedOption(asset);
    onSelectSymbol(asset.symbol);
    setCompanyQuery("");
    setCompanyOpen(false);
  };

  const replayThesis = async () => {
    if (!selectedSymbol || !replayDate) return;
    setThesisLoading(true);
    setError(null);
    try {
      const created = await createThesisVersion(selectedSymbol, replayDate);
      setActiveThesis(created);
      setThesisVersions(await fetchThesisVersions(selectedSymbol));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Point-in-time replay failed");
    } finally {
      setThesisLoading(false);
    }
  };

  return (
    <section className="research-workbench">
      <div className="research-controls">
        <div className="research-control-copy">
          <span className="section-kicker">Prototype research brief</span>
          <h3>Ask one model to synthesize the evidence</h3>
          <p>
            The backend calculates every metric first. Groq explains only the evidence IDs shown
            here, making this a safe bridge to the later multi-agent ThesisGraph.
          </p>
        </div>
        <div className="research-form">
          <label>
            Company name or NSE symbol
            <div className="company-combobox">
              <Search size={14} />
              <input
                aria-autocomplete="list"
                aria-expanded={companyOpen}
                aria-controls="company-results"
                placeholder="Try Reliance Industries or RELIANCE"
                value={companyOpen ? companyQuery : selectedCompanyLabel}
                onFocus={(event) => {
                  setCompanyOpen(true);
                  setCompanyQuery("");
                  event.currentTarget.select();
                }}
                onChange={(event) => {
                  setCompanyQuery(event.target.value);
                  setCompanyOpen(true);
                }}
                onBlur={(event) => {
                  if (!event.currentTarget.parentElement?.contains(event.relatedTarget)) {
                    setCompanyOpen(false);
                    setCompanyQuery("");
                  }
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && companyMatches[0]) {
                    event.preventDefault();
                    chooseCompany(companyMatches[0]);
                  }
                  if (event.key === "Escape") {
                    setCompanyQuery("");
                    setCompanyOpen(false);
                  }
                }}
              />
              {companyOpen && (
                <div className="company-results" id="company-results" role="listbox">
                  {companySearching ? (
                    <p className="company-searching"><LoaderCircle className="spin" size={15} /> Searching the NSE catalogue…</p>
                  ) : companyMatches.length ? companyMatches.map((asset) => (
                    <button
                      key={asset.symbol}
                      type="button"
                      role="option"
                      aria-selected={asset.symbol === selectedSymbol}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => chooseCompany(asset)}
                    >
                      <span>{asset.symbol.replace(".NS", "")}</span>
                      <strong>{asset.name ?? asset.symbol}</strong>
                      <small>{asset.exchange ?? "NSE"}</small>
                    </button>
                  )) : <p>No NSE equity or SME symbol matches “{companyQuery}”.</p>}
                </div>
              )}
            </div>
            <small>Searches the full NSE equity and SME catalogue. Price history and recent news load only after selection.</small>
          </label>
          <label>
            Horizon
            <select value={horizon} onChange={(event) => setHorizon(event.target.value as Horizon)}>
              <option value="short_term">Short term</option>
              <option value="medium_term">Medium term</option>
              <option value="long_term">Long term</option>
            </select>
          </label>
          <label>
            Risk lens
            <select
              value={riskProfile}
              onChange={(event) => setRiskProfile(event.target.value as RiskProfile)}
            >
              <option value="conservative">Conservative</option>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </label>
          <button
            className="generate-button"
            type="button"
            disabled={!snapshot || generating}
            onClick={() => void generate()}
          >
            {generating ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
            {generating ? "Building brief…" : "Generate AI brief"}
          </button>
        </div>
      </div>

      {error && (
        <div className="research-error" role="alert">
          <AlertCircle size={18} />
          <div><strong>Research brief needs attention</strong><span>{error}</span></div>
        </div>
      )}

      {loadingSnapshot && (
        <div className="research-loading"><LoaderCircle className="spin" /> Preparing price history and recent company news…</div>
      )}

      {snapshot && !loadingSnapshot && (
        <>
          <div className="research-overview-grid">
            <article className="research-scorecard">
              <span>Current regime</span>
              <strong>{snapshot.technical.signal}</strong>
              <small>{snapshot.technical.observation_count} daily observations · {snapshot.technical.source}</small>
            </article>
            <article className="research-scorecard">
              <span>60-day return</span>
              <strong>{metric(snapshot.technical.returns.sixty_day_pct)}</strong>
              <small>Price change, not a forecast</small>
            </article>
            <article className="research-scorecard">
              <span>RSI (14)</span>
              <strong>{metric(snapshot.technical.momentum.rsi_14, "")}</strong>
              <small>Momentum temperature, not direction alone</small>
            </article>
            <article className="research-scorecard">
              <span>Worst 5% daily tail</span>
              <strong>{metric(snapshot.technical.risk.cvar_95_daily_pct)}</strong>
              <small>Historical CVaR from stored returns</small>
            </article>
          </div>

          <section className="thesis-lifecycle">
            <div className="thesis-lifecycle-head">
              <div>
                <span className="section-kicker">Testable novelty · no LLM required</span>
                <h3>Point-in-time thesis lifecycle</h3>
                <p>Replay only the evidence available by a historical date, persist it, and compare it with the previous version.</p>
              </div>
              <div className="replay-controls">
                <label>
                  Historical cutoff
                  <input
                    type="date"
                    max={new Date().toISOString().slice(0, 10)}
                    value={replayDate}
                    onChange={(event) => setReplayDate(event.target.value)}
                  />
                </label>
                <button type="button" disabled={thesisLoading} onClick={() => void replayThesis()}>
                  {thesisLoading ? <LoaderCircle className="spin" size={15} /> : <CalendarClock size={15} />}
                  {thesisLoading ? "Replaying…" : "Save replay"}
                </button>
              </div>
            </div>
            {activeThesis ? (
              <div className="thesis-lifecycle-body">
                <article className={`thesis-state state-${activeThesis.state}`}>
                  <span>Latest persisted state · v{activeThesis.version_number}</span>
                  <strong>{activeThesis.state.replace("_", " ")}</strong>
                  <small>{Math.round(activeThesis.confidence * 100)}% evidence confidence · {activeThesis.evidence_coverage_pct}% source coverage</small>
                  <time>{new Date(activeThesis.cutoff).toLocaleDateString("en-IN")}</time>
                </article>
                <article className="change-ledger">
                  <div><GitCompareArrows size={16} /><span>What changed</span></div>
                  {activeThesis.changes.length ? activeThesis.changes.map((change) => (
                    <p key={change.field}><strong>{change.label}</strong>{change.interpretation}</p>
                  )) : <p>No metric crossed a declared materiality threshold.</p>}
                </article>
                <article className="breaker-ledger">
                  <span>Machine-testable thesis breakers</span>
                  {activeThesis.breakers.map((breaker) => (
                    <div className={breaker.breached ? `breaker-hit breaker-${breaker.severity}` : "breaker-clear"} key={breaker.rule_id}>
                      {breaker.breached ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}
                      <p><strong>{breaker.label}</strong><small>{breaker.current_value === null ? "Insufficient data" : `Current ${breaker.current_value.toFixed(2)} · threshold ${breaker.threshold.toFixed(2)}`}</small></p>
                    </div>
                  ))}
                </article>
                <div className="version-strip">
                  {thesisVersions.slice(0, 8).map((version) => (
                    <div key={version.thesis_id} title={version.snapshot_hash}>
                      <span>v{version.version_number}</span>
                      <strong>{version.state.replace("_", " ")}</strong>
                      <time>{new Date(version.cutoff).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" })}</time>
                    </div>
                  ))}
                </div>
                <div className="validation-lab">
                  <article>
                    <span>Contradiction engine</span>
                    <strong>{activeThesis.contradictions.length}</strong>
                    <small>cross-signal conflicts detected</small>
                    {activeThesis.contradictions.length ? activeThesis.contradictions.map((item) => (
                      <p className={`contradiction-${item.severity}`} key={item.contradiction_id}>
                        <b>{item.summary}</b>{item.interpretation}
                      </p>
                    )) : <p>No declared cross-signal contradiction was triggered.</p>}
                  </article>
                  <article>
                    <span>Evidence sensitivity</span>
                    <strong>{activeThesis.sensitivity.filter((item) => item.fragile).length}</strong>
                    <small>fragile evidence categories</small>
                    {activeThesis.sensitivity.map((item) => (
                      <div className="sensitivity-row" key={item.scenario_id}>
                        <label>{item.removed_category.replace("_", " ")}</label>
                        <div><i style={{ width: `${Math.min(item.confidence_delta * 500, 100)}%` }} /></div>
                        <b>−{Math.round(item.confidence_delta * 100)} pts</b>
                      </div>
                    ))}
                    {!activeThesis.sensitivity.length && <p>Save this cutoff again to create a thesis-v2 sensitivity run.</p>}
                  </article>
                  <article>
                    <span>Forward outcome audit</span>
                    <strong>{thesisEvaluation?.directional_accuracy === null || thesisEvaluation?.directional_accuracy === undefined ? "—" : `${Math.round(thesisEvaluation.directional_accuracy * 100)}%`}</strong>
                    <small>{thesisEvaluation ? `${thesisEvaluation.expected_direction} thesis · evaluation only` : "loading evaluation"}</small>
                    <div className="outcome-grid">
                      {thesisEvaluation?.outcomes.map((outcome) => (
                        <div key={outcome.horizon_trading_days}>
                          <span>{outcome.horizon_trading_days}D</span>
                          <b>{outcome.realized_return_pct === null ? "Pending" : `${outcome.realized_return_pct >= 0 ? "+" : ""}${outcome.realized_return_pct.toFixed(2)}%`}</b>
                          <small>{outcome.thesis_aligned === null ? "not scored" : outcome.thesis_aligned ? "aligned" : "diverged"}</small>
                        </div>
                      ))}
                    </div>
                  </article>
                  <footer>Future outcomes are evaluation-only and never enter the saved thesis. Sensitivity measures dependence, not causality.</footer>
                </div>
              </div>
            ) : (
              <div className="thesis-empty">Choose a cutoff and save the first replay. Repeating an identical cutoff is idempotent.</div>
            )}
          </section>

          <div className="coverage-strip">
            <div><span>Evidence coverage</span><strong>{snapshot.company_name}</strong></div>
            {coverageLabels.map(([key, label]) => {
              const available = snapshot.coverage[key] === true;
              return (
                <div className={available ? "coverage-ready" : "coverage-missing"} key={key}>
                  {available ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                  <span>{label}</span>
                  <small>{available ? "Available" : "Not connected"}</small>
                </div>
              );
            })}
          </div>

          <div className="research-detail-grid">
            <section className="research-subpanel">
              <div className="research-subheading"><BookOpenCheck size={18} /><div><span>Structured claims</span><h3>What the backend can defend</h3></div></div>
              <div className="claim-list">
                {snapshot.claims.map((claim) => (
                  <article key={claim.claim_id} className={`claim-card claim-${claim.status}`}>
                    <div><span>{claim.claim_type.replaceAll("_", " ")}</span><small>{Math.round(claim.confidence * 100)}% evidence confidence</small></div>
                    <p>{claim.claim}</p>
                    <div className="claim-links">
                      {claim.evidence_ids.map((id) => <code title={evidenceById.get(id)?.title} key={id}>{id}</code>)}
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="research-subpanel">
              <div className="research-subheading"><ShieldAlert size={18} /><div><span>Evidence ledger</span><h3>Inspect every input</h3></div></div>
              <div className="research-evidence-list">
                {snapshot.evidence.map((item) => <EvidenceRow item={item} key={item.evidence_id} />)}
              </div>
            </section>
          </div>
        </>
      )}

      {!activeNarrative && snapshot && !loadingSnapshot && (
        <div className="ai-empty-state">
          <BrainCircuit size={27} />
          <div>
            <strong>The deterministic brief is ready.</strong>
            <p>Generate the AI layer to translate these exact claims into plain language, scenarios and thesis breakers.</p>
          </div>
          <ArrowRight size={18} />
        </div>
      )}

      {activeNarrative && (
        <section className="ai-brief">
          <div className="ai-brief-header">
            <div><span className="section-kicker">Groq synthesis · evidence grounded</span><h3>{activeNarrative.narrative.executive_summary}</h3></div>
            <div className="confidence-ring"><strong>{Math.round(activeNarrative.narrative.confidence * 100)}%</strong><span>confidence</span></div>
          </div>
          <div className="plain-language-grid">
            <article><span>What is happening?</span><p>{activeNarrative.narrative.what_is_happening}</p></article>
            <article><span>Why does it matter?</span><p>{activeNarrative.narrative.why_it_matters}</p></article>
          </div>
          <div className="ai-evidence-columns">
            <section>
              <h4>Evidence supporting the view</h4>
              {activeNarrative.narrative.supporting_evidence.map((item) => (
                <article key={`${item.title}-${item.evidence_ids.join("-")}`}><strong>{item.title}</strong><p>{item.explanation}</p><div>{item.evidence_ids.map((id) => <code key={id}>{id}</code>)}</div></article>
              ))}
            </section>
            <section>
              <h4>Contradictions and caution</h4>
              {activeNarrative.narrative.contradicting_evidence.length ? activeNarrative.narrative.contradicting_evidence.map((item) => (
                <article key={`${item.title}-${item.evidence_ids.join("-")}`}><strong>{item.title}</strong><p>{item.explanation}</p><div>{item.evidence_ids.map((id) => <code key={id}>{id}</code>)}</div></article>
              )) : <p className="narrative-empty">No contradiction was identified in the available evidence. Missing data still limits this conclusion.</p>}
            </section>
          </div>
          <div className="scenario-grid">
            <ScenarioCard scenario={activeNarrative.narrative.bull_case} tone="bull" />
            <ScenarioCard scenario={activeNarrative.narrative.base_case} tone="base" />
            <ScenarioCard scenario={activeNarrative.narrative.bear_case} tone="bear" />
          </div>
          <div className="thesis-grid">
            <article><span>Assumptions that must hold</span><ul>{activeNarrative.narrative.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></article>
            <article><span>What would break this view?</span><ul>{activeNarrative.narrative.thesis_breakers.map((item) => <li key={item}>{item}</li>)}</ul></article>
            <article><span>Known data gaps</span><ul>{activeNarrative.narrative.data_gaps.map((item) => <li key={item}>{item}</li>)}</ul></article>
          </div>
          <footer className="ai-audit-footer">
            <span>{activeNarrative.model}</span><span>Prompt {activeNarrative.prompt_version}</span><span>Analysis {activeNarrative.analysis_id.slice(0, 8)}</span><p>{activeNarrative.narrative.disclaimer}</p>
          </footer>
        </section>
      )}
    </section>
  );
}
