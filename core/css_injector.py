from __future__ import annotations
import shutil
from pathlib import Path

SYSTEM_FONT_STACK = "'Vazirmatn', -apple-system, BlinkMacSystemFont, 'Segoe UI', Tahoma, Arial, sans-serif"

class CSSInjector:
    def generate_css(self, font_path=None, fonts_dir=None):
        font_face = ''
        family = SYSTEM_FONT_STACK
        if font_path:
            src = Path(font_path)
            family_name = src.stem
            if fonts_dir:
                dest_dir = Path(fonts_dir)
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / src.name)
            font_face = f"@font-face {{ font-family: '{family_name}'; src: url('{src.name}'); font-weight: normal; font-style: normal; }}\n"
            family = f"'{family_name}', {SYSTEM_FONT_STACK}"
        css = font_face
        css += f'body {{ direction: rtl !important; font-family: {family} !important; }}\n'
        css += 'code, pre { direction: ltr !important; text-align: left !important; }\n'
        return css

    build_css = generate_css

    def inject(self, raw_dir, font_path=None, css_rel_path='styles/style.css'):
        raw = Path(raw_dir)
        css_path = raw / css_rel_path
        css_path.parent.mkdir(parents=True, exist_ok=True)
        fonts_dir = raw / 'fonts' if font_path else None
        css = self.generate_css(font_path=font_path, fonts_dir=fonts_dir)
        if font_path:
            name = Path(font_path).name
            css = css.replace(f"url('{name}')", f"url('../fonts/{name}')")
        css_path.write_text(css, encoding='utf-8')
        return css_path
