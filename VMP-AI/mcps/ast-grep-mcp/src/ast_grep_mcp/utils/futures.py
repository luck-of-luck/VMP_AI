"""Daemon-thread pool helper enforcing per-item timeouts.

The corrected wait lifecycle lives here once, shared by deduplication
enrichment, batch test-coverage checks, and cross-language search:

- Wait on each future directly with ``future.result(timeout=...)`` —
  ``as_completed()`` without a timeout only yields finished futures, which
  makes a per-item timeout unreachable and lets one hung worker block forever.
- Workers are daemon threads, not a ``ThreadPoolExecutor``: the executor's
  workers are non-daemon and joined both by ``concurrent.futures``' atexit
  hook and by ``threading._shutdown``, so a single permanently hung worker
  blocks clean interpreter exit until SIGKILL. Daemon workers never block
  exit; a worker still hung at return time is abandoned, counted, and logged.
- Cancel a future the moment its wait fails — a cancelled future's work item
  is skipped by its worker (``set_running_or_notify_cancel``), so an item
  already reported as timed out can never start running later.
- Pass ``total_timeout_seconds`` to bound the total wall-clock for the entire
  call to T seconds instead of N × per-item timeout.
- Wait expiries are delivered as ``WaitTimeoutError``; a ``TimeoutError``
  raised by ``func`` itself passes through unchanged, so adopters never
  mistake a worker-raised timeout (``socket.timeout``, ``OSError(ETIMEDOUT)``
  — all the builtin ``TimeoutError`` on Python 3.11+) for a wait expiry.
"""

import queue
import threading
import time
from concurrent.futures import Future
from typing import Callable, List, Optional, Sequence, Tuple, TypeVar

from ..core.logging import get_logger

ItemT = TypeVar("ItemT")
ResultT = TypeVar("ResultT")

logger = get_logger(__name__)

_WORKER_THREAD_NAME_PREFIX = "map-timeout-worker"


class WaitTimeoutError(TimeoutError):
    """An item's wait window expired before its future delivered a result.

    Raised only by ``map_with_per_item_timeout`` (per-item wait expiry or the
    shared global deadline) — never by ``func``. A ``TimeoutError`` raised by
    ``func`` reaches ``on_error`` as-is, so ``isinstance(error,
    WaitTimeoutError)`` cleanly separates "the helper gave up waiting" from
    "the operation itself timed out" even though both are the builtin
    ``TimeoutError`` on Python 3.11+.
    """


class CancelledBeforeStartError(WaitTimeoutError):
    """A timed-out item that was never dequeued from the work queue.

    A subtype of ``WaitTimeoutError`` raised when ``future.cancel()`` returns
    ``True`` after the wait expires — meaning the item was still PENDING (queued
    but not yet picked up by a worker) when the timeout fired. The item was
    "starved" behind hung workers and never ran, as opposed to a
    ``WaitTimeoutError`` where a worker started the item but did not finish in
    time.

    Use ``isinstance(error, CancelledBeforeStartError)`` to distinguish "never
    ran" from "ran but exceeded the deadline" in error callbacks and telemetry.
    """


def _run_worker(
    work_queue: "queue.SimpleQueue[Tuple[Future[ResultT], ItemT]]",
    func: Callable[[ItemT], ResultT],
) -> None:
    """Drain the work queue, delivering each result through its future.

    A future cancelled before its work item is dequeued is skipped —
    ``set_running_or_notify_cancel`` returns False for cancelled futures,
    which is what guarantees a timed-out queued item never runs.
    """
    while True:
        try:
            future, item = work_queue.get_nowait()
        except queue.Empty:
            return
        if not future.set_running_or_notify_cancel():
            continue
        try:
            result = func(item)
        except BaseException as error:  # noqa: BLE001 — delivered via the future
            future.set_exception(error)
        else:
            future.set_result(result)


def _compute_item_timeout(deadline: Optional[float], timeout_seconds: float) -> Optional[float]:
    """Return this item's wait budget, or ``None`` when the deadline has passed."""
    if deadline is None:
        return timeout_seconds
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    return min(timeout_seconds, remaining)


def _wait_for_item(
    future: "Future[ResultT]",
    item: ItemT,
    item_timeout: float,
    on_success: Callable[[ItemT, ResultT], None],
    on_error: Callable[[ItemT, Exception], None],
) -> None:
    """Wait on one future, dispatching to the success or error callback."""
    try:
        result = future.result(timeout=item_timeout)
    except Exception as error:
        # result() re-raises a worker-raised exception as the exact
        # stored object; a wait expiry raises a fresh TimeoutError.
        # Only the latter becomes WaitTimeoutError — worker-raised
        # timeouts pass through with their real message.
        if isinstance(error, TimeoutError) and not (future.done() and future.exception() is error):
            # Cancel before building the error: future.cancel() returns True
            # when the future is still PENDING (never picked up by a worker),
            # False when it is already RUNNING or DONE. This distinguishes
            # "starved behind hung workers — never ran" from "ran but exceeded
            # the deadline", giving callers cleaner telemetry (CR-07).
            was_pending = future.cancel()
            if was_pending:
                error = CancelledBeforeStartError(
                    f"Cancelled before start (starved after {item_timeout} seconds)"
                )
            else:
                error = WaitTimeoutError(f"No result within {item_timeout} seconds")
        else:
            # Cancel is a no-op for running/done futures; still called so a
            # queued future that squeezed past the timeout check never runs.
            future.cancel()
        on_error(item, error)
    else:
        on_success(item, result)


