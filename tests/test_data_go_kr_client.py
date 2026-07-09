"""data.go.kr 사업자등록 검증 클라이언트의 요청/응답 변환을 검증한다."""

import os
import unittest
from unittest.mock import patch

from ocr_service.data_go_kr_client import (
    lookup_business_status,
    normalize_business_registration_number,
    normalize_representative_name,
    normalize_yyyymmdd,
    validate_business_registration_fields,
    verify_business_registration_authenticity,
)


class FakeResponse:
    def __init__(self, payload: dict, ok: bool = True):
        self.payload = payload
        self.ok = ok
        self.text = str(payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        raise RuntimeError("http error")


class DataGoKrClientTests(unittest.TestCase):
    def test_normalizes_business_registration_number(self):
        self.assertEqual(normalize_business_registration_number("368-88-03013"), "3688803013")

    def test_normalizes_opening_date(self):
        self.assertEqual(normalize_yyyymmdd("2024-06-24"), "20240624")

    def test_normalizes_representative_name_for_authenticity(self):
        self.assertEqual(normalize_representative_name("유미혜외 1명"), "유미혜")
        self.assertEqual(normalize_representative_name("유미혜 외 1명"), "유미혜")
        self.assertEqual(normalize_representative_name("조용길"), "조용길")

    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "service-key"}, clear=False)
    @patch("ocr_service.data_go_kr_client.requests.post")
    def test_lookup_business_status_posts_number_and_summarizes_status(self, mock_post):
        mock_post.return_value = FakeResponse(
            {
                "status_code": "OK",
                "data": [
                    {
                        "b_no": "3688803013",
                        "b_stt": "계속사업자",
                        "b_stt_cd": "01",
                        "tax_type": "부가가치세 일반과세자",
                        "tax_type_cd": "01",
                        "end_dt": "",
                        "rbf_tax_type": "해당없음",
                        "rbf_tax_type_cd": "99",
                    }
                ],
            }
        )

        validation = lookup_business_status("368-88-03013")

        self.assertTrue(validation["isValid"])
        self.assertTrue(validation["isActive"])
        self.assertEqual(validation["businessRegistrationNumber"], "368-88-03013")
        self.assertEqual(validation["previousTaxType"], "해당없음")
        self.assertEqual(validation["previousTaxTypeCode"], "99")
        self.assertEqual(mock_post.call_args.kwargs["json"], {"b_no": ["3688803013"]})

    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "service-key"}, clear=False)
    @patch("ocr_service.data_go_kr_client.requests.post")
    def test_verify_business_registration_authenticity_posts_certificate_fields(self, mock_post):
        mock_post.return_value = FakeResponse(
            {
                "status_code": "OK",
                "data": [
                    {
                        "b_no": "3688803013",
                        "valid": "01",
                        "valid_msg": "확인되었습니다.",
                        "status": {
                            "b_stt": "계속사업자",
                            "b_stt_cd": "01",
                            "tax_type": "부가가치세 일반과세자",
                            "tax_type_cd": "01",
                            "end_dt": "",
                            "rbf_tax_type": "해당없음",
                            "rbf_tax_type_cd": "99",
                        },
                    }
                ],
            }
        )
        fields = {
            "businessRegistrationNumber": "368-88-03013",
            "openingDate": "2024-06-24",
            "representativeName": "이상옥",
            "companyName": "(주)글로벌데이터로드",
            "businessType": "정보통신업",
            "businessItem": "응용 소프트웨어 개발 및 공급업",
            "businessAddress": "서울특별시 송파구 오금로46길 41,2층 2404호(가락동)",
        }

        validation = verify_business_registration_authenticity(fields)

        request_business = mock_post.call_args.kwargs["json"]["businesses"][0]
        self.assertEqual(request_business["b_no"], "3688803013")
        self.assertEqual(request_business["start_dt"], "20240624")
        self.assertEqual(request_business["p_nm"], "이상옥")
        self.assertEqual(request_business["b_nm"], "(주)글로벌데이터로드")
        self.assertNotIn("b_sector", request_business)
        self.assertNotIn("b_type", request_business)
        self.assertNotIn("b_adr", request_business)
        self.assertEqual(
            request_business,
            {
                "b_no": "3688803013",
                "start_dt": "20240624",
                "p_nm": "이상옥",
                "b_nm": "(주)글로벌데이터로드",
            },
        )
        self.assertTrue(validation["isValid"])
        self.assertTrue(validation["isActive"])
        self.assertEqual(validation["previousTaxType"], "해당없음")

    def test_validate_business_registration_fields_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            validate_business_registration_fields({}, "unknown")


if __name__ == "__main__":
    unittest.main()
