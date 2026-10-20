import { ExternalLink, MessageSquareText } from "lucide-react";
import { formatDateTime } from "../format";
import type { ContentSummary } from "../types";

interface ContentPanelProps {
  items: ContentSummary[];
  newsCount: number;
  socialCount: number;
}

export function ContentPanel({ items, newsCount, socialCount }: ContentPanelProps) {
  return (
    <section className="panel content-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Unstructured evidence</span>
          <h2>News and social</h2>
        </div>
        <MessageSquareText size={20} />
      </div>
      <div className="content-counts">
        <div><span>News</span><strong>{newsCount.toLocaleString()}</strong></div>
        <div><span>Social</span><strong>{socialCount.toLocaleString()}</strong></div>
      </div>
      <div className="content-list">
        {items.map((item) => (
          <a className="content-row" href={item.url} target="_blank" rel="noreferrer" key={`${item.source}:${item.external_id}`}>
            <div>
              <span>{item.source} · {item.symbols.join(", ") || "Market"}</span>
              <strong>{item.title}</strong>
              <small>{formatDateTime(item.published_at)}</small>
            </div>
            <ExternalLink size={14} />
          </a>
        ))}
        {items.length === 0 && (
          <div className="compact-empty content-empty">
            <MessageSquareText size={22} />
            <p>GDELT news is ready to ingest. Social connectors remain credential-gated.</p>
          </div>
        )}
      </div>
    </section>
  );
}
