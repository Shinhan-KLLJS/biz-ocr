"""사업자등록증 분석 서비스의 검증 전처리를 검증한다."""

import unittest
from unittest.mock import patch

from ocr_service.services.business_registration import (
    analyze_business_registration,
    verify_business_registration_submission,
)


class BusinessRegistrationServiceTests(unittest.TestCase):
    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    def test_skips_authenticity_validation_when_representative_name_is_missing(
        self,
        mock_parse,
        mock_validate,
    ):
        mock_parse.return_value = {
            "fields": {
                "businessRegistrationNumber": "132-81-48751",
                "companyName": "애드컴주식회사",
                "openingDate": "2003-02-14",
                "businessAddress": "경기도 남양주시",
                "businessType": "제조",
                "businessItem": "광고물제작",
            },
            "advertisingClassification": {"isAdvertisingRelated": True, "reviewRequired": False},
        }

        parsed = analyze_business_registration({"images": []}, "authenticity")

        self.assertEqual(parsed["decision"]["status"], "review_required")
        self.assertEqual(parsed["decision"]["reasonCode"], "MISSING_REQUIRED_FIELDS")
        self.assertEqual(parsed["decision"]["missingFields"], ["representativeName"])
        self.assertEqual(parsed["validation"]["missingFields"], ["representativeName"])
        mock_validate.assert_not_called()

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    def test_returns_review_required_when_validation_input_is_malformed(
        self,
        mock_parse,
        mock_validate,
    ):
        mock_parse.return_value = {
            "fields": {
                "businessRegistrationNumber": "bad-number",
                "companyName": "애드컴주식회사",
                "representativeName": "조용길",
                "openingDate": "2003-02-14",
                "businessAddress": "경기도 남양주시",
                "businessType": "제조",
                "businessItem": "광고물제작",
            },
            "advertisingClassification": {"isAdvertisingRelated": True, "reviewRequired": False},
        }
        mock_validate.side_effect = ValueError("businessRegistrationNumber must contain 10 digits")

        parsed = analyze_business_registration({"images": []}, "authenticity")

        self.assertEqual(parsed["decision"]["status"], "review_required")
        self.assertEqual(parsed["decision"]["reasonCode"], "VALIDATION_INPUT_INCOMPLETE")
        self.assertIn("10 digits", parsed["decision"]["validationError"])

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    def test_verifies_user_corrected_fields(self, mock_validate):
        mock_validate.return_value = {
            "mode": "authenticity",
            "isCertificateValid": True,
            "isRegistered": True,
            "isActive": True,
        }

        parsed = verify_business_registration_submission(
            {
                "businessRegistrationNumber": "3688803013",
                "representativeName": "이상옥",
                "openingDate": "20240624",
                "businessType": "서비스업",
                "businessItem": "광고대행",
            }
        )

        self.assertEqual(parsed["decision"]["status"], "accepted")
        self.assertEqual(parsed["validation"]["mode"], "authenticity")
        self.assertTrue(parsed["advertisingClassification"]["isAdvertisingRelated"])
        mock_validate.assert_called_once()

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    def test_rejects_separator_in_verification_submission(self, mock_validate):
        parsed = verify_business_registration_submission(
            {
                "businessRegistrationNumber": "368-88-03013",
                "representativeName": "이상옥",
                "openingDate": "2024-06-24",
            }
        )

        self.assertEqual(parsed["decision"]["status"], "review_required")
        self.assertEqual(parsed["decision"]["reasonCode"], "VALIDATION_INPUT_INCOMPLETE")
        self.assertIn("without separators", parsed["decision"]["validationError"])
        mock_validate.assert_not_called()

    @patch("ocr_service.services.business_registration.validate_business_registration_fields")
    def test_requires_advertising_fields_for_final_decision(self, mock_validate):
        mock_validate.return_value = {
            "mode": "authenticity",
            "isCertificateValid": True,
            "isRegistered": True,
            "isActive": True,
        }

        parsed = verify_business_registration_submission(
            {
                "businessRegistrationNumber": "3688803013",
                "representativeName": "이상옥",
                "openingDate": "20240624",
            }
        )

        self.assertEqual(parsed["decision"]["status"], "review_required")
        self.assertEqual(parsed["decision"]["reasonCode"], "ADVERTISING_CLASSIFICATION_INPUT_INCOMPLETE")
        self.assertEqual(parsed["decision"]["missingFields"], ["businessType", "businessItem"])


if __name__ == "__main__":
    unittest.main()
