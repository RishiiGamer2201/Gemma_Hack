import type { HealthResponse } from "../api/types";
import { describeError } from "../api/client";

interface Props {
  health: HealthResponse | null;
  loading: boolean;
  error: unknown;
  onRefresh: () => void;
  compact?: boolean;
}

/**
 * Connectivity / local-model status. "Offline" is the expected, desirable state:
 * the only thing that must be reachable is the loopback backend and the local model.
 */
export function HealthStatus({ health, loading, error, onRefresh, compact }: Props) {
  const backendUp = !error && health !== null;

  const strip = (
    <div className="status-strip">
      <span
        className={`badge ${backendUp ? "badge-ok" : "badge-danger"}`}
        title="Local FastAPI backend on 127.0.0.1:8000"
      >
        <span className="dot" aria-hidden="true" />
        {loading
          ? "Checking local server…"
          : backendUp
            ? "Local server: running"
            : "Local server: unreachable"}
      </span>

      <span
        className={`badge ${
          health?.ollama_reachable ? "badge-ok" : "badge-warn"
        }`}
        title="Local model runtime (Ollama on loopback)"
      >
        <span className="dot" aria-hidden="true" />
        {health?.ollama_reachable
          ? `Local model: ${health.model || "ready"}`
          : "Local model: not detected"}
      </span>

      <span
        className={`badge ${health?.corpus_loaded ? "badge-ok" : "badge-warn"}`}
        title="Offline law corpus"
      >
        <span className="dot" aria-hidden="true" />
        {health?.corpus_loaded
          ? `Law corpus: ${health.chunk_count.toLocaleString()} chunks`
          : "Law corpus: not loaded"}
      </span>

      <span className="badge" title="This app makes no internet requests.">
        <span className="dot" aria-hidden="true" />
        Internet: not used
      </span>
    </div>
  );

  if (compact) {
    return strip;
  }

  return (
    <section className="card" aria-labelledby="status-heading">
      <div className="card-title">
        <h2 id="status-heading">System status</h2>
        <button
          type="button"
          className="btn-secondary btn-small"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? "Checking…" : "Re-check"}
        </button>
      </div>

      {strip}

      {error ? (
        <div className="alert alert-danger" role="alert" style={{ marginTop: 12 }}>
          <h3>The local backend is not answering</h3>
          <p>{describeError(error)}</p>
          <p className="card-subtle">
            Start it from the project root, then press <strong>Re-check</strong>.
          </p>
        </div>
      ) : null}

      {health && !health.corpus_loaded ? (
        <div className="alert alert-warn" role="alert" style={{ marginTop: 12 }}>
          <h3>Law corpus is not loaded</h3>
          <p>
            Retrieval will return nothing until the offline corpus is built. You
            can still use intake and the legal-aid finder.
          </p>
        </div>
      ) : null}

      {health?.corpus_sha256 ? (
        <p className="hashline" style={{ marginTop: 10 }}>
          Corpus SHA-256: {health.corpus_sha256}
        </p>
      ) : null}
    </section>
  );
}
