"""Add NPTEL lectures (with timestamps) so the video button can show a matching clip.

    python -m core.nptel.ingest "<YouTube playlist or video URL>" --course "Basic Electronics"
    python -m core.nptel.ingest --file urls.txt --course "Digital Circuits"

Needs once:  pip install yt-dlp youtube-transcript-api
It lists the videos, downloads each lecture's captions (text + timestamps only, never the video), cuts them
into ~75 s windows and writes data/nptel/<video_id>.jsonl. Re-running skips videos already done.
Lectures without captions are skipped and listed at the end.
"""
import argparse
import json
import re
import time
from pathlib import Path

OUT = Path("data/nptel")
LANGS = ["en", "en-IN", "en-US", "en-GB"]


def list_videos(url):
    from yt_dlp import YoutubeDL

    with YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True}) as y:
        info = y.extract_info(url, download=False)
    entries = info.get("entries") or [info]
    return [(e["id"], e.get("title") or e["id"]) for e in entries if e and e.get("id")]


def get_transcript(video_id):
    """-> list of (start_seconds, duration, text); works with old and new youtube-transcript-api versions."""
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=LANGS)
        return [(s.start, s.duration, s.text) for s in fetched]
    except AttributeError:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=LANGS)
        return [(d["start"], d["duration"], d["text"]) for d in data]


def clean(t):
    t = re.sub(r"\[[^\]]*\]", " ", t)          # [Music], [Applause]
    t = t.replace(">>", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", t).strip()


def windows(snips, size=75, step=45, min_words=15):
    if not snips:
        return []
    end_all = snips[-1][0] + snips[-1][1]
    out, t = [], 0.0
    while t < end_all:
        text = " ".join(clean(s[2]) for s in snips if t <= s[0] < t + size)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text.split()) >= min_words:
            out.append({"start": round(t, 1), "end": round(t + size, 1), "text": text})
        t += step
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file", help="text file with one playlist/video URL per line")
    ap.add_argument("--course", default="NPTEL")
    ap.add_argument("--limit", type=int, default=0, help="only the first N videos of each URL (for a quick test)")
    a = ap.parse_args()
    urls = list(a.urls)
    if a.file:
        urls += [x.strip() for x in Path(a.file).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    if not urls:
        ap.error("give a playlist/video URL or --file urls.txt")
    OUT.mkdir(parents=True, exist_ok=True)

    done = skipped = 0
    no_captions = []
    for url in urls:
        vids = list_videos(url)
        if a.limit:
            vids = vids[: a.limit]
        print(f"\n{url}: {len(vids)} video(s)")
        for vid, title in vids:
            f = OUT / f"{vid}.jsonl"
            if f.exists():
                skipped += 1
                continue
            try:
                snips = get_transcript(vid)
            except Exception as e:
                no_captions.append(f"{title} ({type(e).__name__})")
                print(f"  - no captions: {title}")
                continue
            segs = windows(snips)
            if not segs:
                no_captions.append(title)
                continue
            with open(f, "w", encoding="utf-8") as fh:
                for s in segs:
                    fh.write(json.dumps({"video_id": vid, "title": title, "course": a.course, **s}, ensure_ascii=False) + "\n")
            done += 1
            print(f"  + {title}: {len(segs)} windows")
            time.sleep(0.7)   # be polite to YouTube
    print(f"\nAdded {done} lecture(s), skipped {skipped} already done, {len(no_captions)} without usable captions.")
    if no_captions:
        print("Without captions:", "; ".join(no_captions[:15]) + (" ..." if len(no_captions) > 15 else ""))


if __name__ == "__main__":
    main()
