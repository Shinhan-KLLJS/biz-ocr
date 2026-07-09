"""data.go.kr 국세청 사업자등록 API 호출과 응답 정리를 담당한다."""

import logging
import os
import re
from urllib.parse import quote

import requests

from ocr_service.config import get_required_env
from ocr_service.errors import ExternalServiceError
from ocr_service.redaction import redact_secrets


NTS_BUSINESSMAN_BASE_URL = "https://api.odcloud.kr/api/nts-businessman/v1"
STATUS_ENDPOINT = "status"
AUTHENTICITY_ENDPOINT = "validate"

logger = logging.getLogger(__name__)


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
    try:
        response = requests.post(
            build_data_go_kr_url(endpoint),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout or int(os.getenv("DATA_GO_KR_TIMEOUT", "30")),
        )
    except requests.RequestException as exc:
        # requests 예외 메시지에는 serviceKey가 담긴 요청 URL이 그대로 들어간다.
        # 연쇄(chaining) 없이 마스킹한 메시지만 올려 호출자와 로그에 키가 남지 않게 한다.
        raise ExternalServiceError(f"NTS business validation request failed: {redact_secrets(exc)}") from None

    if not response.ok:
        logger.error(
            "NTS business validation responded %s: %s",
            response.status_code,
            redact_secrets(response.text),
        )
        raise ExternalServiceError(f"NTS business validation responded with HTTP {response.status_code}")

    result = response.json()
    status_code = result.get("status_code")
    if status_code and status_code != "OK":
        raise ExternalServiceError(f"NTS business validation failed: {status_code}")
    return result


def lookup_business_status(registration_number: str, timeout: int | None = None) -> dict:
    business_number = normalize_business_registration_number(registration_number)
    result = post_nts_businessman(STATUS_ENDPOINT, {"b_no": [business_number]}, timeout=timeout)
    item = first_response_item(result)
    return summarize_business_status(business_number, item)


def summarize_business_status(business_number: str, item: dict) -> dict:
    registered = is_registered_status_item(item)
    return {
        "provider": "data.go.kr/nts-businessman",
        "mode": "status",
        "businessRegistrationNumber": format_business_registration_number(business_number),
        "isCertificateValid": None,
        "isRegistered": registered,
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
    representative_name = normalize_representative_name(require_field(fields, "representativeName"))

    business = {
        "b_no": business_number,
        "start_dt": opening_date,
        "p_nm": representative_name,
    }
    # 진위확인은 Swagger 예시의 핵심 식별값만 보낸다. OCR 업태/종목/주소는 흔들림이 커서 일치 검증에 쓰지 않는다.
    add_optional_business_description(business, "b_nm", fields.get("companyName"))

    result = post_nts_businessman(AUTHENTICITY_ENDPOINT, {"businesses": [business]}, timeout=timeout)
    item = first_response_item(result)
    status = item.get("status") or {}
    status_summary = summarize_business_status(business_number, status) if status else {}
    if not status_summary:
        status_summary = lookup_business_status(business_number, timeout=timeout)
    certificate_valid = item.get("valid") == "01"

    return {
        "provider": "data.go.kr/nts-businessman",
        "mode": "authenticity",
        "businessRegistrationNumber": format_business_registration_number(business_number),
        "isCertificateValid": certificate_valid,
        "isRegistered": status_summary.get("isRegistered"),
        "isValid": certificate_valid,
        "validCode": item.get("valid"),
        "validMessage": item.get("valid_msg"),
        "isActive": status_summary.get("isActive"),
        "businessStatus": status_summary.get("businessStatus"),
        "businessStatusCode": status_summary.get("businessStatusCode"),
        "taxType": status_summary.get("taxType"),
        "taxTypeCode": status_summary.get("taxTypeCode"),
        "closedDate": status_summary.get("closedDate"),
        "unitTaxClosure": status_summary.get("unitTaxClosure"),
        "taxTypeChangeDate": status_summary.get("taxTypeChangeDate"),
        "invoiceApplyDate": status_summary.get("invoiceApplyDate"),
        "previousTaxType": status_summary.get("previousTaxType"),
        "previousTaxTypeCode": status_summary.get("previousTaxTypeCode"),
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


def normalize_representative_name(value: str) -> str:
    # 사업자등록증에는 "대표자 외 N명" 표기가 있지만 국세청 진위확인은 대표자명만 받는다.
    normalized = re.sub(r"\s+", "", value or "")
    normalized = re.sub(r"외\d+명$", "", normalized)
    normalized = re.sub(r"외[0-9]+명$", "", normalized)
    if not normalized:
        raise ValueError("representativeName is required for authenticity validation")
    return normalized


def add_optional_business_description(business: dict, key: str, value: str | None) -> None:
    if value:
        business[key] = value


def format_business_registration_number(value: str) -> str:
    digits = normalize_business_registration_number(value)
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
