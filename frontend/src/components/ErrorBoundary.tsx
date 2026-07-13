import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Last-resort guard: a render crash must never leave the user with a blank page.
 * Errors are shown locally only; nothing is reported anywhere.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Local console only. No telemetry, no remote logging.
    // eslint-disable-next-line no-console
    console.error("Nyaya Navigator UI error:", error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }
    return (
      <div style={{ padding: 24 }}>
        <div className="alert alert-danger" role="alert">
          <h3>The interface hit an unexpected error</h3>
          <p>
            Your information never left this computer. You can go back and try
            again; if the problem repeats, reload the page.
          </p>
          <p className="mono">{error.message}</p>
          <div className="row">
            <button type="button" className="btn-secondary" onClick={this.reset}>
              Go back
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </div>
        </div>
      </div>
    );
  }
}
