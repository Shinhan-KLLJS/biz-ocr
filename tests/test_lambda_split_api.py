"""OCR/검증 분리 API의 Lambda 분기 동작을 검증한다."""

import json
import unittest
from unittest.mock import patch

from ocr_service.documents import DocumentSource
from ocr_service.lambda_handler import handler, resolve_operation


class LambdaSplitApiTests(unittest.TestCase):
    def test_resolve_split_api_operations(self):
        self.assertEqual(resolve_operation({"rawPath": "/business-registrations/ocr"}), "ocr")
        self.assertEqual(
            resolve_operation({"requestContext": {"http": {"path": "/business-registrations/verification"}}}),
            "verification",
        )
        self.assertEqual(resolve_operation({"action": "verify"}), "verification")
        self.assertEqual(resolve_operation({"action": "legacy"}), "unsupported")
        self.assertEqual(resolve_operation({"bucket": "ocr-bucket", "key": "incoming/file.png"}), "unsupported")

    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    @patch("ocr_service.lambda_handler.call_ocr")
    @patch("ocr_service.lambda_handler.call_business_license_ocr")
    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_ocr_operation_returns_editable_fields_without_validation(
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
        self.assertEqual(body["business"]["businessRegistrationNumber"], "3688803013")
        self.assertEqual(body["business"]["openingDate"], "20240624")
        self.assertEqual(body["business"]["businessItem"], "광고대행")
        self.assertNotIn("advertisingClassification", body)
        self.assertNotIn("eligibility", body)
        mock_call_ocr.assert_not_called()

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    def test_verification_operation_uses_corrected_fields_without_ocr(self, mock_business_validation):
        mock_business_validation.return_value = {
            "mode": "authenticity",
            "isCertificateValid": True,
            "isRegistered": True,
            "isActive": True,
        }

        response = handler(
            {
                "action": "verification",
                "business": make_verification_business_fields(),
            },
            None,
        )
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["status"], "accepted")
        self.assertTrue(body["verification"]["isCertificateValid"])
        self.assertTrue(body["eligibility"]["isEligible"])
        self.assertTrue(body["advertisingClassification"]["isAdvertisingRelated"])
        mock_business_validation.assert_called_once_with(
            {
                "businessRegistrationNumber": "3688803013",
                "representativeName": "이정현",
                "openingDate": "20240624",
            },
            "authenticity",
        )


def make_parsed_registration() -> dict:
    return {
        "documentType": "businessRegistrationCertificate",
        "fields": make_corrected_business_fields(),
        "advertisingClassification": {"isAdvertisingRelated": True, "reviewRequired": False},
        "warnings": [],
    }


def make_corrected_business_fields() -> dict:
    return {
        "businessRegistrationNumber": "368-88-03013",
        "companyName": "신한 KLLJS",
        "representativeName": "이정현",
        "openingDate": "2024-06-24",
        "businessAddress": "서울특별시 송파구",
        "businessType": "서비스업",
        "businessItem": "광고대행",
    }


def make_verification_business_fields() -> dict:
    return {
        "businessRegistrationNumber": "3688803013",
        "representativeName": "이정현",
        "openingDate": "20240624",
        "businessType": "서비스업",
        "businessItem": "광고대행",
    }


if __name__ == "__main__":
    unittest.main()
