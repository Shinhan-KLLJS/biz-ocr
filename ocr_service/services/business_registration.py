"""사업자등록증 파싱, 검증, 판정을 하나의 업무 흐름으로 묶는다."""

import re

from ocr_service.data_go_kr_client import validate_business_registration_fields
from ocr_service.extractors.business_registration import (
    classify_advertising_business,
    parse_business_registration_result,
)
from ocr_service.extractors.business_registration.constants import REQUIRED_BUSINESS_FIELDS
from ocr_service.policies.business_registration import decide_business_registration
from ocr_service.policies.business_registration_verification import decide_business_registration_verification


VALIDATION_REQUIRED_FIELDS = {
    "status": ("businessRegistrationNumber",),
    "authenticity": ("businessRegistrationNumber", "openingDate", "representativeName"),
}
VERIFICATION_SUBMISSION_FIELDS = VALIDATION_REQUIRED_FIELDS["authenticity"]
ADVERTISING_CLASSIFICATION_FIELDS = ("businessType", "businessItem")

# data.go.kr로 보내기 전에 확인하는 필드별 형식이다. 형식 규칙이 없는 필드는 담지 않는다.
VALIDATION_FIELD_FORMATS = {
    "businessRegistrationNumber": (r"\d{10}", "businessRegistrationNumber must be 10 digits without separators"),
    "openingDate": (r"\d{8}", "openingDate must be YYYYMMDD without separators"),
}


def analyze_business_registration(
    result: dict,
    validation_mode: str | None = None,
    fallback_result: dict | None = None,
) -> dict:
    parsed = parse_business_registration_with_fallback(result, fallback_result)
    return evaluate_business_registration(parsed, validation_mode)


def evaluate_business_registration(parsed: dict, validation_mode: str | None = None) -> dict:
    # 공식 국세청 API 검증은 사용자가 요청한 경우에만 수행한다.
    if validation_mode:
        parsed["validation"] = validate_if_fields_are_ready(parsed.get("fields", {}), validation_mode)

    parsed["decision"] = decide_business_registration(parsed)
    return parsed


def verify_business_registration_submission(fields: dict, validation_mode: str = "authenticity") -> dict:
    """사용자가 확정한 값으로 진위/상태 확인과 광고업 최종 판정을 수행한다."""
    normalized_mode = normalize_validation_mode(validation_mode)
    verification_fields = select_verification_submission_fields(fields or {})
    classification_fields = select_advertising_classification_fields(fields or {})
    parsed = {
        "documentType": "businessRegistrationCertificate",
        "fields": {**verification_fields, **classification_fields},
        "advertisingClassification": classify_advertising_business(classification_fields),
    }
    parsed["validation"] = validate_submission_if_fields_are_ready(verification_fields, normalized_mode)
    parsed["decision"] = decide_business_registration_verification(
        parsed["validation"],
        parsed["advertisingClassification"],
    )
    return parsed


def select_verification_submission_fields(fields: dict) -> dict:
    return {
        key: fields.get(key)
        for key in VERIFICATION_SUBMISSION_FIELDS
        if fields.get(key) is not None
    }


def select_advertising_classification_fields(fields: dict) -> dict:
    return {
        key: fields.get(key)
        for key in ADVERTISING_CLASSIFICATION_FIELDS
        if fields.get(key) is not None
    }


def validate_submission_if_fields_are_ready(fields: dict, validation_mode: str) -> dict:
    missing_fields = find_missing_validation_fields(fields, validation_mode)
    if missing_fields:
        return make_validation_input_error(validation_mode, missing_fields)

    format_error = find_verification_format_error(fields, validation_mode)
    if format_error:
        return make_validation_input_error(validation_mode, [], format_error)

    try:
        return validate_business_registration_fields(fields, validation_mode)
    except ValueError as exc:
        return make_validation_input_error(validation_mode, [], str(exc))


def find_verification_format_error(fields: dict, validation_mode: str) -> str | None:
    """해당 모드가 실제로 data.go.kr에 보내는 필드만 형식을 검사한다.

    status 모드는 사업자등록번호만 보내므로 개업일자를 요구하지 않는다.
    """
    for key in required_validation_fields(validation_mode):
        rule = VALIDATION_FIELD_FORMATS.get(key)
        if rule and not re.fullmatch(rule[0], str(fields.get(key, ""))):
            return rule[1]
    return None


def parse_business_registration_with_fallback(result: dict, fallback_result: dict | None = None) -> dict:
    parsed = parse_business_registration_result(result)
    if not fallback_result or not has_missing_required_business_fields(parsed):
        return parsed

    fallback = parse_business_registration_result(fallback_result)
    merged_fields = {
        **fallback.get("fields", {}),
        **parsed.get("fields", {}),
    }
    parsed["fields"] = merged_fields
    parsed["advertisingClassification"] = decide_advertising_classification(merged_fields, parsed)
    parsed["warnings"] = merge_warnings_without_missing(parsed, fallback)
    return parsed


def has_missing_required_business_fields(parsed: dict) -> bool:
    fields = parsed.get("fields", {})
    return any(not fields.get(key) for key in REQUIRED_BUSINESS_FIELDS)


def decide_advertising_classification(fields: dict, parsed: dict) -> dict:
    parsed["fields"] = fields
    return classify_advertising_business(fields)


def merge_warnings_without_missing(parsed: dict, fallback: dict) -> list[str]:
    warnings = [
        warning
        for warning in [*fallback.get("warnings", []), *parsed.get("warnings", [])]
        if not warning.startswith("missing required fields:")
    ]
    missing = [key for key in REQUIRED_BUSINESS_FIELDS if not parsed.get("fields", {}).get(key)]
    if missing:
        warnings.append(f"missing required fields: {', '.join(missing)}")
    return warnings


def validate_if_fields_are_ready(fields: dict, validation_mode: str) -> dict:
    missing_fields = find_missing_validation_fields(fields, validation_mode)
    if missing_fields:
        return make_validation_input_error(validation_mode, missing_fields)

    try:
        return validate_business_registration_fields(fields, validation_mode)
    except ValueError as exc:
        return make_validation_input_error(validation_mode, [], str(exc))


def required_validation_fields(validation_mode: str) -> tuple[str, ...]:
    """모드가 data.go.kr에 보내는 필수 필드를 돌려준다. 누락 검사와 형식 검사가 함께 쓴다."""
    return VALIDATION_REQUIRED_FIELDS.get(validation_mode, tuple(REQUIRED_BUSINESS_FIELDS))


def find_missing_validation_fields(fields: dict, validation_mode: str) -> list[str]:
    return [key for key in required_validation_fields(validation_mode) if not fields.get(key)]


def normalize_validation_mode(validation_mode: str | None) -> str:
    mode = (validation_mode or "authenticity").strip().lower()
    if mode not in VALIDATION_REQUIRED_FIELDS:
        raise ValueError("business registration validation mode must be 'status' or 'authenticity'")
    return mode


def make_validation_input_error(
    validation_mode: str,
    missing_fields: list[str],
    message: str | None = None,
) -> dict:
    return {
        "mode": validation_mode,
        "isValid": None,
        "isActive": None,
        "error": message or "required validation fields are missing",
        "missingFields": missing_fields,
    }
