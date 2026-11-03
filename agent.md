# agent.md - Project Log

## Step 1 - Initial infrastructure (2026-11-03)

### Status
- Tests: PASS - python test_step1.py
- Git commit: 0d37732 feat(core): initialize project with llm_client, tag_preserver, and tests

### Modules and functions (Step 1)
- core/llm_client.py - LLMClient.generate with exponential backoff for 429/502/503/504, max 4 retries
- core/tag_preserver.py - preserve_tags, restore_tags in descending id order, align_missing_placeholders proportional fallback
- test_step1.py - round-trip, fallback, descending-order tests

## Step 2 - EPUB extraction, style census, structure generator (2026-11-03)

### Status
- Tests: PASS - python test_step2.py
- Git commit: d45fc1a feat(epub): implement epub extraction, style census, and structure generator

### Modules and functions (Step 2)
- core/epub_handler.py - extract with Zip Slip protection, find_opf_path, get_spine_xhtml, repackage with mimetype ZIP_STORED first
- core/style_census.py - scan_styles with first, middle, last samples, generate_structure with cache and role validation
- core/css_injector.py - default Vazirmatn system stack, rtl body, ltr code and pre, optional custom font-face
- test_step2.py - synthetic EPUB, Zip Slip, CSS tests

## Step 3 - Book scouting, style profiling, interactive review (2026-11-03)

### Status
- Config: .env updated locally and gitignored, .env.example updated to MODEL_REVIEW claude-haiku-4-5-20251001 and MODEL_TRANSLATE deepseek-v4.1-flash-1017, real API key kept only in .env, never in .env.example or agent.md
- Tests: PASS - python test_step3.py printed PASS: all step-3 scenarios passed
- Git commit: being created at end of this step with message feat(scout): implement book scouting, style profiling, and interactive review

### Architecture decisions (Step 3)
- Scout reads only p and title roles from structure.json, skip roles are excluded before any LLM call
- Chunks split only at paragraph boundaries, clamped to 100000 to 150000 characters, default 120000
- Merge deduplicates identical lines across waves and guarantees VOICES, CHARACTERS and TERMS headings exist
- Cache: existing work/scout.md is returned with zero LLM calls
- Interactive pause prints the exact Persian review message and waits for Enter, --auto-approve skips it for non-interactive runs

### Modules and functions (Step 3)
- prompts/scout.md - VOICES profiling, CHARACTERS table, TERMS and CANON table, mandatory uncensored rule, mandatory preserve imperial units rule, output headings VOICES, CHARACTERS, TERMS
- core/scout.py - BookScouter.collect_paragraphs, chunk_paragraphs, merge_results, interactive_pause, scout, run alias, parse_args with --auto-approve; model defaults to MODEL_TRANSLATE env
- test_step3.py - fictional multi-paragraph text with John Carter, Mary Hale, five miles, six feet, two pounds, Blackwood Manor, skip paragraph excluded, generation and cache check, chunk split check, parse_args check

### Bugs found (Step 3)
- None

### Next step
- Await user instruction for step 4, expected translation pipeline on top of EpubHandler, StyleCensus, TagPreserver, LLMClient and BookScouter. Do not start it before approval.

Skipped: pytest run, direct execution was accepted alternative and passed; live LLM call, FakeLLMClient used because interactive review and real API cost were not in scope for this test; real book scout, synthetic fiction used, so long-book multi-wave merge remains untested on a real EPUB.
