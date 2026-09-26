"""The one quote verifier, shared by the Story Bible and the editors (ADR-020)."""

import pytest

from nanoif.errors import BuildError, NanoifError
from nanoif.twee.quotes import clean_quote, normalize_text, quote_found

TEXT = "Thirty years I’ve poled this river,\n  Tamsin Reave said."


def test_normalize_text_folds_typographic_quotes_and_whitespace():
    assert normalize_text("  Thirty  years\nI’ve “poled” ") == "Thirty years I've \"poled\""


def test_clean_quote_strips_wrapping_quotation_marks():
    assert clean_quote('  "Thirty years"  ') == "Thirty years"
    assert clean_quote("“Thirty years”") == "Thirty years"


def test_quote_found_is_a_whitespace_normalized_substring():
    assert quote_found("Thirty years I've poled this river, Tamsin Reave said", [TEXT])
    assert quote_found('"Tamsin Reave said."', ["other text", TEXT])


def test_quote_found_is_case_sensitive_and_never_matches_empty():
    assert not quote_found("thirty years I've poled", [TEXT])
    assert not quote_found("   ", [TEXT])
    assert not quote_found('""', [TEXT])


@pytest.mark.intent("ADR-020")
def test_review_uses_the_twee_quote_verifier():
    from nanoif.review import findings

    assert findings.quote_found is quote_found
    assert findings.clean_quote is clean_quote


@pytest.mark.intent("ADR-020")
def test_bible_errors_are_typed():
    from nanoif.errors import BibleCacheError, BibleError

    assert issubclass(BibleError, NanoifError)
    assert issubclass(BibleCacheError, BuildError)
