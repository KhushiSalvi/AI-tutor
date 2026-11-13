import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Clapperboard, Film, Play } from "./Icons.jsx";
import { api } from "../api.js";

const LABELS = {
  planning: "Planning the video from your sources…",
  rendering: "Rendering scenes and narration…",
  queued: "Queued behind another render…",
};

function mmss(s) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

// Interactive web video cards (official embed, loaded only on click)
function WebVideosRow({ videos, title = "Related Web Videos" }) {
  const [activeVid, setActiveVid] = useState(null);
  if (!videos || videos.length === 0) return null;

  return (
    <div className="web-videos-section" style={{ marginTop: "16px" }}>
      <div style={{ fontSize: "13px", fontWeight: 600, color: "#e0af68", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
        <span>🌐 {title}</span>
        <span style={{ fontSize: "11px", fontWeight: 400, color: "#7a829e" }}>(Web video, not made from your syllabus)</span>
      </div>

      {activeVid && (
        <div style={{ marginBottom: "14px", borderRadius: "10px", overflow: "hidden", aspectRatio: "16/9", background: "#000" }}>
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${activeVid}?autoplay=1&rel=0&modestbranding=1`}
            title="Web Video Player"
            width="100%"
            height="100%"
            allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen"
            allowFullScreen
            style={{ border: "none" }}
          />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "10px" }}>
        {videos.map((v) => (
          <div
            key={v.id}
            onClick={() => setActiveVid(v.id)}
            style={{
              cursor: "pointer",
              background: "#1a1b26",
              borderRadius: "8px",
              border: activeVid === v.id ? "1px solid #e0af68" : "1px solid #282836",
              overflow: "hidden",
              transition: "transform 0.15s, border-color 0.15s",
            }}
          >
            <div style={{ position: "relative", width: "100%", height: "115px", background: "#101014" }}>
              <img
                src={v.thumbnail}
                alt={v.title}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                loading="lazy"
              />
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: "rgba(0,0,0,0.3)",
                }}
              >
                <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Play size={16} fill="#fff" />
                </div>
              </div>
              <div
                style={{
                  position: "absolute",
                  bottom: "6px",
                  right: "6px",
                  background: "rgba(0,0,0,0.8)",
                  padding: "2px 5px",
                  borderRadius: "4px",
                  fontSize: "10px",
                  color: "#fff",
                }}
              >
                {mmss(v.duration)}
              </div>
            </div>
            <div style={{ padding: "8px 10px" }}>
              <div style={{ fontSize: "12px", fontWeight: 600, color: "#c0caf5", maxHeight: "32px", overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                {v.title}
              </div>
              <div style={{ fontSize: "11px", color: "#7a829e", marginTop: "4px" }}>
                {v.channel}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// A short clip of the matching NPTEL lecture, played straight from YouTube
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
  const webVideos = status.web_videos || [];

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
        {webVideos.length > 0 && <WebVideosRow videos={webVideos} title="Suggested Web Videos" />}
        {nptel}
      </>
    );
  }

  // NOT_COVERED Video Route: Job completed with kind="web_videos"
  if (status.status === "done" && status.kind === "web_videos") {
    return (
      <div className="video-card" style={{ padding: "16px" }}>
        <div className="video-card-title" style={{ color: "#e0af68" }}>
          <Film size={16} /> Not in your syllabus: Web Videos for {topic}
        </div>
        <div className="video-card-sub" style={{ marginBottom: "12px" }}>
          This topic is outside your indexed books. Here are the top educational videos found on the web:
        </div>
        <WebVideosRow videos={webVideos} title="Curated YouTube Lectures" />
        {nptel}
      </div>
    );
  }

  // COVERED or PARTIAL local render done
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
        {webVideos.length > 0 && <WebVideosRow videos={webVideos} title="Related Web Videos" />}
        {nptel}
      </>
    );
  }

  const isQueued = status.status === "queued";
  const queuePos = status.queue_position;

  return (
    <>
      <div className="video-card video-card-loading">
        <div className="spinner" />
        <div style={{ flex: 1 }}>
          <div className="video-card-title" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Clapperboard size={16} /> Making a video: {topic}
            {isQueued && queuePos && (
              <span style={{
                fontSize: "11px", fontWeight: 700, padding: "2px 8px",
                borderRadius: "10px", background: "rgba(224,175,104,0.15)",
                color: "#e0af68", border: "1px solid rgba(224,175,104,0.3)",
                marginLeft: "4px",
              }}>
                #{queuePos} in queue
              </span>
            )}
          </div>
          <div className="video-card-sub">
            {isQueued
              ? `Waiting for the previous video to finish… (position ${queuePos} of ${queuePos})`
              : (status.detail || LABELS[status.status] || "Working…")}
          </div>
        </div>
      </div>
      {nptel}
    </>
  );
}
