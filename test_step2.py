import asyncio
import json
import tempfile
import zipfile
from pathlib import Path

from core.css_injector import CSSInjector
from core.epub_handler import EpubHandler
from core.style_census import StyleCensus

CONTAINER = '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
OPF = '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bid" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bid">test-book</dc:identifier><dc:title>Test</dc:title><dc:language>en</dc:language></metadata><manifest><item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>'

def xhtml(body):
    return '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body>' + body + '</body></html>'

def build_epub(path):
    toc1 = ''.join(f'<p class="toc">Toc {i}</p>' for i in range(5))
    toc2 = ''.join(f'<p class="toc">Toc {i}</p>' for i in range(5, 10))
    ch1 = xhtml('<h1 class="title">Book Title</h1><h2 class="subtitle">A Subtitle</h2><p class="body">Body one</p>' + toc1)
    ch2 = xhtml(toc2 + '<p class="body">Body two</p><ul><li class="note">A note</li></ul>')
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', CONTAINER, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/content.opf', OPF, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/chapter1.xhtml', ch1, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/chapter2.xhtml', ch2, compress_type=zipfile.ZIP_DEFLATED)

class FakeLLMClient:
    def __init__(self):
        self.calls = 0
    async def generate(self, system_prompt, user_prompt, temperature=0.0, model=None):
        self.calls += 1
        assert model
        return 'h1.title = title\nh2.subtitle = subtitle\np.body = p\np.toc = skip\nli.note = note'

def test_epub_extract_census_and_structure():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        epub_path = base / 'book.epub'
        build_epub(epub_path)
        handler = EpubHandler(epub_path, work_dir=base / 'work')
        raw = handler.extract()
        assert (raw / 'META-INF' / 'container.xml').exists()
        spine_files = handler.get_spine_xhtml()
        assert [p.name for p in spine_files] == ['chapter1.xhtml', 'chapter2.xhtml']
        census = StyleCensus()
        result = census.scan_styles(spine_files)
        assert result[('h1', 'title')]['count'] == 1
        assert result[('p', 'body')]['count'] == 2
        assert result[('p', 'toc')]['count'] == 10
        assert result[('p', 'toc')]['samples'] == ['Toc 0', 'Toc 5', 'Toc 9']
        fake = FakeLLMClient()
        structure = asyncio.run(census.generate_structure(fake, base / 'work'))
        assert structure['h1.title'] == 'title'
        assert structure['p.toc'] == 'skip'
        saved = (base / 'work' / 'structure.json').read_text(encoding='utf-8')
        assert json.loads(saved) == structure
        assert '\n  "h1.title"' in saved
        cached = asyncio.run(census.generate_structure(fake, base / 'work'))
        assert cached == structure
        assert fake.calls == 1
        out_epub = base / 'repacked.epub'
        handler.repackage(out_epub)
        with zipfile.ZipFile(out_epub) as zf:
            infos = zf.infolist()
            assert infos[0].filename == 'mimetype'
            assert infos[0].compress_type == zipfile.ZIP_STORED
            assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in infos[1:])

def test_zip_slip_blocked():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        evil = base / 'evil.epub'
        with zipfile.ZipFile(evil, 'w') as zf:
            zf.writestr('../evil.txt', 'x')
        handler = EpubHandler(evil, work_dir=base / 'work')
        try:
            handler.extract()
            raise AssertionError('Zip Slip was not blocked')
        except ValueError:
            pass
        assert not (base / 'evil.txt').exists()

def test_css_default_and_custom_font():
    injector = CSSInjector()
    css = injector.generate_css()
    assert '@font-face' not in css
    assert "font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, 'Segoe UI', Tahoma, Arial, sans-serif !important;" in css
    assert 'direction: rtl !important;' in css
    assert 'code, pre { direction: ltr !important;' in css
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        raw = base / 'raw'
        raw.mkdir()
        font = base / 'MyFont.ttf'
        font.write_bytes(b'fake-font')
        css_path = injector.inject(raw, font_path=font)
        assert (raw / 'fonts' / 'MyFont.ttf').exists()
        custom = css_path.read_text(encoding='utf-8')
        assert '@font-face' in custom
        assert "font-family: 'MyFont', 'Vazirmatn'" in custom
        assert '../fonts/MyFont.ttf' in custom

if __name__ == '__main__':
    test_epub_extract_census_and_structure()
    test_zip_slip_blocked()
    test_css_default_and_custom_font()
    print('PASS: all step-2 scenarios passed')
