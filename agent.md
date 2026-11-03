# agent.md - Project Log

## Step 1 - Initial infrastructure (2026-11-03)

### Status
- Project directory was empty; initial scaffold created in step 1.
- Tests: PASS - python test_step1.py printed PASS: all step-1 scenarios passed.
- Git commit: 0d37732 feat(core): initialize project with llm_client, tag_preserver, and tests.

### Architecture decisions (Step 1)
- LLMClient builds endpoint as base plus /chat/completions when API_BASE_URL already ends with /v1, otherwise base plus /v1/chat/completions, avoiding duplicated /v1.
- TagPreserver remembers last masked text so align_missing_placeholders can work with its documented 2-argument call.

### Modules and functions (Step 1)
- .env.example - API_BASE_URL, API_KEY, MODEL_TRANSLATE, MODEL_REVIEW.
- requirements.txt - httpx, pytest.
- core/llm_client.py - LLMClient.generate(system_prompt, user_prompt, temperature, model=None); retries 429/502/503/504 and network errors with exponential backoff, max 4 retries; EmptyResponseError on missing or empty content.
- core/tag_preserver.py - TagPreserver.preserve_tags, restore_tags in descending numeric id order, align_missing_placeholders with proportional fallback snapped to nearest word boundary.
- test_step1.py - round-trip, proportional-fallback, descending-order tests.

## Step 2 - EPUB extraction, style census, structure generator (2026-11-03)

### Status
- Tests: PASS - python test_step2.py printed PASS: all step-2 scenarios passed.
- Scenario 1: minimal synthetic EPUB extracted, spine order chapter1 then chapter2, census counts h1.title 1, p.body 2, p.toc 10, toc samples Toc 0, Toc 5, Toc 9 (first, middle, last), structure.json saved with indent 2, cached second call made no extra LLM call.
- Scenario 2: Zip Slip entry ../evil.txt blocked with ValueError and no file escaped work dir.
- Scenario 3: default CSS has no font-face, has Vazirmatn system stack with important, rtl body, ltr code and pre; custom font copied to fonts, font-face added, family prioritized, url rewritten to ../fonts/.
- Git commit: being created at end of this step with message feat(epub): implement epub extraction, style census, and structure generator.

### Architecture decisions (Step 2)
- Zip Slip: every zip entry resolved and checked to stay under resolved raw dir before writing.
- OPF parsing is namespace-agnostic by stripping namespace prefix from tags, so container and OPF in different namespaces still parse.
- Spine order is authoritative for chapter order; manifest items filtered by xhtml media type or xhtml/html extension.
- Repackage writes mimetype first as ZIP_STORED, all other files sorted as ZIP_DEFLATED, per EPUB standard.
- StyleCensus samples: up to 3 texts per tag and class pair; if more than 3, first, middle, last only, so list styles are not confused with body text.
- generate_structure cache: existing work/structure.json is returned without any LLM call; otherwise prompt lists tag.class, count, samples, model must reply one line per known style only, roles limited to title, subtitle, p, verse, note, skip.
- CSSInjector default embeds no font; custom font is copied, not moved, and font-face uses file name only, rewritten on inject to ../fonts/ path.

### Modules and functions (Step 2)
- core/epub_handler.py - EpubHandler.extract, find_opf_path, get_spine_xhtml, repackage; work dir defaults to work, raw dir is work/raw.
- core/style_census.py - StyleCensus.scan_styles(xhtml_files), generate_structure(llm_client, work_dir); TEXT_TAGS are h1 to h6, p, div, li; validation rejects unknown styles, invalid roles, missing styles, and malformed lines.
- core/css_injector.py - CSSInjector.generate_css(font_path, fonts_dir), build_css alias, inject(raw_dir, font_path, css_rel_path); default css_rel_path is styles/style.css.
- test_step2.py - synthetic EPUB builder, FakeLLMClient returning fixed role mapping, Zip Slip test, CSS default and custom font test.

### Bugs found (Step 2)
- None.

### Next step
- Await user instruction for step 3, expected translation pipeline on top of EpubHandler, StyleCensus, TagPreserver, and LLMClient. Do not start it before approval.

Skipped: pytest run, direct execution was accepted alternative and passed; live LLM call, FakeLLMClient used because no real API_KEY was available; real-world EPUB, minimal synthetic EPUB used, so large or malformed EPUBs remain untested.
