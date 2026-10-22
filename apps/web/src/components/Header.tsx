import { Database, RefreshCw } from "lucide-react";
import { formatDateTime } from "../format";

interface HeaderProps {
  connected: boolean;
  refreshing: boolean;
  generatedAt: string | null;
  onRefresh: () => void;
  currentPage: string;
}

const pages = [
  ["overview", "Home"],
  ["research", "Explore"],
  ["portfolio", "Portfolio"],
  ["learn", "Learn"],
  ["pipeline", "Data status"],
];

export function Header({ connected, refreshing, generatedAt, onRefresh, currentPage }: HeaderProps) {
  return (
    <header className="floating-nav">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          <Database size={18} />
        </div>
        <div>
          <div className="eyebrow">MarketLab · Demo</div>
          <h1>Data. Metrics. Decisions.</h1>
        </div>
      </div>

      <nav className="section-nav" aria-label="Dashboard sections">
        {pages.map(([path, label]) => (
          <a className={currentPage === path ? "is-active" : ""} href={`#/${path}`} key={path}>{label}</a>
        ))}
      </nav>

      <div className="topbar-actions">
        <div className={`connection-state ${connected ? "is-live" : "is-offline"}`}>
          <span className="pulse" />
          <div>
            <strong>{connected ? "Live polling" : "API unavailable"}</strong>
            <small>{generatedAt ? `Updated ${formatDateTime(generatedAt)}` : "Connecting"}</small>
          </div>
        </div>
        <button className="icon-button" onClick={onRefresh} type="button" aria-label="Refresh data">
          <RefreshCw className={refreshing ? "spin" : ""} size={18} />
        </button>
      </div>
    </header>
  );
}
