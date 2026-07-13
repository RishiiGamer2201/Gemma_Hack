import { useCallback, useEffect, useRef, useState } from "react";

import { type AdvocateEvent, streamDevilsAdvocate } from "../api/client";
import type { ConfirmedFacts } from "../api/types";
import { ErrorNotice } from "./Feedback";

/**
 * The Devil's Advocate stress test. It runs only on a case that already produced a
 * verified answer (the backend refuses otherwise), then streams three sequential
 * stages — the user's strongest cautious argument, the opposing side, and a
 * cautious rebuttal — over one loaded model. Tokens are shown as they arrive so the
 * sequential local generations never look frozen. It concludes with weaknesses to
 * investigate, never a prediction of who wins.
 */

const STAGES = [
  { key: "advocate", label: "⚖️ Your strongest argument" },
  { key: "opponent", label: "🛡️ The other side's case" },
  { key: "rebuttal", label: "↩️ Cautious response" },
] as const;

type StageKey = (typeof STAGES)[number]["key"];

interface Props {
  facts: ConfirmedFacts;
  approvedProfiles: string[];
}

export function DevilsAdvocate({ facts, approvedProfiles }: Props) {
  const [running, setRunning] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [active, setActive] = useState<StageKey | null>(null);
  const [text, setText] = useState<Record<StageKey, string>>({
    advocate: "",
    opponent: "",
    rebuttal: "",
  });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const run = useCallback(async () => {
    setRunning(true);
    setDone(false);
    setError(null);
    setActive(null);
    setText({ advocate: "", opponent: "", rebuttal: "" });
    setPreparing(false);
    const controller = new AbortController();
    controllerRef.current = controller;

    const handle = (event: AdvocateEvent) => {
      if (event.kind === "error") {
        setError(new Error(event.message ?? "The stress test stopped early."));
        return;
      }
      if (event.kind === "preparing") {
        setPreparing(true);
        return;
      }
      const stage = event.stage as StageKey | undefined;
      if (!stage) {
        return;
      }
      if (event.kind === "started") {
        setPreparing(false);
        setActive(stage);
      } else if (event.kind === "token" && event.text) {
        setText((prev) => ({ ...prev, [stage]: prev[stage] + event.text }));
      } else if (event.kind === "completed" && event.text) {
        // The completed event carries the full, cleaned stage text.
        setText((prev) => ({ ...prev, [stage]: event.text as string }));
      }
    };

    try {
      await streamDevilsAdvocate(
        { facts, approved_profiles: approvedProfiles, limit: 4 },
        handle,
        controller.signal,
      );
      setDone(true);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught);
      }
    } finally {
      setActive(null);
      setPreparing(false);
      setRunning(false);
    }
  }, [facts, approvedProfiles]);

  const cancel = useCallback(() => controllerRef.current?.abort(), []);

  return (
    <section className="card" aria-labelledby="devil-heading">
      <div className="card-title">
        <h3 id="devil-heading">Stress-test both sides</h3>
        {running ? (
          <button type="button" className="btn-link btn-small" onClick={cancel}>
            Stop
          </button>
        ) : null}
      </div>
      <p className="card-subtle">
        See the argument for your position, the strongest case against it, and a
        cautious response — all grounded in the same verified sources. This points to
        weaknesses worth investigating; it does not predict an outcome.
      </p>

      {!running && !done ? (
        <div className="row row-end">
          <button type="button" className="btn-secondary" onClick={() => void run()}>
            Run the stress test
          </button>
        </div>
      ) : null}

      <ErrorNotice error={error} title="The stress test could not finish" />

      {preparing ? (
        <p className="card-subtle" role="status">
          Preparing the case from your verified answer… this takes a few seconds.
        </p>
      ) : null}

      <div className="advocate-stages">
        {STAGES.map((stage) => {
          const body = text[stage.key];
          if (!body && active !== stage.key) {
            return null;
          }
          return (
            <div className="advocate-stage" key={stage.key}>
              <h4>
                {stage.label}
                {active === stage.key ? <span className="typing" aria-hidden="true" /> : null}
              </h4>
              <p className="advocate-text">
                {body || (active === stage.key ? "Thinking…" : "")}
              </p>
            </div>
          );
        })}
      </div>

      {done ? (
        <p className="hint">
          These are points to raise with a lawyer, not a verdict. Nothing here
          changes the verified answer above.
        </p>
      ) : null}
    </section>
  );
}
