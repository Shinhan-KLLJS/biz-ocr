"""사업자등록증 필드 정규화 유틸리티를 검증한다."""

import unittest

from ocr_service.extractors.business_registration import normalize_date


class BusinessRegistrationNormalizationTests(unittest.TestCase):
    def test_normalize_date(self):
        self.assertEqual(normalize_date("2024 년 06 월 24 일"), "2024-06-24")


if __name__ == "__main__":
    unittest.main()
