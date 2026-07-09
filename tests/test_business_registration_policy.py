"""사업자등록증 최종 승인 정책을 검증한다."""

import unittest

from ocr_service.policies.business_registration import decide_business_registration


def make_parsed(validation=None, classification=None):
    return {
        "fields": {
            "businessRegistrationNumber": "368-88-03013",
            "companyName": "(주)글로벌데이터로드",
            "representativeName": "이상옥",
            "openingDate": "2024-06-24",
            "businessAddress": "서울특별시 송파구",
            "businessType": "서비스업",
            "businessItem": "광고대행",
        },
        "validation": validation,
        "advertisingClassification": classification
        or {
            "isAdvertisingRelated": True,
            "reviewRequired": False,
        },
    }


class BusinessRegistrationPolicyTests(unittest.TestCase):
    def test_accepts_only_active_valid_advertising_business(self):
        decision = decide_business_registration(
            make_parsed({"mode": "authenticity", "isCertificateValid": True, "isActive": True})
        )

        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(decision["reasonCode"], "ACCEPTED")

    def test_rejects_invalid_certificate(self):
        decision = decide_business_registration(
            make_parsed({"mode": "authenticity", "isCertificateValid": False, "isActive": True})
        )

        self.assertEqual(decision["status"], "rejected")
        self.assertEqual(decision["reasonCode"], "INVALID_CERTIFICATE")

    def test_rejects_inactive_business(self):
        decision = decide_business_registration(
            make_parsed({"mode": "status", "isRegistered": True, "isActive": False})
        )

        self.assertEqual(decision["status"], "rejected")
        self.assertEqual(decision["reasonCode"], "INACTIVE_BUSINESS")

    def test_rejects_non_advertising_business(self):
        decision = decide_business_registration(
            make_parsed(
                {"mode": "authenticity", "isCertificateValid": True, "isActive": True},
                {"isAdvertisingRelated": False, "reviewRequired": False},
            )
        )

        self.assertEqual(decision["status"], "rejected")
        self.assertEqual(decision["reasonCode"], "NON_ADVERTISING_BUSINESS")

    def test_requires_review_without_validation(self):
        parsed = make_parsed()
        parsed.pop("validation")

        decision = decide_business_registration(parsed)

        self.assertEqual(decision["status"], "review_required")
        self.assertEqual(decision["reasonCode"], "VALIDATION_REQUIRED")

    def test_requires_review_for_broad_advertising_match(self):
        decision = decide_business_registration(
            make_parsed(
                {"mode": "authenticity", "isCertificateValid": True, "isActive": True},
                {"isAdvertisingRelated": True, "reviewRequired": True},
            )
        )

        self.assertEqual(decision["status"], "review_required")
        self.assertEqual(decision["reasonCode"], "ADVERTISING_CLASSIFICATION_REVIEW_REQUIRED")

    def test_requires_authenticity_validation_after_status_check(self):
        decision = decide_business_registration(
            make_parsed({"mode": "status", "isRegistered": True, "isActive": True})
        )

        self.assertEqual(decision["status"], "review_required")
        self.assertEqual(decision["reasonCode"], "AUTHENTICITY_VALIDATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
