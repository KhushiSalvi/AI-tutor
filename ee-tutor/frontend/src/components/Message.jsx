import { useState } from "react";
import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp } from "./Icons.jsx";
import AnswerExtras from "./AnswerExtras.jsx";

const arr = (x) => (Array.isArray(x) ? x : []);
function normalize(r) {
  return {
    ...r,
    key_points: arr(r.key_points).map(String),
    figures: arr(r.figures).map(String),
    sources: arr(r.sources),
    cited: arr(r.cited),
    figure_pages: r.figure_pages && typeof r.figure_pages === "object" ? r.figure_pages : {},
    web_sources: arr(r.web_sources),
  };
}

function plainText(res) {
  if (res.mode === "error") return res.error;
  if (res.mode === "card" && res.found)
    return [res.title, res.answer, res.explanation, ...(res.key_points || []).map((k) => "- " + k)]
      .filter(Boolean)
      .join("\n\n");
  return res.reply || res.answer || "";
}

function Figure({ res, no }) {
  const [failed, setFailed] = useState(false);
  const [full, setFull] = useState(false);
  const source = res.sources?.[0]?.source;
  const near = res.figure_pages?.[no];
  if (!source || !near) return null;
  const q = `source_id=${encodeURIComponent(source)}`;

  if (failed)
    return (
      <div className="cap">
        Figure {no} is mentioned in the sources but could not be cropped.{" "}
        <button className="link" onClick={() => setFull(!full)}>
          {full ? "Hide page" : `Show the page (PDF p.${near})`}
        </button>
        {full && <img className="pageimg" alt="" src={`/api/page?${q}&pdf_page=${near}`} />}
      </div>
    );

  return (
    <figure className="fig">
      <img alt={`Figure ${no}`} src={`/api/figure?${q}&fig=${no}&near=${near}`} onError={() => setFailed(true)} />
      <figcaption className="cap">Figure {no} from the book</figcaption>
    </figure>
  );
}

function Body({ res }) {
  if (res.mode === "error") return <p className="err">{res.error}</p>;
  if (res.mode === "card") {
    const empty = !res.answer && !res.explanation && res.key_points.length === 0;
    if (!res.found || empty)
      return (
        <p>
          {res.answer ||
            res.reply ||
            (res.found ? "No answer came back. Try rephrasing, or press regenerate." : "The book does not seem to cover this.")}
        </p>
      );
    return (
      <>
        {res.title && <h3>{res.title}</h3>}
        <p className="lead">{res.answer}</p>
        {res.explanation && (
          <>
            <h4>Explanation</h4>
            <p>{res.explanation}</p>
          </>
        )}
        {res.key_points?.length > 0 && (
          <>
            <h4>Key points</h4>
            <ul>
              {res.key_points.map((k, i) => (
                <li key={i}>{k}</li>
              ))}
            </ul>
          </>
        )}
        {res.formula && (
          <>
            <h4>Key formula</h4>
            <pre className="code">{res.formula}</pre>
            {res.formula_where && <p className="cap">{res.formula_where}</p>}
            <p className="cap">Check this formula against the cited page. Book text can have broken equations.</p>
          </>
        )}
      </>
    );
  }
  const text = res.reply || res.answer || res.explanation;
  return <p className="reply">{text || "No answer came back. Try rephrasing, or press regenerate."}</p>;
}

function Sources({ res }) {
  const cited = (res.sources || []).filter((s) => res.cited?.includes(s.n));
  if (!cited.length) return null;
  const pages = [...new Set(cited.map((s) => s.page))];
  return (
    <div className="src">
      <span>Sources</span>
      {pages.map((p) => (
        <span className="chip" key={p}>
          p.{p}
        </span>
      ))}
      <details>
        <summary>Show source passages</summary>
        {cited.map((s) => (
          <div key={s.n} className="passage">
            <b>
              printed p.{s.page} (PDF p.{s.pdf_page})
            </b>
            <p>{s.text}</p>
          </div>
        ))}
      </details>
    </div>
  );
}

function WebNote({ res }) {
  if (!res.web_used) return null;
  return (
    <div className="webnote">
      <span>Not from your sources — answered from a web search.</span>
      {res.web_sources?.length > 0 && (
        <span className="weblinks">
          {res.web_sources.map((w, i) => (
            <a key={i} href={w.url} target="_blank" rel="noreferrer">
              [{i + 1}] {w.title || w.url}
            </a>
          ))}
        </span>
      )}
    </div>
  );
}

export default function Message({ msg, isLast, onRegenerate, onAsk }) {
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState(null);

  if (msg.role === "user")
    return (
      <div className="turn user-row">
        <div className="user-bubble">{msg.content}</div>
      </div>
    );

  const res = normalize(msg.res || { mode: "error", error: "Empty response from the server." });
  const copy = () => {
    navigator.clipboard.writeText(plainText(res));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="turn ai">
      <Body res={res} />
      {res.found && res.figures?.map((no) => <Figure key={no} res={res} no={no} />)}
      <AnswerExtras res={res} onAsk={onAsk} />
      {res.found && <Sources res={res} />}
      <WebNote res={res} />
      <div className="actions">
        <button className="act" title="Copy" onClick={copy}>
          {copied ? <Check size={16} /> : <Copy size={16} />}
        </button>
        <button className={"act" + (vote === "up" ? " on" : "")} title="Good response" onClick={() => setVote(vote === "up" ? null : "up")}>
          <ThumbsUp size={16} />
        </button>
        <button className={"act" + (vote === "down" ? " on" : "")} title="Bad response" onClick={() => setVote(vote === "down" ? null : "down")}>
          <ThumbsDown size={16} />
        </button>
        {isLast && (
          <button className="act" title="Regenerate" onClick={onRegenerate}>
            <RefreshCw size={16} />
          </button>
        )}
      </div>
    </div>
  );
}