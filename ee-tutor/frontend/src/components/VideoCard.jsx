import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Clapperboard, Film } from "./Icons.jsx";
import { api } from "../api.js";

const LABELS = {
  planning: "Planning the video from your sources…",
  rendering: "Rendering scenes and narration…",
};

function mmss(s) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

// a short clip of the matching NPTEL lecture, played straight from YouTube
function NptelClip({ clip }) {
  const src =
    `https://www.youtube-nocookie.com/embed/${clip.video_id}` +
    `?start=${Math.floor(clip.start)}&end=${Math.ceil(clip.end)}&rel=0&modestbranding=1`;
  const link = `https://www.youtube.com/watch?v=${clip.video_id}&t=${Math.floor(clip.start)}s`;
  return (
    <div className="video-card nptel-card">
      <div className="video-card-title">
        <Film size={16} /> NPTEL lecture clip{clip.course ? ` · ${clip.course}` : ""}
      </div>
      <div className="video-card-sub">
        {clip.title} · {mmss(clip.start)}–{mmss(clip.end)}
      </div>
      <div className="nptel-frame">
        <iframe
          src={src}
          title={clip.title}
          loading="lazy"
          allow="accelerometer; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
        />
      </div>
      <div className="video-card-sub">
        “{clip.snippet}”{" "}
        <a className="link" href={link} target="_blank" rel="noreferrer">
          Open on YouTube
        </a>
      </div>
    </div>
  );
}

export default function VideoCard({ jobId, topic }) {
  const [status, setStatus] = useState({ status: "planning", title: "", seconds: 0, error: "" });
  const timer = useRef(null);

  useEffect(() => {
    let stopped = false;
    async function poll() {
      try {
        const s = await api(`/video/${jobId}`);
        if (stopped) return;
        setStatus(s);
        if (s.status !== "done" && s.status !== "error") {
          timer.current = setTimeout(poll, 2000);
        }
      } catch {
        if (!stopped) timer.current = setTimeout(poll, 3000);
      }
    }
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer.current);
    };
  }, [jobId]);

  const nptel = status.nptel ? <NptelClip clip={status.nptel} /> : null;

  if (status.status === "error") {
    return (
      <>
        <div className="video-card video-card-error">
          <AlertTriangle size={18} />
          <div>
            <div className="video-card-title">Couldn't make an animated video for this</div>
            <div className="video-card-sub">{status.error || "The sources don't cover this topic well enough."}</div>
          </div>
        </div>
        {nptel}
      </>
    );
  }

  if (status.status === "done") {
    return (
      <>
        <div className="video-card">
          <div className="video-card-title">
            <Film size={16} /> {status.title || topic}
          </div>
          <video controls preload="metadata" src={status.url}>
            Your browser can't play this video.
          </video>
          <div className="video-card-sub">{Math.round(status.seconds)}s explainer, generated from your sources.</div>
        </div>
        {nptel}
      </>
    );
  }

  return (
    <>
      <div className="video-card video-card-loading">
        <div className="spinner" />
        <div>
          <div className="video-card-title">
            <Clapperboard size={16} /> Making a video: {topic}
          </div>
          <div className="video-card-sub">{status.detail || LABELS[status.status] || "Working…"}</div>
        </div>
      </div>
      {nptel}
    </>
  );
}
