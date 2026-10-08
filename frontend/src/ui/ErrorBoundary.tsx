import { Component, type ErrorInfo, type ReactNode } from 'react';

interface State { error: Error | null; }

/**
 * Last line of defence: a rendering error in one screen shows a recoverable
 * message instead of unmounting the whole app to a blank page.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="error-screen" role="alert">
        <div className="error-card">
          <h2>Something went wrong on this screen</h2>
          <p>Your data is safe — nothing was saved by the step that failed. Reload to continue.</p>
          <pre>{this.state.error.message}</pre>
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={() => window.location.reload()}>Reload</button>
            <button className="btn btn-secondary" onClick={() => { window.location.hash = '#/dashboard'; window.location.reload(); }}>
              Go to dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }
}
