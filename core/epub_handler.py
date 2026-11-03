from __future__ import annotations
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

def _local(tag):
    return tag.rsplit('}', 1)[-1]

class EpubHandler:
    def __init__(self, epub_path, work_dir='work'):
        self.epub_path = Path(epub_path)
        self.work_dir = Path(work_dir)
        self.raw_dir = self.work_dir / 'raw'
        self.opf_path = None
        self.opf_dir = None

    def extract(self):
        if self.raw_dir.exists():
            shutil.rmtree(self.raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        root = self.raw_dir.resolve()
        with zipfile.ZipFile(self.epub_path) as zf:
            for info in zf.infolist():
                target = (self.raw_dir / info.filename).resolve()
                if target != root and root not in target.parents:
                    raise ValueError(f'Unsafe zip entry (Zip Slip): {info.filename}')
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
        return self.raw_dir

    def find_opf_path(self):
        container = self.raw_dir / 'META-INF' / 'container.xml'
        for el in ET.parse(container).getroot().iter():
            if _local(el.tag) == 'rootfile' and el.get('full-path'):
                self.opf_path = self.raw_dir / unquote(el.get('full-path'))
                self.opf_dir = self.opf_path.parent
                return self.opf_path
        raise ValueError('OPF file not found in META-INF/container.xml')

    def get_spine_xhtml(self):
        if self.opf_path is None:
            self.find_opf_path()
        manifest = {}
        spine = []
        for el in ET.parse(self.opf_path).getroot().iter():
            name = _local(el.tag)
            if name == 'item' and el.get('id'):
                manifest[el.get('id')] = (el.get('href', ''), el.get('media-type', ''))
            elif name == 'itemref' and el.get('idref'):
                spine.append(el.get('idref'))
        files = []
        for idref in spine:
            if idref not in manifest:
                continue
            href, media_type = manifest[idref]
            if media_type in ('application/xhtml+xml', 'text/html') or href.lower().endswith(('.xhtml', '.html', '.htm')):
                files.append((self.opf_dir / unquote(href)).resolve())
        return files

    def repackage(self, output_path, source_dir=None):
        src = Path(source_dir) if source_dir else self.raw_dir
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        mimetype = src / 'mimetype'
        others = sorted(p for p in src.rglob('*') if p.is_file() and p.resolve() != mimetype.resolve() if mimetype.exists() or True)
        others = [p for p in others if p != mimetype]
        with zipfile.ZipFile(out, 'w') as zf:
            if mimetype.exists():
                zf.write(mimetype, arcname='mimetype', compress_type=zipfile.ZIP_STORED)
            for path in others:
                zf.write(path, arcname=path.relative_to(src).as_posix(), compress_type=zipfile.ZIP_DEFLATED)
        return out
