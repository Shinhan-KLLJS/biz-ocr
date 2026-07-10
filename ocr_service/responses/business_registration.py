"""OCR 파싱 결과를 프론트가 검토/수정할 수 있는 최소 응답으로 줄인다."""

import re

from ocr_service.extractors.business_registration.constants import REQUIRED_BUSINESS_FIELDS


# 사업장주소는 저장하지도 검증하지도 않는 개인정보라 응답에 넣지 않는다.
CLIENT_EDITABLE_FIELDS = (
    "companyName",
    "representativeName",
    "businessRegistrationNumber",
    "openingDate",
    "businessType",
    "businessItem",
    "businessTypeCandidates",
    "businessItemsRaw",
)


def build_business_registration_ocr_response(parsed: dict) -> dict:
    """프론트가 OCR 추정값을 검토/수정할 수 있는 응답을 만든다."""
    fields = parsed.get("fields") or {}
    business = select_editable_business_fields(fields)
    missing_fields = [
        key
        for key in REQUIRED_BUSINESS_FIELDS
        if not business.get(key)
    ]
    response = {
        "status": "ocr_completed",
        "documentType": parsed.get("documentType", "businessRegistrationCertificate"),
        "business": business,
        "missingFields": missing_fields,
        "warnings": parsed.get("warnings", []),
    }
    if parsed.get("source"):
        response["source"] = parsed["source"]
    return response


def select_editable_business_fields(fields: dict) -> dict:
    return {
        key: normalize_ocr_response_field(key, fields.get(key))
        for key in CLIENT_EDITABLE_FIELDS
        if key in fields
    }


def normalize_ocr_response_field(key: str, value: object) -> object:
    if key == "businessRegistrationNumber":
        return normalize_digit_field(value, 10)
    if key == "openingDate":
        return normalize_digit_field(value, 8)
    return value


def normalize_digit_field(value: object, expected_length: int) -> str | None:
    """서버가 그대로 data.go.kr에 보낼 수 있도록 구분자를 제거한다."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == expected_length else None
