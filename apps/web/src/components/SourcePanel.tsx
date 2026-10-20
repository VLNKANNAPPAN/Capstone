import { Cable, CircleCheck, Clock3, DatabaseZap } from "lucide-react";
import { label, relativeTime } from "../format";
import type { SourceSummary } from "../types";

interface SourcePanelProps {
  sources: SourceSummary[];
}

export function SourcePanel({ sources }: SourcePanelProps) {
  return (
    <section className="panel source-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Provider health</span>
          <h2>Data sources</h2>
        </div>
        <Cable size={20} />
      </div>

      <div className="source-list">
        {sources.map((source) => (
          <article className="source-row" key={`${source.source}-${source.dataset}`}>
            <div className="source-glyph">
              <DatabaseZap size={18} />
            </div>
            <div className="source-main">
              <strong>{source.source.toUpperCase()}</strong>
              <span>{label(source.dataset)}</span>
            </div>
            <div className="source-meta">
              <strong>{source.record_count.toLocaleString()}</strong>
              <span>
                <Clock3 size={12} /> {relativeTime(source.latest_ingested_at)}
              </span>
            </div>
            <div className={`status-dot status-${source.latest_run_status ?? "waiting"}`}>
              <CircleCheck size={13} />
              {source.latest_run_status ?? "waiting"}
            </div>
          </article>
        ))}
        {sources.length === 0 && (
          <div className="compact-empty">
            <Cable size={22} />
            <p>No provider batches have completed yet.</p>
          </div>
        )}
      </div>
    </section>
  );
}

