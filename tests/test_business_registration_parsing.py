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

    def test_parse_spaced_representative_label(self):
        text = """
등록번호 : 132-81-48751
법 인 명 (단 체 명) : 애드컴주식회사
대 표 자 : 조용길
개 업 연 월 일 : 2003 년 02 월 14 일
사업장 소재지 : 경기도 남양주시 진건읍 진관산단로54번길 10
사 업 의 종 류 : 업태 제조
종목 광고물제작
"""

        parsed = parse_business_registration_text(text)

        self.assertEqual(parsed["fields"]["companyName"], "애드컴주식회사")
        self.assertEqual(parsed["fields"]["representativeName"], "조용길")
        self.assertEqual(parsed["fields"]["openingDate"], "2003-02-14")

    def test_parse_actual_ocr_order_for_adcom_certificate(self):
        text = """
등록번호
:
132-81-48751
법인명
(단체명)
:
애드컴주식회사
대
표
자
:
조용길
사
업
의
종
류
:
업태
개
업
연
월
일
:
2003
년
02
월
14
일
사업장
소재지
:
경기도
남양주시
종목
제조
제조
전기,
가스,
증기
및
수도사업
건설업
부동산
서비스
서비스서업
광고물제작
광고대행
디자인
발
급
사
유
:
정정
"""

        parsed = parse_business_registration_text(text)

        self.assertEqual(parsed["fields"]["representativeName"], "조용길")
        self.assertIn("제조", parsed["fields"]["businessType"])
        self.assertIn("서비스서업", parsed["fields"]["businessType"])
        self.assertIn("광고물제작", parsed["fields"]["businessItem"])
        self.assertNotIn("missing required fields: businessType", parsed["warnings"])


if __name__ == "__main__":
    unittest.main()
