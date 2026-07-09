"""업태와 종목 후보 수집처럼 줄 순서에 민감한 로직을 검증한다."""

import unittest

from ocr_service.extractors.business_registration import parse_business_registration_text


class BusinessRegistrationItemTests(unittest.TestCase):
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
        self.assertEqual(parsed["fields"]["businessItem"], "응용 소프트웨어 개발 및 공급업")

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
        self.assertEqual(parsed["fields"]["businessItem"], "주택관리업 및 건축물 일반 청소업")

    def test_business_item_stops_before_split_footer_labels(self):
        text = """
사
업
의
종
류
:
업태
서비스
발
급
사
유
:
대표자정정
종목
연구용역
사업자
단위
과세
적용사업자
여부
:
여(
)
부(V)
"""

        parsed = parse_business_registration_text(text)

        self.assertEqual(parsed["fields"]["businessType"], "서비스")
        self.assertEqual(parsed["fields"]["businessItem"], "연구용역")


if __name__ == "__main__":
    unittest.main()
