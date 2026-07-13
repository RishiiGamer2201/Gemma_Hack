import { useState } from "react";

import type { Facts, MissingQuestion, RouteResponse } from "../api/types";
import {
  DOMAIN_OPTIONS,
  describeDocumentWarning,
  describeRoleSignal,
} from "../api/types";

/**
 * The backend asks for `legal_domain` and `incident_date` by name. Both are typed
 * fields, not free text: `domain` is a closed enum (free text would be rejected as a
 * 422) and `incident_date` must be an ISO date. Render the right control for each.
 */
export const DOMAIN_FACT_KEYS = new Set(["legal_domain", "domain"]);
export const DATE_FACT_KEYS = new Set(["incident_date"]);
import { ErrorNotice } from "./Feedback";
import { LegalAidPanel } from "./LegalAidPanel";

/**
 * priority === "immediate_human_help".
 * Rendered ABOVE everything else. No ordinary legal content is shown alongside it.
 */
export function UrgentSafetyPanel({
  route,
  facts,
  onRestart,
}: {
  route: RouteResponse;
  facts: Facts;
  onRestart: () => void;
}) {
  return (
    <section className="urgent-panel" role="alert" aria-labelledby="urgent-heading">
      <h2 id="urgent-heading">Please get human help first</h2>
      <p style={{ fontWeight: 600 }}>
        Based on what you confirmed, this situation needs a person, not a
        document search. General legal explanation is being held back on purpose
        so it does not delay you.
      </p>

      {route.protective_prompts.length > 0 ? (
        <ul>
          {route.protective_prompts.map((prompt) => (
            <li key={prompt}>{prompt}</li>
          ))}
        </ul>
      ) : null}

      {/*
        Every contact shown to a user in danger is served by the API from the
        verified offline directory, with an official URL and a last-verified date.
        Helpline numbers are deliberately NOT hardcoded here. An earlier revision
        of this panel listed numbers recalled from model memory rather than from a
        receipted source, which is precisely the fabrication this project exists to
        prevent -- and the urgent panel is the worst possible place to get a phone
        number wrong. If further emergency numbers should appear, add them to the
        reviewed directory with a source and verified date; do not retype them here.
      */}
      <div className="alert alert-danger" style={{ background: "#fff" }}>
        <h3>If you are in immediate physical danger</h3>
        <p style={{ marginBottom: 0 }}>
          Contact your local emergency services or the police immediately, or
          reach someone you trust who can be with you. Do this before reading any
          legal information. The verified legal-aid contacts below can help
          afterwards, but they are not an emergency service.
        </p>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <LegalAidPanel
          bare
          heading="Free legal aid near you"
          initialDistrict={facts.location ?? ""}
          initialState={facts.jurisdiction ?? ""}
          autoSearch={Boolean(facts.location)}
        />
      </div>

      {route.terminal_reason ? (
        <p className="card-subtle" style={{ marginTop: 12 }}>
          Reason recorded: {route.terminal_reason}
        </p>
      ) : null}

      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" className="btn-secondary" onClick={onRestart}>
          Start over with a different description
        </button>
      </div>
    </section>
  );
}

