from core.tag_preserver import TagPreserver

SAMPLE = "<div class='book'><p style='color: red'>Hello <b><i>beautiful</i></b> world</p><p>Second paragraph</p></div>"

def test_preserve_and_restore_roundtrip():
    preserver = TagPreserver()
    masked, tag_map = preserver.preserve_tags(SAMPLE)
    assert '<' not in masked and '>' not in masked
    assert tag_map['[id0]'] == "<div class='book'><p style='color: red'>"
    assert tag_map['[id1]'] == '<b><i>'
    assert preserver.restore_tags(masked, tag_map) == SAMPLE

def test_missing_placeholder_proportional_fallback():
    preserver = TagPreserver()
    masked, tag_map = preserver.preserve_tags(SAMPLE)
    broken = masked.replace('[id1]', '')
    assert '[id1]' not in broken
    aligned = preserver.align_missing_placeholders(broken, list(tag_map))
    assert '[id1]' in aligned
    assert preserver.restore_tags(aligned, tag_map) == SAMPLE

def test_restore_descending_id_order():
    preserver = TagPreserver()
    sample = ''.join(f'<b>w{i}</b> ' for i in range(12))
    masked, tag_map = preserver.preserve_tags(sample)
    assert '[id10]' in masked
    assert preserver.restore_tags(masked, tag_map) == sample

if __name__ == '__main__':
    test_preserve_and_restore_roundtrip()
    test_missing_placeholder_proportional_fallback()
    test_restore_descending_id_order()
    print('PASS: all step-1 scenarios passed')
