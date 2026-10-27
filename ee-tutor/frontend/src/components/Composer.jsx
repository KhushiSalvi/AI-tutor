import { useEffect, useRef, useState } from "react";
import { ArrowUp, Plus, Video, Square } from "./Icons.jsx";

let lastDraft = 0; // remembers which restored question was already put back in the box

export default function Composer({ onSend, onMakeVideo, onStop, draft, disabled }) {
  const [text, setText] = useState("");
  const ref = useRef(null);

  // after "Stop", the question comes back here so you can fix it and send again
  useEffect(() => {
    if (!draft || draft.n === lastDraft) return;
    lastDraft = draft.n;
    setText(draft.text);
    requestAnimationFrame(() => {
      if (!ref.current) return;
      ref.current.style.height = "auto";
      ref.current.style.height = Math.min(ref.current.scrollHeight, 200) + "px";
      ref.current.focus();
    });
  }, [draft]);

  function grow() {
    const el = ref.current;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  function submit() {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
    requestAnimationFrame(() => ref.current && (ref.current.style.height = "auto"));
  }

  return (
    <div className="composer-wrap">
      <div className="composer">
        <button className="plus" disabled title="Upload sources (coming soon)">
          <Plus size={20} />
        </button>
        <textarea
          ref={ref}
          rows={1}
          autoFocus
          value={text}
          placeholder="Ask anything"
          onChange={(e) => {
            setText(e.target.value);
            grow();
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape" && disabled && onStop) onStop();
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {onMakeVideo && (
          <button
            className="video-btn"
            disabled={!text.trim() || disabled}
            title="Make a short explainer video for this topic"
            onClick={() => {
              if (!text.trim() || disabled) return;
              onMakeVideo(text);
              setText("");
              requestAnimationFrame(() => ref.current && (ref.current.style.height = "auto"));
            }}
          >
            <Video size={18} />
          </button>
        )}
        {disabled && onStop ? (
          <button className="send stop" onClick={onStop} title="Stop (Esc)">
            <Square size={16} />
          </button>
        ) : (
          <button className="send" disabled={!text.trim() || disabled} onClick={submit} title="Send message">
            <ArrowUp size={20} />
          </button>
        )}
      </div>
    </div>
  );
}
