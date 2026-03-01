from applypilot.apply import launcher


def test_extract_result_meta_parses_json_and_inline_fields():
    output = """
    RESULT:APPLIED:task_id=inline-task:confidence=0.42
    RESULT_META: {"confirmation_url":"https://jobs.example.com/confirm/123","verification_confidence":0.91,"task_id":"json-task"}
    """

    meta = launcher._extract_result_meta(output)

    assert meta["task_id"] == "json-task"
    assert meta["confirmation_url"] == "https://jobs.example.com/confirm/123"
    assert meta["verification_confidence"] == 0.91


def test_looks_like_successful_submission_requires_multiple_markers():
    weak_output = "The page mentions application submitted but nothing else."
    strong_output = "Thank you for applying. Your application has been submitted."

    assert launcher._looks_like_successful_submission(weak_output) is False
    assert launcher._looks_like_successful_submission(strong_output) is True
