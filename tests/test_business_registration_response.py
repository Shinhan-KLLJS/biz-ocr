"""클라이언트에 노출하는 사업자등록증 응답 축약을 검증한다."""

import unittest

from ocr_service.responses.business_registration import (
    build_business_registration_ocr_response,
    build_business_registration_response,
    build_business_registration_verification_response,
)


class BusinessRegistrationResponseTests(unittest.TestCase):
    def test_builds_minimal_client_response(self):
        response = build_business_registration_response(
            {
                "fields": {
                    "companyName": "신한 KLLJS",
                    "representativeName": "이정현",
                    "businessRegistrationNumber": "49-592-40582",
                    "businessAddress": "서울특별시",
                },
                "validation": {
                    "mode": "authenticity",
                    "isCertificateValid": True,
                    "isRegistered": True,
                    "isActive": True,
                    "businessStatus": "계속사업자",
                    "taxType": "부가가치세 일반과세자",
                    "raw": {"hidden": True},
                },
                "advertisingClassification": {"isAdvertisingRelated": True, "matchedKeywords": ["광고"]},
                "decision": {
                    "status": "accepted",
                    "reasonCode": "ACCEPTED",
                    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다.",
                },
                "rawText": "노출하지 않는 OCR 원문",
            }
        )

        self.assertEqual(
            response,
            {
                "status": "accepted",
                "business": {
                    "companyName": "신한 KLLJS",
                    "representativeName": "이정현",
                    "businessRegistrationNumber": "49-592-40582",
                },
                "eligibility": {
                    "isEligible": True,
                    "isCertificateValid": True,
                    "isRegistered": True,
                    "isActive": True,
                    "isAdvertisingRelated": True,
                    "validationMode": "authenticity",
                    "validationCode": None,
                    "validationMessage": None,
                    "businessStatus": "계속사업자",
                    "taxType": "부가가치세 일반과세자",
                    "reasonCode": "ACCEPTED",
                    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다.",
                },
            },
        )

    def test_builds_ocr_review_response_for_frontend_editing(self):
        response = build_business_registration_ocr_response(
            {
                "documentType": "businessRegistrationCertificate",
                "fields": {
                    "companyName": "신한 KLLJS",
                    "representativeName": "이정현",
                    "businessRegistrationNumber": "49-592-40582",
                    "openingDate": "2024-06-24",
                    "businessAddress": "서울특별시",
                    "businessType": "서비스업",
                    "businessItem": "광고대행",
                    "businessTypeCandidates": ["서비스업"],
                    "businessItemsRaw": ["광고대행"],
                },
                "advertisingClassification": {"isAdvertisingRelated": True},
                "warnings": ["검토 필요"],
                "source": {"bucket": "ocr-bucket", "key": "incoming/file.png"},
            }
        )

        self.assertEqual(response["status"], "ocr_completed")
        self.assertEqual(response["missingFields"], [])
        self.assertEqual(response["business"]["businessRegistrationNumber"], "4959240582")
        self.assertEqual(response["business"]["openingDate"], "20240624")
        self.assertEqual(response["business"]["businessItem"], "광고대행")
        self.assertEqual(response["business"]["businessItemsRaw"], ["광고대행"])
        self.assertEqual(response["source"]["bucket"], "ocr-bucket")

    def test_marks_invalid_ocr_identity_fields_as_missing(self):
        response = build_business_registration_ocr_response(
            {
                "fields": {
                    "companyName": "신한 KLLJS",
                    "representativeName": "이정현",
                    "businessRegistrationNumber": "49-592",
                    "openingDate": "2024년",
                    "businessAddress": "서울특별시",
                    "businessType": "서비스업",
                    "businessItem": "광고대행",
                },
            }
        )

        self.assertIsNone(response["business"]["businessRegistrationNumber"])
        self.assertIsNone(response["business"]["openingDate"])
        self.assertIn("businessRegistrationNumber", response["missingFields"])
        self.assertIn("openingDate", response["missingFields"])

    def test_builds_verification_response_with_required_identity_fields(self):
        response = build_business_registration_verification_response(
            {
                "fields": {
                    "businessRegistrationNumber": "4959240582",
                    "representativeName": "이정현",
                    "openingDate": "20240624",
                    "businessType": "서비스업",
                    "businessItem": "광고대행",
                },
                "validation": {
                    "mode": "authenticity",
                    "isCertificateValid": True,
                    "isRegistered": True,
                    "isActive": True,
                    "businessStatus": "계속사업자",
                    "taxType": "부가가치세 일반과세자",
                },
                "decision": {
                    "status": "accepted",
                    "reasonCode": "ACCEPTED",
                    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다.",
                },
                "advertisingClassification": {
                    "isAdvertisingRelated": True,
                    "reviewRequired": False,
                    "matchedKeywords": ["광고대행"],
                },
            }
        )

        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["business"]["openingDate"], "20240624")
        self.assertTrue(response["verification"]["isCertificateValid"])
        self.assertEqual(response["verification"]["businessStatus"], "계속사업자")
        self.assertTrue(response["eligibility"]["isEligible"])
        self.assertTrue(response["eligibility"]["isAdvertisingRelated"])


if __name__ == "__main__":
    unittest.main()
