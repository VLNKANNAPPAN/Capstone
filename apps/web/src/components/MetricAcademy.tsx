import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, BookOpen, CheckCircle2, GraduationCap } from "lucide-react";

type Scenario = "constructive" | "mixed" | "risk";

interface Lesson {
  id: string;
  module: string;
  name: string;
  goal: string;
  definition: string;
  formula: string;
  example: string;
  reading: string[];
  caution: string;
  chartLabel: string;
  chart: Array<{ period: string; value: number }>;
  reference?: number;
  scenarios: Record<Scenario, { title: string; observation: string; context: string }>;
}

const lessons: Lesson[] = [
  {
    id: "returns",
    module: "01 · Foundations",
    name: "Returns & momentum",
    goal: "Separate an observed price move from a prediction.",
    definition: "Return is the percentage change between two prices. Momentum compares returns over a consistent window to ask whether a move has persisted.",
    formula: "Return = (latest price ÷ starting price − 1) × 100",
    example: "A move from ₹1,000 to ₹1,120 is a 12% return. It says what happened; it does not say another 12% will follow.",
    reading: ["Positive 20D and 60D returns suggest persistence.", "Positive 20D but negative 60D can be an early rebound.", "Negative readings across both windows indicate broad weakness."],
    caution: "Window choice matters. A result announcement can make short-window momentum look unusually strong or weak.",
    chartLabel: "Illustrative price index",
    chart: [{ period: "Start", value: 100 }, { period: "M1", value: 103 }, { period: "M2", value: 101 }, { period: "M3", value: 108 }, { period: "Now", value: 112 }],
    scenarios: {
      constructive: { title: "Persistent advance", observation: "20D +6%, 60D +14%, volume above normal", context: "Trend evidence agrees, but valuation and events still need checking." },
      mixed: { title: "Early rebound", observation: "20D +5%, 60D −9%", context: "Improving short-term action inside a still-damaged medium-term trend." },
      risk: { title: "Falling momentum", observation: "20D −8%, 60D −17%", context: "Weakness is persistent; do not label it cheap from price action alone." },
    },
  },
  {
    id: "sma",
    module: "02 · Trend & momentum",
    name: "Moving averages",
    goal: "Use a baseline to identify trend without treating it as support magic.",
    definition: "A simple moving average is the mean closing price over a rolling window. Distance from SMA20 measures how stretched the latest price is from its recent baseline.",
    formula: "Distance = (price ÷ SMA20 − 1) × 100",
    example: "A ₹105 price and ₹100 SMA20 gives +5%. The stock is above trend, but may also be temporarily extended.",
    reading: ["Price above rising SMA20: constructive short trend.", "Price below falling SMA20: negative trend.", "Repeated crossings: range-bound or noisy regime."],
    caution: "Moving averages lag. They confirm a move after it begins and can whipsaw in sideways markets.",
    chartLabel: "Price versus baseline",
    chart: [{ period: "D1", value: 96 }, { period: "D2", value: 99 }, { period: "D3", value: 101 }, { period: "D4", value: 104 }, { period: "Now", value: 106 }],
    reference: 100,
    scenarios: {
      constructive: { title: "Healthy trend", observation: "Price +3% above a rising SMA20", context: "Constructive, especially if medium-term return and volume agree." },
      mixed: { title: "Possible recovery", observation: "Price crosses above a still-falling SMA20", context: "Early improvement, not yet a confirmed trend change." },
      risk: { title: "Breakdown", observation: "Price −7% below SMA20 after high-volume selling", context: "Negative trend with event risk; inspect news and filings." },
    },
  },
  {
    id: "rsi",
    module: "02 · Trend & momentum",
    name: "RSI (14)",
    goal: "Read momentum temperature without using automatic buy/sell rules.",
    definition: "RSI compares the magnitude of recent gains with recent losses on a 0–100 scale. It measures speed and persistence, not business value.",
    formula: "RSI = 100 − 100 ÷ (1 + average gain ÷ average loss)",
    example: "RSI 26 means losses dominated the 14-period sample. It is called oversold, but a strong downtrend can remain oversold.",
    reading: ["Above 70: stretched buying pressure.", "40–60: broadly balanced momentum.", "Below 30: stretched selling pressure."],
    caution: "Overbought is not an automatic sell, and oversold is not an automatic buy.",
    chartLabel: "RSI scale",
    chart: [{ period: "D1", value: 58 }, { period: "D4", value: 49 }, { period: "D8", value: 38 }, { period: "D11", value: 31 }, { period: "D14", value: 26 }],
    reference: 30,
    scenarios: {
      constructive: { title: "Momentum reset", observation: "RSI rises from 28 to 42 while price stabilizes", context: "Selling pressure is easing; require trend confirmation." },
      mixed: { title: "Neutral", observation: "RSI oscillates near 50", context: "Momentum has no strong edge; other evidence should dominate." },
      risk: { title: "Persistent oversold", observation: "RSI below 30 and price keeps making new lows", context: "The trend remains stronger than the reversal signal." },
    },
  },
  {
    id: "volatility",
    module: "03 · Risk",
    name: "Volatility",
    goal: "Translate price variability into position and uncertainty context.",
    definition: "Annualized volatility scales the standard deviation of daily returns to a one-year equivalent. It measures movement size, not direction.",
    formula: "Annualized volatility = daily return standard deviation × √252",
    example: "30% volatility does not mean a 30% loss. It means outcomes have recently been much more dispersed than a 12% volatility stock.",
    reading: ["Compare like-for-like windows and sectors.", "Rising volatility around an event increases uncertainty.", "Low volatility can change abruptly; it is not permanent safety."],
    caution: "Volatility assumes past variation is informative and can understate discontinuous event risk.",
    chartLabel: "Illustrative annualized volatility",
    chart: [{ period: "W1", value: 11 }, { period: "W2", value: 13 }, { period: "W3", value: 12 }, { period: "W4", value: 22 }, { period: "Now", value: 29 }],
    scenarios: {
      constructive: { title: "Calm advance", observation: "Positive return with stable 14% volatility", context: "Return is being achieved with relatively controlled variability." },
      mixed: { title: "Event expansion", observation: "Volatility jumps from 16% to 31% after results", context: "Direction is unresolved; size assumptions need widening." },
      risk: { title: "Disorderly decline", observation: "Negative return and volatility above 40%", context: "Downside and uncertainty reinforce each other." },
    },
  },
  {
    id: "sharpe",
    module: "03 · Risk",
    name: "Sharpe ratio",
    goal: "Judge excess return per unit of total volatility.",
    definition: "Sharpe compares return above a risk-free rate with total return variability. It lets us compare paths, not just ending returns.",
    formula: "Sharpe = annualized excess return ÷ annualized volatility",
    example: "Portfolio A returns 14% at 10% volatility; B returns 16% at 25%. A may have the better Sharpe despite the lower raw return.",
    reading: ["Above 1: historically efficient risk-adjusted return.", "Near 0: little excess return for variability taken.", "Below 0: underperformed the assumed risk-free return."],
    caution: "Sharpe treats upside and downside movement equally and changes with the risk-free assumption and sample window.",
    chartLabel: "Risk-adjusted path",
    chart: [{ period: "Q1", value: 0.2 }, { period: "Q2", value: 0.5 }, { period: "Q3", value: 0.9 }, { period: "Q4", value: 1.2 }],
    reference: 1,
    scenarios: {
      constructive: { title: "Efficient return", observation: "Sharpe 1.3 with positive 60D return", context: "The historical path rewarded variability, subject to sample stability." },
      mixed: { title: "Raw return only", observation: "Return positive but Sharpe 0.2", context: "Gains came with substantial noise or weak excess return." },
      risk: { title: "Negative efficiency", observation: "Sharpe −0.8", context: "The asset failed to compensate for total variability in the window." },
    },
  },
  {
    id: "sortino",
    module: "03 · Risk",
    name: "Sortino ratio",
    goal: "Focus risk-adjusted analysis on harmful downside variation.",
    definition: "Sortino replaces total volatility with downside deviation. Positive upside jumps are not counted as harmful risk.",
    formula: "Sortino = annualized excess return ÷ annualized downside deviation",
    example: "Two stocks can share the same Sharpe, while the stock with fewer negative shocks has the better Sortino.",
    reading: ["Use alongside Sharpe to inspect asymmetry.", "A much higher Sortino suggests volatility was mostly upside.", "A negative value still signals poor excess return."],
    caution: "Short samples with few negative days can produce unstable or deceptively high readings.",
    chartLabel: "Downside efficiency",
    chart: [{ period: "Q1", value: -0.3 }, { period: "Q2", value: 0.1 }, { period: "Q3", value: 0.6 }, { period: "Q4", value: 1.0 }],
    reference: 0,
    scenarios: {
      constructive: { title: "Upside-skewed", observation: "Sharpe 0.8, Sortino 1.5", context: "Much of the variability came from positive rather than harmful moves." },
      mixed: { title: "Similar ratios", observation: "Sharpe 0.7, Sortino 0.8", context: "Upside and downside variability were more balanced." },
      risk: { title: "Downside-dominated", observation: "Sortino −1.1", context: "Return did not compensate for harmful variation." },
    },
  },
  {
    id: "drawdown",
    module: "03 · Risk",
    name: "Maximum drawdown",
    goal: "Understand the worst observed capital decline and recovery burden.",
    definition: "Maximum drawdown is the largest fall from a running peak to a later trough within the selected window.",
    formula: "Drawdown = trough price ÷ prior peak price − 1",
    example: "A fall from ₹100 to ₹70 is −30%. Recovering to ₹100 then requires +42.9%, not +30%.",
    reading: ["Shows path-dependent pain hidden by average return.", "Compare drawdowns across the same market window.", "Pair with recovery time and event context."],
    caution: "The worst future loss can exceed the historical sample, and changing the start date changes the result.",
    chartLabel: "Peak-to-trough index",
    chart: [{ period: "Peak", value: 100 }, { period: "M1", value: 94 }, { period: "M2", value: 82 }, { period: "Trough", value: 70 }, { period: "Now", value: 84 }],
    reference: 100,
    scenarios: {
      constructive: { title: "Contained", observation: "Max drawdown −9%, rapid recovery", context: "Historical capital impairment was limited in this window." },
      mixed: { title: "Recovering", observation: "Drawdown −25%, price now halfway back", context: "Momentum improved, but prior holders still face recovery risk." },
      risk: { title: "Deep and open", observation: "Drawdown −42%, no recovery", context: "The historical loss path remains severe and unresolved." },
    },
  },
  {
    id: "cvar",
    module: "03 · Risk",
    name: "VaR & CVaR",
    goal: "Read a loss threshold and what happens beyond it.",
    definition: "Historical VaR is a percentile loss threshold. CVaR is the average loss among observations worse than that threshold.",
    formula: "95% CVaR = average return in the worst 5% of observed days",
    example: "VaR −2% and CVaR −3.2% means 5% of days were worse than −2%, averaging about −3.2% within that tail.",
    reading: ["CVaR is usually more informative for severe-loss planning.", "Use sufficient observations and a disclosed window.", "Compare with maximum drawdown for multi-day damage."],
    caution: "Historical tails omit events more extreme than the sample and do not model liquidity gaps.",
    chartLabel: "Worst-tail daily loss",
    chart: [{ period: "P50", value: 0 }, { period: "P25", value: -0.6 }, { period: "P10", value: -1.4 }, { period: "VaR", value: -2.0 }, { period: "CVaR", value: -3.2 }],
    reference: -2,
    scenarios: {
      constructive: { title: "Contained tail", observation: "CVaR −1.4% with stable volatility", context: "Recent extreme daily losses were relatively limited." },
      mixed: { title: "Changing tail", observation: "CVaR worsens after one event gap", context: "The sample now reflects materially higher event sensitivity." },
      risk: { title: "Heavy tail", observation: "CVaR −4.8%", context: "Worst days have been severe; average volatility alone understates risk." },
    },
  },
  {
    id: "fcf",
    module: "04 · Business quality",
    name: "Free-cash-flow yield",
    goal: "Connect market price with cash left after reinvestment.",
    definition: "FCF yield compares annual free cash flow with market capitalization. It is a cash-based valuation lens.",
    formula: "FCF yield = (cash from operations − capital expenditure) ÷ market cap",
    example: "₹500 crore FCF on a ₹10,000 crore market cap gives a 5% FCF yield.",
    reading: ["Higher can indicate cheaper cash generation.", "Check whether FCF is recurring or boosted by working capital.", "Compare firms with similar reinvestment needs."],
    caution: "A high yield can reflect a collapsing business; one-year FCF can be unusually volatile.",
    chartLabel: "Illustrative FCF yield",
    chart: [{ period: "FY1", value: 2.2 }, { period: "FY2", value: 3.1 }, { period: "FY3", value: 4.0 }, { period: "FY4", value: 5.0 }],
    reference: 4,
    scenarios: {
      constructive: { title: "Cash compounding", observation: "FCF yield 5%, FCF growing, debt stable", context: "Valuation and cash quality reinforce each other." },
      mixed: { title: "Temporary boost", observation: "Yield 7% after working-capital release", context: "Normalize cash flow before concluding the stock is cheap." },
      risk: { title: "Value trap", observation: "Yield 9%, revenue falling, leverage rising", context: "High yield may compensate for deteriorating fundamentals." },
    },
  },
  {
    id: "roic",
    module: "04 · Business quality",
    name: "ROIC",
    goal: "Test whether the business earns attractive returns on operating capital.",
    definition: "Return on invested capital compares after-tax operating profit with debt and equity capital used by operations.",
    formula: "ROIC = NOPAT ÷ average invested capital",
    example: "₹120 crore NOPAT on ₹1,000 crore invested capital gives 12% ROIC.",
    reading: ["Compare ROIC with the company’s cost of capital.", "Sustained high ROIC can indicate a durable business advantage.", "Growth creates value only when incremental returns remain attractive."],
    caution: "Accounting choices, acquisitions and financial-company balance sheets require sector-specific adjustments.",
    chartLabel: "ROIC versus cost of capital",
    chart: [{ period: "FY1", value: 9 }, { period: "FY2", value: 11 }, { period: "FY3", value: 13 }, { period: "FY4", value: 15 }],
    reference: 10,
    scenarios: {
      constructive: { title: "Value creation", observation: "ROIC 15% versus 10% capital cost", context: "Operations earn more than their financing hurdle." },
      mixed: { title: "Near the hurdle", observation: "ROIC 10.5% versus 10% cost", context: "Growth adds little value unless returns improve." },
      risk: { title: "Value destruction", observation: "ROIC 7% versus 11% cost", context: "More investment can destroy value despite revenue growth." },
    },
  },
  {
    id: "bond-yield",
    module: "05 · Fixed income",
    name: "Coupon, price & YTM",
    goal: "Separate the stated coupon from the return implied by the purchase price.",
    definition: "A coupon is the contractual interest on face value. Yield to maturity discounts all remaining coupons and principal so their present value equals the bond price.",
    formula: "Price = Σ cash flowₜ ÷ (1 + periodic YTM)ᵗ",
    example: "An 8% ₹1,000 bond pays ₹80 annually. Buying below ₹1,000 normally makes YTM exceed 8%; buying above face value normally makes it lower.",
    reading: ["Coupon is calculated on face value, not market price.", "YTM assumes promised cash flows and reinvestment at the calculated rate.", "Compare clean price, accrued interest and total dirty price."],
    caution: "YTM is not guaranteed when the issuer can default, the bond is called early, or the investor sells before maturity.",
    chartLabel: "Price as market yield changes",
    chart: [{ period: "5%", value: 112 }, { period: "6%", value: 108 }, { period: "7%", value: 104 }, { period: "8%", value: 100 }, { period: "9%", value: 96 }],
    reference: 100,
    scenarios: {
      constructive: { title: "Discount purchase", observation: "Price ₹96, coupon 8%, YTM above coupon", context: "Higher yield may compensate for rate or credit risk; inspect why it trades below par." },
      mixed: { title: "Near par", observation: "Price ₹100, coupon and YTM near 8%", context: "Cash-flow return is straightforward, subject to issuer and reinvestment risk." },
      risk: { title: "Misleading coupon", observation: "Coupon 11%, price unavailable and no recent trades", context: "The coupon alone cannot establish expected return, liquidity or fair value." },
    },
  },
  {
    id: "duration",
    module: "05 · Fixed income",
    name: "Duration, DV01 & convexity",
    goal: "Measure how strongly a bond price responds to interest-rate changes.",
    definition: "Modified duration approximates percentage price change for a one-percentage-point yield move. DV01 converts that sensitivity into currency for one basis point; convexity improves larger-shock estimates.",
    formula: "Approx. ΔPrice% = −Duration × ΔYield + ½ × Convexity × ΔYield²",
    example: "A modified duration of 6 implies roughly a 6% price fall if yield rises 1%, before the convexity adjustment.",
    reading: ["Longer maturity usually means greater rate sensitivity.", "Lower coupons usually increase duration.", "Use DV01 to compare currency risk across position sizes."],
    caution: "Duration models small parallel shifts. Real curves can steepen, flatten or move unevenly across tenors.",
    chartLabel: "Illustrative price response",
    chart: [{ period: "−100bp", value: 106.4 }, { period: "−50bp", value: 103.1 }, { period: "Now", value: 100 }, { period: "+50bp", value: 97.1 }, { period: "+100bp", value: 94.4 }],
    reference: 100,
    scenarios: {
      constructive: { title: "Rates fall", observation: "Yield −75 bps, duration 6", context: "Price may rise, but reinvestment income on future cash flows can fall." },
      mixed: { title: "Short horizon", observation: "Duration 1.2, maturity matched to goal", context: "Rate sensitivity is contained because cash is returned relatively soon." },
      risk: { title: "Long-duration shock", observation: "Yield +100 bps, duration 9", context: "A substantial mark-to-market loss can occur even without default." },
    },
  },
  {
    id: "credit-spread",
    module: "05 · Fixed income",
    name: "Credit spread & ratings",
    goal: "Understand the extra yield offered over a sovereign benchmark.",
    definition: "Credit spread is corporate-bond yield minus a comparable-maturity government yield. It compensates for expected loss, liquidity and uncertainty—not just default probability.",
    formula: "Credit spread = corporate YTM − matched-tenor G-Sec yield",
    example: "A corporate YTM of 8.4% against a 7.0% G-Sec benchmark gives a 1.4 percentage-point, or 140 bp, spread.",
    reading: ["Match maturities before comparing yields.", "Track rating agency, rating date and outlook.", "Widening spreads can precede a downgrade or reflect market-wide stress."],
    caution: "A rating is an opinion, not a guarantee. Old ratings and apparently high yields require current issuer evidence.",
    chartLabel: "Illustrative credit spread",
    chart: [{ period: "AAA", value: 55 }, { period: "AA", value: 95 }, { period: "A", value: 170 }, { period: "BBB", value: 280 }, { period: "Below", value: 520 }],
    scenarios: {
      constructive: { title: "Stable high grade", observation: "AAA, positive outlook, spread 70 bps", context: "Lower credit compensation is consistent with stronger assessed quality, not zero risk." },
      mixed: { title: "Spread widening", observation: "Rating unchanged, spread widens 80 bps", context: "Market liquidity or new issuer risk may be moving faster than the formal rating." },
      risk: { title: "Yield trap", observation: "Very high coupon, stale rating, no trades", context: "Headline income can conceal default and exit risk." },
    },
  },
  {
    id: "bond-ladder",
    module: "05 · Fixed income",
    name: "Ladders & liquidity",
    goal: "Match maturities to spending needs while reducing single-date rate risk.",
    definition: "A ladder distributes capital across maturity buckets. Principal is returned at different dates, which can reduce reinvestment timing concentration and support planned cash needs.",
    formula: "Bucket allocation = planned cash need ÷ total fixed-income budget",
    example: "₹1 lakh can be split across 1Y, 3Y and 5Y maturities instead of depending on one sale date.",
    reading: ["Keep near-term liabilities in near-term maturities.", "Check lot size and actual secondary-market liquidity.", "Reinvest matured principal only after reviewing the new curve."],
    caution: "A ladder does not eliminate default, inflation or reinvestment risk, and a database listing does not ensure a buyer exists.",
    chartLabel: "Illustrative maturity allocation",
    chart: [{ period: "1Y", value: 30 }, { period: "2Y", value: 20 }, { period: "3Y", value: 20 }, { period: "4Y", value: 15 }, { period: "5Y", value: 15 }],
    scenarios: {
      constructive: { title: "Goal matched", observation: "Near-term buckets cover known cash needs", context: "The investor is less dependent on selling a long bond during an unfavorable rate move." },
      mixed: { title: "Reinvestment trade-off", observation: "Large 1Y allocation while rates may fall", context: "Capital risk is lower, but future reinvestment yield may decline." },
      risk: { title: "Illiquid concentration", observation: "One callable corporate bond dominates the ladder", context: "Credit, call and liquidity risks defeat the intended diversification." },
    },
  },
];

