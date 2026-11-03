# agent.md - Project Log

## Step 1 - Initial infrastructure (2026-11-03)

### Status
- Project directory was empty; initial scaffold created in this step.
- Tests: PASS - `python test_step1.py` printed `PASS: all step-1 scenarios passed`.
  - Scenario 1: preserve/restore round-trip on nested styled HTML reconstructs the document exactly.
  - Scenario 2: deliberate deletion of `[id1]`; proportional fallback in align_missing_placeholders reinserts it and round-trip still matches the original.
  - Scenario 3: >=12 placeholders; restore_tags replaces in descending numeric id order ([id10] before [id1]) without corruption.
- Git commit: being created at the end of this step with message `feat(core): initialize project with llm_client, tag_preserver, and tests`.

### Architecture decisions
- LLMClient builds the endpoint as base + '/chat/completions' when API_BASE_URL already ends with '/v1', otherwise base + '/v1/chat/completions', avoiding a duplicated '/v1'.
- TagPreserver remembers the last masked text so align_missing_placeholders can work with its documented 2-argument call.

### Modules and functions
- .env.example - API_BASE_URL (default https://positionapi.top/v1), API_KEY (sk-...), MODEL_TRANSLATE (deepseek-v4.1-flash-1017), MODEL_REVIEW (claude-sonnet-5).
- requirements.txt - httpx>=0.27, pytest>=8.0.
- core/llm_client.py - LLMClient.generate(system_prompt, user_prompt, temperature, model=None); retries 429/502/503/504 and network errors with exponential backoff, max 4 retries; EmptyResponseError on missing/empty content, LLMClientError on missing API_KEY or exhausted retries.
- core/tag_preserver.py - TagPreserver.preserve_tags(text) -> (masked_text, tag_map), adjacent tags merged into one placeholder; restore_tags replaces placeholders in descending numeric id order; align_missing_placeholders reinserts missing placeholders at the proportional character position from the source, snapped to the nearest word boundary.
- test_step1.py - round-trip, proportional-fallback, and descending-order tests above.

### Bugs found
- None.

### Next step
- Await user instruction for step 2 (expected: EPUB parsing/extraction pipeline on top of LLMClient + TagPreserver). Do not start it before approval.

Skipped: pytest run (direct execution already required by the task as an accepted alternative and passed); live API call (no real API_KEY available, LLMClient covered by code inspection only).
