import { useCallback, useEffect, useState } from "react";

import { postLegalAid } from "../api/client";
import type { LegalAidResponse } from "../api/types";
import { Empty, ErrorNotice, Progress } from "./Feedback";

interface Props {
  initialDistrict?: string;
  initialState?: string;
  autoSearch?: boolean;
  /** Urgent mode drops the surrounding card chrome so it can sit inside the safety panel. */
  bare?: boolean;
  heading?: string;
}

export function LegalAidPanel({
  initialDistrict = "",
  initialState = "",
  autoSearch = false,
  bare = false,
  heading = "Legal Aid Finder",
}: Props) {
  const [district, setDistrict] = useState(initialDistrict);
  const [stateName, setStateName] = useState(initialState);
  const [result, setResult] = useState<LegalAidResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const search = useCallback(
    async (districtValue: string, stateValue: string) => {
      const trimmed = districtValue.trim();
      if (!trimmed) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        setResult(await postLegalAid(trimmed, stateValue.trim() || undefined));
      } catch (caught) {
        setError(caught);
        setResult(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (autoSearch && initialDistrict.trim()) {
      void search(initialDistrict, initialState);
    }
  }, [autoSearch, initialDistrict, initialState, search]);

  const body = (
    <>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void search(district, stateName);
        }}
      >
        <div className="field">
          <label htmlFor="aid-district">District or city</label>
          <input
            id="aid-district"
            type="text"
            value={district}
            placeholder="e.g. New Delhi"
            onChange={(event) => setDistrict(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="aid-state">State or UT (optional)</label>
          <input
            id="aid-state"
            type="text"
            value={stateName}
            placeholder="e.g. Delhi"
            onChange={(event) => setStateName(event.target.value)}
          />
        </div>
        <div className="row row-end">
          <button
            type="submit"
            className="btn-primary btn-small"
            disabled={loading || !district.trim()}
          >
            {loading ? "Searching…" : "Find legal aid"}
          </button>
        </div>
      </form>

      {loading ? <Progress label="Searching the offline directory…" /> : null}

      <ErrorNotice
        error={error}
        title="Legal-aid lookup failed"
        onRetry={() => void search(district, stateName)}
      />

      {result ? (
        <>
          {result.warnings.length > 0 ? (
            <div className="warning-block" role="alert">
              <strong>Read this first</strong>
              <ul>
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="card-subtle">
            Match status: <strong>{result.match_status}</strong>
          </p>

          <h4>District authority</h4>
          {result.contacts.length === 0 ? (
            <Empty>
              No exact district match. Use the national fallbacks below — the
              directory never guesses a nearby district.
            </Empty>
          ) : (
            result.contacts.map((contact) => (
              <div className="contact-card" key={contact.contact_id}>
                <strong>{contact.authority}</strong>
                <span className="card-subtle">
                  {[contact.district, contact.state].filter(Boolean).join(", ")}
                  {contact.designation ? ` — ${contact.designation}` : ""}
                </span>
                {contact.phone ? (
                  <p style={{ margin: "4px 0 0" }}>
                    Phone: <a href={`tel:${contact.phone.replace(/\s+/g, "")}`}>{contact.phone}</a>
                  </p>
                ) : null}
                {contact.email ? (
                  <p style={{ margin: 0 }}>
                    Email: <a href={`mailto:${contact.email}`}>{contact.email}</a>
                  </p>
                ) : null}
                {contact.official_url ? (
                  <p style={{ margin: "4px 0 0" }}>
                    <a
                      href={contact.official_url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      Official page (opens in a new tab)
                    </a>
                  </p>
                ) : null}
                {contact.verified_date ? (
                  <p className="hint">Last verified: {contact.verified_date}</p>
                ) : null}
              </div>
            ))
          )}

          {result.fallbacks.length > 0 ? (
            <>
              <h4>National fallbacks</h4>
              {result.fallbacks.map((fallback) => (
                <div className="contact-card" key={fallback.fallback_id}>
                  <strong>{fallback.service}</strong>
                  <p style={{ margin: "2px 0" }}>{fallback.description}</p>
                  {fallback.phone ? (
                    <p style={{ margin: 0 }}>
                      Phone:{" "}
                      <a href={`tel:${fallback.phone.replace(/\s+/g, "")}`}>
                        {fallback.phone}
                      </a>
                    </p>
                  ) : null}
                  {fallback.official_url ? (
                    <p style={{ margin: "4px 0 0" }}>
                      <a
                        href={fallback.official_url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        Official page (opens in a new tab)
                      </a>
                    </p>
                  ) : null}
                </div>
              ))}
            </>
          ) : null}
        </>
      ) : null}

      {!result && !loading && !error ? (
        <Empty>
          Enter a district to find the District Legal Services Authority. Free
          legal aid is a statutory right for eligible people.
        </Empty>
      ) : null}
    </>
  );

  if (bare) {
    return (
      <div>
        <h3>{heading}</h3>
        {body}
      </div>
    );
  }

  return (
    <section className="card" aria-labelledby="aid-heading">
      <h2 id="aid-heading">{heading}</h2>
      {body}
    </section>
  );
}
