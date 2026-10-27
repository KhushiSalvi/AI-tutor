"""Background process that renders one video. Started by core/tutor.py (never import this in the web server)."""
import json
import sys
import traceback
from pathlib import Path

from core.video.animate import build_video

VIDEO_DIR = Path("data/videos")


def main(job_id):
    work = VIDEO_DIR / job_id
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))

    def progress(msg):
        print(msg, flush=True)
        try:
            (work / "progress.json").write_text(json.dumps({"detail": msg}), encoding="utf-8")
        except OSError:
            pass

    final, total = build_video(plan["scenes"], VIDEO_DIR, job_id, progress=progress)
    (work / "result.json").write_text(json.dumps({"seconds": total}), encoding="utf-8")
    print(f"DONE {final} ({total:.0f}s of video)", flush=True)


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception:
        traceback.print_exc()
        sys.exit(1)
