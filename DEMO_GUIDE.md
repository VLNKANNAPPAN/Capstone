# MarketLab demo guide

This branch is the focused presentation build. It deliberately exposes fewer capabilities than
`main` while keeping a complete, explainable workflow.

## One-sentence pitch

MarketLab turns normalized Indian-market data into transparent company metrics and an educational,
constraint-aware portfolio without hiding uncertainty.

## Recommended 6-minute walkthrough

### 1. Home — 45 seconds

Say:

> The prototype follows four steps: acquire reliable records, normalize them, calculate comparable
> metrics, and explain the result without presenting it as a guaranteed prediction.

Point out the stored asset, price-bar, context, and quality counts. These prove that the screens are
backed by persisted records rather than hard-coded cards.

### 2. Explore — 2 minutes

Choose one company and explain:

1. The chart is the normalized historical closing-price record.
2. The 60-day return describes recent direction.
3. RSI shows whether recent buying or selling is stretched.
4. Sharpe compares historical return with overall variability.
5. Maximum drawdown shows the worst observed peak-to-trough fall.

Use this line if the signals disagree:

> Disagreement is a valid result. The system keeps the conclusion mixed instead of forcing a buy or
> sell label.

The linked-headline section may be empty. That is intentional: missing evidence is displayed rather
than fabricated.

### 3. Portfolio — 2 minutes

Enter a budget, risk level, and duration, then click **Create demo portfolio**.

Explain the three-stage logic:

1. Rank the stored universe using returns, volatility, downside risk, and trend.
2. Apply sector and correlation controls so one industry does not dominate.
3. Fit whole-share quantities to the budget and show leftover cash.

The return range is a historical model estimate, not a promise. The confidence score describes data
coverage and diversification—not the probability of earning the stated return.

### 4. Learn — 45 seconds

Show that every metric used in the demo has a plain-language definition and a warning about common
misinterpretation. This is the beginner-friendly layer of the product.

### 5. Data status — 30 seconds

Show source provenance, ingestion freshness, recent acquisition runs, and quality issues. This is the
audit trail behind the user-facing results.

## Intentionally hidden in this branch

- Multi-agent debate and orchestration
- Point-in-time thesis replay and sensitivity experiments
- Detailed filing/XBRL evidence screens
- Bond analytics
- YouTube briefing workspace
- Advanced market-breadth and metric-trend panels
- Full administrative controls

Those implementations remain on `main`; they were not deleted from the project history.

## Run locally

```powershell
git switch demo-building-stage
$env:DATABASE_URL='sqlite:///D:/Capstone_project/data/dashboard_preview.db'
.venv\Scripts\python.exe -m uvicorn market_platform.api.app:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd apps\web
.\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/#/overview`.

## Safety language

Call every output an **educational model**, **historical measurement**, or **research aid**. Avoid
calling it a recommendation, guaranteed return, live trading system, or personalized financial advice.
