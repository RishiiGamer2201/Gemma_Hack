import { useCallback, useMemo, useState } from "react";

import type {
  AnswerResponse,
  ClaimVerdict,
  ClaimView,
  ConfirmedFacts,
  EvidenceItem,
  Facts,
} from "../api/types";
import { DevilsAdvocate } from "./DevilsAdvocate";
import { Empty } from "./Feedback";
import { EvidenceCard, evidenceDomId } from "./EvidenceCard";
import { RightsCard } from "./RightsCard";

const VERDICT_META: Record<
  ClaimVerdict,
  { label: string; badge: string; explanation: string }
> = {
  supported: {
    label: "Supported",
    badge: "badge badge-ok",
    explanation:
      "The verifier found this statement backed by the cited official text.",
  },
  contradicted: {
    label: "Contradicted",
    badge: "badge badge-danger",
    explanation:
      "The cited official text does not agree with this statement. Do not rely on it.",
  },
  insufficient: {
    label: "Not enough support",
    badge: "badge badge-warn",
    explanation:
      "The sources retrieved do not settle this statement either way. Treat it as unverified.",
  },
};

/**
 * A section of the structured answer. An empty list is a real, meaningful result:
 * it means the sources say nothing on the point. We say so, rather than hiding the
 * section (which would obscure the gap) or filling it (which would fabricate).
 */
