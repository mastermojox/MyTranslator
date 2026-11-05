import asyncio
import json
import os
import re
from pathlib import Path
from core.logger import log
from core.tag_preserver import TagPreserver
from core.translator import ID_RE, parse_blocks

_MARKER_RE = re.compile(r'\[\[\[\s*(THINK|P)\s*(\d+)\s*\]\]\]|\[\[\s*(THINK|P)\s*(\d+)\s*\]\]|\[\s*(THINK|P)\s*(\d+)\s*\]|(?:\*\*|#)?\s*(THINK|P)\s*(\d+)\s*[:：]', re.IGNORECASE)
_REVIEW_P_RE = _MARKER_RE

def _strip_code_fences(text):
    return str(text).replace('```markdown', '').replace('```', '').strip()

def _marker_info(match):
    groups = match.groups()
    for i in range(0, len(groups), 2):
        if groups[i] is not None:
            return groups[i].upper(), int(groups[i + 1])
    return None, None

def _parse_review_output(text):
    cleaned = _strip_code_fences(text)
    matches = list(_MARKER_RE.finditer(cleaned))
    blocks = {}
    notes = {}
    for k, m in enumerate(matches):
        kind, pid = _marker_info(m)
        if kind is None:
            continue
        end = matches[k + 1].start() if k + 1 < len(matches) else len(cleaned)
        content = cleaned[m.end():end].strip()
        if not content:
            continue
        if kind == 'THINK':
            notes[pid] = content
        elif kind == 'P':
            blocks[pid] = content
    if not blocks:
        blocks = parse_blocks(cleaned)
    return blocks, notes

def _parse_review_blocks(text):
    return _parse_review_output(text)[0]

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
        return 'Revise the Persian draft against the English source. For each paragraph output [[[THINK id]]] analysis first, then the final [[[P id]]] block. Preserve [idN] placeholders.'

    async def review_chunk(self, record, scout_text=''):
        items = record['items']
        src = '\n'.join(f'[[[P {j}]]] ' + it['masked'] for j, it in enumerate(items))
        draft = '\n'.join(f'[[[P {j}]]] ' + it['translated_masked'] for j, it in enumerate(items))
        user = 'SOURCE:\n' + src + '\n\nDRAFT:\n' + draft + '\n\nSCOUT:\n' + scout_text
        raw = await self.llm_client.generate(self.load_prompt(), user, temperature=0.2, model=self.model)
        blocks, notes = _parse_review_output(raw)
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
            if j in notes:
                copied['notes'] = notes[j]
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
