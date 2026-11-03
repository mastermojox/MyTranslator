from __future__ import annotations
import argparse
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

def _local(tag):
    return tag.rsplit('}', 1)[-1].lower()

TEXT_ROLES = {'p', 'title'}

class BookScouter:
    def __init__(self, llm_client=None, work_dir='work', chunk_size=120000, model=None, prompt_path='prompts/scout.md'):
        self.llm_client = llm_client
        self.work_dir = Path(work_dir)
        self.chunk_size = max(100000, min(int(chunk_size), 150000))
        self.model = model or os.getenv('MODEL_TRANSLATE', 'deepseek-v4.1-flash-1017')
        self.prompt_path = Path(prompt_path)
        self.scout_path = self.work_dir / 'scout.md'

    def load_structure(self, structure_path=None):
        path = Path(structure_path) if structure_path else self.work_dir / 'structure.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def collect_paragraphs(self, xhtml_files, structure=None):
        structure = structure if structure is not None else self.load_structure()
        paragraphs = []
        for file_path in xhtml_files:
            for el in ET.parse(file_path).getroot().iter():
                tag = _local(el.tag)
                classes = (el.get('class') or '').split() or ['']
                text = ' '.join(''.join(el.itertext()).split())
                if not text:
                    continue
                for cls in classes:
                    key = f'{tag}.{cls}' if cls else tag
                    role = structure.get(key, structure.get(tag))
                    if role in TEXT_ROLES:
                        paragraphs.append(text)
                        break
        return paragraphs

    def chunk_paragraphs(self, paragraphs, max_chars=None):
        limit = max_chars or self.chunk_size
        chunks, current = [], ''
        for para in paragraphs:
            candidate = para if not current else current + '\n\n' + para
            if current and len(candidate) > limit:
                chunks.append(current)
                current = para
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    def _system_prompt(self):
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding='utf-8')
        return 'Extract VOICES, CHARACTERS and TERMS. Preserve profanity uncensored and never convert imperial units to metric.'

    @staticmethod
    def merge_results(results):
        seen, lines = set(), []
        for result in results:
            for line in str(result).splitlines():
                stripped = line.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    lines.append(line.rstrip())
        merged = '\n'.join(lines).strip() + '\n'
        for section in ('## VOICES', '## CHARACTERS', '## TERMS'):
            if section not in merged:
                merged += section + '\n'
        return merged

    def interactive_pause(self, auto_approve=False):
        if auto_approve:
            return True
        print('Scout file created at work/scout.md. Please review/edit the names and equivalents, then press Enter to start translation...')
        input()
        return True

    async def scout(self, xhtml_files, auto_approve=False):
        if self.scout_path.exists():
            return self.scout_path.read_text(encoding='utf-8')
        if self.llm_client is None:
            raise ValueError('llm_client is required when work/scout.md does not exist')
        paragraphs = self.collect_paragraphs(xhtml_files)
        if not paragraphs:
            raise ValueError('No p/title paragraphs found to scout')
        results = []
        for chunk in self.chunk_paragraphs(paragraphs):
            results.append(await self.llm_client.generate(self._system_prompt(), chunk, temperature=0.2, model=self.model))
        merged = self.merge_results(results)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.scout_path.write_text(merged, encoding='utf-8')
        self.interactive_pause(auto_approve=auto_approve)
        return merged

    run = scout

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='EPUB translator')
    parser.add_argument('--auto-approve', action='store_true', help='Skip the interactive scout.md review pause')
    return parser.parse_args(argv)
