"""Lambda 핸들러의 이벤트 정규화와 검증 옵션 처리를 검증한다."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ocr_service.lambda_handler import (
    handler,
    normalize_event,
    parse_business_validation_mode,
    parse_event_template_ids,
)


class LambdaHandlerTests(unittest.TestCase):
    def test_normalize_api_gateway_body(self):
        event = {"body": json.dumps({"bucket": "ocr-bucket", "key": "incoming/file.png"})}

        self.assertEqual(
            normalize_event(event),
            {"body": event["body"], "bucket": "ocr-bucket", "key": "incoming/file.png"},
        )

    def test_parse_event_template_ids(self):
        self.assertEqual(parse_event_template_ids({"templateIds": "1, 2"}), [1, 2])
        self.assertEqual(parse_event_template_ids({"template_ids": [3, "4"]}), [3, 4])

    def test_parse_business_validation_mode(self):
        self.assertEqual(parse_business_validation_mode({"businessRegistrationValidation": True}), "status")
        self.assertEqual(
            parse_business_validation_mode({"business_registration_validation": "authenticity"}),
            "authenticity",
        )
        self.assertIsNone(parse_business_validation_mode({"businessRegistrationValidation": "off"}))

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    @patch("ocr_service.lambda_handler.call_ocr")
    @patch("ocr_service.lambda_handler.validate_file_size")
    @patch("ocr_service.lambda_handler.download_s3_object")
    def test_handler_downloads_s3_and_returns_parsed_payload(
        self,
        mock_download,
        mock_validate,
        mock_call_ocr,
        mock_parse,
        mock_business_validation,
    ):
        mock_download.return_value = Path("/tmp/file.png")
        mock_call_ocr.return_value = {"images": []}
        mock_parse.return_value = {
            "documentType": "businessRegistrationCertificate",
            "fields": {
                "businessRegistrationNumber": "368-88-03013",
                "companyName": "신한 KLLJS",
                "representativeName": "이정현",
            },
            "advertisingClassification": {},
            "warnings": [],
        }

        response = handler({"bucket": "ocr-bucket", "key": "incoming/file.png"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            body["business"],
            {
                "businessRegistrationNumber": "368-88-03013",
                "companyName": "신한 KLLJS",
                "representativeName": "이정현",
            },
        )
        self.assertEqual(body["status"], "review_required")
        mock_download.assert_called_once_with("ocr-bucket", "incoming/file.png")
        mock_validate.assert_called_once_with(Path("/tmp/file.png"))
        mock_call_ocr.assert_called_once()
        mock_business_validation.assert_not_called()

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    @patch("ocr_service.lambda_handler.call_ocr")
    @patch("ocr_service.lambda_handler.validate_file_size")
    @patch("ocr_service.lambda_handler.download_s3_object")
    def test_handler_adds_business_validation_when_requested(
        self,
        mock_download,
        mock_validate,
        mock_call_ocr,
        mock_parse,
        mock_business_validation,
    ):
        mock_download.return_value = Path("/tmp/file.png")
        mock_call_ocr.return_value = {"images": []}
        mock_parse.return_value = {
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
            "advertisingClassification": {"isAdvertisingRelated": True, "reviewRequired": False},
            "warnings": [],
        }
        mock_business_validation.return_value = {"mode": "status", "isValid": True, "isActive": True}

        response = handler(
            {
                "bucket": "ocr-bucket",
                "key": "incoming/file.png",
                "businessRegistrationValidation": "status",
            },
            None,
        )
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["status"], "accepted")
        self.assertTrue(body["eligibility"]["isEligible"])
        self.assertTrue(body["eligibility"]["isActive"])
        mock_business_validation.assert_called_once_with(
            mock_parse.return_value["fields"],
            "status",
        )


if __name__ == "__main__":
    unittest.main()
