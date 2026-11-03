import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from core.css_injector import CSSInjector
from core.epub_handler import EpubHandler
from core.tag_preserver import TagPreserver
from core.translator import parse_and_collect

def _local(tag):
    return tag.rsplit('}', 1)[-1].lower()

def _ns(tag):
    return tag[1:].split('}')[0] if tag.startswith('{') else ''

def set_inner(el, restored):
    for child in list(el):
        el.remove(child)
    el.text = None
    try:
        wrap = ET.fromstring('<root>' + restored + '</root>')
    except ET.ParseError:
        el.text = restored
        return
    el.text = wrap.text
    for child in list(wrap):
        el.append(child)

class EpubBuilder:
    def __init__(self, work_dir='work', raw_dir=None):
        self.work_dir = Path(work_dir)
        self.raw_dir = Path(raw_dir) if raw_dir else self.work_dir / 'raw'

    def load_records(self):
        folder = self.work_dir / 'ed'
        if not folder.exists() or not list(folder.glob('*.json')):
            folder = self.work_dir / 'tr'
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))]

    def find_opf(self, handler=None):
        if handler is not None:
            return handler.opf_path if handler.opf_path is not None else handler.find_opf_path()
        found = sorted(self.raw_dir.rglob('*.opf'))
        if not found:
            raise ValueError('OPF file not found in raw dir')
        return found[0]

    def build(self, output_path, font_path=None, xhtml_files=None, handler=None):
        structure = json.loads((self.work_dir / 'structure.json').read_text(encoding='utf-8'))
        stored = {}
        for rec in self.load_records():
            for item in rec['items']:
                stored[(item['file'], item['index'])] = item
        opf_path = self.find_opf(handler)
        opf_dir = opf_path.parent
        css_path = opf_dir / 'styles' / 'translation.css'
        css_path.parent.mkdir(parents=True, exist_ok=True)
        font_name = None
        if font_path:
            font_name = Path(font_path).name
            css = CSSInjector().generate_css(font_path=font_path, fonts_dir=opf_dir / 'Fonts')
            css = css.replace("url('" + font_name + "')", "url('../Fonts/" + font_name + "')")
        else:
            css = CSSInjector().generate_css()
        css += '\nh1 { font-size: 2rem !important; }\nh2 { font-size: 1.5rem !important; }\np { font-size: 1em !important; }\n.note, small { font-size: 0.85em !important; }\n'
        css_path.write_text(css, encoding='utf-8')
        files = list(xhtml_files) if xhtml_files else sorted(self.raw_dir.rglob('*.xhtml'))
        for file_path in files:
            root, pairs = parse_and_collect(file_path, structure)
            ns = _ns(root.tag)
            if ns:
                ET.register_namespace('', ns)
            for el, item in pairs:
                saved = stored.get((item['file'], item['index']))
                if not saved:
                    continue
                restored = TagPreserver().restore_tags(saved.get('reviewed_masked') or saved.get('translated_masked', ''), saved.get('tag_map', {}))
                set_inner(el, restored)
            head = None
            for child in root:
                if _local(child.tag) == 'head':
                    head = child
                    break
            if head is None:
                head = ET.Element(f'{{{ns}}}head') if ns else ET.Element('head')
                root.insert(0, head)
            href = os.path.relpath(css_path, Path(file_path).parent).replace(os.sep, '/')
            if not any(_local(c.tag) == 'link' and c.get('href') == href for c in head):
                link = ET.SubElement(head, f'{{{ns}}}link' if ns else 'link')
                link.set('rel', 'stylesheet')
                link.set('type', 'text/css')
                link.set('href', href)
            ET.ElementTree(root).write(file_path, encoding='utf-8', xml_declaration=True)
        otree = ET.parse(opf_path)
        oroot = otree.getroot()
        ons = _ns(oroot.tag)
        if ons:
            ET.register_namespace('', ons)
        ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
        manifest = None
        spine = None
        for el in oroot.iter():
            if _local(el.tag) == 'manifest' and manifest is None:
                manifest = el
            elif _local(el.tag) == 'spine' and spine is None:
                spine = el
        if spine is not None:
            spine.set('page-progression-direction', 'rtl')
        def add_item(item_id, href, media):
            if manifest is None:
                return
            if any(_local(e.tag) == 'item' and e.get('href') == href for e in manifest):
                return
            it = ET.SubElement(manifest, f'{{{ons}}}item' if ons else 'item')
            it.set('id', item_id)
            it.set('href', href)
            it.set('media-type', media)
        add_item('translation-css', 'styles/translation.css', 'text/css')
        if font_name:
            media = 'font/woff2' if font_name.lower().endswith('.woff2') else 'font/ttf'
            add_item('custom-font', 'Fonts/' + font_name, media)
        otree.write(opf_path, encoding='utf-8', xml_declaration=True)
        out_handler = handler or EpubHandler(self.raw_dir / 'book.epub', work_dir=self.work_dir)
        out_handler.raw_dir = self.raw_dir
        out_handler.repackage(output_path, source_dir=self.raw_dir)
        return Path(output_path)

    build_epub = build
