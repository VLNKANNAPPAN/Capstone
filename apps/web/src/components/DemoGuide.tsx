import { Activity, Gauge, ShieldAlert, TrendingUp } from "lucide-react";

const lessons = [
  { icon: TrendingUp, title: "60-day return", meaning: "How much the price changed over roughly three months.", read: "Positive means the recent direction was upward; it does not predict the next move." },
  { icon: Gauge, title: "RSI", meaning: "Compares recent gains with recent losses on a 0–100 scale.", read: "Above 70 can be stretched; below 30 can be heavily sold. Always confirm with trend." },
  { icon: Activity, title: "Sharpe ratio", meaning: "Return earned relative to total price variability.", read: "A higher value is usually preferable, but the observation window and risk-free rate matter." },
  { icon: ShieldAlert, title: "Maximum drawdown", meaning: "The worst peak-to-trough fall in the observed period.", read: "It turns risk into an intuitive question: could you tolerate that historical decline?" },
];

export function DemoGuide() {
  return <div className="demo-guide">
    <section className="demo-guide-flow panel"><div><span>1</span><strong>Observe</strong><p>Start with price history.</p></div><div><span>2</span><strong>Measure</strong><p>Calculate comparable metrics.</p></div><div><span>3</span><strong>Combine</strong><p>Use several signals together.</p></div><div><span>4</span><strong>Decide carefully</strong><p>Keep uncertainty visible.</p></div></section>
    <section className="demo-lesson-grid">{lessons.map(({ icon: Icon, title, meaning, read }) => <article className="panel" key={title}><Icon size={21} /><span className="section-kicker">Core metric</span><h3>{title}</h3><p>{meaning}</p><div><strong>How to read it</strong><p>{read}</p></div></article>)}</section>
    <section className="demo-boundary"><strong>What this demo intentionally leaves for later</strong><p>Live execution, multi-agent debate, advanced filing replay, bond analytics and social-media ingestion remain in the full research branch—not in this presentation build.</p></section>
  </div>;
}
