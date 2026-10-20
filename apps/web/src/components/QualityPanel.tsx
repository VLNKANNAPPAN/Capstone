import { CheckCircle2, ShieldAlert } from "lucide-react";
import { formatDateTime, label } from "../format";
import type { QualityIssueSummary } from "../types";

interface QualityPanelProps {
  issues: QualityIssueSummary[];
}

export function QualityPanel({ issues }: QualityPanelProps) {
  return (
    <section className="panel quality-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Validation queue</span>
          <h2>Data quality</h2>
        </div>
        <ShieldAlert size={20} />
      </div>
      {issues.length === 0 ? (
        <div className="quality-clear">
          <CheckCircle2 size={30} />
          <div>
            <strong>No quarantined records</strong>
            <p>Validation has not detected malformed records.</p>
          </div>
        </div>
      ) : (
        <div className="issue-list">
          {issues.map((issue) => (
            <article key={issue.issue_id} className="issue-row">
              <span className={`severity severity-${issue.severity}`}>{issue.severity}</span>
              <div>
                <strong>{label(issue.code)}</strong>
                <p>{issue.message}</p>
                <small>{issue.source} · {issue.partition_key} · {formatDateTime(issue.detected_at)}</small>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

