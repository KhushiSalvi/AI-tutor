"""Single-slot FIFO render queue.

Only ONE video renders at a time. Additional jobs wait with status 'queued'
and a numeric position (2 = next up, 3 = after that, …).

Thread-safe: all mutations happen under _LOCK.

API
---
enqueue(job_id, fn, *args, **kwargs)
    Submit a render job. fn(*args, **kwargs) will be called when the slot is free.
    The job_id is used only for position tracking.

get_position(job_id) -> int | None
    Returns the queue position (1 = rendering now, 2 = queued next, …).
    Returns None if job_id is not in the queue.

cancel(job_id) -> bool
    Remove a waiting (not-yet-started) job from the queue. Returns True if removed.

cleanup_old_work_dirs(video_dir, max_age_hours=24)
    Delete per-job work subdirectories for jobs that finished more than
    max_age_hours ago. Keeps the .mp4 and .json metadata files; only
    deletes the intermediate work/ folder (plan.json, scene_N.mp4, worker.log…).
"""
import threading
import time
from collections import deque
from pathlib import Path

_LOCK   = threading.Lock()
_QUEUE  = deque()          # list of (job_id, fn, args, kwargs)
_ACTIVE = None             # job_id of the currently-rendering job (or None)
_DONE   = {}               # job_id -> finish_time (for cleanup tracking)


def enqueue(job_id: str, fn, *args, **kwargs) -> None:
    """Add job to the queue and start processing if the slot is free."""
    with _LOCK:
        _QUEUE.append((job_id, fn, args, kwargs))
    _maybe_start()


def get_position(job_id: str):
    """Return 1-based queue position (1 = rendering now). None if not in queue."""
    with _LOCK:
        if _ACTIVE == job_id:
            return 1
        for i, (jid, *_) in enumerate(_QUEUE):
            if jid == job_id:
                # +2: 1 for the active job, +1 for 1-based index
                return 2 + i
    return None


def cancel(job_id: str) -> bool:
    """Remove a waiting job. Returns True if it was in the queue."""
    with _LOCK:
        for i, (jid, *_) in enumerate(_QUEUE):
            if jid == job_id:
                del _QUEUE[i]
                return True
    return False


def cleanup_old_work_dirs(video_dir, max_age_hours: float = 24.0) -> int:
    """Delete intermediate work subdirectories older than max_age_hours.

    Keeps the final .mp4 and .json metadata files.
    Returns the number of directories removed.
    """
    removed = 0
    cutoff  = time.time() - max_age_hours * 3600
    video_path = Path(video_dir)
    if not video_path.exists():
        return 0
    for d in video_path.iterdir():
        if not d.is_dir():
            continue
        try:
            mtime = d.stat().st_mtime
            if mtime < cutoff:
                import shutil
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except OSError:
            pass
    return removed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _maybe_start():
    """If the slot is free and there's a job waiting, start it in a new thread."""
    with _LOCK:
        global _ACTIVE
        if _ACTIVE is not None:
            return  # slot busy
        if not _QUEUE:
            return  # nothing waiting
        job_id, fn, args, kwargs = _QUEUE.popleft()
        _ACTIVE = job_id

    t = threading.Thread(target=_run_job, args=(job_id, fn, args, kwargs), daemon=True)
    t.start()


def _run_job(job_id, fn, args, kwargs):
    """Run the job, then release the slot and start the next one."""
    global _ACTIVE
    try:
        fn(*args, **kwargs)
    finally:
        with _LOCK:
            _DONE[job_id] = time.time()
            _ACTIVE = None
        _maybe_start()
