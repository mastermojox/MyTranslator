import argparse
import asyncio
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from core.builder import EpubBuilder
from core.epub_handler import EpubHandler
from core.llm_client import LLMClient
from core.reviewer import Reviewer
from core.scout import BookScouter
from core.style_census import StyleCensus
from core.logger import log
from core.translator import Translator

def load_env(path='.env'):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='EPUB book translator (EN to FA)')
    parser.add_argument('book_path')
    parser.add_argument('--font', default=None, help='Custom font file (.woff2 or .ttf)')
    parser.add_argument('--jobs', type=int, default=4, help='Parallel review jobs')
    parser.add_argument('--sample', type=int, nargs='?', const=1, default=None, help='Health-check mode: translate only chapter N (default first chapter) and write sample_translated.epub')
    parser.add_argument('--chapter', type=int, default=None, help='Translate only chapter N')
    parser.add_argument('--resume', action='store_true', help='Resume from existing work/tr chunks')
    parser.add_argument('--auto-approve', action='store_true', help='Skip the interactive scout.md review pause')
    return parser.parse_args(argv)

async def run_pipeline(book_path, font=None, jobs=4, sample=None, chapter=None, resume=False, auto_approve=False, llm_client=None, review_client=None, work_dir='work', output_path=None):
    load_env()
    selected = chapter if chapter is not None else (1 if sample is True else sample)
    work = Path(work_dir)
    translate_client = llm_client or LLMClient()
    edit_client = review_client or llm_client or LLMClient()
    log.start()
    log.info(f'Starting pipeline for {book_path}')
    log.set_phase('Scout', 1)
    handler = EpubHandler(book_path, work_dir=work)
    handler.extract()
    log.info(f'EPUB extracted to {work}')
    spine = handler.get_spine_xhtml()
    def _words(path):
        try:
            return sum(len(''.join(e.itertext()).split()) for e in ET.parse(path).getroot().iter() if e.tag.rsplit('}', 1)[-1].lower() in {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'})
        except Exception:
            return 0
    if selected is not None:
        content = [f for f in spine if _words(f) >= 200] or spine
        if selected < 1 or selected > len(content):
            raise ValueError(f'Chapter {selected} out of range (book has {len(content)} content chapters)')
        files = [content[selected - 1]]
        log.info(f'Sample mode: content chapter {selected} is {files[0]}')
    else:
        files = spine
    census = StyleCensus()
    census.scan_styles(spine)
    structure = await census.generate_structure(translate_client, work)
    scout_text = await BookScouter(llm_client=translate_client, work_dir=work).scout(files, auto_approve=auto_approve)
    await Translator(llm_client=translate_client, work_dir=work).translate(files, structure, scout_text, resume=resume)
    await Reviewer(llm_client=edit_client, work_dir=work, jobs=jobs).review_all(scout_text, resume=resume)
    out = Path(output_path) if output_path else (Path('sample_translated.epub') if selected is not None else Path(Path(book_path).stem + '_translated.epub'))
    EpubBuilder(work_dir=work).build(out, font_path=font, xhtml_files=files, handler=handler)
    log.phase_done('Build')
    log.info(f'Output ready: {out}')
    log.stop()
    return out

def main(argv=None):
    args = parse_args(argv)
    out = asyncio.run(run_pipeline(args.book_path, font=args.font, jobs=args.jobs, sample=args.sample, chapter=args.chapter, resume=args.resume, auto_approve=args.auto_approve))
    print(str(out))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
