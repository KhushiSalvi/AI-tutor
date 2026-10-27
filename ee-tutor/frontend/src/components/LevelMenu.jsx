import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "./Icons.jsx";

const LEVELS = [
  { id: "beginner", title: "Beginner", desc: "Simple language, skips advanced chapters" },
  { id: "advanced", title: "Advanced", desc: "Concise and technical" },
];

export default function LevelMenu({ level, setLevel }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="level" ref={ref}>
      <button className="model-btn" onClick={() => setOpen(!open)}>
        EE Tutor <span className="muted">{level === "beginner" ? "Beginner" : "Advanced"}</span>
        <ChevronDown size={16} className="muted" />
      </button>
      {open && (
        <div className="menu">
          {LEVELS.map((l) => (
            <button
              key={l.id}
              className="menu-item"
              onClick={() => {
                setLevel(l.id);
                setOpen(false);
              }}
            >
              <div>
                <div>{l.title}</div>
                <div className="menu-desc">{l.desc}</div>
              </div>
              {level === l.id && <Check size={18} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
