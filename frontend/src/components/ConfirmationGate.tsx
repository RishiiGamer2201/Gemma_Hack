import { useMemo, useState } from "react";

import { DEFAULT_DOMAIN, DOMAIN_OPTIONS } from "../api/types";
import type { Facts, IntakeResponse, UrgencySignal } from "../api/types";
import { ErrorNotice, Progress } from "./Feedback";
import { ListEditor } from "./ListEditor";

interface Props {
  intake: IntakeResponse;
  facts: Facts;
  onFactsChange: (facts: Facts) => void;
  confirmedUrgencies: string[];
  onUrgenciesChange: (categories: string[]) => void;
  onConfirm: () => void;
  onEditText: () => void;
  submitting: boolean;
  error: unknown;
}

function urgencyKey(signal: UrgencySignal): string {
  return signal.category;
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/**
 * HARD GATE. Retrieval, routing, and any personalised legal information are blocked
 * until the user explicitly confirms these facts. Urgency signals are proposals only:
 * they are never auto-applied — the user must tick them.
 */
export function ConfirmationGate({
  intake,
  facts,
  onFactsChange,
  confirmedUrgencies,
  onUrgenciesChange,
  onConfirm,
  onEditText,
  submitting,
  error,
}: Props) {
  const [acknowledged, setAcknowledged] = useState(false);

  const uniqueSignals = useMemo(() => {
    const seen = new Set<string>();
    return intake.urgency_signals.filter((signal) => {
      const key = urgencyKey(signal);
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }, [intake.urgency_signals]);

  function patch(update: Partial<Facts>) {
    onFactsChange({ ...facts, ...update });
  }

  const summaryMissing = facts.incident_summary.trim().length === 0;
  const canConfirm = acknowledged && !summaryMissing && !submitting;

  return (
    <section className="card" aria-labelledby="confirm-heading">
      <div className="card-title">
        <h2 id="confirm-heading">Step 3 of 4 — Confirm the facts</h2>
        <span className="badge badge-warn">Nothing proceeds without your confirmation</span>
      </div>

      <p>
        This is what was understood from your description. Everything below is
        editable. <strong>Nothing is retrieved, analysed, or explained until you
        confirm it is correct.</strong> Wrong facts produce wrong law.
      </p>

      <div className="alert alert-info">
        <h3>Restatement</h3>
        <p style={{ marginBottom: 0 }}>{intake.restatement || "(none returned)"}</p>
        <p className="card-subtle" style={{ marginTop: 8, marginBottom: 0 }}>
          Detected language: <strong>{intake.language.language}</strong> (
          {intake.language.devanagari_letters} Devanagari /{" "}
          {intake.language.latin_letters} Latin letters,{" "}
          {intake.language.romanized_hindi_markers} Hinglish markers)
        </p>
      </div>

      {uniqueSignals.length > 0 ? (
        <fieldset
          style={{
            border: "2px solid var(--danger-line)",
            borderRadius: "var(--radius)",
            padding: "12px 14px",
            margin: "0 0 16px",
            background: "var(--danger-tint)",
          }}
        >
          <legend style={{ fontWeight: 700, color: "var(--danger)", padding: "0 6px" }}>
            Possible urgent situation — please confirm
          </legend>
          <p style={{ color: "var(--danger)" }}>
            These phrases were spotted in your description. They have{" "}
            <strong>not</strong> been assumed to be true. Tick only what actually
            applies to you. Ticking one may route you to human help before any
            legal explanation.
          </p>
          {uniqueSignals.map((signal) => {
            const key = urgencyKey(signal);
            const checked = confirmedUrgencies.includes(key);
            return (
              <div className="checkbox-row urgency" key={key}>
                <input
                  type="checkbox"
                  id={`urgency-${key}`}
                  checked={checked}
                  disabled={submitting}
                  onChange={(event) => {
                    onUrgenciesChange(
                      event.target.checked
                        ? [...confirmedUrgencies, key]
                        : confirmedUrgencies.filter((c) => c !== key),
                    );
                  }}
                />
                <label htmlFor={`urgency-${key}`}>
                  <strong>{humanizeKey(signal.category)}</strong>
                  <br />
                  <span className="card-subtle">
                    matched the words “{signal.matched_phrase}”
                  </span>
                </label>
              </div>
            );
          })}
        </fieldset>
      ) : null}

      <h3>Extracted facts</h3>

      <div className="field">
        <label htmlFor="fact-summary">What happened (summary)</label>
        <textarea
          id="fact-summary"
          value={facts.incident_summary}
          rows={4}
          disabled={submitting}
          onChange={(event) => patch({ incident_summary: event.target.value })}
          aria-invalid={summaryMissing}
        />
        {summaryMissing ? (
          <p className="hint" style={{ color: "var(--danger)" }}>
            A summary is required before you can confirm.
          </p>
        ) : null}
      </div>

      <div className="grid-2">
        <div className="field">
          <label htmlFor="fact-date">Incident date</label>
          <input
            id="fact-date"
            type="date"
            value={facts.incident_date ?? ""}
            disabled={submitting}
            onChange={(event) =>
              patch({ incident_date: event.target.value || null })
            }
          />
          <p className="hint">
            The date decides which law applies (for example IPC vs BNS). Leave
            blank if you are unsure — do not guess.
          </p>
        </div>

        <div className="field">
          <label htmlFor="fact-jurisdiction">Jurisdiction (state / UT)</label>
          <input
            id="fact-jurisdiction"
            type="text"
            value={facts.jurisdiction ?? ""}
            placeholder="e.g. Delhi"
            disabled={submitting}
            onChange={(event) =>
              patch({ jurisdiction: event.target.value || null })
            }
          />
        </div>

        <div className="field">
          <label htmlFor="fact-location">Location (district / city)</label>
          <input
            id="fact-location"
            type="text"
            value={facts.location ?? ""}
            placeholder="e.g. New Delhi"
            disabled={submitting}
            onChange={(event) => patch({ location: event.target.value || null })}
          />
        </div>

        <div className="field">
          <label htmlFor="fact-domain">Area of law</label>
          <select
            id="fact-domain"
            value={facts.domain ?? DEFAULT_DOMAIN}
            disabled={submitting}
            onChange={(event) => patch({ domain: event.target.value })}
          >
            {DOMAIN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="hint">
            If this was guessed wrong, correct it. The area of law decides which
            statutes are searched.
          </p>
        </div>
      </div>

      <ListEditor
        id="parties"
        label="People and organisations involved"
        hint="Use roles rather than full names where you can (e.g. “employer”, “landlord”)."
        placeholder="e.g. Employer"
        values={facts.parties}
        disabled={submitting}
        onChange={(parties) => patch({ parties })}
      />

      <ListEditor
        id="material-facts"
        label="Material facts"
        hint="The specific things that happened, with amounts and dates where known."
        placeholder="e.g. Salary of ₹18,000 unpaid since April 2026"
        values={facts.material_facts}
        disabled={submitting}
        onChange={(material_facts) => patch({ material_facts })}
      />

      <ListEditor
        id="documents"
        label="Documents you have"
        placeholder="e.g. Appointment letter"
        values={facts.documents}
        disabled={submitting}
        onChange={(documents) => patch({ documents })}
      />

      {facts.missing_material_facts.length > 0 ? (
        <div className="alert alert-warn">
          <h3>Still missing</h3>
          <p>
            These were not found in your description. Add them above if you know
            them — they may be needed to answer properly.
          </p>
          <ul>
            {facts.missing_material_facts.map((item) => (
              <li key={item}>{humanizeKey(item)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <hr className="divider" />

      <ErrorNotice error={error} title="Could not continue" onRetry={onConfirm} />

      {submitting ? (
        <Progress
          label="Checking safety and routing…"
          detail="Running locally on your confirmed facts"
        />
      ) : null}

      <div className="checkbox-row">
        <input
          type="checkbox"
          id="ack"
          checked={acknowledged}
          disabled={submitting}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        <label htmlFor="ack">
          I have read the facts above and they are correct. I understand this
          tool gives legal information, not legal advice.
        </label>
      </div>

      <div className="row row-end">
        <button
          type="button"
          className="btn-secondary"
          onClick={onEditText}
          disabled={submitting}
        >
          Go back and rewrite my description
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={onConfirm}
          disabled={!canConfirm}
        >
          Yes, this is correct — continue
        </button>
      </div>
      {!acknowledged ? (
        <p className="hint" style={{ textAlign: "right" }}>
          Tick the box above to enable this button.
        </p>
      ) : null}
    </section>
  );
}
