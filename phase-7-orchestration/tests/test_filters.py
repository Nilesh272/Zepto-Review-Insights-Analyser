"""Quality filters: emoji / too_short / other-language drop rules (requested for Phase 1)."""

from pulse.config import Settings
from pulse.ingestion.filters import classify, drop_reason


def test_emoji_dropped(fake_detector):
    s = Settings()
    c = classify("Absolutely love this trading app so much 😍 wow", s, fake_detector)
    assert c.reason == "emoji"


def test_too_short_dropped(fake_detector):
    s = Settings()
    assert drop_reason("Nice app", s, fake_detector) == "too_short"
    assert drop_reason("good", s, fake_detector) == "too_short"


def test_other_language_dropped(fake_detector):
    s = Settings()
    c = classify("Cette application est vraiment excellente pour investir", s, fake_detector)
    assert c.reason == "language:fr"
    assert c.lang == "fr"


def test_english_kept(fake_detector):
    s = Settings()
    c = classify("This app makes tracking my mutual funds simple and fast", s, fake_detector)
    assert c.reason is None
    assert c.lang == "en"
    assert c.word_count >= 4


def test_emoji_toggle_off_keeps(fake_detector):
    s = Settings(filters={"drop_emoji": False, "drop_other_languages": True, "min_words": 4})
    c = classify("Absolutely love this trading app so much 😍 wow", s, fake_detector)
    assert c.reason is None


def test_language_toggle_off_keeps(fake_detector):
    s = Settings(filters={"drop_emoji": True, "drop_other_languages": False, "min_words": 4})
    c = classify("Cette application est vraiment excellente pour investir", s, fake_detector)
    assert c.reason is None


def test_order_emoji_before_language(fake_detector):
    # A short French review with emoji is attributed to emoji (first matching rule).
    s = Settings()
    c = classify("Cette application 😍", s, fake_detector)
    assert c.reason == "emoji"
