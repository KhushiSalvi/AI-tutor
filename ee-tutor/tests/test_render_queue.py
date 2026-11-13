"""Tests for core/video/render_queue.py — FIFO render queue."""
import sys
import time
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import core.video.render_queue as rq


def _reset():
    """Reset module state between tests."""
    with rq._LOCK:
        rq._QUEUE.clear()
        rq._ACTIVE = None
        rq._DONE.clear()


def test_enqueue_runs_job():
    _reset()
    done = threading.Event()
    rq.enqueue("j1", lambda: done.set())
    assert done.wait(timeout=2), "Job never ran"
    _reset()


def test_get_position_active_is_1():
    _reset()
    started = threading.Event()
    finished = threading.Event()

    def slow_job():
        started.set()
        finished.wait(timeout=3)

    rq.enqueue("j1", slow_job)
    started.wait(timeout=2)
    pos = rq.get_position("j1")
    finished.set()
    assert pos == 1
    _reset()


def test_queued_job_gets_position_2():
    _reset()
    started = threading.Event()
    allow_finish = threading.Event()
    j2_started = threading.Event()

    def slow_job():
        started.set()
        allow_finish.wait(timeout=3)

    def slow_j2():
        j2_started.set()

    rq.enqueue("j1", slow_job)
    started.wait(timeout=2)
    rq.enqueue("j2", slow_j2)
    # Check position before releasing j1
    pos = rq.get_position("j2")
    allow_finish.set()
    j2_started.wait(timeout=2)  # let j2 finish
    assert pos == 2
    _reset()


def test_cancel_removes_waiting_job():
    _reset()
    started = threading.Event()
    allow_finish = threading.Event()

    def slow_job():
        started.set()
        allow_finish.wait(timeout=3)

    rq.enqueue("j1", slow_job)
    started.wait(timeout=2)
    rq.enqueue("j2", lambda: None)
    removed = rq.cancel("j2")
    allow_finish.set()
    assert removed is True
    assert rq.get_position("j2") is None
    _reset()


def test_cancel_active_job_returns_false():
    _reset()
    started = threading.Event()
    allow_finish = threading.Event()

    def slow_job():
        started.set()
        allow_finish.wait(timeout=3)

    rq.enqueue("j1", slow_job)
    started.wait(timeout=2)
    removed = rq.cancel("j1")  # active jobs can't be cancelled
    allow_finish.set()
    assert removed is False
    _reset()


def test_cleanup_removes_old_dirs():
    import tempfile, shutil
    _reset()
    tmp_path = Path(tempfile.mkdtemp())
    try:
        # Create a fake old work dir
        old_dir = tmp_path / "oldjob"
        old_dir.mkdir()
        # Set its mtime to 25 hours ago
        old_time = time.time() - 25 * 3600
        import os
        os.utime(old_dir, (old_time, old_time))

        # Create a recent dir
        new_dir = tmp_path / "newjob"
        new_dir.mkdir()

        removed = rq.cleanup_old_work_dirs(tmp_path, max_age_hours=24)
        assert removed >= 1
        assert not old_dir.exists()
        assert new_dir.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
    _reset()
