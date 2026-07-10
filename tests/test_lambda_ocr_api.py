"""OCR 전용 Lambda의 분기와 입력 방어를 검증한다."""

import json
import os
import unittest
from unittest.mock import patch

from ocr_service.documents import DocumentSource
from ocr_service.lambda_handler import handler, resolve_operation


class OperationRoutingTests(unittest.TestCase):
    def test_resolves_ocr_operation_from_path_or_action(self):
        self.assertEqual(resolve_operation({"rawPath": "/business-registrations/ocr"}), "ocr")
        self.assertEqual(
            resolve_operation({"requestContext": {"http": {"path": "/business-registrations/ocr"}}}),
            "ocr",
        )
        self.assertEqual(resolve_operation({"action": "ocr"}), "ocr")

    def test_verification_is_no_longer_an_operation_of_this_lambda(self):
        # 진위 확인과 최종 판정은 서버가 수행한다.
        self.assertEqual(resolve_operation({"action": "verification"}), "unsupported")
        self.assertEqual(resolve_operation({"rawPath": "/business-registrations/verification"}), "unsupported")

    def test_bare_s3_payload_without_operation_is_unsupported(self):
        self.assertEqual(resolve_operation({"bucket": "ocr-bucket", "key": "incoming/file.png"}), "unsupported")


class OcrOperationTests(unittest.TestCase):
    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    @patch("ocr_service.lambda_handler.call_ocr")
    @patch("ocr_service.lambda_handler.call_business_license_ocr")
    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_ocr_returns_editable_fields_without_any_validation(
        self,
        mock_load_document,
        mock_call_business_ocr,
        mock_call_ocr,
        mock_parse,
    ):
        mock_load_document.return_value = DocumentSource(name="file.png", content=b"image")
        mock_call_business_ocr.return_value = {"images": []}
        mock_parse.return_value = make_parsed_registration()

        response = handler({"action": "ocr", "bucket": "ocr-bucket", "key": "incoming/file.png"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["status"], "ocr_completed")
        self.assertEqual(body["business"]["companyName"], "신한 KLLJS")
        self.assertEqual(body["business"]["businessRegistrationNumber"], "3688803013")
        self.assertEqual(body["business"]["openingDate"], "20240624")
        self.assertEqual(body["business"]["businessItem"], "광고대행")
        self.assertNotIn("businessAddress", body["business"])
        # 판정 결과는 서버 몫이므로 응답에 들어가지 않는다.
        self.assertNotIn("advertisingClassification", body)
        self.assertNotIn("eligibility", body)
        self.assertNotIn("verification", body)
        mock_call_ocr.assert_not_called()


class InputGuardTests(unittest.TestCase):
    @patch.dict(os.environ, {"OCR_INPUT_BUCKET": "loovi-ocr-input"}, clear=False)
    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_ocr_rejects_a_bucket_outside_the_allowlist_before_reading_s3(self, mock_load_document):
        response = handler({"action": "ocr", "bucket": "someone-elses-bucket", "key": "secret.png"}, None)

        self.assertEqual(response["statusCode"], 400)
        mock_load_document.assert_not_called()

    def test_missing_s3_location_is_a_client_error_not_a_server_error(self):
        response = handler({"action": "ocr"}, None)

        self.assertEqual(response["statusCode"], 400)
        self.assertIn("Missing S3 object location", json.loads(response["body"])["message"])

    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_verification_request_is_rejected_with_a_clear_reason(self, mock_load_document):
        response = handler({"action": "verification", "business": {}}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["error"], "UnsupportedOperation")
        mock_load_document.assert_not_called()


def make_parsed_registration() -> dict:
    return {
        "documentType": "businessRegistrationCertificate",
        "fields": {
            "businessRegistrationNumber": "368-88-03013",
            "companyName": "신한 KLLJS",
            "representativeName": "이정현",
            "openingDate": "2024-06-24",
            "businessAddress": "서울특별시 송파구",
            "businessType": "서비스업",
            "businessItem": "광고대행",
        },
        "warnings": [],
    }


if __name__ == "__main__":
    unittest.main()
