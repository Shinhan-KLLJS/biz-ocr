"""CloudWatch 로그가 시크릿을 다시 출력하지 않는지 검증한다."""

import logging
import unittest
from unittest.mock import Mock

from ocr_service.observability import (
    log_invocation_completed,
    log_invocation_failed,
    log_invocation_started,
)


class Context:
    aws_request_id = "request-123"


class ObservabilityTests(unittest.TestCase):
    def test_start_log_uses_request_id_without_document_location(self):
        logger = Mock(spec=logging.Logger)

        log_invocation_started(logger, Context(), {"action": "ocr", "key": "private/file.png"})

        logger.info.assert_called_once_with(
            "OCR invocation started: request_id=%s operation=%s",
            "request-123",
            "ocr",
        )

    def test_failure_log_uses_the_redacted_message(self):
        logger = Mock(spec=logging.Logger)
        try:
            raise RuntimeError("https://example.com/?secret=raw-value")
        except RuntimeError as exc:
            log_invocation_failed(logger, Context(), exc, "secret=***REDACTED***")

        rendered = " ".join(map(str, logger.error.call_args.args))
        self.assertIn("request-123", rendered)
        self.assertIn("secret=***REDACTED***", rendered)
        self.assertNotIn("raw-value", rendered)

    def test_completion_log_uses_request_id(self):
        logger = Mock(spec=logging.Logger)

        log_invocation_completed(logger, Context())

        logger.info.assert_called_once_with("OCR invocation completed: request_id=%s", "request-123")
