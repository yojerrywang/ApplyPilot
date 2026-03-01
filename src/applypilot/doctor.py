"""Environment and configuration diagnostics for ApplyPilot."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import dotenv_values

from applypilot import config
from applypilot.database import get_connection, init_db


@dataclass
class CheckResult:
    """Single doctor check outcome."""

    level: str  # ok | warn | fail
    check: str
    message: str
    fix: str | None = None


def _ok(check: str, message: str, fix: str | None = None) -> CheckResult:
    return CheckResult("ok", check, message, fix)


def _warn(check: str, message: str, fix: str | None = None) -> CheckResult:
    return CheckResult("warn", check, message, fix)


def _fail(check: str, message: str, fix: str | None = None) -> CheckResult:
    return CheckResult("fail", check, message, fix)


def _parse_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("Expected a JSON object at the top level")
    return loaded


def _parse_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Expected a YAML mapping at the top level")
    return loaded


def run_checks() -> list[CheckResult]:
    """Run doctor checks and return all results."""
    results: list[CheckResult] = []

    # Basic filesystem + DB checks
    try:
        config.ensure_dirs()
        results.append(_ok("Directories", f"App directory ready at {config.APP_DIR}"))
    except Exception as exc:
        results.append(_fail("Directories", f"Failed to create app directories: {exc}"))

    try:
        init_db()
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        results.append(_ok("Database", f"SQLite database reachable at {config.DB_PATH}"))
    except Exception as exc:
        results.append(_fail("Database", f"Cannot initialize database at {config.DB_PATH}: {exc}"))

    # Profile checks
    if not config.PROFILE_PATH.exists():
        results.append(
            _fail(
                "Profile",
                f"Missing profile at {config.PROFILE_PATH}",
                "Run `applypilot init` to generate profile.json.",
            )
        )
    else:
        try:
            profile = _parse_json(config.PROFILE_PATH)
            results.append(_ok("Profile JSON", "profile.json parses successfully"))

            personal = profile.get("personal", {})
            if not isinstance(personal, dict):
                results.append(_fail("Profile shape", "`personal` must be an object"))
            else:
                missing_personal = [k for k in ("full_name", "email") if not personal.get(k)]
                if missing_personal:
                    results.append(
                        _warn(
                            "Profile fields",
                            f"Missing recommended personal fields: {', '.join(missing_personal)}",
                            "Fill missing values in profile.json for better apply autofill.",
                        )
                    )
                else:
                    results.append(_ok("Profile fields", "Required personal fields are present"))

            has_legacy = "location_accept" in profile or "location_reject_non_remote" in profile
            has_nested = bool(profile.get("preferences", {}).get("location"))
            if has_legacy and has_nested:
                results.append(
                    _warn(
                        "Location schema",
                        "Both legacy and nested location schemas are present in profile.json.",
                        "Keep one schema to avoid ambiguity (prefer `preferences.location`).",
                    )
                )
            else:
                results.append(_ok("Location schema", "No conflicting location schema detected"))
        except Exception as exc:
            results.append(_fail("Profile JSON", f"profile.json is invalid: {exc}"))

    # Search config checks
    if not config.SEARCH_CONFIG_PATH.exists():
        results.append(
            _warn(
                "Search config",
                f"Missing searches.yaml at {config.SEARCH_CONFIG_PATH}",
                "Run `applypilot init` or create searches.yaml manually.",
            )
        )
    else:
        try:
            search_cfg = _parse_yaml(config.SEARCH_CONFIG_PATH)
            results.append(_ok("Search YAML", "searches.yaml parses successfully"))

            queries = search_cfg.get("queries", [])
            if not isinstance(queries, list) or not queries:
                results.append(_fail("Search queries", "`queries` must be a non-empty list"))
            else:
                bad_queries = [q for q in queries if not isinstance(q, dict) or not str(q.get("query", "")).strip()]
                if bad_queries:
                    results.append(_fail("Search queries", "Each query entry must include non-empty `query` text"))
                else:
                    results.append(_ok("Search queries", f"{len(queries)} query entries configured"))

            locations = search_cfg.get("locations", [])
            if not isinstance(locations, list) or not locations:
                results.append(_warn("Search locations", "No explicit `locations` configured"))
            else:
                results.append(_ok("Search locations", f"{len(locations)} location entries configured"))

            excluded = search_cfg.get("exclude_titles", [])
            if excluded and not isinstance(excluded, list):
                results.append(_fail("exclude_titles", "`exclude_titles` must be a list of strings"))
            elif excluded and not all(isinstance(item, str) for item in excluded):
                results.append(_fail("exclude_titles", "`exclude_titles` must contain only strings"))
            else:
                results.append(_ok("exclude_titles", "Title exclusion config is valid"))
        except Exception as exc:
            results.append(_fail("Search YAML", f"searches.yaml is invalid: {exc}"))

    # .env and runtime keys
    if not config.ENV_PATH.exists():
        results.append(
            _warn(
                "Environment file",
                f"Missing .env at {config.ENV_PATH}",
                "Run `applypilot init` to configure an LLM provider.",
            )
        )
        env_values = {}
    else:
        try:
            env_values = dotenv_values(config.ENV_PATH)
            results.append(_ok("Environment file", ".env parses successfully"))
        except Exception as exc:
            env_values = {}
            results.append(_fail("Environment file", f".env could not be parsed: {exc}"))

    has_llm = any((env_values.get(k) or "").strip() for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_URL"))
    if has_llm:
        results.append(_ok("LLM config", "At least one LLM provider key is configured"))
    else:
        results.append(
            _warn(
                "LLM config",
                "No LLM provider configured (Tier 2 features unavailable).",
                "Set GEMINI_API_KEY, OPENAI_API_KEY, or LLM_URL in .env.",
            )
        )

    # Sites config pattern sanity
    try:
        sites_cfg = config.load_sites_config()
        blocked = sites_cfg.get("blocked", {}) if isinstance(sites_cfg, dict) else {}
        patterns = blocked.get("url_patterns", []) if isinstance(blocked, dict) else []
        if not isinstance(patterns, list):
            results.append(_fail("Blocked patterns", "`blocked.url_patterns` must be a list"))
        else:
            malformed = [p for p in patterns if not isinstance(p, str) or not p.strip()]
            no_wildcards = [p for p in patterns if isinstance(p, str) and p.strip() and "%" not in p and "_" not in p]
            if malformed:
                results.append(_fail("Blocked patterns", "One or more blocked URL patterns are empty/non-string"))
            elif no_wildcards:
                sample = no_wildcards[0]
                results.append(
                    _warn(
                        "Blocked patterns",
                        f"Pattern `{sample}` has no SQL wildcard (% or _), may not match as intended.",
                        "Use patterns like `%domain.com/path%`.",
                    )
                )
            else:
                results.append(_ok("Blocked patterns", "Blocked URL patterns are valid"))
    except Exception as exc:
        results.append(_warn("Blocked patterns", f"Could not validate blocked URL patterns: {exc}"))

    # Tier-3 runtime probes
    if shutil.which("claude"):
        results.append(_ok("Claude CLI", "Found `claude` executable on PATH"))
    else:
        results.append(
            _warn(
                "Claude CLI",
                "Claude Code CLI not found on PATH (Tier 3 auto-apply unavailable).",
                "Install from https://claude.ai/code.",
            )
        )

    try:
        chrome_path = config.get_chrome_path()
        results.append(_ok("Chrome", f"Detected browser executable at {chrome_path}"))
    except Exception as exc:
        results.append(
            _warn(
                "Chrome",
                f"Chrome/Chromium not detected: {exc}",
                "Install Chrome or set CHROME_PATH.",
            )
        )

    return results
