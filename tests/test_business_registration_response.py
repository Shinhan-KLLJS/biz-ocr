"""클라이언트에 노출하는 사업자등록증 응답 축약을 검증한다."""

import unittest

from ocr_service.responses.business_registration import build_business_registration_response


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
                "validation": {"isValid": True, "isActive": True, "raw": {"hidden": True}},
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
                    "isActive": True,
                    "isAdvertisingRelated": True,
                    "reasonCode": "ACCEPTED",
                    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다.",
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
