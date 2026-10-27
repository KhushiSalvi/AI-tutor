import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error("UI crash:", error, info);
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ maxWidth: 720, margin: "10vh auto", padding: 24, color: "#ececec", fontFamily: "system-ui" }}>
        <h2>Something broke in the UI</h2>
        <p style={{ color: "#b4b4b4", margin: "8px 0 16px" }}>Copy the text below and send it to your developer.</p>
        <pre style={{ whiteSpace: "pre-wrap", background: "#0d0d0d", padding: 16, borderRadius: 12, fontSize: 13 }}>
          {String(this.state.error?.stack || this.state.error)}
        </pre>
        <button
          onClick={() => location.reload()}
          style={{ marginTop: 16, padding: "8px 16px", borderRadius: 999, background: "#fff", color: "#000", border: 0, cursor: "pointer" }}
        >
          Reload
        </button>
      </div>
    );
  }
}
