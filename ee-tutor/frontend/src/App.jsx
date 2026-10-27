import { useEffect, useRef, useState } from "react";
import { PanelLeft, SquarePen } from "./components/Icons.jsx";
import { api, post } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import LevelMenu from "./components/LevelMenu.jsx";
import Message from "./components/Message.jsx";
import Composer from "./components/Composer.jsx";
import VideoCard from "./components/VideoCard.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";

const SUGGESTIONS = [
  "Why does drain current stop increasing at large Vds?",
  "Explain channel length modulation",
  "How does the body effect change threshold voltage?",
];

export default function App() {
  const [chats, setChats] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(window.innerWidth > 768);
  const [level, setLevel] = useState(localStorage.getItem("level") || "beginner");
  const [status, setStatus] = useState(null);
  const endRef = useRef(null);
  const lastRef = useRef(null);
  const scrollMode = useRef("bottom");
  const runRef = useRef(null); // the answer currently being generated (so it can be stopped)
  const [draft, setDraft] = useState(null);

  const loadChats = () => api("/chats").then(setChats).catch(() => {});

  useEffect(() => {
    loadChats();
    api("/status")
      .then(setStatus)
      .catch(() => setStatus({ llm_ready: false, help: "Backend not reachable. Run: uvicorn api:app --port 8000" }));
  }, []);
  useEffect(() => {
    localStorage.setItem("level", level);
  }, [level]);
  useEffect(() => {
    if (scrollMode.current === "answer" && lastRef.current) {
      lastRef.current.scrollIntoView({ block: "start" });
      scrollMode.current = "bottom";
    } else {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, busy]);

  async function openChat(id) {
    const c = await api(`/chats/${id}`);
    scrollMode.current = "bottom";
    setActiveId(id);
    setMessages(c.messages);
  }

  function newChat() {
    setActiveId(null);
    setMessages([]);
  }

  async function removeChat(id) {
    await api(`/chats/${id}`, { method: "DELETE" });
    if (id === activeId) newChat();
    loadChats();
  }

  async function ask(body, base, before, text) {
    setBusy(true);
    const ctrl = new AbortController();
    const rid = Date.now().toString(36) + Math.random().toString(36).slice(2);
    runRef.current = { ctrl, rid, before, text };
    try {
      const r = await post("/chat", { chat_id: activeId, level, rid, ...body }, ctrl.signal);
      if (ctrl.signal.aborted || r.cancelled) return;
      scrollMode.current = "answer";
      setActiveId(r.chat_id);
      setMessages([...base, r.message]);
      loadChats();
    } catch (e) {
      if (ctrl.signal.aborted) return; // stopped on purpose, stop() already tidied up the screen
      setMessages([...base, { role: "assistant", res: { mode: "error", error: e.message } }]);
    } finally {
      if (runRef.current && runRef.current.ctrl === ctrl) {
        runRef.current = null;
        setBusy(false);
      }
    }
  }

  function stop() {
    const run = runRef.current;
    if (!run) return;
    runRef.current = null;
    run.ctrl.abort();
    post("/chat/cancel", { rid: run.rid }).catch(() => {}); // tells the backend to throw the answer away
    setBusy(false);
    if (run.before) {
      // take the question back so it can be edited and sent again
      setMessages(run.before);
      setDraft({ text: run.text, n: Date.now() });
    }
  }

  function send(text) {
    const t = text.trim();
    if (!t || busy) return;
    const base = [...messages, { role: "user", content: t }];
    setMessages(base);
    ask({ content: t }, base, messages, t);
  }

  function makeVideo(text) {
    const t = text.trim();
    if (!t || busy) return;
    post("/video", { content: t, level, chat_id: activeId })
      .then((r) => {
        if (r.chat_id) {
          setActiveId(r.chat_id);
          loadChats();
        }
        const base = [
          ...messages,
          { role: "user", content: t },
          { role: "assistant", video: { jobId: r.job_id, topic: t } },
        ];
        scrollMode.current = "answer";
        setMessages(base);
      })
      .catch((e) => {
        setMessages([...messages, { role: "user", content: t }, { role: "assistant", res: { mode: "error", error: e.message } }]);
      });
  }

  function regenerate() {
    if (busy) return;
    const base = [...messages];
    while (base.length && base[base.length - 1].role === "assistant") base.pop();
    setMessages(base);
    ask({ regenerate: true }, base);
  }

  const empty = messages.length === 0;
  const composer = <Composer onSend={send} onMakeVideo={makeVideo} onStop={stop} draft={draft} disabled={busy} />;

  return (
    <div className="app">
      <Sidebar
        open={open}
        onToggle={() => setOpen(!open)}
        chats={chats}
        activeId={activeId}
        onNew={newChat}
        onOpen={openChat}
        onDelete={removeChat}
        status={status}
      />
      <div className="main">
        <div className="topbar">
          {!open && (
            <>
              <button className="icon-btn" title="Open sidebar" onClick={() => setOpen(true)}>
                <PanelLeft size={20} />
              </button>
              <button className="icon-btn" title="New chat" onClick={newChat}>
                <SquarePen size={20} />
              </button>
            </>
          )}
          <LevelMenu level={level} setLevel={setLevel} />
          <ThemeToggle />
        </div>

        {status && !status.llm_ready && <div className="banner">{status.help}</div>}

        {empty ? (
          <div className="hero">
            <h1>What are you studying today?</h1>
            {composer}
            <div className="suggest">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="scroll">
              <div className="thread">
                {messages.map((m, i) => (
                  <div key={i} ref={i === messages.length - 1 ? lastRef : undefined}>
                    {m.video ? (
                      <div className="turn ai">
                        <VideoCard jobId={m.video.jobId} topic={m.video.topic} />
                      </div>
                    ) : (
                      <Message
                        msg={m}
                        isLast={i === messages.length - 1}
                        onRegenerate={regenerate}
                        onAsk={send}
                      />
                    )}
                  </div>
                ))}
                {busy && (
                  <div className="turn">
                    <span className="dot" />
                  </div>
                )}
                <div ref={endRef} />
              </div>
            </div>
            {composer}
            <div className="disclaimer">EE Tutor answers only from your textbook sources. Check important info.</div>
          </>
        )}
      </div>
    </div>
  );
}