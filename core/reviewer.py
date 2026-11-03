import asyncio
import json
import os
from pathlib import Path
from core.tag_preserver import TagPreserver
from core.translator import ID_RE, parse_blocks

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
        blocks = parse_blocks(raw)
        if not blocks:
            raise ValueError('Reviewer response has no [[[P id]]] blocks')
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
        return out

    async def review_all(self, scout_text='', resume=False):
        if self.llm_client is None:
            raise ValueError('llm_client is required')
        files = sorted(self.tr_dir.glob('*.json'))
        if not files:
            raise ValueError('No translated chunks found in work/tr')
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
