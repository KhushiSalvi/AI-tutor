import { useState } from "react";
import { PanelLeft, Search, SquarePen, Trash2, Zap } from "./Icons.jsx";

export default function Sidebar({ open, onToggle, chats, activeId, onNew, onOpen, onDelete, status }) {
  const [searching, setSearching] = useState(false);
  const [q, setQ] = useState("");
  const shown = chats.filter((c) => c.title.toLowerCase().includes(q.toLowerCase()));

  return (
    <aside className={"sidebar" + (open ? "" : " closed")}>
      <div className="sb-head">
        <button className="icon-btn" title="EE Tutor" onClick={onNew}>
          <Zap size={20} />
        </button>
        <button className="icon-btn" title="Close sidebar" onClick={onToggle}>
          <PanelLeft size={20} />
        </button>
      </div>

      <button className="nav-item" onClick={onNew}>
        <SquarePen size={18} /> New chat
      </button>
      <button
        className="nav-item"
        onClick={() => {
          setSearching(!searching);
          setQ("");
        }}
      >
        <Search size={18} /> Search chats
      </button>
      {searching && (
        <input className="search" autoFocus placeholder="Search chats" value={q} onChange={(e) => setQ(e.target.value)} />
      )}

      <div className="label">Chats</div>
      <nav className="chat-list">
        {shown.map((c) => (
          <div key={c.id} className={"nav-item chat-item" + (c.id === activeId ? " active" : "")} onClick={() => onOpen(c.id)}>
            <span className="ellipsis">{c.title}</span>
            <button
              className="del"
              title="Delete chat"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
              }}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {shown.length === 0 && <div className="empty-list">No chats yet</div>}
      </nav>

      <div className="profile">
        <div className="avatar">S</div>
        <div>
          <div className="p-name">Student</div>
          <div className="p-sub">{status?.llm_ready ? `${status.provider} ready` : "LLM not configured"}</div>
        </div>
      </div>
    </aside>
  );
}
