import asyncio
import zipfile
from pathlib import Path
import tempfile
from main import parse_args, run_pipeline

CONTAINER = "<?xml version='1.0'?><container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>"
OPF = "<package xmlns='http://www.idpf.org/2007/opf' unique-identifier='bid' version='3.0'><metadata xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:identifier id='bid'>test-book</dc:identifier><dc:title>Test</dc:title><dc:language>en</dc:language></metadata><manifest><item id='c1' href='chapter1.xhtml' media-type='application/xhtml+xml'/><item id='c2' href='chapter2.xhtml' media-type='application/xhtml+xml'/></manifest><spine><itemref idref='c1'/><itemref idref='c2'/></spine></package>"

def xhtml(body):
    return "<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><head><title>t</title></head><body>" + body + '</body></html>'

def build_epub(path):
    ch1 = xhtml("<h1 class='title'>Blackwood Manor</h1><p class='body'>John Carter walked five miles to Blackwood Manor. <b>damn</b> the rain.</p><p class='toc'>Contents SKIPME</p>")
    ch2 = xhtml("<p class='body'>Mary Hale stayed home and waited.</p>")
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', CONTAINER, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/content.opf', OPF, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/chapter1.xhtml', ch1, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr('OEBPS/chapter2.xhtml', ch2, compress_type=zipfile.ZIP_DEFLATED)

class FakeLLMClient:
    def __init__(self):
        self.calls = 0
    async def generate(self, system_prompt, user_prompt, temperature=0.3, model=None):
        self.calls += 1
        if 'classify EPUB text styles' in system_prompt:
            out = []
            roles = {'title': 'title', 'body': 'p', 'toc': 'skip', 'subtitle': 'subtitle', 'note': 'note'}
            for line in user_prompt.splitlines():
                if ' count=' not in line:
                    continue
                left = line.split(' count=')[0]
                cls = left.rsplit('.', 1)[-1]
                out.append(left + ' = ' + roles.get(cls, 'p'))
            return '\n'.join(out)
        if 'Scout Prompt' in system_prompt:
            return '\n'.join(['## VOICES', 'First-person narrator, short harsh sentences.', '## CHARACTERS', '| Original Name | Persian Translation | Gender and Persian Pronoun/Verb Example | Voice Traits |', '| John Carter | جان کارتر | male, او گفت | rough street slang |', '| Mary Hale | مری هیل | female, او گفت | dry, formal |', '## TERMS', '| Original Term or Place | Canonical Persian Rendering | Note |', '| Blackwood Manor | عمارت بلک‌وود | place |', '| five miles | پنج مایل | imperial unit, not converted |'])
        if 'Review Prompt' in system_prompt:
            return user_prompt.split('DRAFT:\n', 1)[1].split('\nSCOUT:', 1)[0].strip()
        if 'Translate Prompt' in system_prompt:
            section = user_prompt.split('TRANSLATE:\n', 1)[1]
            out = []
            for line in section.splitlines():
                if line.startswith('[[[P '):
                    out.append(line.replace(']]] ', ']]] ترجمه: ', 1))
            out.append('[[[META]]]')
            out.append('plot: John Carter reaches Blackwood Manor in the rain.')
            out.append('terms: five miles')
            return '\n'.join(out)
        raise AssertionError('Unexpected system prompt')

def test_cli_args():
    args = parse_args(['book.epub'])
    assert args.jobs == 4 and args.sample is None and args.resume is False
    assert parse_args(['book.epub', '--sample']).sample == 1
    assert parse_args(['book.epub', '--sample', '1']).sample == 1
    assert parse_args(['book.epub', '--chapter', '2']).chapter == 2
    assert parse_args(['book.epub', '--auto-approve', '--resume']).auto_approve is True

def test_sample_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        epub_path = base / 'book.epub'
        build_epub(epub_path)
        work = base / 'work'
        out_path = base / 'sample_translated.epub'
        fake = FakeLLMClient()
        result = asyncio.run(run_pipeline(epub_path, work_dir=work, output_path=out_path, sample=1, auto_approve=True, llm_client=fake, review_client=fake))
        assert result == out_path and out_path.exists()
        assert (work / 'tr' / '0001.json').exists()
        assert (work / 'ed' / '0001.json').exists()
        assert (work / 'state.json').exists()
        assert (work / 'scout.md').exists()
        with zipfile.ZipFile(out_path) as zf:
            assert zf.testzip() is None
            infos = zf.infolist()
            assert infos[0].filename == 'mimetype'
            assert infos[0].compress_type == zipfile.ZIP_STORED
            assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in infos[1:])
            names = zf.namelist()
            assert 'OEBPS/styles/translation.css' in names
            chapter1 = zf.read('OEBPS/chapter1.xhtml').decode('utf-8')
            chapter2 = zf.read('OEBPS/chapter2.xhtml').decode('utf-8')
            css = zf.read('OEBPS/styles/translation.css').decode('utf-8')
            opf = zf.read('OEBPS/content.opf').decode('utf-8')
        assert 'ترجمه:' in chapter1
        assert 'جان کارتر' in chapter1
        assert 'پنج مایل' in chapter1
        assert 'عمارت بلک‌وود' in chapter1
        assert '<b>damn</b>' in chapter1
        assert 'SKIPME' in chapter1
        assert 'Mary Hale stayed home' in chapter2
        assert 'Vazirmatn' in css and 'direction: rtl !important;' in css
        assert '@font-face' not in css
        assert 'page-progression-direction' in opf and 'rtl' in opf
        assert 'styles/translation.css' in opf

if __name__ == '__main__':
    test_cli_args()
    test_sample_end_to_end()
    print('PASS: all end-to-end scenarios passed')