const scenarioLabels: Record<Scenario, string> = {
  constructive: "Constructive",
  mixed: "Mixed",
  risk: "Risk case",
};

const investorNotes: Record<string, {
  use: string;
  combine: string;
  warning: string;
  question: string;
}> = {
  returns: {
    use: "Investors compare returns over several windows to separate a short rebound from a durable trend and to benchmark opportunity cost.",
    combine: "Volatility, benchmark-relative strength, valuation and the event that caused the move.",
    warning: "One exceptional starting or ending day, a corporate action, or a result-day gap can dominate a short window.",
    question: "Did the return come from improving business evidence or simply a change in market enthusiasm?",
  },
  sma: {
    use: "Trend followers use moving averages to define regime, reduce emotional timing decisions and identify when price behavior changes.",
    combine: "60-day return, volume, RSI and a slower average such as SMA50 or SMA200.",
    warning: "Frequent crossings with a flat average indicate noise; a large distance above trend can signal crowding rather than strength.",
    question: "Is the average rising, and is price holding above it across more than one observation?",
  },
  rsi: {
    use: "RSI helps investors see whether recent gains or losses are becoming unusually one-sided before sizing or adding to a position.",
    combine: "Primary trend, support levels, volume and event risk. RSI should confirm context, never create it alone.",
    warning: "Strong trends can remain above 70 or below 30 for weeks, making automatic reversal trades dangerous.",
    question: "Is momentum actually turning, or is the stock merely stretched inside an unchanged trend?",
  },
  volatility: {
    use: "Professional allocators translate volatility into position size so one turbulent holding does not dominate total portfolio risk.",
    combine: "Correlation, CVaR, drawdown, liquidity and the investor’s time horizon.",
    warning: "Quiet periods often precede volatility expansion; annualization also assumes the recent sample remains representative.",
    question: "How much portfolio risk does this position contribute after its correlations are included?",
  },
  sharpe: {
    use: "Sharpe compares how efficiently different assets or strategies converted total variability into excess return.",
    combine: "Sortino, drawdown, turnover, benchmark return and the exact risk-free-rate assumption.",
    warning: "A high value from a short, unusually calm sample can collapse when the market regime changes.",
    question: "Is the ratio stable across multiple windows, or dependent on one favorable period?",
  },
  sortino: {
    use: "Sortino is useful when investors care more about harmful downside than beneficial upside volatility.",
    combine: "Sharpe, CVaR, maximum drawdown and the number of negative observations in the sample.",
    warning: "Too few negative days can make the denominator unstable and the ratio look unrealistically attractive.",
    question: "Does the asset still look efficient when only its bad outcomes are treated as risk?",
  },
  drawdown: {
    use: "Drawdown translates abstract risk into capital loss and the recovery return an investor would have needed to break even.",
    combine: "Recovery time, CVaR, liquidity, leverage and the event behind the decline.",
    warning: "Historical maximum drawdown is only the worst observed loss—not a boundary on future losses.",
    question: "Could the investor remain invested financially and emotionally through a similar decline?",
  },
  cvar: {
    use: "Risk teams use CVaR to estimate the average severity of the worst observed daily outcomes instead of stopping at a percentile threshold.",
    combine: "VaR, volatility, drawdown, event scenarios and liquidity under stress.",
    warning: "A limited history may contain too few crises, while market gaps can be worse than every observation in the sample.",
    question: "What happens beyond the normal-loss threshold, and can the position be exited during stress?",
  },
  fcf: {
    use: "Long-term investors use free-cash-flow yield to connect valuation with cash that remains after maintaining and growing the business.",
    combine: "Revenue growth, ROIC, debt, working-capital movements and management’s capital-allocation record.",
    warning: "Temporary working-capital releases or underinvestment can inflate one year of free cash flow.",
    question: "Is cash generation repeatable after normalizing investment and working capital?",
  },
  roic: {
    use: "Quality investors look for businesses that can reinvest for years at returns above their cost of capital.",
    combine: "Incremental ROIC, revenue runway, margins, leverage, competitive advantage and valuation.",
    warning: "Accounting acquisitions, goodwill and financial-sector balance sheets require specialized adjustments.",
    question: "Can the company deploy additional capital at similarly attractive returns without weakening its moat?",
  },
  "bond-yield": {
    use: "Bond investors use YTM to compare different coupons, prices and maturities on a common annualized basis.",
    combine: "Clean and dirty price, maturity, call terms, credit spread, liquidity and tax treatment.",
    warning: "A calculator can be precise while its cash-flow dates or entered price are wrong; validate the source terms first.",
    question: "Is this yield based on an executable price and cash flows the issuer is likely to pay?",
  },
  duration: {
    use: "Portfolio managers use duration and DV01 to limit the damage from changing interest rates and compare positions of different sizes.",
    combine: "Yield-curve scenarios, convexity, investment horizon and the timing of liabilities.",
    warning: "A single duration number cannot describe non-parallel curve changes, embedded options or credit-spread shocks.",
    question: "Could I hold through the modeled mark-to-market loss without needing to sell?",
  },
  "credit-spread": {
    use: "Credit spread helps separate the sovereign time value of money from compensation for issuer and liquidity risk.",
    combine: "Current rating rationale, issuer filings, leverage, interest coverage, covenants and recent trades.",
    warning: "Comparing mismatched maturities or using a stale corporate price produces a meaningless spread.",
    question: "What specific risk explains the extra yield, and is the compensation adequate?",
  },
  "bond-ladder": {
    use: "Ladders organize fixed-income cash flows around goals instead of relying on a single rate forecast or maturity date.",
    combine: "Emergency liquidity, inflation, credit limits, callable exposure and actual minimum lot sizes.",
    warning: "Equal rupee buckets can still hide concentrated duration or issuer exposure.",
    question: "Does each maturity bucket correspond to a real future cash need or a deliberate reinvestment decision?",
  },
};

