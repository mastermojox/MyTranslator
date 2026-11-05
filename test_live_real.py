import asyncio, zipfile
import sys
from pathlib import Path
from main import run_pipeline
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
C = "<?xml version='1.0'?><container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>"
O = "<package xmlns='http://www.idpf.org/2007/opf' unique-identifier='bid' version='3.0'><metadata xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:identifier id='bid'>live-test</dc:identifier><dc:title>Live Test</dc:title><dc:language>en</dc:language></metadata><manifest><item id='c1' href='chapter1.xhtml' media-type='application/xhtml+xml'/><item id='c2' href='chapter2.xhtml' media-type='application/xhtml+xml'/></manifest><spine><itemref idref='c1'/><itemref idref='c2'/></spine></package>"
def x(b):
    return "<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><head><title>t</title></head><body>" + b + '</body></html>'
base = Path('live_test_run')
base.mkdir(exist_ok=True)
epub = base / 'small.epub'
ch1 = x("<h1 class='title'>The Old Lighthouse</h1><p class='body'>John Carter walked five miles to the old lighthouse. Damn the cold wind, he muttered.</p><p class='body'>Mary Hale waited three feet from the door, holding two pounds of letters.</p>")
ch2 = x("<p class='body'>The second chapter was not sampled.</p>")
with zipfile.ZipFile(epub, 'w') as z:
    z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
    z.writestr('META-INF/container.xml', C, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/content.opf', O, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/chapter1.xhtml', ch1, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/chapter2.xhtml', ch2, compress_type=zipfile.ZIP_DEFLATED)
out = base / 'sample_translated.epub'
work = base / 'work'
result = asyncio.run(run_pipeline(epub, work_dir=work, output_path=out, sample=1, auto_approve=True, jobs=2))
assert result == out and out.exists(), 'output epub missing'
assert (work / 'structure.json').exists(), 'structure.json missing'
assert (work / 'scout.md').exists(), 'scout.md missing'
assert (work / 'tr' / '0001.json').exists(), 'translated chunk missing'
assert (work / 'ed' / '0001.json').exists(), 'edited chunk missing'
assert (work / 'state.json').exists(), 'state.json missing'
print('SCOUT:', (work / 'scout.md').read_text(encoding='utf-8')[:1500])
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None, 'output epub is corrupt'
    infos = z.infolist()
    assert infos[0].filename == 'mimetype' and infos[0].compress_type == zipfile.ZIP_STORED, 'mimetype not stored first'
    ch = z.read('OEBPS/chapter1.xhtml').decode('utf-8')
    assert any(0x600 <= ord(c) <= 0x6FF for c in ch), 'No Persian text in output chapter'
    print('OUTPUT_CHAPTER:', ch[:1500])
print('PASS: live real-API sample pipeline completed, output =', out)
