import re

class TagPreserver:
    _TAG_GROUP_RE = re.compile(r'<[^>]+>(?:\s*<[^>]+>)*')
    _PLACEHOLDER_RE = re.compile(r'\[id(\d+)\]')

    def __init__(self):
        self._last_masked_text = None
        self._last_tag_map = {}

    @staticmethod
    def _ph_id(placeholder):
        match = TagPreserver._PLACEHOLDER_RE.search(placeholder)
        return int(match.group(1)) if match else -1

    def preserve_tags(self, text):
        tag_map = {}
        def repl(match):
            placeholder = f'[id{len(tag_map)}]'
            tag_map[placeholder] = match.group(0)
            return placeholder
        masked = self._TAG_GROUP_RE.sub(repl, text)
        self._last_masked_text = masked
        self._last_tag_map = dict(tag_map)
        return masked, tag_map

    def restore_tags(self, masked_text, tag_map):
        result = masked_text
        for placeholder in sorted(tag_map, key=self._ph_id, reverse=True):
            result = result.replace(placeholder, tag_map[placeholder])
        return result

    def align_missing_placeholders(self, translated_text, expected_placeholders, source_text=None):
        expected = list(expected_placeholders.keys()) if isinstance(expected_placeholders, dict) else list(expected_placeholders)
        source = source_text or self._last_masked_text
        result = translated_text
        for placeholder in sorted(expected, key=self._ph_id):
            if placeholder in result:
                continue
            if source and placeholder in source:
                target = int((source.index(placeholder) / len(source)) * len(result)) if result else 0
            else:
                target = int(((self._ph_id(placeholder) + 1) / (len(expected) + 1)) * len(result)) if result else 0
            boundaries = [0, len(result)] + [i + 1 for i, ch in enumerate(result) if ch.isspace()]
            insert_at = min(boundaries, key=lambda pos: abs(pos - target))
            result = result[:insert_at] + placeholder + result[insert_at:]
        return result
