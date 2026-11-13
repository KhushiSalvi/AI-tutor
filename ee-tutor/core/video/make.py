"""CLI for testing the agentic video generator without the UI.

Usage:
  python -m core.video.make "working of a MOSFET" --seconds 60 --trace
  python -m core.video.make "how a transformer works"
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Load .env from project root
def _load_env():
    env = Path(__file__).parent.parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip("\"'")
        os.environ.setdefault(k.strip(), v)

_load_env()


def main():
    parser = argparse.ArgumentParser(description="EE Tutor agentic video generator")
    parser.add_argument("query", help="Topic to explain")
    parser.add_argument("--seconds", type=int, default=90,
                        help="Target video length in seconds (sets VIDEO_SECONDS env var)")
    parser.add_argument("--level", default="beginner", choices=["beginner", "advanced"])
    parser.add_argument("--trace", action="store_true", help="Print full tool trace after generation")
    parser.add_argument("--job-id", default=None, help="Override job ID (for testing)")
    args = parser.parse_args()

    os.environ.setdefault("VIDEO_SECONDS", str(args.seconds))

    import uuid
    job_id = args.job_id or uuid.uuid4().hex[:12]

    print(f"\n🎬 EE Tutor Video Agent")
    print(f"   Query : {args.query}")
    print(f"   Level : {args.level}")
    print(f"   Job ID: {job_id}")
    print(f"   Target: ~{args.seconds}s\n")

    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    from core.video.agent import run_video_agent

    def progress(msg):
        print(f"  ▸ {msg}", flush=True)

    try:
        job = run_video_agent(args.query, args.level, job_id, progress_fn=progress)
    except Exception as e:
        print(f"\n❌ Agent crashed: {e}")
        raise

    print(f"\n{'='*60}")
    if job.final_mp4 and Path(job.final_mp4).exists():
        print(f"✅ Video ready: {job.final_mp4}")
        total_s = sum(sc.audio_duration for sc in job.scenes)
        print(f"   Duration  : {total_s:.1f}s")
        print(f"   Scenes    : {len(job.scenes)}")
        print(f"   Tool calls: {job.tool_calls}")
    else:
        print(f"⚠️  Video not generated. Error: {job.error or 'unknown'}")

    if args.trace and job.trace:
        print(f"\n{'─'*60}")
        print("TOOL TRACE:")
        for i, call in enumerate(job.trace, 1):
            status = "✓" if "error" not in call["result"] else "✗"
            args_str = ", ".join(f"{k}={repr(v)[:25]}" for k, v in list(call["args"].items())[:3])
            print(f"  {i:2}. {status} {call['tool']}({args_str}) [{call['ms']}ms]")
            if "error" in call["result"]:
                print(f"       ERROR: {call['result']['error']}")

    # Print scene summary
    if job.scenes:
        print(f"\nSCENE SUMMARY:")
        for sc in job.scenes:
            status = "✅" if sc.done else "⚠️"
            print(f"  {status} Scene {sc.id}: [{sc.scene_type}] {sc.title}")
            print(f"       bg={sc.background_spec.get('kind','?')} "
                  f"anim={sc.animation_spec.get('type','?')} "
                  f"dur={sc.audio_duration:.1f}s")

    print()


if __name__ == "__main__":
    main()
