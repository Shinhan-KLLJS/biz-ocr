import unittest

from ocr_service.extractors.business_registration import (
    normalize_date,
    parse_business_registration_result,
    parse_business_registration_text,
)


SAMPLE_OCR_TEXT = """
국세청
nts.go.kr
사 업 자 등 록 증
(법인사업자)
등록번호 : 368-88-03013
사 업 의 종 류 : 업태
법인명 (단체명) : (주)글로벌데이터로드
대표 자 : 이상옥
개 업 연 월 일 : 2024 년 06 월 24 일
법인등록번호 : 110111-8947321
사업장 소재지 : 서울특별시 송파구 오금로46길 41,2층 2404호(가락동)
본점 소 재 지 : 서울특별시 송파구 오금로46길 41,2층 2404호(가락동)
종목
정보동신업
정보통신업
발 급 사유
2024 년 06 월 19 일
송 파 세 무 서 장
"""


class BusinessRegistrationTests(unittest.TestCase):
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
        self.assertNotIn("missing required fields: businessType", parsed["warnings"])

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

    def test_collects_only_leading_subject_business_type_candidates(self):
        text = """
종목
정보동신업
정보통신업
정보동신업
응용
소프트웨어
개발
및
공급업
발
급
사유
"""

        parsed = parse_business_registration_text(text)

        self.assertEqual(parsed["fields"]["businessType"], "정보동신업 정보통신업")
        self.assertEqual(parsed["fields"]["businessTypeCandidates"], ["정보동신업", "정보통신업"])

    def test_collects_business_type_candidates_before_misread_subject_label(self):
        text = """
본
점
소
재
지
:
대전광역시
서구
서비스업
부동산업
서비스업
중목
주택관리업
및
건축물
일반
청소업
발
급
사
유
:
"""

        parsed = parse_business_registration_text(text)

        self.assertEqual(parsed["fields"]["businessType"], "서비스업 부동산업")
        self.assertEqual(parsed["fields"]["businessTypeCandidates"], ["서비스업", "부동산업"])

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
            },
        )
        self.assertEqual(parsed["warnings"], [])

    def test_normalize_date(self):
        self.assertEqual(normalize_date("2024 년 06 월 24 일"), "2024-06-24")


if __name__ == "__main__":
    unittest.main()
