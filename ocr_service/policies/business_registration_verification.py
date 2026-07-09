"""검증 API의 진위/현황 결과와 광고업 판단을 최종 판정으로 합친다."""

from ocr_service.policies.business_registration import make_decision


def decide_business_registration_verification(validation: dict, classification: dict) -> dict:
    if validation.get("error"):
        return make_decision(
            "review_required",
            "VALIDATION_INPUT_INCOMPLETE",
            "사업자등록증 진위 확인에 필요한 필수 값이 부족하거나 형식이 올바르지 않습니다.",
            missingFields=validation.get("missingFields", []),
            validationError=validation.get("error"),
        )
    if validation.get("isRegistered") is False:
        return make_decision("rejected", "UNREGISTERED_BUSINESS", "등록된 사업자로 확인되지 않았습니다.")
    if validation.get("isCertificateValid") is False:
        return make_decision("rejected", "INVALID_CERTIFICATE", "사업자등록증 진위 확인에 실패했습니다.")
    if validation.get("isActive") is False:
        return make_decision("rejected", "INACTIVE_BUSINESS", "현재 운영 중인 사업자로 확인되지 않았습니다.")
    if classification.get("missingFields"):
        return make_decision(
            "review_required",
            "ADVERTISING_CLASSIFICATION_INPUT_INCOMPLETE",
            "광고업 판단에 필요한 업태/종목 값이 부족합니다.",
            missingFields=classification.get("missingFields", []),
        )
    if classification.get("isAdvertisingRelated") is False:
        return make_decision("rejected", "NON_ADVERTISING_BUSINESS", "광고 관련 사업자로 분류되지 않았습니다.")
    if classification.get("reviewRequired"):
        return make_decision(
            "review_required",
            "ADVERTISING_CLASSIFICATION_REVIEW_REQUIRED",
            "광고 관련성이 넓은 키워드로만 확인되어 수동 검토가 필요합니다.",
        )
    if validation.get("isCertificateValid") is True:
        return make_decision("accepted", "ACCEPTED", "현재 운영 중인 광고 관련 사업자로 확인되었습니다.")
    return make_decision("review_required", "VALIDATION_UNDETERMINED", "사업자등록증 검증 결과를 확정할 수 없습니다.")
