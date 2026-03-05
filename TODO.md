# TODO

## Immediate
- [ ] Run `applypilot tailor-doc` on the latest tailored output and verify the generated Google Doc + PDF visually.
- [ ] Confirm template placeholders are in final preferred order/spacing.
- [ ] Rotate exposed OpenAI API key and update `~/.applypilot/.env`.

## This Week
- [ ] Implement JD text override input for standalone tailor (`--job-text` / `--job-file`).
- [ ] Add provider fallback behavior for 429 rate-limit handling.
- [ ] Add docs note for forcing provider with `LLM_PROVIDER`.

## Nice to Have
- [ ] Add `--template-doc-id` directly to `applypilot tailor` to render docs immediately after tailoring.
- [ ] Add `--export-pdf` toggle to emit local PDF snapshots for all rendered docs.
- [ ] Add command to list Drive output links after upload.
