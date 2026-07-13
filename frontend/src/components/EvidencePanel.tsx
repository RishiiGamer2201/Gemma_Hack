import type { EvidenceResponse, Facts } from "../api/types";
import { Empty, ErrorNotice, Progress } from "./Feedback";
import { EvidenceCard } from "./EvidenceCard";

interface Props {
  facts: Facts;
  evidence: EvidenceResponse | null;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  onEditFacts: () => void;
  onRestart: () => void;
}

export function EvidencePanel({
  facts,
  evidence,
  loading,
  error,
  onRetry,
  onEditFacts,
  onRestart,
}: Props) {
  return (
    <section className="card" aria-labelledby="evidence-heading">
      <div className="card-title">
        <h2 id="evidence-heading">Official law that may apply</h2>
        <span className="badge">Verbatim sources only</span>
      </div>

      {/*
        Warnings are rendered first, always expanded, never a toast.
        They carry things like "commencement date not proven".
      */}
      {evidence && evidence.warnings.length > 0 ? (
        <div className="warning-block" role="alert" aria-live="polite">
          <strong>Important limitations on the sources below</strong>
          <ul>
            {evidence.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="alert alert-info">
        <p style={{ marginBottom: 0 }}>
          <strong>Situation:</strong> {facts.incident_summary || "(not stated)"}
        </p>
        <p className="card-subtle" style={{ margin: "6px 0 0" }}>
          {facts.incident_date
            ? `Incident date ${facts.incident_date} — this determines which version of the law applies.`
            : "No incident date confirmed. Where a law changed (for example IPC to BNS), the correct version cannot be determined without one."}
        </p>
      </div>

      {loading ? (
        <Progress
          label="Retrieving official sources…"
          detail="Searching the offline corpus on this machine"
        />
      ) : null}

      <ErrorNotice error={error} title="Retrieval failed" onRetry={onRetry} />

      {evidence ? (
        <>
          {evidence.query ? (
            <p className="hint">
              Retrieval query used: <span className="mono">{evidence.query}</span>
            </p>
          ) : null}

          {evidence.evidence.length === 0 ? (
            <Empty>
              No official source in the offline corpus matched these facts. That
              is a real answer, not a failure: nothing will be made up to fill
              the gap. Try correcting the facts, or use the Legal Aid Finder.
            </Empty>
          ) : (
            <>
              <p className="card-subtle">
                {evidence.evidence.length} source
                {evidence.evidence.length === 1 ? "" : "s"} found. Expand a card
                to read the exact text, its effective date, and the official
                link. Read the law itself — do not rely on a summary.
              </p>
              {evidence.evidence.map((item, index) => (
                <EvidenceCard
                  key={`${item.source_id}-${index}`}
                  item={item}
                  index={index}
                  defaultOpen={index === 0}
                />
              ))}
            </>
          )}
        </>
      ) : null}

      <hr className="divider" />

      <p className="card-subtle">
        These excerpts are what the official text says. They are not a prediction
        of what will happen in your case, and they are not legal advice. Use the
        Evidence Checklist to prepare, and the Legal Aid Finder to reach a
        person.
      </p>

      <div className="row row-end">
        <button type="button" className="btn-secondary" onClick={onEditFacts}>
          Correct my facts
        </button>
        <button type="button" className="btn-secondary" onClick={onRetry} disabled={loading}>
          Search again
        </button>
        <button type="button" className="btn-primary" onClick={onRestart}>
          Start a new question
        </button>
      </div>
    </section>
  );
}
