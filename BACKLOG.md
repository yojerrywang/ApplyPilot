# Backlog

## P0 (Next)
- Add robust LinkedIn job-description fallback for standalone `tailor` when scrape fails (accept pasted JD text/file as direct input).
- Add provider fallback chain in runtime (`openai -> gemini -> local`) when 429/5xx occurs.
- Add secret hygiene guardrails:
  - redact API keys in logs/console
  - refuse committing env/token/credentials files
  - document key rotation workflow.

## P1
- Add batch URL UX for standalone mode with per-job status report (`queued/ok/failed`) and retry list output.
- Add `tailor-doc` direct pipeline mode (`--from-tailor-out DIR`) to auto-render every tailored txt into doc+pdf.
- Add optional Drive folder auto-creation by date/company.

## P2
- Add Gmail draft creation command for follow-up emails tied to generated resumes.
- Add Calendar follow-up reminder command (5-7 day post-apply reminders).
- Add resume quality metrics report (keyword coverage, section length, banned phrase score).

## Testing Backlog
- Unit tests for `doc_template.py` parsing + placeholder mapping.
- Integration test for Drive copy -> Docs replace -> PDF export path.
- Regression test for `llm.py` provider detection with env loaded after import.
- Regression test for Google Docs download/export in `download_file()`.
