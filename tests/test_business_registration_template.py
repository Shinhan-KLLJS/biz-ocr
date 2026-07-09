"""Template OCR 응답을 사업자등록증 필드로 변환하는 경로를 검증한다."""

import unittest

from ocr_service.extractors.business_registration import parse_business_registration_result


class BusinessRegistrationTemplateTests(unittest.TestCase):
    def test_parse_template_response_extracts_all_required_fields(self):
        result = {
            "images": [
                {
                    "fields": [
                        {"name": "사업자등록번호", "inferText": "368-88-03013", "inferConfidence": 0.99},
                        {"name": "상호(단체명 등)", "inferText": "(주)글로벌데이터로드", "inferConfidence": 0.98},
                        {"name": "대표자명", "inferText": "이상옥", "inferConfidence": 0.97},
                        {"name": "개업연월일", "inferText": "2024 년 06 월 24 일", "inferConfidence": 0.96},
                        {
                            "name": "사업장주소",
                            "inferText": "서울특별시 송파구 오금로46길 41,2층 2404호(가락동)",
                            "inferConfidence": 0.95,
                        },
                        {"name": "업태", "inferText": "정보통신업", "inferConfidence": 0.94},
                        {"name": "종목", "inferText": "응용 소프트웨어 개발 및 공급업", "inferConfidence": 0.94},
                    ]
                }
            ]
        }

        parsed = parse_business_registration_result(result)

        self.assertEqual(
            parsed["fields"],
            {
                "businessRegistrationNumber": "368-88-03013",
                "companyName": "(주)글로벌데이터로드",
                "representativeName": "이상옥",
                "openingDate": "2024-06-24",
                "businessAddress": "서울특별시 송파구 오금로46길 41,2층 2404호(가락동)",
                "businessType": "정보통신업",
                "businessItem": "응용 소프트웨어 개발 및 공급업",
            },
        )
        self.assertFalse(parsed["advertisingClassification"]["isAdvertisingRelated"])
        self.assertEqual(parsed["warnings"], [])


if __name__ == "__main__":
    unittest.main()
