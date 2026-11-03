"""Unit tests for utils.futures.map_with_per_item_timeout.

The shared helper owns the corrected wait lifecycle (per-item
future.result(timeout=...) + shutdown(wait=False, cancel_futures=True))
adopted by deduplication enrichment, batch coverage, and cross-language
search.
"""

import gc
import subprocess
import sys
import textwrap
import threading
import time
import weakref

import pytest

from ast_grep_mcp.utils import futures as futures_module
from ast_grep_mcp.utils.futures import CancelledBeforeStartError, WaitTimeoutError, map_with_per_item_timeout

TIMEOUT_SECONDS = 1
PROMPT_RETURN_BOUND_SECONDS = 10
HUNG_WORKER_SAFETY_NET_SECONDS = 30
SUBPROCESS_EXIT_BOUND_SECONDS = 30


class TestMapWithPerItemTimeout:
    def test_success_results_delivered_per_item(self):
        results = {}
        errors = {}

        map_with_per_item_timeout(
            ["a", "b", "c"],
            lambda item: item.upper(),
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=2,
            on_success=lambda item, result: results.__setitem__(item, result),
            on_error=lambda item, error: errors.__setitem__(item, error),
        )

        assert results == {"a": "A", "b": "B", "c": "C"}
        assert errors == {}

    def test_worker_exception_routed_to_on_error(self):
        results = {}
        errors = {}

        def func(item):
            if item == "bad":
                raise ValueError("boom")
            return item

        map_with_per_item_timeout(
            ["ok", "bad"],
            func,
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=2,
            on_success=lambda item, result: results.__setitem__(item, result),
            on_error=lambda item, error: errors.__setitem__(item, error),
        )

        assert results == {"ok": "ok"}
        assert isinstance(errors["bad"], ValueError)
        assert str(errors["bad"]) == "boom"

    def test_hung_worker_times_out_without_blocking_return(self):
        release = threading.Event()
        results = {}
        errors = {}

        def func(item):
            if item == "hung":
                release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS)
            return item

        try:
            start = time.monotonic()
            map_with_per_item_timeout(
                ["hung", "fast"],
                func,
                timeout_seconds=TIMEOUT_SECONDS,
                max_workers=2,
                on_success=lambda item, result: results.__setitem__(item, result),
                on_error=lambda item, error: errors.__setitem__(item, error),
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < PROMPT_RETURN_BOUND_SECONDS, f"helper should return promptly, took {elapsed:.1f}s"
        assert isinstance(errors["hung"], TimeoutError)
        assert results == {"fast": "fast"}

    def test_item_starved_behind_hung_workers_reported_as_error(self):
        release = threading.Event()
        errors = {}

        def func(item):
            release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            map_with_per_item_timeout(
                ["h1", "h2", "starved"],
                func,
                timeout_seconds=TIMEOUT_SECONDS,
                max_workers=2,
                on_success=lambda item, result: None,
                on_error=lambda item, error: errors.__setitem__(item, error),
            )
        finally:
            release.set()

        assert set(errors) == {"h1", "h2", "starved"}
        assert all(isinstance(error, TimeoutError) for error in errors.values())

    def test_empty_items_is_a_no_op(self):
        map_with_per_item_timeout(
            [],
            lambda item: item,
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=1,
            on_success=lambda item, result: (_ for _ in ()).throw(AssertionError("unexpected success callback")),
            on_error=lambda item, error: (_ for _ in ()).throw(AssertionError("unexpected error callback")),
        )

    def test_callbacks_run_on_calling_thread(self):
        calling_thread = threading.current_thread()
        callback_threads = []

        map_with_per_item_timeout(
            ["a", "b"],
            lambda item: item,
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=2,
            on_success=lambda item, result: callback_threads.append(threading.current_thread()),
            on_error=lambda item, error: callback_threads.append(threading.current_thread()),
        )

        assert callback_threads and all(thread is calling_thread for thread in callback_threads)


class TestTimedOutPendingFutureCancellation:
    """A queued item whose wait timed out must never execute later (CR-06)."""

    def test_timed_out_queued_item_never_runs_after_worker_frees(self):
        release = threading.Event()
        executed = []
        results = {}
        errors = {}

        def func(item):
            executed.append(item)
            if item == "hung":
                release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS)
            return item

        def on_error(item, error):
            errors[item] = error
            if item == "queued":
                # Free the hung worker while the loop is still waiting on
                # "last". Pre-fix, the freed worker dequeued and ran "queued"
                # even though it was already reported as timed out; post-fix
                # "queued" was cancelled before this callback ran.
                release.set()

        try:
            map_with_per_item_timeout(
                ["hung", "queued", "last"],
                func,
                timeout_seconds=TIMEOUT_SECONDS,
                max_workers=1,
                on_success=lambda item, result: results.__setitem__(item, result),
                on_error=on_error,
            )
        finally:
            release.set()

        assert "queued" not in executed, "timed-out queued item must not run after a worker frees"
        assert isinstance(errors["hung"], TimeoutError)
        assert isinstance(errors["queued"], TimeoutError)


