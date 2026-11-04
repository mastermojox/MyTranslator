import asyncio
import json
import os
from pathlib import Path
from core.logger import log
from core.tag_preserver import TagPreserver
from core.translator import ID_RE, parse_blocks
import re

_REVIEW_P_RE = re.compile(r'\[\[\[\s*P\s*(\d+)\s*\]\]\]|\[\[\s*P\s*(\d+)\s*\]\]|\[\s*P\s*(\d+)\s*\]|(?:\*\*|#)?\s*P\s*(\d+)\s*[:：]', re.IGNORECASE)

def _strip_code_fences(text):
    return str(text).replace('```markdown', '').replace('```', '').strip()

def _parse_review_blocks(text):
    blocks = parse_blocks(_strip_code_fences(text))
    if blocks:
        return blocks
    cleaned = _strip_code_fences(text)
    matches = list(_REVIEW_P_RE.finditer(cleaned))
    out = {}
    for k, m in enumerate(matches):
        pid = int(next(g for g in m.groups() if g is not None))
        end = matches[k + 1].start() if k + 1 < len(matches) else len(cleaned)
        content = cleaned[m.end():end].strip()
        if content:
            out[pid] = content
    return out

def _map_review_lines(text, expected_count):
    cleaned = _strip_code_fences(text)
    parts = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]
    if len(parts) != expected_count:
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        lines = [re.sub(r'^\d+[\.\)]\s*', '', ln) for ln in lines]
        parts = lines if len(lines) == expected_count else []
    return {i: parts[i] for i in range(expected_count)} if len(parts) == expected_count else {}

def _warn_review_fallback(chunk_num):
    msg = f'Review parse failed for chunk {chunk_num}; falling back to draft translation'
    try:
        log._print(f'[yellow][WARN][/yellow] {msg}')
    except Exception:
        print(f'[WARN] {msg}')

class Reviewer:
    def __init__(self, llm_client=None, work_dir='work', jobs=4, model=None, prompt_path='prompts/review.md'):
        self.llm_client = llm_client
        self.work_dir = Path(work_dir)
        self.tr_dir = self.work_dir / 'tr'
        self.ed_dir = self.work_dir / 'ed'
        self.jobs = max(1, int(jobs))
        self.model = model or os.getenv('MODEL_REVIEW', 'claude-haiku-4-5-20251001')
        self.prompt_path = Path(prompt_path)

    def load_prompt(self):
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding='utf-8')
        return 'Revise the Persian draft against the English source. Preserve [idN] placeholders. Return only [[[P id]]] blocks.'

    async def review_chunk(self, record, scout_text=''):
        items = record['items']
        src = '\n'.join(f'[[[P {j}]]] ' + it['masked'] for j, it in enumerate(items))
        draft = '\n'.join(f'[[[P {j}]]] ' + it['translated_masked'] for j, it in enumerate(items))
        user = 'SOURCE:\n' + src + '\n\nDRAFT:\n' + draft + '\n\nSCOUT:\n' + scout_text
        raw = await self.llm_client.generate(self.load_prompt(), user, temperature=0.2, model=self.model)
        blocks = _parse_review_blocks(raw)
        if not blocks:
            blocks = _map_review_lines(raw, len(items))
        if not blocks:
            _warn_review_fallback(record['chunk'])
            blocks = {}
        new_items = []
        for j, item in enumerate(items):
            reviewed = blocks.get(j, item['translated_masked'])
            missing = [p for p in ID_RE.findall(item['masked']) if p not in reviewed]
            if missing:
                reviewed = TagPreserver().align_missing_placeholders(reviewed, missing, source_text=item['masked'])
            copied = dict(item)
            copied['reviewed_masked'] = reviewed
            copied['translated_masked'] = reviewed
            new_items.append(copied)
        out = {'chunk': record['chunk'], 'items': new_items, 'meta': record.get('meta', {})}
        self.ed_dir.mkdir(parents=True, exist_ok=True)
        (self.ed_dir / f"{record['chunk']:04d}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        log.worker(f"Review chunk {record['chunk']} saved")
        log.advance()
        return out

    async def review_all(self, scout_text='', resume=False):
        if self.llm_client is None:
            raise ValueError('llm_client is required')
        files = sorted(self.tr_dir.glob('*.json'))
        if not files:
            raise ValueError('No translated chunks found in work/tr')
        log.set_phase('Review', len(files))
        semaphore = asyncio.Semaphore(self.jobs)
        async def run_one(path):
            record = json.loads(path.read_text(encoding='utf-8'))
            out_path = self.ed_dir / path.name
            if resume and out_path.exists():
                return json.loads(out_path.read_text(encoding='utf-8'))
            async with semaphore:
                return await self.review_chunk(record, scout_text)
        return list(await asyncio.gather(*[run_one(p) for p in files]))

    run = review_all

ParallelReviewer = Reviewer
