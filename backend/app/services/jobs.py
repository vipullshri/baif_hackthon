"""
Background job worker.

A small thread-pool executes the (CPU-bound) translation pipeline off the request
thread, so the API stays responsive and the UI can poll/stream progress.

A single worker is used by default to avoid CPU oversubscription on BAIF's target
hardware. For higher throughput, raise `max_workers` or swap this module for
Celery + Redis without touching the pipeline code.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app.services import cancellation
from app.services.pipeline import process_job

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bhashasetu-worker")


def submit_job(job_id: str) -> None:
    """Queue a job for background processing."""
    logger.info("Queuing job %s", job_id)
    future = _executor.submit(process_job, job_id)
    cancellation.register(job_id, future)


def shutdown() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)