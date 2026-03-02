import json

from applypilot.scoring import tailor


class _FakeClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = 0

    def chat(self, messages, max_tokens=0, temperature=0.0):
        response = self._responses[self.calls]
        self.calls += 1
        return response


def _tailor_json_payload():
    return json.dumps(
        {
            "title": "Backend Engineer",
            "summary": "Python backend engineer with API and platform delivery experience.",
            "skills": {
                "Languages": "Python, SQL",
                "Frameworks": "FastAPI, Flask",
                "DevOps & Infra": "Docker, AWS",
                "Databases": "PostgreSQL",
                "Tools": "Git, Linux",
            },
            "experience": [
                {
                    "header": "Backend Engineer at Acme",
                    "subtitle": "Python | 2022-2025",
                    "bullets": [
                        "Built API services for core workflows.",
                        "Improved processing throughput by 40%.",
                    ],
                }
            ],
            "projects": [
                {
                    "header": "Project Atlas - Internal platform",
                    "subtitle": "Python | 2024",
                    "bullets": ["Automated operational reporting."],
                }
            ],
            "education": "State University | Bachelor's",
        }
    )


def _profile():
    return {
        "personal": {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-000-1111",
            "linkedin_url": "",
            "github_url": "",
        },
        "resume_facts": {
            "preserved_companies": ["Acme"],
            "preserved_projects": ["Project Atlas"],
            "preserved_school": "State University",
            "real_metrics": ["40%"],
        },
        "skills_boundary": {
            "languages": ["Python", "SQL"],
        },
        "experience": {"education_level": "Bachelor's"},
    }


def _job():
    return {
        "title": "Backend Engineer",
        "site": "ExampleCo",
        "location": "Remote",
        "full_description": "Build backend services and APIs",
    }


def test_tailor_resume_retries_when_programmatic_validation_fails(monkeypatch):
    fake_client = _FakeClient([_tailor_json_payload(), _tailor_json_payload()])
    monkeypatch.setattr(tailor, "get_client", lambda: fake_client)
    monkeypatch.setattr(tailor, "validate_json_fields", lambda data, profile: {"passed": True, "errors": [], "warnings": []})

    programmatic_calls = {"count": 0}

    def _fake_programmatic(text, profile, original_text=""):
        programmatic_calls["count"] += 1
        if programmatic_calls["count"] == 1:
            return {"passed": False, "errors": ["Missing required section: PROJECTS"], "warnings": []}
        return {"passed": True, "errors": [], "warnings": []}

    monkeypatch.setattr(tailor, "validate_tailored_resume", _fake_programmatic)
    monkeypatch.setattr(tailor, "judge_tailored_resume", lambda *_: {"passed": True, "verdict": "PASS", "issues": "none"})

    tailored_text, report = tailor.tailor_resume("Original resume text", _job(), _profile(), max_retries=1)

    assert report["status"] == "approved"
    assert report["attempts"] == 2
    assert "PROJECTS" in tailored_text
    assert fake_client.calls == 2


def test_tailor_resume_returns_failed_programmatic_on_final_attempt(monkeypatch):
    fake_client = _FakeClient([_tailor_json_payload(), _tailor_json_payload()])
    monkeypatch.setattr(tailor, "get_client", lambda: fake_client)
    monkeypatch.setattr(tailor, "validate_json_fields", lambda data, profile: {"passed": True, "errors": [], "warnings": []})
    monkeypatch.setattr(
        tailor,
        "validate_tailored_resume",
        lambda text, profile, original_text="": {"passed": False, "errors": ["Missing required section: EXPERIENCE"], "warnings": []},
    )
    monkeypatch.setattr(tailor, "judge_tailored_resume", lambda *_: {"passed": True, "verdict": "PASS", "issues": "none"})

    _, report = tailor.tailor_resume("Original resume text", _job(), _profile(), max_retries=1)

    assert report["status"] == "failed_programmatic"
    assert report["attempts"] == 2
