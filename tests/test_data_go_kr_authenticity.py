"""data.go.kr 진위확인 보조 흐름을 검증한다."""

import os
import unittest
from unittest.mock import patch

from ocr_service.data_go_kr_client import verify_business_registration_authenticity


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload
        self.ok = True
        self.text = str(payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        raise RuntimeError("http error")


class DataGoKrAuthenticityTests(unittest.TestCase):
    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "service-key"}, clear=False)
    @patch("ocr_service.data_go_kr_client.requests.post")
    def test_authenticity_failure_without_status_fetches_status(self, mock_post):
        mock_post.side_effect = [
            FakeResponse(
                {
                    "status_code": "OK",
                    "data": [{"b_no": "1328148751", "valid": "02", "valid_msg": "확인할 수 없습니다."}],
                }
            ),
            FakeResponse(
                {
                    "status_code": "OK",
                    "data": [
                        {
                            "b_no": "1328148751",
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
            ),
        ]
        fields = {
            "businessRegistrationNumber": "132-81-48751",
            "openingDate": "2003-02-14",
            "representativeName": "조용길",
        }

        validation = verify_business_registration_authenticity(fields)

        self.assertFalse(validation["isCertificateValid"])
        self.assertTrue(validation["isRegistered"])
        self.assertTrue(validation["isActive"])
        self.assertEqual(validation["taxType"], "부가가치세 일반과세자")
        self.assertEqual(validation["validMessage"], "확인할 수 없습니다.")
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"], {"b_no": ["1328148751"]})

    @patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "service-key"}, clear=False)
    @patch("ocr_service.data_go_kr_client.requests.post")
    def test_authenticity_request_uses_primary_representative_name(self, mock_post):
        mock_post.return_value = FakeResponse(
            {
                "status_code": "OK",
                "data": [
                    {
                        "b_no": "1320557431",
                        "valid": "01",
                        "status": {
                            "b_stt": "계속사업자",
                            "b_stt_cd": "01",
                            "tax_type": "부가가치세 일반과세자",
                        },
                    }
                ],
            }
        )
        fields = {
            "businessRegistrationNumber": "132-05-57431",
            "openingDate": "1998-02-01",
            "representativeName": "유미혜외 1명",
            "companyName": "삼주전자",
        }

        verify_business_registration_authenticity(fields)

        request_business = mock_post.call_args.kwargs["json"]["businesses"][0]
        self.assertEqual(request_business["p_nm"], "유미혜")


if __name__ == "__main__":
    unittest.main()
