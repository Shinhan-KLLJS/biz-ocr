"""백엔드와 고정한 OCR 응답 계약을 검증한다."""

import unittest

from ocr_service.responses.business_registration import build_business_registration_ocr_response


class BusinessRegistrationOcrResponseTests(unittest.TestCase):
    def test_builds_the_six_contract_fields_for_the_backend(self):
        response = build_business_registration_ocr_response(
            {
                "documentType": "businessRegistrationCertificate",
                "fields": {
                    "companyName": "신한 KLLJS",
                    "representativeName": "이정현",
                    # 파서(normalization.normalize_date)가 이미 정리해 넘겨주는 형태다.
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

        # 계약은 정확히 이 6개다. 파서가 더 많이 읽어와도 여기서 잘라낸다.
        self.assertEqual(
            response,
            {
                "companyName": "신한 KLLJS",
                "representativeName": "이정현",
                "businessNumber": "4959240582",       # 구분자 제거
                "businessOpeningDate": "2024-06-24",  # yyyy-MM-dd
                "businessType": "서비스업",
                "businessItem": "광고대행",
            },
        )

    def test_response_carries_no_verification_or_decision_fields(self):
        # 진위 확인과 광고업 판단은 서버가 한다. Lambda 응답에 판정이 섞이면 안 된다.
        response = build_business_registration_ocr_response({"fields": {"companyName": "신한 KLLJS"}})

        self.assertNotIn("advertisingClassification", response)
        self.assertNotIn("eligibility", response)
        self.assertNotIn("verification", response)
        # 사업장주소는 저장하지도 검증하지도 않는 개인정보라 응답 계층에서 막는다.
        self.assertNotIn("businessAddress", response)

    def test_every_contract_key_exists_even_when_ocr_read_nothing(self):
        # 백엔드가 키 유무를 확인하지 않고 값만 보면 되도록, 인식 실패도 null로 채워 내려간다.
        response = build_business_registration_ocr_response({"fields": {}})

        self.assertEqual(
            response,
            {
                "companyName": None,
                "representativeName": None,
                "businessNumber": None,
                "businessOpeningDate": None,
                "businessType": None,
                "businessItem": None,
            },
        )

    def test_identity_fields_the_server_cannot_use_are_nulled_out(self):
        response = build_business_registration_ocr_response(
            {
                "fields": {
                    "companyName": "신한 KLLJS",
                    "businessRegistrationNumber": "49-592",  # 10자리가 아니다
                    "openingDate": "2024년",                 # 8자리가 아니다
                    "businessType": "",                       # 빈 문자열은 인식 실패와 같다
                },
            }
        )

        # 서버가 그대로 국세청에 보낼 수 없는 값은 null로 내려 사용자가 직접 입력하게 한다.
        self.assertIsNone(response["businessNumber"])
        self.assertIsNone(response["businessOpeningDate"])
        self.assertIsNone(response["businessType"])
        self.assertEqual(response["companyName"], "신한 KLLJS")


if __name__ == "__main__":
    unittest.main()
