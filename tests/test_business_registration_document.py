"""Ncloud Document OCR 사업자등록증 응답 매핑을 검증한다."""

import unittest

from ocr_service.extractors.business_registration import parse_business_registration_result


class BusinessRegistrationDocumentTests(unittest.TestCase):
    def test_parse_document_response_extracts_required_fields(self):
        parsed = parse_business_registration_result(
            make_document_response(
                {
                    "registerNumber": [{"text": "368-88-03013"}],
                    "companyName": [{"text": "(주)글로벌데이터로드"}],
                    "repName": [{"text": "이상옥"}],
                    "openDate": [{"text": "2024 년 06 월 24 일"}],
                    "bisAddress": [{"text": "서울특별시 송파구 오금로46길 41"}],
                    "bisType": [{"text": "서비스업"}],
                    "bisItem": [{"text": "광고대행"}],
                    "socialNumber": [{"text": "900101-1234567"}],
                }
            )
        )

        self.assertEqual(
            parsed["fields"],
            {
                "businessRegistrationNumber": "368-88-03013",
                "companyName": "(주)글로벌데이터로드",
                "representativeName": "이상옥",
                "openingDate": "2024-06-24",
                "businessAddress": "서울특별시 송파구 오금로46길 41",
                "businessType": "서비스업",
                "businessItem": "광고대행",
            },
        )
        self.assertNotIn("socialNumber", parsed["fields"])
        self.assertTrue(parsed["advertisingClassification"]["isAdvertisingRelated"])

    def test_parse_document_response_uses_corp_name_when_company_name_is_missing(self):
        parsed = parse_business_registration_result(make_document_response({"corpName": [{"text": "주식회사 광고"}]}))

        self.assertEqual(parsed["fields"]["companyName"], "주식회사 광고")

    def test_parse_document_response_uses_head_address_when_business_address_is_missing(self):
        parsed = parse_business_registration_result(
            make_document_response({"headAddress": [{"text": "서울특별시 강남구"}]})
        )

        self.assertEqual(parsed["fields"]["businessAddress"], "서울특별시 강남구")


def make_document_response(document_result: dict) -> dict:
    return {
        "images": [
            {
                "bizLicense": {
                    "result": document_result,
                }
            }
        ]
    }


if __name__ == "__main__":
    unittest.main()
