"""사업자등록증 일반 텍스트 파싱 결과를 검증한다."""

import unittest

from ocr_service.extractors.business_registration import parse_business_registration_text
from tests.business_registration_samples import SAMPLE_OCR_TEXT


class BusinessRegistrationParsingTests(unittest.TestCase):
    def test_parse_text_extracts_fields_and_business_type_candidates(self):
        parsed = parse_business_registration_text(SAMPLE_OCR_TEXT)

        self.assertEqual(parsed["fields"]["businessRegistrationNumber"], "368-88-03013")
        self.assertEqual(parsed["fields"]["companyName"], "(주)글로벌데이터로드")
        self.assertEqual(parsed["fields"]["representativeName"], "이상옥")
        self.assertEqual(parsed["fields"]["openingDate"], "2024-06-24")
        self.assertEqual(
            parsed["fields"]["businessAddress"],
            "서울특별시 송파구 오금로46길 41,2층 2404호(가락동)",
        )
        self.assertEqual(parsed["fields"]["businessType"], "정보동신업 정보통신업")
        self.assertEqual(parsed["fields"]["businessTypeCandidates"], ["정보동신업", "정보통신업"])
        self.assertEqual(parsed["fields"]["businessItem"], "정보동신업 정보통신업")
        self.assertEqual(parsed["fields"]["businessItemsRaw"], ["정보동신업", "정보통신업"])
        self.assertNotIn("missing required fields: businessType", parsed["warnings"])
        self.assertNotIn("missing required fields: businessItem", parsed["warnings"])

    def test_parse_split_general_ocr_text(self):
        split_text = """
등록번호
:
368-88-03013
법인명
(단체명)
:
(주)글로벌데이터로드
대표
자
:
이상옥
개
업
연
월
일
:
2024
년
06
월
24
일
사업장
소재지
:
서울특별시
송파구
오금로46길
41,2층
2404호(가락동)
사
업
의
종
류
:
업태
정보통신업
종목
응용
소프트웨어
"""

        parsed = parse_business_registration_text(split_text)

        self.assertEqual(parsed["fields"]["businessRegistrationNumber"], "368-88-03013")
        self.assertEqual(parsed["fields"]["companyName"], "(주)글로벌데이터로드")
        self.assertEqual(parsed["fields"]["representativeName"], "이상옥")
        self.assertEqual(parsed["fields"]["openingDate"], "2024-06-24")
        self.assertEqual(
            parsed["fields"]["businessAddress"],
            "서울특별시 송파구 오금로46길 41,2층 2404호(가락동)",
        )
        self.assertEqual(parsed["fields"]["businessType"], "정보통신업")
        self.assertEqual(parsed["fields"]["businessItem"], "응용 소프트웨어")


if __name__ == "__main__":
    unittest.main()
