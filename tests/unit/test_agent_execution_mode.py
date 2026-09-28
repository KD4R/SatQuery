"""P2-04 / P6-05: how an accepted agent run is started (thread vs Celery worker)."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from services.agent.app.api.routers import execute


@pytest.mark.unit
@pytest.mark.parametrize(
    "value, expected",
    [(None, "thread"), ("thread", "thread"), ("CELERY", "celery"), ("bogus", "thread")],
)
def test_execution_mode_defaults_to_thread_and_ignores_garbage(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("AGENT_EXECUTION_MODE", raising=False)
    else:
        monkeypatch.setenv("AGENT_EXECUTION_MODE", value)
    assert execute._execution_mode() == expected


@pytest.mark.unit
def test_thread_mode_starts_a_daemon_thread_and_never_touches_the_broker(monkeypatch):
    monkeypatch.setenv("AGENT_EXECUTION_MODE", "thread")
    thread_cls = MagicMock()
    monkeypatch.setattr(execute.threading, "Thread", thread_cls)

    execute._dispatch_run("job-1")

    thread_cls.assert_called_once()
    assert thread_cls.call_args.kwargs["daemon"] is True
    thread_cls.return_value.start.assert_called_once()


@pytest.mark.unit
def test_celery_mode_enqueues_the_task_and_starts_no_thread(monkeypatch):
    from services.agent import worker

    monkeypatch.setenv("AGENT_EXECUTION_MODE", "celery")
    delay = MagicMock()
    monkeypatch.setattr(worker.process_agent_run, "delay", delay)
    thread_cls = MagicMock()
    monkeypatch.setattr(execute.threading, "Thread", thread_cls)

    execute._dispatch_run("job-2")

    delay.assert_called_once_with("job-2")
    thread_cls.assert_not_called()


@pytest.mark.unit
def test_celery_mode_broker_failure_fails_the_run_and_returns_503(monkeypatch):
    """A run the caller was promised must not sit INITIALIZED forever."""
    from services.agent import worker

    monkeypatch.setenv("AGENT_EXECUTION_MODE", "celery")
    monkeypatch.setattr(
        worker.process_agent_run, "delay", MagicMock(side_effect=OSError("broker down"))
    )
    run = MagicMock(errors=[])
    orchestrator = MagicMock()
    orchestrator.get_run.return_value = run
    monkeypatch.setattr(execute, "get_orchestrator", lambda: orchestrator)

    with pytest.raises(HTTPException) as caught:
        execute._dispatch_run("job-3")

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "QUEUE_UNAVAILABLE"
    assert caught.value.detail["retryable"] is True
    assert run.status == "FAILED"
    assert "could not be queued" in run.errors[0]
    orchestrator.save_run.assert_called_once_with(run)