class TestCancelledBeforeStartDisambiguation:
    """Never-started items must be labelled CancelledBeforeStartError, not
    WaitTimeoutError, so callers can distinguish "starved" from "ran but slow"
    in error callbacks and telemetry (CR-07)."""

    def test_starved_item_raises_cancelled_before_start_error(self):
        """A queued item that times out before a worker picks it up is reported as
        CancelledBeforeStartError, not a generic WaitTimeoutError."""
        release = threading.Event()
        errors = {}

        def func(item):
            if item == "hung":
                release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            map_with_per_item_timeout(
                ["hung", "starved"],
                func,
                timeout_seconds=TIMEOUT_SECONDS,
                max_workers=1,  # only 1 worker; "starved" is queued behind "hung"
                on_success=lambda item, result: None,
                on_error=lambda item, error: errors.__setitem__(item, error),
            )
        finally:
            release.set()

        # "hung" ran but exceeded the deadline → WaitTimeoutError (not CancelledBefore)
        assert isinstance(errors["hung"], WaitTimeoutError)
        assert not isinstance(errors["hung"], CancelledBeforeStartError)
        # "starved" never dequeued → CancelledBeforeStartError (subtype of WaitTimeoutError)
        assert isinstance(errors["starved"], CancelledBeforeStartError)
        assert isinstance(errors["starved"], WaitTimeoutError)  # is-a WaitTimeoutError

    def test_running_timed_out_item_is_not_cancelled_before_start(self):
        """A running item that exceeds the deadline is WaitTimeoutError, not
        CancelledBeforeStartError."""
        release = threading.Event()
        errors = {}

        def func(item):
            release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            map_with_per_item_timeout(
                ["item"],
                func,
                timeout_seconds=TIMEOUT_SECONDS,
                max_workers=1,
                on_success=lambda item, result: None,
                on_error=lambda item, error: errors.__setitem__(item, error),
            )
        finally:
            release.set()

        assert isinstance(errors["item"], WaitTimeoutError)
        assert not isinstance(errors["item"], CancelledBeforeStartError)


class TestWaitTimeoutDisambiguation:
    """A TimeoutError raised by func must not be misread as a wait expiry (CR-08)."""

    def test_worker_raised_timeout_error_passes_through_unchanged(self):
        raised = TimeoutError("[Errno 60] read timed out after 2s")
        errors = {}

        def func(item):
            raise raised

        map_with_per_item_timeout(
            ["x"],
            func,
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=1,
            on_success=lambda item, result: None,
            on_error=lambda item, error: errors.__setitem__(item, error),
        )

        assert errors["x"] is raised
        assert not isinstance(errors["x"], WaitTimeoutError)

    def test_wait_expiry_delivered_as_wait_timeout_error(self):
        release = threading.Event()
        errors = {}

        try:
            map_with_per_item_timeout(
                ["hung"],
                lambda item: release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS),
                timeout_seconds=0.2,
                max_workers=1,
                on_success=lambda item, result: None,
                on_error=lambda item, error: errors.__setitem__(item, error),
            )
        finally:
            release.set()

        assert isinstance(errors["hung"], WaitTimeoutError)
        assert str(errors["hung"])

    def test_expired_global_deadline_delivered_as_wait_timeout_error(self):
        errors = {}

        def func(item):
            if item == "slow":
                time.sleep(0.5)

        map_with_per_item_timeout(
            ["slow", "after_deadline"],
            func,
            timeout_seconds=10.0,
            max_workers=1,
            on_success=lambda item, result: None,
            on_error=lambda item, error: errors.__setitem__(item, error),
            total_timeout_seconds=0.3,
        )

        assert isinstance(errors["after_deadline"], WaitTimeoutError)


class TestPoolHardening:
    """Guards restoring ThreadPoolExecutor parity lost in the daemon-pool rewrite."""

    def test_zero_workers_rejected(self):
        with pytest.raises(ValueError, match="max_workers"):
            map_with_per_item_timeout(
                ["a"],
                lambda item: item,
                timeout_seconds=TIMEOUT_SECONDS,
                max_workers=0,
                on_success=lambda item, result: None,
                on_error=lambda item, error: None,
            )

    def test_cancelled_queued_items_not_pinned_by_hung_worker(self):
        release = threading.Event()

        class Payload:
            pass

        payload = Payload()
        payload_ref = weakref.ref(payload)

        def func(item):
            if item == "hung":
                release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            map_with_per_item_timeout(
                ["hung", payload],
                func,
                timeout_seconds=0.2,
                max_workers=1,
                on_success=lambda item, result: None,
                on_error=lambda item, error: None,
            )
            del payload
            gc.collect()
            assert payload_ref() is None, "cancelled queued item still pinned after return"
        finally:
            release.set()


class _RecordingLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, event, **kwargs):
        self.warnings.append((event, kwargs))


