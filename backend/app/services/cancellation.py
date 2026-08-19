"""
Cooperative job cancellation registry.

Kept in its own module (importing neither `jobs` nor `pipeline`) so both the
worker layer and the pipeline can share it without a circular import.

Two mechanisms are combined:

* If a job is still queued, its `Future` can be cancelled outright before it
  ever starts.
* If a job is already running, we record a cancellation *request*; the pipeline
  polls :func:`is_requested` at stage boundaries and aborts cooperatively.
"""
from __future__ import annotations

import threading
from concurrent.futures import Future

_lock = threading.Lock()
_requested: set[str] = set()
_futures: dict[str, Future] = {}


def register(job_id: str, future: Future) -> None:
    """Track the worker future for a queued/running job."""
    with _lock:
        _futures[job_id] = future


def request(job_id: str) -> Future | None:
    """Mark a job for cancellation; return its future (if any) for the caller."""
    with _lock:
        _requested.add(job_id)
        return _futures.get(job_id)


def is_requested(job_id: str) -> bool:
    with _lock:
        return job_id in _requested


def clear(job_id: str) -> None:
    """Forget all cancellation state for a finished/aborted job."""
    with _lock:
        _requested.discard(job_id)
        _futures.pop(job_id, None)