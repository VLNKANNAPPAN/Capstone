import { ExternalLink, FileText } from "lucide-react";
import { formatDateTime } from "../format";
import type { FilingSummary } from "../types";

interface FilingListProps {
  filings: FilingSummary[];
}

export function FilingList({ filings }: FilingListProps) {
  return (
    <section className="panel filing-panel">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">Supplementary evidence</span>
          <h2>Other regulatory filings</h2>
        </div>
        <FileText size={20} />
      </div>
      <div className="filing-list">
        {filings.map((filing) => (
          <a
            className="filing-row"
            href={filing.source_url}
            target="_blank"
            rel="noreferrer"
            key={filing.accession_number}
          >
            <span className="form-chip">{filing.form}</span>
            <div>
              <strong>{filing.symbol}</strong>
              <span>Available {formatDateTime(filing.available_at)}</span>
            </div>
            <ExternalLink size={15} />
          </a>
        ))}
        {filings.length === 0 && (
          <div className="compact-empty">
            <FileText size={22} />
            <p>No additional filing metadata. Indian XBRL facts appear above.</p>
          </div>
        )}
      </div>
    </section>
  );
}
