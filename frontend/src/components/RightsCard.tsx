import { useCallback, useEffect, useRef, useState } from "react";

import { postRightsCard } from "../api/client";
import type { ConfirmedFacts } from "../api/types";
import { ErrorNotice, Progress } from "./Feedback";

/**
 * Generate a shareable Rights Card for a published case. The image is rendered by
 * the backend entirely from verified inputs — the answer's rights, the retrieved
 * citations, directory helplines, and a QR to an official source — so the card
 * cannot assert anything the answer did not. It is a PNG the user can save or
 * forward; it is not stored anywhere.
 */

interface Props {
  facts: ConfirmedFacts;
  approvedProfiles: string[];
}

export function RightsCard({ facts, approvedProfiles }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [url, setUrl] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  const revoke = useCallback(() => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  useEffect(() => revoke, [revoke]);

  const generate = useCallback(async () => {
    setBusy(true);
    setError(null);
    revoke();
    setUrl(null);
    try {
      const blob = await postRightsCard({
        facts,
        approved_profiles: approvedProfiles,
        legal_aid_district: facts.location ?? null,
        legal_aid_state: facts.jurisdiction ?? null,
        limit: 4,
      });
      const objectUrl = URL.createObjectURL(blob);
      urlRef.current = objectUrl;
      setUrl(objectUrl);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }, [facts, approvedProfiles, revoke]);

  return (
    <section className="card" aria-labelledby="card-heading">
      <div className="card-title">
        <h3 id="card-heading">Rights Card</h3>
      </div>
      <p className="card-subtle">
        A pocket summary you can save or share — your rights, the sources they rest
        on, free-help numbers, and a QR to the official law. Every line comes from
        the verified answer; nothing is added.
      </p>

      {!url ? (
        <div className="row row-end">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void generate()}
            disabled={busy}
          >
            {busy ? "Generating…" : "Generate Rights Card"}
          </button>
        </div>
      ) : null}

      {busy ? <Progress label="Rendering the card on this machine…" /> : null}
      <ErrorNotice error={error} title="Could not generate the card" />

      {url ? (
        <div className="rights-card-preview">
          <img src={url} alt="Rights Card summarising your situation and rights" />
          <div className="row row-end" style={{ marginTop: 12 }}>
            <button type="button" className="btn-link btn-small" onClick={() => void generate()}>
              Regenerate
            </button>
            <a className="btn-primary btn-small" href={url} download="rights-card.png">
              Download PNG
            </a>
          </div>
        </div>
      ) : null}
    </section>
  );
}
