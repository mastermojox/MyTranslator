from __future__ import annotations
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

TEXT_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li'}
VALID_ROLES = {'title', 'subtitle', 'p', 'verse', 'note', 'skip'}
ROLE_ALIASES = {'paragraph': 'p', 'body': 'p', 'text': 'p', 'normal': 'p', 'content': 'p', 'para': 'p', 'heading': 'title', 'header': 'title', 'booktitle': 'title'}

def _local(tag):
    return tag.rsplit('}', 1)[-1].lower()

class StyleCensus:
    def __init__(self):
        self.census = {}

    def scan_styles(self, xhtml_files):
        occurrences = {}
        for file_path in xhtml_files:
            for el in ET.parse(file_path).getroot().iter():
                tag = _local(el.tag)
                if tag not in TEXT_TAGS:
                    continue
                text = ' '.join(''.join(el.itertext()).split())
                classes = (el.get('class') or '').split() or ['']
                for cls in classes:
                    occurrences.setdefault((tag, cls), []).append(text)
        self.census = {}
        for key, texts in occurrences.items():
            if len(texts) <= 3:
                samples = list(texts)
            else:
                samples = [texts[0], texts[len(texts) // 2], texts[-1]]
            self.census[key] = {'count': len(texts), 'samples': samples}
        return self.census

    async def generate_structure(self, llm_client, work_dir):
        work = Path(work_dir)
        output = work / 'structure.json'
        if output.exists():
            return json.loads(output.read_text(encoding='utf-8'))
        if not self.census:
            raise ValueError('scan_styles must be called before generate_structure')
        summary_lines = []
        for (tag, cls), info in self.census.items():
            summary_lines.append(f"{tag}.{cls or '-'} count={info['count']} samples={info['samples']}")
        system_prompt = 'You classify EPUB text styles. Reply with exactly one line per style in the form: tag.class = role . Use class - when there is no class. Valid roles: title, subtitle, p, verse, note, skip. Never invent a style that is not listed.'
        user_prompt = 'Styles:\n' + '\n'.join(summary_lines)
        model = os.getenv('MODEL_TRANSLATE', 'deepseek-v4.1-flash-1017')
        raw = await llm_client.generate(system_prompt, user_prompt, temperature=0.0, model=model)
        structure = {}
        seen = set()
        for line in str(raw).splitlines():
            line = line.strip()
            if not line:
                continue
            if '=' not in line:
                raise ValueError(f'Invalid structure line: {line}')
            left, role = [part.strip() for part in line.rsplit('=', 1)]
            role = ROLE_ALIASES.get(role.lower(), role.lower())
            if role not in VALID_ROLES:
                raise ValueError(f'Invalid role: {role}')
            if '.' in left:
                tag, cls = left.split('.', 1)
                cls = '' if cls == '-' else cls
            else:
                tag, cls = left, ''
            key = (tag, cls)
            if key not in self.census:
                raise ValueError(f'Unknown style returned by model: {left}')
            seen.add(key)
            structure[f'{tag}.{cls}' if cls else tag] = role
        if seen != set(self.census):
            raise ValueError('Model output is missing one or more known styles')
        work.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding='utf-8')
        return structure