/** priority === "hard_abstain". */
export function AbstainPanel({
  route,
  onRestart,
  onEditFacts,
}: {
  route: RouteResponse;
  onRestart: () => void;
  onEditFacts: () => void;
}) {
  return (
    <section className="card" aria-labelledby="abstain-heading">
      <div className="alert alert-warn" role="alert">
        <h2 id="abstain-heading">This tool will not answer this one</h2>
        <p>
          {route.terminal_reason ??
            "The request falls outside what this prototype is allowed to answer."}
        </p>
        <p style={{ marginBottom: 0 }}>
          Refusing is deliberate. Producing a confident-sounding answer without
          official support would be worse than saying nothing.
        </p>
      </div>

      {route.document_warnings.length > 0 ? (
        <div className="warning-block">
          <strong>Warnings</strong>
          <ul>
            {route.document_warnings.map((warning) => (
              <li key={warning.pattern_name}>{describeDocumentWarning(warning)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p>
        A District Legal Services Authority or a qualified lawyer can take this
        further. The Legal Aid Finder in the side panel lists free options.
      </p>

      <div className="row row-end">
        <button type="button" className="btn-secondary" onClick={onEditFacts}>
          Correct my facts
        </button>
        <button type="button" className="btn-primary" onClick={onRestart}>
          Start over
        </button>
      </div>
    </section>
  );
}

/** priority === "needs_information". Only the missing questions are shown. */
export function NeedsInformationPanel({
  questions,
  answers,
  onAnswersChange,
  onSubmit,
  onEditFacts,
  submitting,
  error,
}: {
  questions: MissingQuestion[];
  answers: Record<string, string>;
  onAnswersChange: (answers: Record<string, string>) => void;
  onSubmit: () => void;
  onEditFacts: () => void;
  submitting: boolean;
  error: unknown;
}) {
  const answeredCount = questions.filter((q) => (answers[q.fact_key] ?? "").trim()).length;

  return (
    <section className="card" aria-labelledby="needs-heading">
      <h2 id="needs-heading">A few facts are missing</h2>
      <p>
        The law that applies depends on these. Rather than guess — which would
        produce the wrong section — the analysis is paused here. Answer what you
        can. If you genuinely do not know something, leave it blank and say so
        rather than estimating.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!submitting) {
            onSubmit();
          }
        }}
      >
        {questions.map((question) => {
          const key = question.fact_key;
          const inputId = `q-${key}`;
          const setAnswer = (value: string) =>
            onAnswersChange({ ...answers, [key]: value });

          return (
            <div className="field" key={key}>
              <label htmlFor={inputId}>{question.question}</label>

              {DOMAIN_FACT_KEYS.has(key) ? (
                <select
                  id={inputId}
                  value={answers[key] ?? ""}
                  disabled={submitting}
                  aria-describedby={`${inputId}-reason`}
                  onChange={(event) => setAnswer(event.target.value)}
                >
                  <option value="">Select…</option>
                  {DOMAIN_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : DATE_FACT_KEYS.has(key) ? (
                <input
                  id={inputId}
                  type="date"
                  value={answers[key] ?? ""}
                  disabled={submitting}
                  aria-describedby={`${inputId}-reason`}
                  onChange={(event) => setAnswer(event.target.value)}
                />
              ) : (
                <input
                  id={inputId}
                  type="text"
                  value={answers[key] ?? ""}
                  disabled={submitting}
                  aria-describedby={`${inputId}-reason`}
                  onChange={(event) => setAnswer(event.target.value)}
                />
              )}

              <p className="hint" id={`${inputId}-reason`}>
                Why this matters: {question.reason}
              </p>
            </div>
          );
        })}

        <ErrorNotice error={error} title="Could not continue" onRetry={onSubmit} />

        <div className="row row-end">
          <button
            type="button"
            className="btn-secondary"
            onClick={onEditFacts}
            disabled={submitting}
          >
            Back to the facts
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={submitting || answeredCount === 0}
          >
            Submit answers and continue
          </button>
        </div>
        {answeredCount === 0 ? (
          <p className="hint" style={{ textAlign: "right" }}>
            Answer at least one question to continue.
          </p>
        ) : null}
      </form>
    </section>
  );
}

/** Non-terminal context shown alongside a standard result. */
export function RouteContext({ route }: { route: RouteResponse }) {
  const [open, setOpen] = useState(false);
  const hasContext =
    route.role_signals.length > 0 ||
    route.protective_prompts.length > 0 ||
    route.domain;

  if (!hasContext) {
    return null;
  }

  return (
    <section className="card" aria-labelledby="route-context-heading">
      <div className="card-title">
        <h2 id="route-context-heading">How your situation was classified</h2>
        <button
          type="button"
          className="btn-link btn-small"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide details" : "Show details"}
        </button>
      </div>

      <div className="status-strip">
        {route.domain ? (
          <span className="badge">Area of law: {route.domain}</span>
        ) : null}
        {route.role_signals.map((signal) => (
          <span className="badge" key={signal.relationship}>
            {describeRoleSignal(signal)}
          </span>
        ))}
      </div>

      {/* Document warnings are never hidden behind the toggle. */}
      {route.document_warnings.length > 0 ? (
        <div className="warning-block" style={{ marginTop: 12 }} role="alert">
          <strong>Document warnings</strong>
          <ul>
            {route.document_warnings.map((warning) => (
              <li key={warning.pattern_name}>{describeDocumentWarning(warning)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {open && route.protective_prompts.length > 0 ? (
        <div className="alert alert-info" style={{ marginTop: 12 }}>
          <h3>Points to keep in mind</h3>
          <ul>
            {route.protective_prompts.map((prompt) => (
              <li key={prompt}>{prompt}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
