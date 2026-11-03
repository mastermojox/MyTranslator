import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from core.tag_preserver import TagPreserver

TEXT_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li'}
TEXT_ROLES = {'title', 'subtitle', 'p', 'verse', 'note'}
P_RE = re.compile(r'\[\[\[P\s+(\d+)\]\]\]')
ID_RE = re.compile(r'\[id\d+\]')

def _local(tag):
    return tag.rsplit('}', 1)[-1].lower()

def inner_xml(el):
    parts = []
    if el.text:
        parts.append(el.text)
    for child in list(el):
        parts.append(ET.tostring(child, encoding='unicode'))
    return ''.join(parts).strip()

def role_for(el, structure):
    tag = _local(el.tag)
    for cls in (el.get('class') or '').split() or ['']:
        key = f'{tag}.{cls}' if cls else tag
        if key in structure:
            return structure[key]
    return structure.get(tag)

def parse_and_collect(xhtml_file, structure):
    root = ET.parse(xhtml_file).getroot()
    pairs = []
    idx = 0
    for el in root.iter():
        tag = _local(el.tag)
        if tag not in TEXT_TAGS:
            continue
        if role_for(el, structure) not in TEXT_ROLES:
            continue
        if not ''.join(el.itertext()).strip():
            continue
        descendants = [d for d in el.iter() if d is not el and _local(d.tag) in TEXT_TAGS and role_for(d, structure) in TEXT_ROLES and ''.join(d.itertext()).strip()]
        if descendants:
            continue
        masked, tag_map = TagPreserver().preserve_tags(inner_xml(el))
        item = {'file': str(xhtml_file), 'index': idx, 'tag': tag, 'role': role_for(el, structure), 'source': inner_xml(el), 'masked': masked, 'tag_map': tag_map}
        pairs.append((el, item))
        idx += 1
    return root, pairs

def collect_elements(xhtml_file, structure):
    return parse_and_collect(xhtml_file, structure)[1]

def collect_items(xhtml_files, structure):
    return [item for f in xhtml_files for _, item in collect_elements(f, structure)]

def parse_scout_terms(scout_text):
    terms = []
    for line in scout_text.splitlines():
        s = line.strip()
        if not s.startswith('|'):
            continue
        parts = [p.strip() for p in s.strip('|').split('|')]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        if parts[0].lower() in ('original name', 'original term or place') or '---' in parts[0]:
            continue
        if (parts[0], parts[1]) not in terms:
            terms.append((parts[0], parts[1]))
    return terms

def apply_terms(text, terms):
    out = text
    for i in sorted(range(len(terms)), key=lambda j: -len(terms[j][0])):
        out = out.replace(terms[i][0], f'[[TERM{i}]]')
    return out

def restore_terms(text, terms):
    out = text
    for i, (orig, pers) in enumerate(terms):
        out = out.replace(f'[[TERM{i}]]', pers)
    return out

def parse_blocks(text):
    blocks = {}
    matches = list(P_RE.finditer(text))
    for k, m in enumerate(matches):
        if k + 1 < len(matches):
            end = matches[k + 1].start()
        else:
            end = text.find('[[[META]]]', m.end())
            if end < 0:
                end = len(text)
        blocks[int(m.group(1))] = text[m.end():end].strip()
    return blocks

def parse_meta(text):
    meta = {'plot': '', 'terms': []}
    if '[[[META]]]' not in text:
        return meta
    for line in text.split('[[[META]]]', 1)[1].splitlines():
        s = line.strip()
        if s.lower().startswith('plot:') or s.lower().startswith('summary:'):
            meta['plot'] = s.split(':', 1)[1].strip()
        elif s.lower().startswith('terms:'):
            meta['terms'] = [t.strip() for t in s.split(':', 1)[1].split(',') if t.strip()]
    return meta

class Translator:
    def __init__(self, llm_client=None, work_dir='work', model=None, prompt_path='prompts/translate.md', chunk_max_tokens=500):
        self.llm_client = llm_client
        self.work_dir = Path(work_dir)
        self.tr_dir = self.work_dir / 'tr'
        self.state_path = self.work_dir / 'state.json'
        self.model = model or os.getenv('MODEL_TRANSLATE', 'deepseek-v4.1-flash-1017')
        self.prompt_path = Path(prompt_path)
        self.chunk_max_tokens = max(300, min(int(chunk_max_tokens), 500))

    def load_prompt(self):
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding='utf-8')
        return 'Translate to Persian. Preserve [idN] placeholders. Reply with [[[P id]]] blocks and a [[[META]]] block with plot and terms.'

    def make_chunks(self, items, max_tokens=None):
        limit = max_tokens or self.chunk_max_tokens
        chunks, cur, total = [], [], 0
        for item in items:
            n = max(1, len(item['masked'].split()))
            if cur and total + n > limit:
                chunks.append(cur)
                cur, total = [], 0
            cur.append(item)
            total += n
        if cur:
            chunks.append(cur)
        return chunks

    chunk_items = make_chunks

    async def translate(self, xhtml_files, structure, scout_text='', resume=False):
        if self.llm_client is None:
            raise ValueError('llm_client is required')
        terms = parse_scout_terms(scout_text)
        items = collect_items(xhtml_files, structure)
        chunks = self.make_chunks(items)
        self.tr_dir.mkdir(parents=True, exist_ok=True)
        state = {'plot_summary': '', 'tail': [], 'completed_chunks': []}
        if resume and self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding='utf-8'))
        results = []
        for num, chunk in enumerate(chunks, 1):
            out_path = self.tr_dir / f'{num:04d}.json'
            if resume and out_path.exists():
                results.append(json.loads(out_path.read_text(encoding='utf-8')))
                continue
            lines = [f'[[[P {j}]]] ' + apply_terms(item['masked'], terms) for j, item in enumerate(chunk)]
            user = 'PLOT SO FAR:\n' + state.get('plot_summary', '') + '\n\nPREVIOUS TAIL:\n' + '\n'.join(state.get('tail', [])) + '\n\nSCOUT:\n' + scout_text + '\n\nTRANSLATE:\n' + '\n'.join(lines)
            raw = await self.llm_client.generate(self.load_prompt(), user, temperature=0.3, model=self.model)
            blocks = parse_blocks(raw)
            meta = parse_meta(raw)
            if not blocks:
                raise ValueError('Translator response has no [[[P id]]] blocks')
            new_items = []
            for j, item in enumerate(chunk):
                if j not in blocks:
                    raise ValueError(f'Missing translated block P {j}')
                trans = blocks[j]
                missing = [p for p in ID_RE.findall(item['masked']) if p not in trans]
                if missing:
                    trans = TagPreserver().align_missing_placeholders(trans, missing, source_text=item['masked'])
                copied = dict(item)
                copied['translated_masked'] = restore_terms(trans, terms)
                new_items.append(copied)
            record = {'chunk': num, 'items': new_items, 'meta': meta}
            out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            if meta.get('plot'):
                state['plot_summary'] = meta['plot']
            state['tail'] = [it['translated_masked'] for it in new_items[-3:]]
            state['completed_chunks'] = sorted(set(state.get('completed_chunks', []) + [num]))
            self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            results.append(record)
        return results

    run = translate

SequentialTranslator = Translator
