"""내부 OCR/검증 결과를 클라이언트용 최소 응답으로 줄인다."""

import re

from ocr_service.extractors.business_registration.constants import REQUIRED_BUSINESS_FIELDS


CLIENT_EDITABLE_FIELDS = (
    "companyName",
    "representativeName",
    "businessRegistrationNumber",
    "openingDate",
    "businessAddress",
    "businessType",
    "businessItem",
    "businessTypeCandidates",
    "businessItemsRaw",
)


def build_business_registration_response(parsed: dict) -> dict:
    fields = parsed.get("fields") or {}
    validation = parsed.get("validation") or {}
    classification = parsed.get("advertisingClassification") or {}
    decision = parsed.get("decision") or {}

    eligibility = {
        "isEligible": decision.get("status") == "accepted",
        "isCertificateValid": validation.get("isCertificateValid"),
        "isRegistered": validation.get("isRegistered"),
        "isActive": validation.get("isActive"),
        "isAdvertisingRelated": classification.get("isAdvertisingRelated"),
        "validationMode": validation.get("mode"),
        "validationCode": validation.get("validCode"),
        "validationMessage": validation.get("validMessage"),
        "businessStatus": validation.get("businessStatus"),
        "taxType": validation.get("taxType"),
        "reasonCode": decision.get("reasonCode"),
        "message": decision.get("message"),
    }
    if decision.get("missingFields"):
        eligibility["missingFields"] = decision["missingFields"]
    if decision.get("validationError"):
        eligibility["validationError"] = decision["validationError"]

    return {
        "status": decision.get("status", "review_required"),
        "business": {
            "companyName": fields.get("companyName"),
            "representativeName": fields.get("representativeName"),
            "businessRegistrationNumber": fields.get("businessRegistrationNumber"),
        },
        "eligibility": eligibility,
    }


def build_business_registration_verification_response(parsed: dict) -> dict:
    """진위/현황 확인과 광고업 판단을 합친 최종 판정을 반환한다."""
    fields = parsed.get("fields") or {}
    validation = parsed.get("validation") or {}
    decision = parsed.get("decision") or {}
    classification = parsed.get("advertisingClassification") or {}

    response = {
        "status": decision.get("status", "review_required"),
        "business": {
            "businessRegistrationNumber": fields.get("businessRegistrationNumber"),
            "representativeName": fields.get("representativeName"),
            "openingDate": fields.get("openingDate"),
            "businessType": fields.get("businessType"),
            "businessItem": fields.get("businessItem"),
        },
        "verification": {
            "isCertificateValid": validation.get("isCertificateValid"),
            "isRegistered": validation.get("isRegistered"),
            "isActive": validation.get("isActive"),
            "validationMode": validation.get("mode"),
            "validationCode": validation.get("validCode"),
            "validationMessage": validation.get("validMessage"),
            "businessStatus": validation.get("businessStatus"),
            "taxType": validation.get("taxType"),
            "reasonCode": decision.get("reasonCode"),
            "message": decision.get("message"),
        },
        "advertisingClassification": classification,
        "eligibility": {
            "isEligible": decision.get("status") == "accepted",
            "isCertificateValid": validation.get("isCertificateValid"),
            "isRegistered": validation.get("isRegistered"),
            "isActive": validation.get("isActive"),
            "isAdvertisingRelated": classification.get("isAdvertisingRelated"),
            "reasonCode": decision.get("reasonCode"),
            "message": decision.get("message"),
        },
    }
    if decision.get("missingFields"):
        response["verification"]["missingFields"] = decision["missingFields"]
        response["eligibility"]["missingFields"] = decision["missingFields"]
    if decision.get("validationError"):
        response["verification"]["validationError"] = decision["validationError"]
        response["eligibility"]["validationError"] = decision["validationError"]
    return response


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
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == expected_length else None
