import { useState } from "react";

import type { EvidenceItem } from "../api/types";

function statusBadgeClass(status: string | null): string {
  const normalized = (status ?? "").toLowerCase();
  if (normalized.includes("in_force") || normalized === "active") {
    return "badge badge-ok";
  }
  if (normalized.includes("repeal") || normalized.includes("omitted")) {
    return "badge badge-danger";
  }
  return "badge badge-warn";
}

function value(input: string | number | null | undefined, fallback = "not stated"): string {
  if (input === null || input === undefined || input === "") {
    return fallback;
  }
  return String(input);
}

/** Stable DOM id so a verified claim can link straight to the source it cites. */
export function evidenceDomId(sourceId: string): string {
  return `evidence-${sourceId.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
}

interface Props {
  item: EvidenceItem;
  index: number;
  open: boolean;
  onToggle: () => void;
  /** Set when the user arrived here by following a claim's citation. */
  highlighted?: boolean;
}

export function EvidenceCard({ item, index, open, onToggle, highlighted }: Props) {
  const [copied, setCopied] = useState(false);
  const bodyId = `${evidenceDomId(item.source_id)}-body`;

  async function copyCitation() {
    const citation = [
      item.section ? `${item.act} — Section ${item.section}` : item.act,
      item.heading ?? "",
      "",
      item.excerpt,
      item.excerpt_truncated ? "[excerpt truncated]" : "",
      "",
      `Effective from: ${value(item.effective_from)}`,
      `Status: ${value(item.status)}`,
      item.official_url ? `Official source: ${item.official_url}` : "",
      item.page ? `Page: ${item.page}` : "",
      item.sha256 ? `SHA-256: ${item.sha256}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    try {
      await navigator.clipboard.writeText(citation);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article
      className="evidence-card"
      id={evidenceDomId(item.source_id)}
      style={
        highlighted
          ? { borderColor: "var(--brand)", boxShadow: "0 0 0 3px var(--brand-tint)" }
          : undefined
      }
    >
      <h3 style={{ margin: 0 }}>
        <button
          type="button"
          className="evidence-summary"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={onToggle}
        >
          <span>
            <span className="card-subtle">Source {index + 1} — </span>
            <span className="evidence-heading">
              {item.act}
              {item.section ? ` · Section ${item.section}` : ""}
            </span>
            <br />
            <span className="card-subtle">
              {item.heading ?? "(no heading recorded)"}
            </span>
          </span>
          <span className="row" style={{ flexWrap: "nowrap" }}>
            <span className={statusBadgeClass(item.status)}>{value(item.status)}</span>
            <span aria-hidden="true" style={{ fontSize: "1.1rem" }}>
              {open ? "−" : "+"}
            </span>
          </span>
        </button>
      </h3>

      <div id={bodyId} className="evidence-body" hidden={!open}>
        <h4>Verbatim text</h4>
        <blockquote className="excerpt">{item.excerpt}</blockquote>
        {item.excerpt_truncated ? (
          <p className="hint" style={{ color: "var(--warn)", fontWeight: 600 }}>
            This excerpt is truncated. Open the official source before relying on it.
          </p>
        ) : null}

        <dl className="meta-grid">
          <div>
            <dt>Effective from</dt>
            <dd>{value(item.effective_from)}</dd>
          </div>
          <div>
            <dt>Effective to</dt>
            <dd>{value(item.effective_to, "still in force / not stated")}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{value(item.status)}</dd>
          </div>
          <div>
            <dt>Page in source</dt>
            <dd>{value(item.page)}</dd>
          </div>
          <div>
            <dt>Retrieved at</dt>
            <dd>{value(item.retrieved_at)}</dd>
          </div>
          <div>
            <dt>Source id</dt>
            <dd className="mono">{value(item.source_id)}</dd>
          </div>
        </dl>

        {item.sha256 ? <p className="hashline">Chunk SHA-256: {item.sha256}</p> : null}

        <div className="row" style={{ marginTop: 10 }}>
          {item.official_url ? (
            <a
              className="btn-secondary btn-small"
              style={{ textDecoration: "none", display: "inline-block" }}
              href={item.official_url}
              target="_blank"
              rel="noreferrer noopener"
            >
              Open official source (new tab)
            </a>
          ) : (
            <span className="badge badge-warn">No official URL recorded</span>
          )}
          <button type="button" className="btn-secondary btn-small" onClick={copyCitation}>
            {copied ? "Copied" : "Copy citation"}
          </button>
        </div>
      </div>
    </article>
  );
}
