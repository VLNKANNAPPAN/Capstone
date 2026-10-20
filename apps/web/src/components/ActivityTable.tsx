import { ArrowDownToLine } from "lucide-react";
import { formatDateTime, label } from "../format";
import type { RunSummary } from "../types";

interface ActivityTableProps {
  runs: RunSummary[];
}

export function ActivityTable({ runs }: ActivityTableProps) {
  return (
    <section className="panel activity-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Acquisition audit</span>
          <h2>Recent ingestion runs</h2>
        </div>
        <ArrowDownToLine size={20} />
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Dataset</th>
              <th>Partition</th>
              <th>Accepted</th>
              <th>Rejected</th>
              <th>Started</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id}>
                <td className="table-strong">{run.source.toUpperCase()}</td>
                <td>{label(run.dataset)}</td>
                <td><code>{run.partition_key}</code></td>
                <td>{run.accepted_count.toLocaleString()}</td>
                <td className={run.rejected_count > 0 ? "text-warning" : ""}>
                  {run.rejected_count.toLocaleString()}
                </td>
                <td>{formatDateTime(run.started_at)}</td>
                <td><span className={`run-badge run-${run.status}`}>{run.status}</span></td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={7} className="table-empty">No ingestion runs recorded.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

