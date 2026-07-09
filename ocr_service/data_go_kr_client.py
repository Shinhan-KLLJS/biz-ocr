"""data.go.kr 국세청 사업자등록 API 호출과 응답 정리를 담당한다."""

import os
import re
import sys
from urllib.parse import quote

import requests

from ocr_service.config import get_required_env


NTS_BUSINESSMAN_BASE_URL = "https://api.odcloud.kr/api/nts-businessman/v1"
STATUS_ENDPOINT = "status"
AUTHENTICITY_ENDPOINT = "validate"


def normalize_business_registration_number(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 10:
        raise ValueError("businessRegistrationNumber must contain 10 digits")
    return digits


def normalize_yyyymmdd(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 8:
        raise ValueError("openingDate must contain 8 digits")
    return digits


def build_data_go_kr_url(endpoint: str) -> str:
    base_url = os.getenv("DATA_GO_KR_NTS_BUSINESSMAN_BASE_URL", NTS_BUSINESSMAN_BASE_URL).rstrip("/")
    service_key = get_required_env("DATA_GO_KR_SERVICE_KEY")
    # 공공데이터포털 키는 이미 URL 인코딩된 값으로 배포되는 경우가 있어 중복 인코딩을 피한다.
    encoded_key = service_key if "%" in service_key else quote(service_key, safe="")
    return f"{base_url}/{endpoint}?serviceKey={encoded_key}"


def post_nts_businessman(endpoint: str, payload: dict, timeout: int | None = None) -> dict:
    response = requests.post(
        build_data_go_kr_url(endpoint),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout or int(os.getenv("DATA_GO_KR_TIMEOUT", "30")),
    )

    if not response.ok:
        print(response.text, file=sys.stderr)
        response.raise_for_status()

    result = response.json()
    status_code = result.get("status_code")
    if status_code and status_code != "OK":
        raise RuntimeError(f"NTS business validation failed: {status_code}")
    return result


def lookup_business_status(registration_number: str, timeout: int | None = None) -> dict:
    business_number = normalize_business_registration_number(registration_number)
    result = post_nts_businessman(STATUS_ENDPOINT, {"b_no": [business_number]}, timeout=timeout)
    item = first_response_item(result)
    registered = is_registered_status_item(item)

    return {
        "provider": "data.go.kr/nts-businessman",
        "mode": "status",
        "businessRegistrationNumber": format_business_registration_number(business_number),
        "isValid": registered,
        "isActive": item.get("b_stt_cd") == "01",
        "businessStatus": item.get("b_stt"),
        "businessStatusCode": item.get("b_stt_cd"),
        "taxType": item.get("tax_type"),
        "taxTypeCode": item.get("tax_type_cd"),
        "closedDate": item.get("end_dt") or None,
        "unitTaxClosure": item.get("utcc_yn") or None,
        "taxTypeChangeDate": item.get("tax_type_change_dt") or None,
        "invoiceApplyDate": item.get("invoice_apply_dt") or None,
        "previousTaxType": item.get("rbf_tax_type"),
        "previousTaxTypeCode": item.get("rbf_tax_type_cd"),
        "raw": item,
    }


def verify_business_registration_authenticity(fields: dict, timeout: int | None = None) -> dict:
    business_number = normalize_business_registration_number(fields.get("businessRegistrationNumber", ""))
    opening_date = normalize_yyyymmdd(fields.get("openingDate", ""))
    representative_name = require_field(fields, "representativeName")

    business = {
        "b_no": business_number,
        "start_dt": opening_date,
        "p_nm": representative_name,
    }
    add_optional_business_description(business, "b_nm", fields.get("companyName"))
    # 국세청 진위확인 API의 업태/종목 입력명은 각각 b_sector/b_type이다.
    add_optional_business_description(business, "b_sector", fields.get("businessType"))
    add_optional_business_description(business, "b_type", fields.get("businessItem"))
    add_optional_business_description(business, "b_adr", fields.get("businessAddress"))

    result = post_nts_businessman(AUTHENTICITY_ENDPOINT, {"businesses": [business]}, timeout=timeout)
    item = first_response_item(result)
    status = item.get("status") or {}

    return {
        "provider": "data.go.kr/nts-businessman",
        "mode": "authenticity",
        "businessRegistrationNumber": format_business_registration_number(business_number),
        "isValid": item.get("valid") == "01",
        "validCode": item.get("valid"),
        "validMessage": item.get("valid_msg"),
        "isActive": status.get("b_stt_cd") == "01",
        "businessStatus": status.get("b_stt"),
        "businessStatusCode": status.get("b_stt_cd"),
        "taxType": status.get("tax_type"),
        "taxTypeCode": status.get("tax_type_cd"),
        "closedDate": status.get("end_dt") or None,
        "unitTaxClosure": status.get("utcc_yn") or None,
        "taxTypeChangeDate": status.get("tax_type_change_dt") or None,
        "invoiceApplyDate": status.get("invoice_apply_dt") or None,
        "previousTaxType": status.get("rbf_tax_type"),
        "previousTaxTypeCode": status.get("rbf_tax_type_cd"),
        "raw": item,
    }


def validate_business_registration_fields(fields: dict, mode: str, timeout: int | None = None) -> dict:
    if mode == "status":
        return lookup_business_status(fields.get("businessRegistrationNumber", ""), timeout=timeout)
    if mode == "authenticity":
        return verify_business_registration_authenticity(fields, timeout=timeout)
    raise ValueError("business registration validation mode must be 'status' or 'authenticity'")


def first_response_item(result: dict) -> dict:
    data = result.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("NTS business validation response did not include data")
    if not isinstance(data[0], dict):
        raise RuntimeError("NTS business validation response item is not an object")
    return data[0]


def is_registered_status_item(item: dict) -> bool:
    tax_type = item.get("tax_type") or ""
    return bool(item.get("b_stt_cd")) and "등록되어 있지 않은" not in tax_type


def require_field(fields: dict, key: str) -> str:
    value = fields.get(key)
    if not value:
        raise ValueError(f"{key} is required for authenticity validation")
    return value


def add_optional_business_description(business: dict, key: str, value: str | None) -> None:
    if value:
        business[key] = value


def format_business_registration_number(value: str) -> str:
    digits = normalize_business_registration_number(value)
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
