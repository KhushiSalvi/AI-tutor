import React from "react";

const STYLES = {
  term: {
    bg: "rgba(125, 207, 255, 0.15)",
    color: "#7dcfff",
    borderBottom: "2px solid #7dcfff",
    textDecoration: "none",
    label: "Key Term (solid)",
  },
  formula: {
    bg: "rgba(187, 154, 247, 0.15)",
    color: "#bb9af7",
    borderBottom: "3px double #bb9af7",
    textDecoration: "none",
    label: "Formula / Relation (double)",
  },
  warning: {
    bg: "rgba(224, 175, 104, 0.15)",
    color: "#e0af68",
    borderBottom: "none",
    textDecoration: "underline wavy #e0af68",
    label: "Watch Out / Warning (wavy)",
  },
  exam: {
    bg: "rgba(247, 118, 142, 0.15)",
    color: "#f7768e",
    borderBottom: "2px dashed #f7768e",
    textDecoration: "none",
    label: "Exam Tip (dashed)",
  },
};

export function HighlightLegend({ highlights }) {
  if (!highlights || highlights.length === 0) return null;
  const kindsUsed = [...new Set(highlights.map((h) => h.kind))];

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", margin: "10px 0", fontSize: "11px", color: "#a9b1d6" }}>
      {kindsUsed.map((k) => {
        const s = STYLES[k] || STYLES.term;
        return (
          <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
            <mark
              style={{
                backgroundColor: s.bg,
                color: s.color,
                borderBottom: s.borderBottom,
                textDecoration: s.textDecoration,
                padding: "1px 5px",
                borderRadius: "3px",
                fontSize: "11px",
              }}
            >
              {k}
            </mark>
            <span>{s.label}</span>
          </span>
        );
      })}
    </div>
  );
}

export function renderHighlightedText(text, highlights) {
  if (!text) return "";
  if (!highlights || highlights.length === 0) return text;

  // Build sorted intervals of substring matches
  const matches = [];
  for (const h of highlights) {
    if (!h.text) continue;
    let idx = text.indexOf(h.text);
    while (idx !== -1) {
      matches.push({ start: idx, end: idx + h.text.length, kind: h.kind, text: h.text });
      idx = text.indexOf(h.text, idx + h.text.length);
    }
  }

  // Sort matches by start position
  matches.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));

  // Filter overlapping matches
  const nonOverlapping = [];
  let lastEnd = 0;
  for (const m of matches) {
    if (m.start >= lastEnd) {
      nonOverlapping.push(m);
      lastEnd = m.end;
    }
  }

  if (nonOverlapping.length === 0) return text;

  const elements = [];
  let cursor = 0;

  nonOverlapping.forEach((m, i) => {
    if (m.start > cursor) {
      elements.push(text.slice(cursor, m.start));
    }
    const s = STYLES[m.kind] || STYLES.term;
    elements.push(
      <mark
        key={i}
        title={`[${m.kind}] ${s.label}`}
        style={{
          backgroundColor: s.bg,
          color: s.color,
          borderBottom: s.borderBottom,
          textDecoration: s.textDecoration,
          padding: "1px 3px",
          borderRadius: "3px",
        }}
      >
        {m.text}
      </mark>
    );
    cursor = m.end;
  });

  if (cursor < text.length) {
    elements.push(text.slice(cursor));
  }

  return elements;
}

export default function CalloutBox({ callout }) {
  if (!callout) return null;
  const kind = callout.kind || "important";
  const colors = {
    important: { border: "#7aa2f7", bg: "rgba(122, 162, 247, 0.08)", icon: "ℹ️" },
    remember: { border: "#73daca", bg: "rgba(115, 218, 202, 0.08)", icon: "💡" },
    watch_out: { border: "#e0af68", bg: "rgba(224, 175, 104, 0.08)", icon: "⚠️" },
    exam_tip: { border: "#bb9af7", bg: "rgba(187, 154, 247, 0.08)", icon: "🎯" },
  };
  const c = colors[kind] || colors.important;

  return (
    <div
      style={{
        margin: "12px 0",
        padding: "12px 16px",
        borderRadius: "8px",
        borderLeft: `4px solid ${c.border}`,
        backgroundColor: c.bg,
        color: "#c0caf5",
        fontSize: "13px",
        lineHeight: "1.5",
      }}
    >
      <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
        <span>{c.icon}</span>
        <span>{callout.title || kind.replace("_", " ").toUpperCase()}</span>
      </div>
      <div>{callout.text}</div>
    </div>
  );
}
