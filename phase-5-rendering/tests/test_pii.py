"""E2.1-E2.5 PII redaction + span audit; X2.1/X2.4/X2.10 edge cases."""

import re

from pulse.preprocess.pii import Scrubber

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def s() -> Scrubber:
    return Scrubber(redact_names=True)


def test_email_redacted():
    r = s().scrub("Email me at john.doe@example.com please")
    assert "[EMAIL]" in r.body_clean
    assert not EMAIL_RE.search(r.body_clean)
    assert r.body_clean == "Email me at [EMAIL] please"


def test_obfuscated_email_redacted():
    # X2.1
    r = s().scrub("reach me john [at] example dot com anytime please")
    assert "[EMAIL]" in r.body_clean


def test_phone_redacted_intl_and_local():
    assert "[PHONE]" in s().scrub("call +91 98765 43210 today").body_clean
    assert "[PHONE]" in s().scrub("ring 9876543210 for help").body_clean


def test_card_redacted():
    r = s().scrub("my card 4111 1111 1111 1111 was charged")
    assert "[CARD]" in r.body_clean


def test_account_keyword_redacted():
    r = s().scrub("account number 123456789012 was debited")
    assert "[ACCOUNT]" in r.body_clean


def test_version_and_year_not_redacted():
    # X2.4 — version numbers and years must survive.
    r = s().scrub("app version 5.2.1 from 2026 keeps crashing on launch")
    assert "5.2.1" in r.body_clean
    assert "2026" in r.body_clean
    assert r.spans == []


def test_author_name_redacted():
    r = s().scrub("Thanks, Asha here and the app is fast", author="Asha Mehta")
    assert "[NAME]" in r.body_clean
    assert "Asha" not in r.body_clean


def test_cue_based_name_redacted():
    r = s().scrub("My name is Rohit and the charts are great", author=None)
    assert "[NAME]" in r.body_clean
    assert "Rohit" not in r.body_clean


def test_product_word_not_over_redacted():
    # X2.3 — domain words must not be redacted as names.
    r = s().scrub("The Groww app is genuinely great for investing", author="Asha")
    assert r.body_clean == "The Groww app is genuinely great for investing"


def test_span_offsets_accurate():
    # E2.5 — spans index into the (normalized) text and map to the redacted regions.
    text = "Email me at john@example.com please"
    r = s().scrub(text)
    assert len(r.spans) == 1
    sp = r.spans[0]
    assert r.normalized[sp.start:sp.end] == "john@example.com"
    assert sp.label == "EMAIL"


def test_homoglyph_fullwidth_email():
    # X2.10 — NFKC normalization defeats fullwidth '＠'.
    r = s().scrub("contact john\uFF20example.com for details")
    assert "[EMAIL]" in r.body_clean


def test_multiple_pii_types_one_review():
    text = "Email a@b.com or call 9876543210 about account number 123456789"
    r = s().scrub(text)
    labels = {sp.label for sp in r.spans}
    assert {"EMAIL", "PHONE", "ACCOUNT"} <= labels
    assert not EMAIL_RE.search(r.body_clean)


def test_no_pii_unchanged():
    text = "The dashboard is clean and the charts load quickly every morning"
    r = s().scrub(text)
    assert r.body_clean == text
    assert r.spans == []
