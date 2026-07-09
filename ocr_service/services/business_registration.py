"""사업자등록증 파싱, 검증, 판정을 하나의 업무 흐름으로 묶는다."""

from ocr_service.data_go_kr_client import validate_business_registration_fields
from ocr_service.extractors.business_registration import parse_business_registration_result
from ocr_service.policies.business_registration import decide_business_registration


def analyze_business_registration(result: dict, validation_mode: str | None = None) -> dict:
    parsed = parse_business_registration_result(result)

    # 공식 국세청 API 검증은 사용자가 요청한 경우에만 수행한다.
    if validation_mode:
        parsed["validation"] = validate_business_registration_fields(
            parsed.get("fields", {}),
            validation_mode,
        )

    parsed["decision"] = decide_business_registration(parsed)
    return parsed