class TestAbandonedWorkerAccounting:
    """Hung workers must not block interpreter exit and must be logged (CR-04)."""

    def test_hung_worker_does_not_block_interpreter_exit(self):
        # Pre-fix, ThreadPoolExecutor's non-daemon worker was joined at exit
        # by concurrent.futures' atexit hook, hanging the process forever;
        # the subprocess timeout below is only reached on regression.
        script = textwrap.dedent(
            """
            import threading
            from ast_grep_mcp.utils.futures import map_with_per_item_timeout

            map_with_per_item_timeout(
                ["hung"],
                lambda item: threading.Event().wait(),
                timeout_seconds=0.2,
                max_workers=1,
                on_success=lambda item, result: None,
                on_error=lambda item, error: None,
            )
            print("RETURNED", flush=True)
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_EXIT_BOUND_SECONDS,
        )
        assert result.returncode == 0, result.stderr
        assert "RETURNED" in result.stdout

    def test_abandoned_workers_logged_with_count(self, monkeypatch):
        recorder = _RecordingLogger()
        monkeypatch.setattr(futures_module, "logger", recorder)
        release = threading.Event()

        try:
            map_with_per_item_timeout(
                ["hung"],
                lambda item: release.wait(timeout=HUNG_WORKER_SAFETY_NET_SECONDS),
                timeout_seconds=0.2,
                max_workers=1,
                on_success=lambda item, result: None,
                on_error=lambda item, error: None,
            )
        finally:
            release.set()

        assert [(event, kwargs["abandoned_count"]) for event, kwargs in recorder.warnings] == [
            ("abandoned_worker_threads", 1)
        ]

    def test_no_abandoned_log_when_all_items_complete(self, monkeypatch):
        recorder = _RecordingLogger()
        monkeypatch.setattr(futures_module, "logger", recorder)

        map_with_per_item_timeout(
            ["a", "b"],
            lambda item: item,
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=2,
            on_success=lambda item, result: None,
            on_error=lambda item, error: None,
        )

        assert recorder.warnings == []


TOTAL_TIMEOUT_SECONDS = 1.5
HUNG_WORKER_TOTAL_SAFETY_NET_SECONDS = 30


class TestMapWithTotalTimeout:
    """Tests for the shared total_timeout_seconds deadline (CR-05 / CR-26)."""

    def test_fast_items_complete_within_total_deadline(self):
        """Items that finish quickly are unaffected by a generous total deadline."""
        results = {}
        errors = {}

        map_with_per_item_timeout(
            ["a", "b", "c"],
            lambda item: item.upper(),
            timeout_seconds=TIMEOUT_SECONDS,
            max_workers=2,
            on_success=lambda item, result: results.__setitem__(item, result),
            on_error=lambda item, error: errors.__setitem__(item, error),
            total_timeout_seconds=TOTAL_TIMEOUT_SECONDS,
        )

        assert results == {"a": "A", "b": "B", "c": "C"}
        assert errors == {}

    def test_total_deadline_caps_wall_clock_below_n_times_per_item(self):
        """With N hung workers, total wall-clock must stay near total_timeout_seconds, not N×timeout."""
        release = threading.Event()
        errors = {}

        # 5 items, 1 worker → serial waits; per-item=5s → worst case 25s without total deadline
        n_items = 5
        per_item_timeout = 5.0
        total_timeout = 2.0  # must return in ~2s, not ~25s

        try:
            start = time.monotonic()
            map_with_per_item_timeout(
                [f"h{i}" for i in range(n_items)],
                lambda item: release.wait(timeout=HUNG_WORKER_TOTAL_SAFETY_NET_SECONDS),
                timeout_seconds=per_item_timeout,
                max_workers=1,
                on_success=lambda item, result: None,
                on_error=lambda item, error: errors.__setitem__(item, error),
                total_timeout_seconds=total_timeout,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < per_item_timeout, f"should return in ~{total_timeout}s, took {elapsed:.2f}s"
        assert len(errors) == n_items
        assert all(isinstance(e, TimeoutError) for e in errors.values())

    def test_expired_deadline_marks_remaining_items_without_waiting(self):
        """Items past the deadline are reported immediately as TimeoutError."""
        errors = {}
        processed = []

        # Simulate: first item takes 0.5s (just under total_timeout=0.3s, so deadline expires)
        # remaining items should be marked without waiting
        def func(item):
            if item == "slow":
                time.sleep(0.5)
            return item

        start = time.monotonic()
        map_with_per_item_timeout(
            ["slow", "after_deadline"],
            func,
            timeout_seconds=10.0,
            max_workers=1,
            on_success=lambda item, result: processed.append(item),
            on_error=lambda item, error: errors.__setitem__(item, error),
            total_timeout_seconds=0.3,
        )
        elapsed = time.monotonic() - start

        # Should have returned quickly (not waited 10s for after_deadline)
        assert elapsed < 2.0, f"should return promptly, took {elapsed:.2f}s"
        assert "after_deadline" in errors
        assert isinstance(errors["after_deadline"], TimeoutError)
