import pytest
import threading
import types
import sys

from applypilot import pipeline


def test_resolve_stages_preserves_canonical_order():
    result = pipeline._resolve_stages(["cover", "discover", "dedupe", "score"])

    assert result == ["discover", "dedupe", "score", "cover"]


def test_resolve_stages_all_expands_full_order():
    result = pipeline._resolve_stages(["all"])

    assert result == list(pipeline.STAGE_ORDER)


def test_resolve_stages_invalid_name_exits():
    with pytest.raises(SystemExit):
        pipeline._resolve_stages(["not-a-stage"])


@pytest.mark.parametrize("stream", [False, True])
def test_run_pipeline_forwards_session_id(monkeypatch, stream):
    captured = {}

    monkeypatch.setattr(pipeline, "load_env", lambda: None)
    monkeypatch.setattr(pipeline, "ensure_dirs", lambda: None)
    monkeypatch.setattr(pipeline, "init_db", lambda: None)
    monkeypatch.setattr(pipeline, "_resolve_stages", lambda _: ["discover"])
    monkeypatch.setattr(
        pipeline,
        "get_stats",
        lambda: {
            "total": 0,
            "pending_detail": 0,
            "with_description": 0,
            "scored": 0,
            "tailored": 0,
            "with_cover_letter": 0,
            "ready_to_apply": 0,
            "applied": 0,
        },
    )

    def fake_sequential(ordered, min_score, workers=1, session_id=None):
        captured["sequential"] = session_id
        return {"stages": [], "errors": {}, "elapsed": 0.0}

    def fake_streaming(ordered, min_score, workers=1, session_id=None):
        captured["streaming"] = session_id
        return {"stages": [], "errors": {}, "elapsed": 0.0}

    monkeypatch.setattr(pipeline, "_run_sequential", fake_sequential)
    monkeypatch.setattr(pipeline, "_run_streaming", fake_streaming)

    pipeline.run_pipeline(stages=["discover"], stream=stream, session_id="batch-123")

    key = "streaming" if stream else "sequential"
    assert captured[key] == "batch-123"


def test_run_stage_streaming_forwards_session_id_for_discover(monkeypatch):
    tracker = pipeline._StageTracker()
    stop_event = threading.Event()
    called = {}

    def fake_discover(workers=1, session_id=None):
        called["session_id"] = session_id
        return {"status": "ok"}

    monkeypatch.setitem(pipeline._STAGE_RUNNERS, "discover", fake_discover)

    pipeline._run_stage_streaming(
        stage="discover",
        tracker=tracker,
        stop_event=stop_event,
        workers=1,
        session_id="batch-stream-1",
    )

    assert called["session_id"] == "batch-stream-1"


def test_run_discover_accepts_session_id_and_calls_smartextract_without_session_arg(monkeypatch):
    calls = {"smart_workers": None}

    mod_jobspy = types.ModuleType("applypilot.discovery.jobspy")
    mod_jobspy.run_discovery = lambda: None

    mod_hiring = types.ModuleType("applypilot.discovery.hiringcafe")
    mod_hiring.run_discovery = lambda: None

    mod_workday = types.ModuleType("applypilot.discovery.workday")
    mod_workday.run_workday_discovery = lambda workers=1: None

    mod_smart = types.ModuleType("applypilot.discovery.smartextract")

    def fake_smart_extract(workers=1):
        calls["smart_workers"] = workers

    mod_smart.run_smart_extract = fake_smart_extract

    monkeypatch.setitem(sys.modules, "applypilot.discovery.jobspy", mod_jobspy)
    monkeypatch.setitem(sys.modules, "applypilot.discovery.hiringcafe", mod_hiring)
    monkeypatch.setitem(sys.modules, "applypilot.discovery.workday", mod_workday)
    monkeypatch.setitem(sys.modules, "applypilot.discovery.smartextract", mod_smart)

    result = pipeline._run_discover(workers=2, session_id="batch-seq-1")

    assert result["smartextract"] == "ok"
    assert calls["smart_workers"] == 2
