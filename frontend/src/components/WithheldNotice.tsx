import type { AnswerResponse } from "../api/types";

/**
 * published === false means the answer was WITHHELD ON PURPOSE. `answer` and `claims`
 * are empty by design in that case.
 *
 * There is deliberately no fallback that renders the raw `evidence` as though it were
 * an answer: unreviewed statute text presented to someone in a crisis, with no verified
 * reasoning attached, is exactly the failure mode this gate exists to prevent.
 */
export function WithheldNotice({ result }: { result: AnswerResponse }) {
  const { route } = result;

  let reason: string;
  if (route.priority === "immediate_human_help") {
    reason =
      "This situation needs a person, not a document search. The legal explanation is being held back so it does not delay you getting help.";
  } else if (route.priority === "hard_abstain") {
    reason =
      "This request falls outside what this prototype is allowed to answer, so nothing is being shown.";
  } else if (route.priority === "needs_information") {
    reason =
      "Some facts are still missing. Answering without them would produce the wrong law, so the answer is paused rather than guessed.";
  } else {
    reason =
      "A statement in the draft answer could not be supported by the official sources retrieved. Rather than show you something unverified, the whole answer was withheld.";
  }

  return (
    <section className="card" aria-labelledby="withheld-heading">
      <div className="alert alert-warn" role="alert" style={{ marginBottom: 0 }}>
        <h2 id="withheld-heading">No answer is being shown</h2>
        <p>{reason}</p>
        {route.terminal_reason ? (
          <p>
            <strong>Reason recorded: </strong>
            {route.terminal_reason}
          </p>
        ) : null}
        <p style={{ marginBottom: 0 }}>
          This is a deliberate outcome, not a failure. An answer that cannot be traced
          back to official text is worse than no answer.
        </p>
      </div>

      {result.warnings.length > 0 ? (
        <div className="warning-block" style={{ marginTop: 12 }} role="alert">
          <strong>Warnings recorded during this attempt</strong>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="card-subtle" style={{ marginTop: 12 }}>
        Pipeline stage: <span className="mono">{result.stage}</span>
      </p>
    </section>
  );
}
