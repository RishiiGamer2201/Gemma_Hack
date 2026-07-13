import type { ReactNode } from "react";

import { describeError } from "../api/client";

interface ErrorNoticeProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

/**
 * Never render a blank screen on failure. Every error surface offers a retry path.
 */
export function ErrorNotice({ error, onRetry, title }: ErrorNoticeProps) {
  if (!error) {
    return null;
  }
  return (
    <div className="alert alert-danger" role="alert">
      <h3>{title ?? "Something went wrong"}</h3>
      <p>{describeError(error)}</p>
      {onRetry ? (
        <button type="button" className="btn-secondary btn-small" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

interface ProgressProps {
  label: string;
  detail?: string;
}

/** Indeterminate progress with an accessible live region. */
export function Progress({ label, detail }: ProgressProps) {
  return (
    <div className="progress" role="status" aria-live="polite">
      <div className="progress-track" aria-hidden="true">
        <div className="progress-bar" />
      </div>
      <span>
        <strong>{label}</strong>
        {detail ? <span className="card-subtle"> — {detail}</span> : null}
      </span>
    </div>
  );
}

interface EmptyProps {
  children: ReactNode;
}

export function Empty({ children }: EmptyProps) {
  return <p className="empty">{children}</p>;
}
