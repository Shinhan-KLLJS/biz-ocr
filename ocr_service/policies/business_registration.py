"""사업자등록증 OCR 결과의 최종 승인 여부를 판정한다."""

from ocr_service.extractors.business_registration.constants import REQUIRED_BUSINESS_FIELDS


def decide_business_registration(parsed: dict) -> dict:
    fields = parsed.get("fields") or {}
    validation = parsed.get("validation")
    classification = parsed.get("advertisingClassification") or {}

    # OCR 필드가 부족하면 외부 검증보다 먼저 수동 검토로 보낸다.
    missing_fields = [
        key for key in REQUIRED_BUSINESS_FIELDS
        if not fields.get(key)
    ]
    if missing_fields:
        return make_decision(
            "review_required",
            "MISSING_REQUIRED_FIELDS",
            "필수 OCR 필드가 누락되어 수동 검토가 필요합니다.",
            missingFields=missing_fields,
        )

    if not validation:
        return make_decision(
            "review_required",
            "VALIDATION_REQUIRED",
            "사업자 상태 또는 진위 검증 결과가 없어 최종 승인할 수 없습니다.",
        )

    if validation.get("error"):
        return make_decision(
            "review_required",
            "VALIDATION_INPUT_INCOMPLETE",
            "사업자 검증에 필요한 OCR 필드가 부족하여 수동 검토가 필요합니다.",
            missingFields=validation.get("missingFields", []),
            validationError=validation.get("error"),
        )

    validation_mode = validation.get("mode")
    if validation.get("isRegistered") is False:
        return make_decision(
            "rejected",
            "UNREGISTERED_BUSINESS",
            "등록된 사업자로 확인되지 않았습니다.",
        )

    if validation.get("isCertificateValid") is False:
        return make_decision(
            "rejected",
            "INVALID_CERTIFICATE",
            "사업자등록증 진위 확인에 실패했습니다.",
        )

    if validation.get("isActive") is False:
        return make_decision(
            "rejected",
            "INACTIVE_BUSINESS",
            "현재 운영 중인 사업자로 확인되지 않았습니다.",
        )

    if validation_mode == "status":
        return make_decision(
            "review_required",
            "AUTHENTICITY_VALIDATION_REQUIRED",
            "사업자 상태는 확인되었지만 사업자등록증 진위 확인이 필요합니다.",
        )

    if not classification:
        return make_decision(
            "review_required",
            "ADVERTISING_CLASSIFICATION_UNAVAILABLE",
            "광고 업종 분류 결과가 없어 수동 검토가 필요합니다.",
        )

    if not classification.get("isAdvertisingRelated"):
        return make_decision(
            "rejected",
            "NON_ADVERTISING_BUSINESS",
            "광고 관련 사업자로 분류되지 않았습니다.",
        )

    if classification.get("reviewRequired"):
        return make_decision(
            "review_required",
            "ADVERTISING_CLASSIFICATION_REVIEW_REQUIRED",
            "광고 관련성이 넓은 키워드로만 확인되어 수동 검토가 필요합니다.",
        )

    return make_decision(
        "accepted",
        "ACCEPTED",
        "현재 운영 중인 광고 관련 사업자로 확인되었습니다.",
    )


def make_decision(status: str, reason_code: str, message: str, **extra: object) -> dict:
    decision = {
        "status": status,
        "reasonCode": reason_code,
        "message": message,
    }
    decision.update(extra)
    return decision