def _cancel_and_drain(
    pairs: List[Tuple["Future[ResultT]", ItemT]],
    work_queue: "queue.SimpleQueue[Tuple[Future[ResultT], ItemT]]",
    timeout_seconds: float,
) -> None:
    """Cancel queued work, drain the queue, and log abandoned workers."""
    for future, _ in pairs:
        future.cancel()
    # Drain the queue so a hung worker's queue reference cannot pin
    # cancelled items in memory (workers skip cancelled futures anyway).
    while True:
        try:
            work_queue.get_nowait()
        except queue.Empty:
            break
    abandoned_count = sum(1 for future, _ in pairs if future.running())
    if abandoned_count:
        logger.warning(
            "abandoned_worker_threads",
            abandoned_count=abandoned_count,
            timeout_seconds=timeout_seconds,
        )


def map_with_per_item_timeout(
    items: Sequence[ItemT],
    func: Callable[[ItemT], ResultT],
    *,
    timeout_seconds: float,
    max_workers: int,
    on_success: Callable[[ItemT, ResultT], None],
    on_error: Callable[[ItemT, Exception], None],
    total_timeout_seconds: Optional[float] = None,
) -> None:
    """Run ``func`` over ``items`` on daemon worker threads, bounding each wait.

    Waits happen in submission order, each bounded by ``timeout_seconds``
    measured from when the wait loop reaches that item's future — so total
    wall clock is up to ``len(items) * timeout_seconds`` when everything
    hangs, and an item queued behind hung workers is reported as timed out
    even though it never ran.

    When ``total_timeout_seconds`` is set, a shared deadline is computed once
    at entry and caps every item's wait at ``min(timeout_seconds, remaining)``.
    Items whose deadline has already expired when the loop reaches them are
    reported as ``TimeoutError`` immediately without submitting a
    ``future.result()`` call, so total wall-clock is bounded to
    ``total_timeout_seconds`` regardless of how many items hang.

    A worker that outlives its timeout is abandoned: it keeps running but its
    result is discarded. ``func`` therefore must not mutate state the caller
    reads after this returns — hand workers private copies and merge results
    in ``on_success``. Workers are daemon threads: an abandoned worker keeps
    its thread (and pins its in-flight item) until it finishes, but never
    blocks interpreter exit — at exit it is terminated abruptly, so ``func``
    must not perform writes that corrupt state if killed mid-operation.
    Workers still running at return time are counted and logged as a warning
    (``abandoned_worker_threads``) so leak accumulation is observable; the
    work queue is drained on return so cancelled queued items are not pinned
    in memory by a hung worker's reference to it.

    Every failed wait cancels its future before ``on_error`` runs: an item
    still queued when it is reported failed can never start later, even if
    the callback unblocks a worker (cancelling a running or finished future
    is a no-op — running workers are abandoned, not stopped).

    Callbacks must not raise: a raising callback aborts the wait loop, skipping
    callbacks for every remaining item (queued work is still cancelled).

    Args:
        items: Work items, one future each.
        func: Called as ``func(item)`` on a daemon worker thread.
        timeout_seconds: Maximum seconds to wait for each individual item.
        max_workers: Number of worker threads for this call.
        on_success: Called on the calling thread with ``(item, result)`` for
            each item completing within its wait window.
        on_error: Called on the calling thread with ``(item, exception)`` when
            the wait timed out (a ``WaitTimeoutError``) or ``func`` raised
            (the original exception, including a ``func``-raised
            ``TimeoutError``, which is never rewrapped).
        total_timeout_seconds: Optional shared wall-clock deadline for all
            items combined. When set, each item's wait is capped at
            ``min(timeout_seconds, remaining_time)`` and items reached after
            the deadline has elapsed are reported as ``WaitTimeoutError``
            immediately. Default ``None`` disables the shared deadline.
    """
    if max_workers < 1:
        raise ValueError(f"max_workers must be >= 1, got {max_workers}")
    if not items:
        return

    deadline: Optional[float] = time.monotonic() + total_timeout_seconds if total_timeout_seconds is not None else None

    pairs: List[Tuple[Future[ResultT], ItemT]] = [(Future(), item) for item in items]
    work_queue: "queue.SimpleQueue[Tuple[Future[ResultT], ItemT]]" = queue.SimpleQueue()
    for pair in pairs:
        work_queue.put(pair)

    try:
        for index in range(min(max_workers, len(pairs))):
            threading.Thread(
                target=_run_worker,
                args=(work_queue, func),
                name=f"{_WORKER_THREAD_NAME_PREFIX}-{index}",
                daemon=True,
            ).start()
        for future, item in pairs:
            item_timeout = _compute_item_timeout(deadline, timeout_seconds)
            if item_timeout is None:
                future.cancel()
                on_error(item, WaitTimeoutError("Global deadline exceeded"))
                continue
            _wait_for_item(future, item, item_timeout, on_success, on_error)
    finally:
        # Threads cannot be killed; cancel queued work that never started and
        # abandon hung workers rather than blocking the caller. Runs even if a
        # callback raised mid-loop.
        _cancel_and_drain(pairs, work_queue, timeout_seconds)