function AnswerSection({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: string[];
  emptyText: string;
}) {
  return (
    <section style={{ marginBottom: 18 }}>
      <h3>{title}</h3>
      {items.length === 0 ? (
        <Empty>{emptyText}</Empty>
      ) : (
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          {items.map((item, index) => (
            <li key={`${title}-${index}`} style={{ marginBottom: 4 }}>
              {item}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

interface Props {
  result: AnswerResponse;
  facts: Facts;
  confirmedFacts: ConfirmedFacts | null;
  onEditFacts: () => void;
  onRestart: () => void;
}

export function AnswerView({
  result,
  facts,
  confirmedFacts,
  onEditFacts,
  onRestart,
}: Props) {
  const [openSources, setOpenSources] = useState<Set<string>>(new Set());
  const [highlighted, setHighlighted] = useState<string | null>(null);

  const evidenceById = useMemo(() => {
    const map = new Map<string, { item: EvidenceItem; index: number }>();
    result.evidence.forEach((item, index) => map.set(item.source_id, { item, index }));
    return map;
  }, [result.evidence]);

  const toggleSource = useCallback((sourceId: string) => {
    setOpenSources((current) => {
      const next = new Set(current);
      if (next.has(sourceId)) {
        next.delete(sourceId);
      } else {
        next.add(sourceId);
      }
      return next;
    });
  }, []);

  /** Follow a claim's citation to the evidence card it rests on. */
  const revealSource = useCallback((sourceId: string) => {
    setOpenSources((current) => new Set(current).add(sourceId));
    setHighlighted(sourceId);
    window.requestAnimationFrame(() => {
      document
        .getElementById(evidenceDomId(sourceId))
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, []);

  const answer = result.answer;

  const verdictCounts = useMemo(() => {
    const counts: Record<ClaimVerdict, number> = {
      supported: 0,
      contradicted: 0,
      insufficient: 0,
    };
    result.claims.forEach((claim) => {
      counts[claim.verdict] += 1;
    });
    return counts;
  }, [result.claims]);

  return (
    <div className="stack">
      {/* Warnings stay pinned at the top, permanently expanded. */}
      {result.warnings.length > 0 ? (
        <div className="warning-block" role="alert">
          <strong>Important limitations on everything below</strong>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="card" aria-labelledby="answer-heading">
        <div className="card-title">
          <h2 id="answer-heading">Your situation and the law</h2>
          <span className="badge badge-ok">Every claim verified against sources</span>
        </div>

        <div className="alert alert-info">
          <p style={{ marginBottom: 0 }}>
            <strong>Situation:</strong>{" "}
            {answer?.situation || facts.incident_summary || "(not stated)"}
          </p>
        </div>

        {answer ? (
          <>
            <AnswerSection
              title="Applicable law"
              items={answer.applicable_law}
              emptyText="The retrieved sources do not identify a specific provision for this situation."
            />
            <AnswerSection
              title="Your rights"
              items={answer.rights}
              emptyText="The sources retrieved do not state a specific right for this situation."
            />
            <AnswerSection
              title="Your options"
              items={answer.options}
              emptyText="The sources retrieved do not set out a specific route to take."
            />
            <AnswerSection
              title="Evidence to preserve"
              items={answer.evidence_to_preserve}
              emptyText="The sources do not specify particular evidence. The Evidence Checklist in the side panel still applies."
            />
            <AnswerSection
              title="Deadlines"
              items={answer.deadlines}
              emptyText="The sources do not state a deadline. That is not the same as there being none — check with a lawyer or your DLSA before assuming you have time."
            />
            <AnswerSection
              title="What happens if you do nothing"
              items={answer.consequences_of_inaction}
              emptyText="The sources do not state a consequence of inaction."
            />
            <AnswerSection
              title="Next steps"
              items={answer.next_steps}
              emptyText="The sources do not set out specific next steps."
            />
            <AnswerSection
              title="Limitations of this answer"
              items={answer.limitations}
              emptyText="No additional limitations were recorded beyond the standing ones above."
            />
          </>
        ) : (
          <Empty>No structured answer was returned.</Empty>
        )}
      </section>

      {/* The verifier trace: the explainability story. */}
      <section className="card" aria-labelledby="verifier-heading">
        <div className="card-title">
          <h2 id="verifier-heading">How each statement was checked</h2>
          <div className="status-strip">
            <span className="badge badge-ok">{verdictCounts.supported} supported</span>
            {verdictCounts.insufficient > 0 ? (
              <span className="badge badge-warn">
                {verdictCounts.insufficient} unverified
              </span>
            ) : null}
            {verdictCounts.contradicted > 0 ? (
              <span className="badge badge-danger">
                {verdictCounts.contradicted} contradicted
              </span>
            ) : null}
          </div>
        </div>

        <p className="card-subtle">
          After drafting the answer, a separate pass re-read every statement in it
          against the retrieved official text. Nothing below is taken on trust from
          the model. Follow a citation to read the exact words it rests on.
        </p>

        {result.claims.length === 0 ? (
          <Empty>No individual claims were recorded for this answer.</Empty>
        ) : (
          result.claims.map((claim) => (
            <ClaimRow
              key={claim.claim_id}
              claim={claim}
              evidenceById={evidenceById}
              onReveal={revealSource}
            />
          ))
        )}
      </section>

      <section className="card" aria-labelledby="sources-heading">
        <div className="card-title">
          <h2 id="sources-heading">Official sources</h2>
          <span className="badge">Verbatim text only</span>
        </div>

        {result.query ? (
          <p className="hint">
            Retrieval query used: <span className="mono">{result.query}</span>
          </p>
        ) : null}

        {result.evidence.length === 0 ? (
          <Empty>No official source was retrieved.</Empty>
        ) : (
          result.evidence.map((item, index) => (
            <EvidenceCard
              key={item.source_id}
              item={item}
              index={index}
              open={openSources.has(item.source_id)}
              highlighted={highlighted === item.source_id}
              onToggle={() => toggleSource(item.source_id)}
            />
          ))
        )}

        <hr className="divider" />
        <p className="card-subtle">
          This is legal information drawn from official text — not legal advice, and
          not a prediction of what will happen in your case.
        </p>

        <div className="row row-end">
          <button type="button" className="btn-secondary" onClick={onEditFacts}>
            Correct my facts
          </button>
          <button type="button" className="btn-primary" onClick={onRestart}>
            Start a new question
          </button>
        </div>
      </section>

      {/*
        Optional actions on a verified answer. Both run only because the answer
        published, and both re-ground on the same confirmed facts, so neither can
        assert anything the verified answer did not.
      */}
      {confirmedFacts ? (
        <>
          <DevilsAdvocate facts={confirmedFacts} approvedProfiles={[]} />
          <RightsCard facts={confirmedFacts} approvedProfiles={[]} />
        </>
      ) : null}
    </div>
  );
}

function ClaimRow({
  claim,
  evidenceById,
  onReveal,
}: {
  claim: ClaimView;
  evidenceById: Map<string, { item: EvidenceItem; index: number }>;
  onReveal: (sourceId: string) => void;
}) {
  const meta = VERDICT_META[claim.verdict];
  // Prefer the sources the verifier actually used; fall back to what the draft cited.
  const sourceIds =
    claim.evidence_source_ids.length > 0
      ? claim.evidence_source_ids
      : claim.cited_source_ids;

  return (
    <div
      className="claim-row"
      data-verdict={claim.verdict}
    >
      <div className="claim-head">
        <span className={meta.badge}>{meta.label}</span>
        <p className="claim-text">{claim.text}</p>
      </div>

      <p className="claim-reason">
        <strong>Why: </strong>
        {claim.verdict_reason || meta.explanation}
      </p>

      {sourceIds.length === 0 ? (
        <p className="hint">
          No source is attached to this statement, so it could not be checked.
        </p>
      ) : (
        <div className="row" style={{ gap: 6 }}>
          <span className="hint" style={{ margin: 0 }}>
            Rests on:
          </span>
          {sourceIds.map((sourceId) => {
            const found = evidenceById.get(sourceId);
            if (!found) {
              return (
                <span className="pill" key={sourceId} title={sourceId}>
                  {sourceId} (not in the returned sources)
                </span>
              );
            }
            const { item, index } = found;
            return (
              <button
                type="button"
                className="pill pill-link"
                key={sourceId}
                onClick={() => onReveal(sourceId)}
              >
                Source {index + 1}: {item.act}
                {item.section ? ` s.${item.section}` : ""}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
