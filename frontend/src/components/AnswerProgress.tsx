import { useEffect, useState } from "react";

/**
 * /api/answer runs several sequential local model calls and takes 30-120s. It does
 * NOT stream, so the backend gives us no true progress events.
 *
 * We therefore show the pipeline's stages and mark the one it is *expected* to be in,
 * based on elapsed time. The label says so explicitly: inventing a precise percentage
 * would be exactly the kind of false confidence this project refuses to produce
 * elsewhere, and it would be just as dishonest here.
 */
const STAGES: Array<{ label: string; startsAt: number }> = [
  { label: "Checking safety routing", startsAt: 0 },
  { label: "Retrieving official law", startsAt: 4 },
  { label: "Drafting a grounded answer", startsAt: 20 },
  { label: "Verifying every claim against the sources", startsAt: 55 },
];

export function AnswerProgress({ onCancel }: { onCancel: () => void }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  let activeIndex = 0;
  STAGES.forEach((stage, index) => {
    if (elapsed >= stage.startsAt) {
      activeIndex = index;
    }
  });

  return (
    <section className="card" aria-labelledby="answer-progress-heading">
      <div className="card-title">
        <h2 id="answer-progress-heading">Working on your answer</h2>
        <button type="button" className="btn-secondary btn-small" onClick={onCancel}>
          Cancel
        </button>
      </div>

      <div className="progress" role="status" aria-live="polite">
        <div className="progress-track" aria-hidden="true">
          <div className="progress-bar" />
        </div>
        <span>
          <strong>{STAGES[activeIndex].label}…</strong>
          <span className="card-subtle"> {elapsed}s elapsed</span>
        </span>
      </div>

      <ol className="steps" style={{ marginBottom: 8 }}>
        {STAGES.map((stage, index) => (
          <li
            key={stage.label}
            data-state={
              index < activeIndex ? "done" : index === activeIndex ? "current" : "todo"
            }
          >
            {index < activeIndex ? <span aria-hidden="true">✓</span> : null}
            {stage.label}
          </li>
        ))}
      </ol>

      <p className="hint">
        This normally takes 30 to 120 seconds. Several model passes run one after
        another, entirely on this computer — nothing is being uploaded. The stage
        shown above is an estimate based on elapsed time: the backend does not
        report its exact progress, so no percentage is invented here.
      </p>
    </section>
  );
}
