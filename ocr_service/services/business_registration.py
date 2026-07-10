"""Document OCR 결과를 파싱하고, 필드가 부족하면 보조 OCR 결과로 메운다.

진위 확인, 광고업 분류, 최종 승인 판정은 이 Lambda가 하지 않는다.
서버가 수행하며 규칙은 docs/server-verification-spec.md에 있다.
"""

from ocr_service.extractors.business_registration import parse_business_registration_result
from ocr_service.extractors.business_registration.constants import REQUIRED_BUSINESS_FIELDS


def parse_business_registration_with_fallback(result: dict, fallback_result: dict | None = None) -> dict:
    parsed = parse_business_registration_result(result)
    if not fallback_result or not has_missing_required_business_fields(parsed):
        return parsed

    # Document OCR이 놓친 필드만 보조 OCR 결과로 채우고, 원래 값은 덮어쓰지 않는다.
    fallback = parse_business_registration_result(fallback_result)
    parsed["fields"] = {
        **fallback.get("fields", {}),
        **parsed.get("fields", {}),
    }
    parsed["warnings"] = merge_warnings_without_missing(parsed, fallback)
    return parsed


def has_missing_required_business_fields(parsed: dict) -> bool:
    fields = parsed.get("fields", {})
    return any(not fields.get(key) for key in REQUIRED_BUSINESS_FIELDS)


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
