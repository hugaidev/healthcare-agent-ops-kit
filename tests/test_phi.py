from __future__ import annotations

import logging

import pytest

from opskit.phi import PhiLogFilter, contains_phi, phi_categories, redact


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("SSN 123-45-6789", "ssn"),
        ("mail jane.doe@example.org", "email"),
        ("call (555) 123-4567", "phone"),
        ("DOB: 03/14/2015", "dob"),
        ("seen on 03/14/2024", "date"),
        ("MRN: AB12345", "mrn"),
        ("Member ID: XYZ123456789", "member_id"),
    ],
)
def test_detects_each_category(text: str, category: str) -> None:
    assert category in phi_categories(text)
    result = redact(text)
    assert f"[REDACTED:{category}]" in result.text
    assert result.count >= 1


@pytest.mark.parametrize(
    "text",
    ["Medically necessary per treatment plan.", "member tomorrow appointment", "units 12 of 97153"],
)
def test_clean_text_untouched(text: str) -> None:
    assert not contains_phi(text)
    assert redact(text).text == text


def test_log_filter_scrubs_formatted_message(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("phi-test")
    logger.addFilter(PhiLogFilter())
    with caplog.at_level(logging.INFO, logger="phi-test"):
        logger.info("lookup for %s", "123-45-6789")
    assert "123-45-6789" not in caplog.text
    assert "[REDACTED:ssn]" in caplog.text
