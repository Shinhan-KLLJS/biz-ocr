"""OCR 전용 Lambda의 분기와 입력 방어를 검증한다."""

import os
import unittest
from unittest.mock import patch

from ocr_service.documents import DocumentSource
from ocr_service.lambda_handler import handler, resolve_operation


class OperationRoutingTests(unittest.TestCase):
    def test_resolves_ocr_operation_from_action(self):
        self.assertEqual(resolve_operation({"action": "ocr"}), "ocr")
        self.assertEqual(resolve_operation({"operation": "parse"}), "ocr")

    def test_verification_is_no_longer_an_operation_of_this_lambda(self):
        # 진위 확인과 최종 판정은 서버가 수행한다.
        self.assertEqual(resolve_operation({"action": "verification"}), "unsupported")

    def test_bare_s3_payload_without_operation_is_unsupported(self):
        # S3 업로드 이벤트로 Lambda가 트리거되도록 잘못 설정해도 실행되지 않아야 한다.
        # OCR 결과를 돌려받을 호출자가 없어 비용만 쓰고 결과는 버려진다.
        self.assertEqual(resolve_operation({"bucket": "ocr-bucket", "key": "incoming/file.png"}), "unsupported")
        self.assertEqual(resolve_operation({"Records": [{"s3": {}}]}), "unsupported")


class OcrOperationTests(unittest.TestCase):
    """백엔드가 SDK로 직접 invoke하므로 API Gateway proxy 봉투 없이 결과 dict를 그대로 돌려준다."""

    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    @patch("ocr_service.lambda_handler.call_ocr")
    @patch("ocr_service.lambda_handler.call_business_license_ocr")
    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_ocr_returns_the_backend_contract_fields(
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

        # 봉투 없이 계약 필드가 최상위에 온다.
        self.assertNotIn("statusCode", response)
        self.assertNotIn("body", response)
        self.assertEqual(
            response,
            {
                "companyName": "신한 KLLJS",
                "representativeName": "이정현",
                "businessNumber": "3688803013",
                "businessOpeningDate": "2024-06-24",
                "businessType": "서비스업",
                "businessItem": "광고대행",
            },
        )
        # 사업장주소와 판정 결과는 응답에 없다 (판정은 서버 몫이다).
        self.assertNotIn("businessAddress", response)
        self.assertNotIn("advertisingClassification", response)
        mock_call_ocr.assert_not_called()


class InputGuardTests(unittest.TestCase):
    """실패해도 예외를 던지지 않고 {"error", "message"}를 돌려준다 (백엔드가 파싱하기 쉽게)."""

    @patch.dict(os.environ, {"OCR_INPUT_BUCKET": "loovi-ocr-input"}, clear=False)
    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_ocr_rejects_a_bucket_outside_the_allowlist_before_reading_s3(self, mock_load_document):
        response = handler({"action": "ocr", "bucket": "someone-elses-bucket", "key": "secret.png"}, None)

        self.assertEqual(response["error"], "ValueError")
        mock_load_document.assert_not_called()

    def test_missing_s3_location_is_reported_as_an_error(self):
        response = handler({"action": "ocr"}, None)

        self.assertEqual(response["error"], "ValueError")
        self.assertIn("Missing S3 object location", response["message"])

    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_verification_request_is_rejected_with_a_clear_reason(self, mock_load_document):
        response = handler({"action": "verification", "business": {}}, None)

        self.assertEqual(response["error"], "ValueError")
        self.assertIn("operation must be 'ocr'", response["message"])
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
