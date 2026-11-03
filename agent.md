# agent.md - Project Log

## Step 1 - Initial infrastructure (2026-11-03)
- Tests: PASS - python test_step1.py
- Commit: 0d37732 feat(core): initialize project with llm_client, tag_preserver, and tests
- core/llm_client.py - LLMClient.generate, exponential backoff on 429/502/503/504, max 4 retries, EmptyResponseError on empty content
- core/tag_preserver.py - preserve_tags (adjacent tags merged), restore_tags descending id order, align_missing_placeholders proportional fallback

## Step 2 - EPUB extraction, style census, structure generator (2026-11-03)
- Tests: PASS - python test_step2.py
- Commit: d45fc1a feat(epub): implement epub extraction, style census, and structure generator
- core/epub_handler.py - extract with Zip Slip protection, find_opf_path, get_spine_xhtml in spine order, repackage (mimetype ZIP_STORED first, rest ZIP_DEFLATED)
- core/style_census.py - scan_styles first/middle/last samples, generate_structure with work/structure.json cache and role validation (title, subtitle, p, verse, note, skip)
- core/css_injector.py - default Vazirmatn system stack, rtl body, ltr code/pre, optional custom font-face

## Step 3 - Book scouting, style profiling, interactive review (2026-11-03)
- Config: real API key only in gitignored .env; .env.example defaults MODEL_TRANSLATE deepseek-v4.1-flash-1017, MODEL_REVIEW claude-haiku-4-5-20251001
- Tests: PASS - python test_step3.py
- Commit: 838676a feat(scout): implement book scouting, style profiling, and interactive review
- prompts/scout.md - VOICES profiling, CHARACTERS and TERMS tables, mandatory uncensored rule, mandatory preserve imperial units rule
- core/scout.py - BookScouter collects only p/title roles, chunks 100000-150000 chars at paragraph boundaries, merge/dedupe, work/scout.md cache, interactive Enter pause, --auto-approve flag

## Step 4 - Translation engine, parallel reviewer, EPUB builder, CLI (2026-11-03)
- Tests: PASS - python test_end_to_end.py
- Commit: c387cb7 feat(pipeline): complete translation engine, parallel reviewer, epub builder, and CLI with sample mode
- Pipeline: EpubHandler.extract -> StyleCensus -> BookScouter.scout -> Translator.translate (sequential) -> Reviewer.review_all (parallel, --jobs) -> EpubBuilder.build -> EpubHandler.repackage

## Step 5 - Live logger and English console (2026-11-03)
- Tests: PASS - 10 passed
- Commit: 3788577 feat(pipeline): complete end-to-end pipeline with live logger, sample mode, custom font injection, and CLI
- core/logger.py - PipelineLogger with Rich Progress, [INFO]/[API]/[RETRY]/[WORKER] event stream, wired into LLMClient, Translator, Reviewer, Builder and main.py; all console text in English

## Step 6 - Bugfix: No p/title paragraphs found to scout (2026-11-03)

### Status
- Tests: PASS - python -m pytest test_step1.py test_step2.py test_step3.py test_end_to_end.py -v, 10 passed in 1.37s
- Old work folder deleted: Remove-Item -Recurse -Force work, Test-Path work returned False, so structure.json and scout.md will be regenerated with the new logic on the next run
- Git commit: being created at the end of this step

### Root cause
- StyleCensus accepted only the exact standard roles; a model replying with non-standard role names such as paragraph or body produced a structure.json whose roles never matched the p/title filter in BookScouter.collect_paragraphs, so Scout collected zero paragraphs and raised ValueError: No p/title paragraphs found to scout.

### Fixes
- core/style_census.py - added ROLE_ALIASES mapping paragraph, body, text, normal, content and para to p, and heading, header and booktitle to title; in generate_structure each returned role is lowercased and normalized through ROLE_ALIASES before validation against VALID_ROLES, so structure.json now always stores only standard roles (title, subtitle, p, verse, note, skip)
- core/scout.py - collect_paragraphs fallback: if the structure-based collection returns no paragraphs, it automatically collects all p and h1-h6 elements from the XHTML files as body text and Scout continues instead of raising an error; marked with a shortcut comment in code

### Next step
- Rerun the pipeline on the affected book from scratch (work was deleted) and verify scout.md is generated; if it still fails, inspect the regenerated work/structure.json.

Skipped: live rerun on the affected real book, it was not provided in this session; only the full offline test suite was rerun.
