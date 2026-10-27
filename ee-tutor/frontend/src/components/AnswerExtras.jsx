import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import "./AnswerExtras.css";

const arr = (x) => (Array.isArray(x) ? x : []);
const HUES = [265, 150, 35, 340, 200];

function MindMap({ map, onAsk }) {
  const [shut, setShut] = useState({});
  const branches = arr(map?.branches).filter((b) => b && b.label);
  if (!map?.center || branches.length < 2) return null;
  return (
    <section className="ax-card">
      <h4 className="ax-h">🧠 Mind map</h4>
      <div className="mm">
        <div className="mm-center">{map.center}</div>
        <div className="mm-branches">
          {branches.map((b, i) => {
            const kids = arr(b.children);
            const closed = !!shut[i];
            return (
              <div key={i} className="mm-branch" style={{ "--h": HUES[i % HUES.length] }}>
                <button
                  className="mm-label"
                  aria-expanded={!closed}
                  onClick={() => setShut({ ...shut, [i]: !closed })}
                >
                  <span className="mm-caret">{closed ? "▸" : "▾"}</span>
                  {b.label}
                </button>
                {!closed && kids.length > 0 && (
                  <div className="mm-kids">
                    {kids.map((k, j) => (
                      <button key={j} className="mm-kid" title="Ask about this" onClick={() => onAsk?.(`Explain "${k}" in more detail`)}>
                        {k}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <p className="ax-hint">Click a branch to fold it, or click a point to ask about it.</p>
    </section>
  );
}

// Light text colour on the page = a dark theme (works with any of the app's themes)
function pageIsDark() {
  const m = getComputedStyle(document.body).color.match(/\d+/g) || [0, 0, 0];
  return (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) > 140;
}

function Flowchart({ code }) {
  const [svg, setSvg] = useState("");
  const [dark, setDark] = useState(pageIsDark());
  const [copied, setCopied] = useState(false);
  const id = useRef("mmd" + Math.random().toString(36).slice(2));

  useEffect(() => {  // re-draw when the theme toggle changes
    const watch = new MutationObserver(() => setDark(pageIsDark()));
    watch.observe(document.documentElement, { attributes: true });
    watch.observe(document.body, { attributes: true });
    return () => watch.disconnect();
  }, []);

  useEffect(() => {
    let off = false;
    import("mermaid")  // loaded only when an answer has a flowchart
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: dark ? "dark" : "neutral",
          fontFamily: "inherit",
          flowchart: { curve: "basis", useMaxWidth: true, htmlLabels: true },
        });
        const out = await mermaid.render(id.current + (dark ? "d" : "l"), code);
        if (!off) setSvg(out.svg);
      })
      .catch(() => !off && setSvg(""));  // bad diagram -> just hide it
    return () => {
      off = true;
    };
  }, [code, dark]);

  if (!svg) return null;
  return (
    <section className="ax-card">
      <h4 className="ax-h">
        🔀 Flowchart
        <button
          className="ax-copy"
          onClick={() => navigator.clipboard?.writeText(code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
        >
          {copied ? "Copied" : "Copy Mermaid code"}
        </button>
      </h4>
      <div className="ax-flow" dangerouslySetInnerHTML={{ __html: svg }} />
    </section>
  );
}

function Steps({ steps }) {
  const list = arr(steps);
  if (list.length < 2) return null;
  return (
    <section className="ax-card">
      <h4 className="ax-h">🪜 Step by step</h4>
      <ol className="ax-steps">
        {list.map((s, i) => (
          <li key={i}>
            <span className="ax-num">{i + 1}</span>
            <span>{s}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function WebImages({ q }) {
  const [imgs, setImgs] = useState([]);
  const [big, setBig] = useState(null);
  useEffect(() => {
    let off = false;
    if (!q) return;
    api(`/webimages?q=${encodeURIComponent(q)}`)
      .then((r) => !off && setImgs(arr(r)))
      .catch(() => {});
    return () => {
      off = true;
    };
  }, [q]);
  if (!imgs.length) return null;
  return (
    <section className="ax-card">
      <h4 className="ax-h">🖼️ Diagrams from the web</h4>
      <div className="ax-imgs">
        {imgs.map((im, i) => (
          <figure key={i} className="ax-img">
            <button onClick={() => setBig(im)} title="Click to enlarge">
              <img src={im.thumb} alt={im.title} loading="lazy" />
            </button>
            <figcaption>
              <a href={im.page} target="_blank" rel="noreferrer">
                {im.title}
              </a>
              <span>{[im.credit, im.license].filter(Boolean).join(" · ")}</span>
            </figcaption>
          </figure>
        ))}
      </div>
      <p className="ax-hint">Not from your textbook. Images are from Wikimedia Commons, credited under their own licences.</p>
      {big && (
        <div className="ax-lightbox" onClick={() => setBig(null)}>
          <img src={big.thumb} alt={big.title} />
        </div>
      )}
    </section>
  );
}

export default function AnswerExtras({ res, onAsk }) {
  if (!res || res.mode === "error") return null;
  const card = res.mode === "card" && res.found;
  const imgQuery = card || res.web_used ? res.title || res.search_q : "";
  const example = card && res.example ? res.example : "";
  const summary = card ? arr(res.summary) : [];
  const follow = arr(res.followups);
  return (
    <div className="ax">
      {card && <MindMap map={res.mindmap} onAsk={onAsk} />}
      {card && res.flowchart && <Flowchart code={res.flowchart} />}
      {card && <Steps steps={res.steps} />}
      {example && (
        <section className="ax-card ax-example">
          <h4 className="ax-h">💡 Example</h4>
          <p>{example}</p>
        </section>
      )}
      <WebImages q={imgQuery} />
      {summary.length > 0 && (
        <section className="ax-card ax-summary">
          <h4 className="ax-h">✅ In short</h4>
          <ul>
            {summary.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </section>
      )}
      {follow.length > 0 && (
        <div className="ax-follow">
          <span>Ask next</span>
          {follow.map((f, i) => (
            <button key={i} onClick={() => onAsk?.(f)}>
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
