"""클라이언트에 노출하는 OCR 응답 축약을 검증한다."""

import unittest

from ocr_service.responses.business_registration import build_business_registration_ocr_response


class BusinessRegistrationOcrResponseTests(unittest.TestCase):
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
        # 파서가 주소를 흘려보내도 응답 계층에서 막는다.
        self.assertNotIn("businessAddress", response["business"])

    def test_response_carries_no_verification_or_decision_fields(self):
        # 진위 확인과 광고업 판단은 서버가 한다. Lambda 응답에 판정이 섞이면 안 된다.
        response = build_business_registration_ocr_response({"fields": {"companyName": "신한 KLLJS"}})

        self.assertNotIn("advertisingClassification", response)
        self.assertNotIn("eligibility", response)
        self.assertNotIn("verification", response)

    def test_marks_invalid_ocr_identity_fields_as_missing(self):
        response = build_business_registration_ocr_response(
            {
                "fields": {
                    "companyName": "신한 KLLJS",
                    "representativeName": "이정현",
                    "businessRegistrationNumber": "49-592",
                    "openingDate": "2024년",
                    "businessType": "서비스업",
                    "businessItem": "광고대행",
                },
            }
        )

        # 서버가 그대로 data.go.kr에 보낼 수 없는 값은 null로 내리고 누락으로 표시한다.
        self.assertIsNone(response["business"]["businessRegistrationNumber"])
        self.assertIsNone(response["business"]["openingDate"])
        self.assertIn("businessRegistrationNumber", response["missingFields"])
        self.assertIn("openingDate", response["missingFields"])


if __name__ == "__main__":
    unittest.main()
