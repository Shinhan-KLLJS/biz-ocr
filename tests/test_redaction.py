"""비밀값이 로그와 오류 응답으로 새어 나가지 않는지 검증한다."""

import json
import os
import unittest
from unittest.mock import patch

import requests

from ocr_service.lambda_handler import handler
from ocr_service.redaction import redact_secrets


SERVICE_KEY = "SUPER-SECRET-SERVICE-KEY-1234567890"
OCR_SECRET_KEY = "SUPER-SECRET-OCR-KEY-0987654321"


class RedactSecretsTests(unittest.TestCase):
    def test_masks_service_key_query_parameter_without_knowing_the_value(self):
        message = "Max retries exceeded with url: /api/validate?serviceKey=UNKNOWN-VALUE (Caused by ...)"

        redacted = redact_secrets(message)

        self.assertNotIn("UNKNOWN-VALUE", redacted)
        self.assertIn("serviceKey=***REDACTED***", redacted)

    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": SERVICE_KEY}, clear=False)
    def test_masks_configured_secret_anywhere_in_the_text(self):
        redacted = redact_secrets(f"connection to host failed while sending {SERVICE_KEY}")

        self.assertNotIn(SERVICE_KEY, redacted)

    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "raw key+with/special=chars"}, clear=False)
    def test_masks_url_encoded_form_of_the_secret(self):
        # 공공데이터포털 키는 URL 인코딩된 형태로 요청 URL에 실린다.
        encoded = "raw%20key%2Bwith%2Fspecial%3Dchars"

        redacted = redact_secrets(f"url: /validate?x={encoded}")

        self.assertNotIn(encoded, redacted)
        self.assertNotIn("raw key+with/special=chars", redacted)

    @patch.dict(os.environ, {"NCLOUD_OCR_SECRET_KEY": OCR_SECRET_KEY}, clear=False)
    def test_masks_ncloud_secret_key(self):
        self.assertNotIn(OCR_SECRET_KEY, redact_secrets(f"X-OCR-SECRET: {OCR_SECRET_KEY}"))

    def test_short_secrets_are_left_alone_to_avoid_false_positives(self):
        with patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "abc"}, clear=False):
            self.assertEqual(redact_secrets("abcdef"), "abcdef")


class HandlerErrorResponseTests(unittest.TestCase):
    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": SERVICE_KEY}, clear=False)
    @patch("ocr_service.data_go_kr_client.requests.post")
    def test_verification_failure_does_not_leak_service_key(self, mock_post):
        # requests는 실패 메시지에 serviceKey가 담긴 요청 URL을 그대로 넣는다.
        mock_post.side_effect = requests.ConnectionError(
            f"HTTPSConnectionPool(host='api.odcloud.kr', port=443): "
            f"Max retries exceeded with url: /api/nts-businessman/v1/validate?serviceKey={SERVICE_KEY}"
        )

        response = handler(
            {
                "action": "verification",
                "business": {
                    "businessRegistrationNumber": "3688803013",
                    "representativeName": "이정현",
                    "openingDate": "20240624",
                    "businessType": "서비스업",
                    "businessItem": "광고대행",
                },
            },
            None,
        )

        self.assertEqual(response["statusCode"], 500)
        self.assertNotIn(SERVICE_KEY, response["body"])
        self.assertNotIn("serviceKey=SUPER", response["body"])
        self.assertEqual(json.loads(response["body"])["error"], "ExternalServiceError")


if __name__ == "__main__":
    unittest.main()
