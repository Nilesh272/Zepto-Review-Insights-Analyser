"""E2.6/E2.7 language detection + allowlist filtering."""

from pulse.preprocess.language import detect_language, is_allowed


def test_english_detected_and_allowed():
    text = "This investing app makes tracking my mutual funds simple and fast"
    assert detect_language(text) == "en"
    assert is_allowed(text, ["en"]) is True


def test_french_detected_and_not_allowed():
    text = "Cette application est vraiment excellente pour investir mon argent facilement"
    assert detect_language(text) == "fr"
    assert is_allowed(text, ["en"]) is False


def test_inconclusive_is_kept():
    # Empty/blank text is undetermined -> kept (avoids dropping valid short reviews).
    assert detect_language("") is None
    assert is_allowed("", ["en"]) is True


def test_ingestion_uses_canonical_detector():
    from pulse.ingestion.filters import default_detector

    detect = default_detector()
    assert detect("This is a clearly english sentence about the app") == "en"
