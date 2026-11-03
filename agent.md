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

### Status
- Tests: PASS - python test_end_to_end.py printed PASS: all end-to-end scenarios passed
- Git commit: being created at end of this step with message feat(pipeline): complete translation engine, parallel reviewer, epub builder, and CLI with sample mode

### Pipeline architecture
- Flow: EpubHandler.extract -> StyleCensus.scan_styles + generate_structure -> BookScouter.scout (interactive pause unless --auto-approve) -> Translator.translate (sequential) -> Reviewer.review_all (parallel, --jobs) -> EpubBuilder.build -> EpubHandler.repackage.
- Chunking (translator): translatable elements are block tags whose structure role is title, subtitle, p, verse or note (skip excluded); ancestors of another translatable element are skipped to avoid double translation. Inner XML of each element is masked with TagPreserver so the publisher outer tags/attributes are never sent or touched. Chunks accumulate whole elements up to 300-500 estimated tokens (whitespace word count), never splitting an element.
- Term substitution: scout.md tables are parsed into (original, Persian) pairs; before sending, originals are replaced longest-first with [[TERM]] codes; after the model replies, codes are restored to the canonical Persian, so names cannot be distorted.
- Rolling plot: work/state.json holds plot_summary, tail (last 3 translated paragraphs of the previous chunk) and completed_chunks; both are injected into the next chunk prompt. The [[[META]]] block of each reply (plot, terms) updates the state.
- Crash resilience: each chunk is written immediately to work/tr/NNNN.json; reviewer output goes to work/ed/NNNN.json; --resume reuses existing tr/ed files and state instead of re-calling the API.
- Reviewer: asyncio with a Semaphore(jobs); sends SOURCE + DRAFT + SCOUT to MODEL_REVIEW, validates [idN] placeholders and repairs missing ones with the proportional fallback.
- Builder: maps edited items back by (file, index) using the same collection routine as the translator, restores tags, sets spine page-progression-direction=rtl in content.opf, writes OEBPS/styles/translation.css and links it from every translated XHTML, registers the CSS (and the font, when given) in the OPF manifest, then repackages with mimetype stored first.
- Fonts: custom font is copied to OEBPS/Fonts, @font-face points to ../Fonts/<file>, relative size rules are added (h1 2rem, h2 1.5rem, p 1em, note/small 0.85em); with no font, only the system Vazirmatn stack CSS is injected and nothing is embedded.
- Sample mode: --sample or --sample N or --chapter N restricts census, scout, translation and review to that single spine chapter (default first), compiles immediately and writes sample_translated.epub; the rest of the book is repackaged untranslated.

### Modules and functions (Step 4)
- prompts/translate.md - faithful voice, mandatory uncensored rule, preserve imperial units, preserve [idN] and [[TERM]] codes, exact response format [[[P id]]] blocks plus [[[META]]] plot/terms.
- prompts/review.md - bilingual critic editor, receives SOURCE + DRAFT + SCOUT, removes translationese, never alters names, units or harsh language, returns only revised [[[P id]]] blocks.
- core/translator.py - parse_and_collect, collect_items, parse_scout_terms, apply_terms, restore_terms, parse_blocks, parse_meta; Translator.make_chunks, Translator.translate (run alias); SequentialTranslator alias.
- core/reviewer.py - Reviewer.review_chunk, Reviewer.review_all (run alias); ParallelReviewer alias; jobs semaphore, model from MODEL_REVIEW.
- core/builder.py - EpubBuilder.load_records (ed preferred over tr), find_opf, build (build_epub alias), set_inner fragment replacement preserving element attributes.
- main.py - load_env (tiny .env loader), parse_args (book_path, --font, --jobs default 4, --sample nargs ? const 1, --chapter, --resume, --auto-approve), async run_pipeline with injectable llm_client/review_client/work_dir/output_path for tests, main entry point.
- test_end_to_end.py - FakeLLMClient dispatching on prompt type (structure, scout, translate, review), builds a 2-chapter EPUB, runs run_pipeline with sample=1, asserts tr/ed/state files, rebuilt EPUB validity, mimetype stored first, Persian terms restored, imperial unit kept as پنج مایل, inline <b> tag restored, skip paragraph untouched, chapter 2 untranslated, system CSS without @font-face, rtl spine in OPF; plus CLI argument tests.

### CLI usage
- Full book: python main.py book.epub [--font path/to/font.woff2] [--jobs 4] [--resume]
- Health check: python main.py book.epub --sample (or --sample 1 / --chapter 2) -> sample_translated.epub
- Non-interactive: add --auto-approve to skip the scout.md review pause.

### Bugs found (Step 4)
- httpx was not installed in this environment: first test_end_to_end.py run failed with ModuleNotFoundError, and pip install -r requirements.txt timed out against mirror-pypi.runflare.com with no matching distribution found. Fix: core/llm_client.py now imports httpx optionally; when missing, AsyncClient is None and generate raises LLMClientError only on a real API call, so offline tests with FakeLLMClient pass. Real API use still requires httpx installed.

### Next step
- Await user instruction for the next phase, expected live run or hardening on a real EPUB. Do not start it before approval.

Skipped: pytest run, direct execution was accepted alternative and passed; live LLM call, FakeLLMClient used because no live run was requested in this test; real-book run, synthetic 2-chapter EPUB used.
