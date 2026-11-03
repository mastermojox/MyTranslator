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
- Translator: block elements with role title, subtitle, p, verse or note only, skip excluded, inner XML masked with TagPreserver, chunks 300-500 estimated tokens without splitting an element, scout term substitution with [[TERM]] codes, rolling plot in work/state.json (plot_summary plus last 3 translated paragraphs), immediate save to work/tr/NNNN.json, --resume reuses tr/ed/state
- Reviewer: asyncio Semaphore(jobs), MODEL_REVIEW, SOURCE plus DRAFT plus SCOUT, [idN] validation and proportional fallback, output to work/ed/NNNN.json
- Builder: restore tags, spine page-progression-direction='rtl' in content.opf, styles/translation.css linked from XHTML and registered in OPF manifest, custom font copied to OEBPS/Fonts with @font-face and rem/em sizes, default mode uses only the Vazirmatn system stack with no embedded font, repackage with mimetype stored first
- Prompts: prompts/translate.md (faithful voice, uncensored, preserve imperial units, [idN] and [[TERM]] codes, [[[P id]]] plus [[[META]]] plot/terms) and prompts/review.md (bilingual critic editor, removes translationese, never changes names, units or harsh language, returns only [[[P id]]] blocks)
- Live mini test (separate run): real API sample pipeline on a small synthetic EPUB passed, with scout.md, structure.json, tr/ed/state files, valid output EPUB and Persian text, imperial units preserved and profanity not softened

## Step 5 - Live logger and English console (2026-11-03)

### Status
- Tests: PASS - python -m pytest test_step1.py test_step2.py test_step3.py test_end_to_end.py -v, 10 passed in 2.46s
- Git commit: being created at the end of this step with message feat(pipeline): complete end-to-end pipeline with live logger, sample mode, custom font injection, and CLI
- Dependencies: rich>=13.7 added to requirements.txt, rich 14.3.4 installed from main PyPI (mirror removed earlier), httpx 0.28.1, pytest 8.3.5

### Live logger architecture
- core/logger.py - PipelineLogger using Rich Progress with SpinnerColumn, BarColumn, TaskProgressColumn, a Chunks counter in the form completed/total Chunks, and TimeRemainingColumn for ETA; global instances log and logger
- Methods: start, stop, set_phase(name, total), advance, info, api, retry, worker, phase_done
- Event stream above the progress bar: [INFO] for phase start/finish and saved files, [API] for model, latency in seconds and approximate tokens (prompt plus response chars divided by 4) with a running total, [RETRY] in yellow with attempt/max, HTTP status and backoff countdown in seconds, [WORKER] in magenta for parallel review chunks without breaking the terminal
- Integration: LLMClient logs [API] on success and [RETRY] on 429/502/503/504 and network errors before each backoff sleep; Translator calls set_phase Translate and advances per saved or resume-skipped chunk; Reviewer calls set_phase Review and logs one [WORKER] line per saved chunk; Builder calls set_phase Build; main.py calls log.start, logs pipeline start and extraction, then phase_done Build, output ready and log.stop
- English console: all logger lines, main.py lines and the Scout interactive pause are in English; the pause now reads Scout file created at work/scout.md. Please review/edit the names and equivalents, then press Enter to start translation...

### CLI usage
- Full book: python main.py book.epub [--font path/to/font.woff2] [--jobs 4] [--resume]
- Health check: python main.py book.epub --sample (or --sample 1 / --chapter 2) -> sample_translated.epub
- Non-interactive: add --auto-approve to skip the scout.md review pause

### Bugs found (Step 5)
- None; logger test asserts total_tokens calculation and phase tracking, and the sample end-to-end test still passes with logging enabled

### Next step
- Await user instruction for the next phase, expected live run on a real EPUB. Do not start it before approval.

Skipped: pytest was run this time (not skipped); live real-book run, synthetic EPUB only; long-book multi-wave scout merge still untested on a real book.
