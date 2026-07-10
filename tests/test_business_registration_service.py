"""Document OCR 결과가 부족할 때의 보조 OCR 병합 동작을 검증한다."""

import unittest
from unittest.mock import patch

from ocr_service.services.business_registration import (
    has_missing_required_business_fields,
    parse_business_registration_with_fallback,
)


COMPLETE_FIELDS = {
    "businessRegistrationNumber": "368-88-03013",
    "companyName": "애드컴주식회사",
    "representativeName": "조용길",
    "openingDate": "2003-02-14",
    "businessType": "제조",
    "businessItem": "광고물제작",
}


class MissingFieldTests(unittest.TestCase):
    def test_complete_fields_are_not_missing(self):
        self.assertFalse(has_missing_required_business_fields({"fields": COMPLETE_FIELDS}))

    def test_absent_representative_name_is_missing(self):
        fields = {**COMPLETE_FIELDS}
        del fields["representativeName"]

        self.assertTrue(has_missing_required_business_fields({"fields": fields}))

    def test_business_address_is_no_longer_required(self):
        # 주소는 저장하지도 검증하지도 않으므로 보조 OCR을 다시 부를 이유가 없다.
        self.assertFalse(has_missing_required_business_fields({"fields": COMPLETE_FIELDS}))


class FallbackMergeTests(unittest.TestCase):
    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    def test_fallback_is_ignored_when_document_ocr_is_complete(self, mock_parse):
        mock_parse.return_value = {"fields": COMPLETE_FIELDS, "warnings": []}

        parsed = parse_business_registration_with_fallback({"images": []}, {"images": ["fallback"]})

        self.assertEqual(parsed["fields"], COMPLETE_FIELDS)
        # 보조 결과를 파싱하지 않고 곧장 반환한다.
        mock_parse.assert_called_once()

    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    def test_fallback_fills_only_the_missing_fields(self, mock_parse):
        primary_fields = {**COMPLETE_FIELDS}
        del primary_fields["representativeName"]
        mock_parse.side_effect = [
            {"fields": primary_fields, "warnings": ["missing required fields: representativeName"]},
            {"fields": {**COMPLETE_FIELDS, "companyName": "잘못 읽은 상호"}, "warnings": ["fallback warning"]},
        ]

        parsed = parse_business_registration_with_fallback({"images": []}, {"images": ["fallback"]})

        self.assertEqual(parsed["fields"]["representativeName"], "조용길")
        # Document OCR이 읽은 값은 보조 결과가 덮어쓰지 않는다.
        self.assertEqual(parsed["fields"]["companyName"], "애드컴주식회사")
        self.assertNotIn("missing required fields: representativeName", parsed["warnings"])
        self.assertIn("fallback warning", parsed["warnings"])

    @patch("ocr_service.services.business_registration.parse_business_registration_result")
    def test_still_reports_fields_that_neither_ocr_could_read(self, mock_parse):
        sparse_fields = {"businessRegistrationNumber": "368-88-03013"}
        mock_parse.side_effect = [
            {"fields": sparse_fields, "warnings": []},
            {"fields": sparse_fields, "warnings": []},
        ]

        parsed = parse_business_registration_with_fallback({"images": []}, {"images": ["fallback"]})

        warning = next(w for w in parsed["warnings"] if w.startswith("missing required fields:"))
        self.assertIn("representativeName", warning)
        self.assertIn("businessItem", warning)


if __name__ == "__main__":
    unittest.main()
