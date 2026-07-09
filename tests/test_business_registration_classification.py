"""광고 관련 업종 분류 결과를 검증한다."""

import unittest

from ocr_service.extractors.business_registration import classify_advertising_business


class BusinessRegistrationClassificationTests(unittest.TestCase):
    def test_classifies_advertising_business_from_business_item(self):
        classification = classify_advertising_business(
            {
                "businessType": "서비스업",
                "businessItem": "광고대행 및 온라인광고",
            }
        )

        self.assertTrue(classification["isAdvertisingRelated"])
        self.assertEqual(classification["classificationStatus"], "matched")
        self.assertEqual(classification["confidence"], "high")
        self.assertEqual(classification["matchedKeywords"], ["광고대행", "온라인광고", "광고"])
        self.assertEqual(
            classification["sourceFields"],
            {
                "businessType": "서비스업",
                "businessItem": "광고대행 및 온라인광고",
            },
        )
        self.assertEqual(classification["missingFields"], [])
        self.assertFalse(classification["reviewRequired"])
        self.assertEqual(classification["reason"], "matched high-confidence advertising keywords")

    def test_classifies_marketing_business_as_review_required(self):
        classification = classify_advertising_business(
            {
                "businessType": "서비스업",
                "businessItem": "마케팅대행 및 브랜딩",
            }
        )

        self.assertTrue(classification["isAdvertisingRelated"])
        self.assertEqual(classification["classificationStatus"], "matched")
        self.assertEqual(classification["confidence"], "medium")
        self.assertEqual(classification["matchedKeywords"], ["마케팅대행", "브랜딩", "마케팅"])
        self.assertTrue(classification["reviewRequired"])
        self.assertEqual(classification["reason"], "matched broad advertising-related keywords")

    def test_classifies_non_advertising_business(self):
        classification = classify_advertising_business(
            {
                "businessType": "정보통신업",
                "businessItem": "응용 소프트웨어 개발 및 공급업",
            }
        )

        self.assertFalse(classification["isAdvertisingRelated"])
        self.assertEqual(classification["classificationStatus"], "not_matched")
        self.assertEqual(classification["confidence"], "none")
        self.assertEqual(classification["matchedKeywords"], [])
        self.assertEqual(classification["missingFields"], [])
        self.assertFalse(classification["reviewRequired"])
        self.assertEqual(classification["reason"], "no advertising keywords matched in businessType or businessItem")

    def test_classifies_incomplete_business_fields_as_unknown_false(self):
        classification = classify_advertising_business({"businessType": "서비스업"})

        self.assertFalse(classification["isAdvertisingRelated"])
        self.assertEqual(classification["classificationStatus"], "unknown")
        self.assertEqual(classification["confidence"], "unknown")
        self.assertEqual(classification["matchedKeywords"], [])
        self.assertEqual(classification["sourceFields"], {"businessType": "서비스업"})
        self.assertEqual(classification["missingFields"], ["businessItem"])
        self.assertTrue(classification["reviewRequired"])
        self.assertEqual(classification["reason"], "missing required classification fields: businessItem")


if __name__ == "__main__":
    unittest.main()
