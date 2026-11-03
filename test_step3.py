import asyncio
import json
import tempfile
from pathlib import Path

from core.scout import BookScouter, parse_args

def xhtml(body):
    return '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body>' + body + '</body></html>'

class FakeLLMClient:
    def __init__(self):
        self.calls = 0
    async def generate(self, system_prompt, user_prompt, temperature=0.2, model=None):
        self.calls += 1
        assert model == 'deepseek-v4.1-flash-1017'
        assert 'Uncensored' in system_prompt
        assert 'imperial' in system_prompt
        assert 'SKIPME' not in user_prompt
        return '\n'.join(['## VOICES', 'First-person narrator, short harsh sentences; John uses street slang, Mary is dry and formal.', '## CHARACTERS', '| John Carter | جان کارتر | male, او گفت | rough street slang, profanity preserved: damn |', '| Mary Hale | مری هیل | female, او گفت | dry, formal |', '## TERMS', '| Blackwood Manor | عمارت بلک‌وود | place |', '| five miles | پنج مایل | imperial unit, not converted |'])

def test_scout_generation_and_cache():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        work = base / 'work'
        work.mkdir()
        (work / 'structure.json').write_text(json.dumps({'h1.title': 'title', 'p.body': 'p', 'p.toc': 'skip'}), encoding='utf-8')
        chapter = base / 'chapter1.xhtml'
        chapter.write_text(xhtml('<h1 class="title">Blackwood Manor</h1><p class="body">I am John Carter. Damn, I walked five miles in the rain to Blackwood Manor.</p><p class="body">Mary Hale stood six feet away, holding two pounds of letters. She never swore.</p><p class="toc">SKIPME contents entry</p>'), encoding='utf-8')
        fake = FakeLLMClient()
        scouter = BookScouter(llm_client=fake, work_dir=work)
        paragraphs = scouter.collect_paragraphs([chapter])
        assert len(paragraphs) == 3
        assert all('SKIPME' not in p for p in paragraphs)
        assert len(scouter.chunk_paragraphs(['a' * 10, 'b' * 10, 'c' * 10], max_chars=25)) == 2
        result = asyncio.run(scouter.scout([chapter], auto_approve=True))
        saved = (work / 'scout.md').read_text(encoding='utf-8')
        assert saved == result
        for section in ('## VOICES', '## CHARACTERS', '## TERMS'):
            assert section in saved
        assert 'جان کارتر' in saved and 'پنج مایل' in saved
        assert 'کیلومتر' not in saved
        assert fake.calls == 1
        cached = asyncio.run(scouter.scout([chapter], auto_approve=True))
        assert cached == result
        assert fake.calls == 1
        assert parse_args(['--auto-approve']).auto_approve is True
        assert scouter.interactive_pause(auto_approve=True) is True

if __name__ == '__main__':
    test_scout_generation_and_cache()
    print('PASS: all step-3 scenarios passed')
