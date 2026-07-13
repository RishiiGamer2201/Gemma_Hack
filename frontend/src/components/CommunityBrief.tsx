import { useCallback, useState } from "react";

import { type CommunityResponse, postCommunity } from "../api/client";
import type { ConfirmedFacts } from "../api/types";
import { ErrorNotice, Progress } from "./Feedback";

/**
 * The Community Elder / Panchayat Bridge brief. It reformats the verified answer as
 * a respectful third-person explanation to show a trusted local intermediary. It is
 * built deterministically from already-verified content, so it cannot say anything
 * the answer did not, and it omits personal identifiers by default.
 */

interface Props {
  facts: ConfirmedFacts;
  approvedProfiles: string[];
}

export function CommunityBrief({ facts, approvedProfiles }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [brief, setBrief] = useState<CommunityResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const generate = useCallback(async () => {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      setBrief(await postCommunity({ facts, approved_profiles: approvedProfiles, limit: 4 }));
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }, [facts, approvedProfiles]);

  const copy = useCallback(async () => {
    if (!brief) {
      return;
    }
    try {
      await navigator.clipboard.writeText(brief.text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }, [brief]);

  return (
    <section className="card" aria-labelledby="community-heading">
      <div className="card-title">
        <h3 id="community-heading">Explain to someone you trust</h3>
      </div>
      <p className="card-subtle">
        A respectful summary to show a family elder, an NGO worker, or a panchayat
        member — so a trusted person can help you act on it. It keeps the law and the
        next steps, and leaves out personal details.
      </p>

      {!brief ? (
        <div className="row row-end">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void generate()}
            disabled={busy}
          >
            {busy ? "Preparing…" : "Prepare this summary"}
          </button>
        </div>
      ) : null}

      {busy ? <Progress label="Preparing the summary on this machine…" /> : null}
      <ErrorNotice error={error} title="Could not prepare the summary" />

      {brief ? (
        <div className="community-brief">
          <pre className="community-text">{brief.text}</pre>
          <div className="row row-end">
            <button type="button" className="btn-link btn-small" onClick={() => void generate()}>
              Regenerate
            </button>
            <button type="button" className="btn-secondary btn-small" onClick={() => void copy()}>
              {copied ? "Copied ✓" : "Copy text"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
