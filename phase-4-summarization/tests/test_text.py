"""Text utils: emoji detection, word count, near-dup fingerprint."""

from pulse.utils.text import has_emoji, normalize_for_hash, strip_emoji, text_fingerprint, word_count


def test_has_emoji():
    assert has_emoji("love it 😍")
    assert has_emoji("great ⭐ app")
    assert has_emoji("nice ❤")
    assert not has_emoji("a perfectly normal review with no symbols")
    assert not has_emoji("")
    assert not has_emoji(None)


def test_strip_emoji():
    assert strip_emoji("love it 😍 a lot").replace("  ", " ").strip() == "love it a lot"


def test_word_count():
    assert word_count("one two three four") == 4
    assert word_count("Nice app") == 2
    assert word_count("") == 0
    assert word_count(None) == 0


def test_fingerprint_near_dup():
    a = "This app is GREAT, really great!!!"
    b = "this app is great really great"
    assert text_fingerprint(a) == text_fingerprint(b)
    assert normalize_for_hash(a) == "this app is great really great"


def test_fingerprint_distinct():
    assert text_fingerprint("totally different text here") != text_fingerprint("another review entirely")
