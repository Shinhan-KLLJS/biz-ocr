"""비밀값이 로그와 오류 응답으로 새어 나가지 않는지 검증한다."""

import json
import os
import unittest
from unittest.mock import patch

import requests

from ocr_service.documents import DocumentSource
from ocr_service.lambda_handler import handler
from ocr_service.redaction import redact_secrets


OCR_SECRET_KEY = "SUPER-SECRET-OCR-KEY-0987654321"


class RedactSecretsTests(unittest.TestCase):
    def test_masks_service_key_query_parameter_without_knowing_the_value(self):
        message = "Max retries exceeded with url: /api/validate?serviceKey=UNKNOWN-VALUE (Caused by ...)"

        redacted = redact_secrets(message)

        self.assertNotIn("UNKNOWN-VALUE", redacted)
        self.assertIn("serviceKey=***REDACTED***", redacted)

    @patch.dict(os.environ, {"NCLOUD_OCR_SECRET_KEY": OCR_SECRET_KEY}, clear=False)
    def test_masks_configured_secret_anywhere_in_the_text(self):
        redacted = redact_secrets(f"connection to host failed while sending {OCR_SECRET_KEY}")

        self.assertNotIn(OCR_SECRET_KEY, redacted)

    @patch.dict(os.environ, {"NCLOUD_OCR_SECRET_KEY": "raw key+with/special=chars"}, clear=False)
    def test_masks_url_encoded_form_of_the_secret(self):
        encoded = "raw%20key%2Bwith%2Fspecial%3Dchars"

        redacted = redact_secrets(f"url: /ocr?x={encoded}")

        self.assertNotIn(encoded, redacted)
        self.assertNotIn("raw key+with/special=chars", redacted)

    @patch.dict(os.environ, {"NCLOUD_OCR_SECRET_KEY": OCR_SECRET_KEY}, clear=False)
    def test_masks_ncloud_secret_key(self):
        self.assertNotIn(OCR_SECRET_KEY, redact_secrets(f"X-OCR-SECRET: {OCR_SECRET_KEY}"))

    def test_short_secrets_are_left_alone_to_avoid_false_positives(self):
        with patch.dict(os.environ, {"NCLOUD_OCR_SECRET_KEY": "abc"}, clear=False):
            self.assertEqual(redact_secrets("abcdef"), "abcdef")


class HandlerErrorResponseTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "NCLOUD_OCR_SECRET_KEY": OCR_SECRET_KEY,
            "NCLOUD_OCR_BIZ_LICENSE_API_URL": "https://ocr.example.com/document/biz-license",
        },
        clear=False,
    )
    @patch("ocr_service.ncloud_client.requests.post")
    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_ocr_failure_returns_502_without_leaking_the_secret(self, mock_load_document, mock_post):
        mock_load_document.return_value = DocumentSource(name="file.png", content=b"image")
        # requests 예외 메시지에는 요청 URL과 헤더 값이 섞여 들어올 수 있다.
        mock_post.side_effect = requests.ConnectionError(
            f"HTTPSConnectionPool(host='ocr.example.com', port=443): "
            f"Max retries exceeded (X-OCR-SECRET: {OCR_SECRET_KEY})"
        )

        response = handler({"action": "ocr", "bucket": "ocr-bucket", "key": "incoming/file.png"}, None)

        # 외부 API 장애는 이 서비스의 결함이 아니므로 502로 구분해 올린다.
        self.assertEqual(response["statusCode"], 502)
        self.assertNotIn(OCR_SECRET_KEY, response["body"])
        self.assertEqual(json.loads(response["body"])["error"], "ExternalServiceError")


if __name__ == "__main__":
    unittest.main()