export function MetricAcademy() {
  const [activeId, setActiveId] = useState(lessons[0].id);
  const [scenario, setScenario] = useState<Scenario>("mixed");
  const lesson = lessons.find((item) => item.id === activeId) ?? lessons[0];
  const modules = useMemo(() => [...new Set(lessons.map((item) => item.module))], []);
  const activeIndex = lessons.findIndex((item) => item.id === lesson.id);
  const investorNote = investorNotes[lesson.id];
  const scenarioChart = useMemo(() => {
    const span = Math.max(...lesson.chart.map((point) => Math.abs(point.value)), 1);
    const adjustment = span * 0.12;
    return lesson.chart.map((point, index) => {
      const progress = index / Math.max(lesson.chart.length - 1, 1);
      const value = scenario === "constructive"
        ? point.value + progress * adjustment
        : scenario === "risk"
          ? point.value - progress * adjustment
          : point.value + (index % 2 === 0 ? -1 : 1) * adjustment * 0.16;
      return { ...point, value: Number(value.toFixed(2)) };
    });
  }, [lesson, scenario]);
  const scenarioColor = scenario === "constructive" ? "#188465" : scenario === "risk" ? "#bd4c46" : "#2256d8";

  return (
    <section className="course-shell">
      <aside className="course-sidebar">
        <div className="course-brand">
          <GraduationCap size={24} />
          <div><span>Short course</span><strong>{lessons.length} lessons · {modules.length} modules</strong></div>
        </div>
        <div className="course-progress"><span style={{ width: `${((activeIndex + 1) / lessons.length) * 100}%` }} /></div>
        {modules.map((module) => (
          <div className="course-module" key={module}>
            <h3>{module}</h3>
            {lessons.filter((item) => item.module === module).map((item) => (
              <button className={item.id === lesson.id ? "is-active" : ""} key={item.id} onClick={() => setActiveId(item.id)} type="button">
                <CheckCircle2 size={14} />{item.name}
              </button>
            ))}
          </div>
        ))}
      </aside>

      <article className="course-lesson">
        <header className="course-lesson-header">
          <div><span>{lesson.module} · Lesson {activeIndex + 1} of {lessons.length}</span><h2>{lesson.name}</h2><p>{lesson.goal}</p></div>
          <BookOpen size={28} />
        </header>

        <div className="lesson-concepts">
          <section><span>What it measures</span><p>{lesson.definition}</p></section>
          <section><span>Core formula</span><code>{lesson.formula}</code></section>
          <section><span>Worked example</span><p>{lesson.example}</p></section>
        </div>

        <section className="investor-notes">
          <div><span>Why investors use it</span><p>{investorNote.use}</p></div>
          <div><span>Best combined with</span><p>{investorNote.combine}</p></div>
          <div><span>Warning signs</span><p>{investorNote.warning}</p></div>
          <div><span>Decision question</span><p>{investorNote.question}</p></div>
        </section>

        <div className="lesson-lab">
          <section className="example-chart-card">
            <div><span className="section-kicker">Visual example · {scenarioLabels[scenario]} state</span><h3>{lesson.chartLabel}</h3></div>
            <ResponsiveContainer width="100%" height={230}>
              <AreaChart data={scenarioChart} margin={{ top: 15, right: 15, left: -18, bottom: 0 }}>
                <defs><linearGradient id="academy-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={scenarioColor} stopOpacity={0.28} /><stop offset="100%" stopColor={scenarioColor} stopOpacity={0.02} /></linearGradient></defs>
                <CartesianGrid stroke="#e7e4dc" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ fontSize: 10, border: "1px solid #ddd9cf" }} />
                {lesson.reference !== undefined && <ReferenceLine y={lesson.reference} stroke="#d47d30" strokeDasharray="4 4" />}
                <Area type="monotone" dataKey="value" stroke={scenarioColor} strokeWidth={2} fill="url(#academy-fill)" />
              </AreaChart>
            </ResponsiveContainer>
          </section>
          <section className="reading-guide">
            <span className="section-kicker">Reading guide</span>
            <h3>Ask these questions</h3>
            <ol>{lesson.reading.map((item) => <li key={item}>{item}</li>)}</ol>
            <div className="course-caution"><strong>Common mistake</strong><p>{lesson.caution}</p></div>
          </section>
        </div>

        <section className="scenario-lab">
          <div className="scenario-lab-header">
            <div><span className="section-kicker">Scenario lab</span><h3>Same metric, different context</h3></div>
            <div className="scenario-tabs">
              {(Object.keys(scenarioLabels) as Scenario[]).map((key) => (
                <button className={scenario === key ? "is-active" : ""} type="button" onClick={() => setScenario(key)} key={key}>{scenarioLabels[key]}</button>
              ))}
            </div>
          </div>
          <div className={`scenario-example scenario-example-${scenario}`}>
            <div><span>Observation</span><strong>{lesson.scenarios[scenario].title}</strong><p>{lesson.scenarios[scenario].observation}</p></div>
            <ArrowRight size={24} />
            <div><span>Decision context</span><strong>What it means</strong><p>{lesson.scenarios[scenario].context}</p></div>
          </div>
        </section>

        <footer className="context-chain">
          <span>Metric</span><ArrowRight size={14} /><span>Compare window</span><ArrowRight size={14} /><span>Confirm with another family</span><ArrowRight size={14} /><strong>Conditional context</strong>
        </footer>
      </article>
    </section>
  );
}
