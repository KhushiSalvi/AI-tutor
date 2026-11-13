/**
 * Formula.jsx — renders LaTeX math using KaTeX (loaded via CDN in index.html).
 *
 * Usage:
 *   <Formula tex="V = IR" display />           ← block / display mode (centred)
 *   <Formula tex="V = IR" />                   ← inline mode
 *   <FormulaBlock formula="V = IR"
 *                 where="V = voltage, I = current, R = resistance" />
 *
 * The backend stores formulas as plain ASCII or LaTeX. We normalise common
 * ASCII patterns before passing to KaTeX so the LLM doesn't have to write
 * perfect LaTeX.
 */
import { useEffect, useRef } from "react";

// ---------------------------------------------------------------------------
// ASCII → LaTeX normalisation
// ---------------------------------------------------------------------------

function normalise(tex) {
  if (!tex) return "";

  // Replace common patterns the LLM writes in ASCII
  return tex
    // fractions: a/b → \frac{a}{b}  (simple single-token numerator/denominator)
    .replace(/([A-Za-z0-9_]+)\s*\/\s*([A-Za-z0-9_^{}]+)/g, "\\frac{$1}{$2}")
    // sqrt(x) → \sqrt{x}
    .replace(/sqrt\(([^)]+)\)/g, "\\sqrt{$1}")
    // x^2 is already valid LaTeX — keep
    // subscripts: x_m → x_{m} (single char subscript is fine, multi needs braces)
    // sum notation: sum_{m=1}^{M}  stays as-is if already LaTeX
    // ohm: Ω or ohm → \Omega
    .replace(/Ω|ohm\b/gi, "\\Omega")
    // mu: µ or mu → \mu
    .replace(/µ|(?<=\d)\s*mu\b/g, "\\mu")
    // degrees: ° → °  (KaTeX handles this)
    // approx: ≈ → \approx
    .replace(/≈/g, "\\approx")
    // ≤ → \leq   ≥ → \geq
    .replace(/≤/g, "\\leq")
    .replace(/≥/g, "\\geq")
    // × → \times
    .replace(/×/g, "\\times")
    // ∑ → \sum
    .replace(/∑/g, "\\sum")
    // ∫ → \int
    .replace(/∫/g, "\\int")
    // π → \pi
    .replace(/π/g, "\\pi")
    // ∞ → \infty
    .replace(/∞/g, "\\infty")
    // → → \rightarrow
    .replace(/→/g, "\\rightarrow")
    // ← → \leftarrow
    .replace(/←/g, "\\leftarrow")
    // Alpha-omega Greek letters written out
    .replace(/\balpha\b/g, "\\alpha")
    .replace(/\bbeta\b/g, "\\beta")
    .replace(/\bgamma\b/g, "\\gamma")
    .replace(/\bdelta\b/g, "\\delta")
    .replace(/\btheta\b/g, "\\theta")
    .replace(/\blambda\b/g, "\\lambda")
    .replace(/\bsigma\b/g, "\\sigma")
    .replace(/\btau\b/g, "\\tau")
    .replace(/\bphi\b/g, "\\phi")
    .replace(/\bomega\b/g, "\\omega");
}

// ---------------------------------------------------------------------------
// Core renderer hook
// ---------------------------------------------------------------------------

function useKaTeX(ref, tex, display) {
  useEffect(() => {
    if (!ref.current) return;
    const katex = window.katex;
    if (!katex) {
      // KaTeX not loaded yet — show plain text as fallback
      ref.current.textContent = tex;
      return;
    }
    try {
      katex.render(normalise(tex), ref.current, {
        displayMode: !!display,
        throwOnError: false,
        strict: false,
      });
    } catch {
      ref.current.textContent = tex;
    }
  }, [tex, display]);
}

// ---------------------------------------------------------------------------
// Inline formula
// ---------------------------------------------------------------------------

export function Formula({ tex }) {
  const ref = useRef(null);
  useKaTeX(ref, tex, false);
  return (
    <span
      ref={ref}
      className="formula-inline"
      style={{ fontFamily: "KaTeX_Main, serif" }}
    />
  );
}

// ---------------------------------------------------------------------------
// Block formula with optional "where" clause
// ---------------------------------------------------------------------------

export function FormulaBlock({ formula, where }) {
  const ref = useRef(null);
  useKaTeX(ref, formula, true);

  if (!formula) return null;

  return (
    <div className="formula-block">
      <div
        ref={ref}
        className="formula-display"
        style={{
          overflowX: "auto",
          padding: "18px 24px",
          background: "var(--formula-bg, rgba(122,162,247,0.07))",
          border: "1px solid var(--formula-border, rgba(122,162,247,0.2))",
          borderRadius: "10px",
          marginTop: "12px",
          marginBottom: where ? "8px" : "12px",
          textAlign: "center",
        }}
      />
      {where && (
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-muted, #8a8a9a)",
            marginTop: "4px",
            marginBottom: "12px",
            paddingLeft: "4px",
          }}
        >
          where: <span style={{ fontStyle: "italic" }}>{where}</span>
        </p>
      )}
    </div>
  );
}

export default FormulaBlock;
