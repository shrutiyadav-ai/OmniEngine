"""
OmniEngine — PII Redactor

Scubs personally identifiable information (PII) like emails, SSNs, credit cards,
and phone numbers before logging messages to telemetry databases.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Regex fallback patterns for PII
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")


class PIIRedactor:
    """PII redaction using Presidio / Regex fallback."""

    def __init__(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self._has_presidio = True
        except Exception as e:
            logger.warning("Presidio PII engines unavailable, using regex fallback: %s", str(e))
            self._has_presidio = False

    def redact(self, text: str) -> str:
        """Redact PII from text."""
        if not text:
            return text

        if self._has_presidio:
            try:
                results = self.analyzer.analyze(text=text, language="en")
                anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
                return str(anonymized.text)
            except Exception as e:
                logger.warning("Presidio redaction failed, using regex: %s", str(e))

        # Regex fallback
        redacted = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
        redacted = PHONE_REGEX.sub("[REDACTED_PHONE]", redacted)
        redacted = SSN_REGEX.sub("[REDACTED_SSN]", redacted)
        return CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", redacted)
