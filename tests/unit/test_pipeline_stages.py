import pytest

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
