"""Lambda 이벤트를 해석해 동작을 고르고, API Gateway 형식 응답을 만든다."""

import json
import os

from ocr_service.ncloud_client import parse_template_ids


VERIFICATION_INPUT_FIELDS = {
    "businessRegistrationNumber",
    "representativeName",
    "openingDate",
    "businessType",
    "businessItem",
}


def make_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def normalize_event(event) -> dict:
    if not isinstance(event, dict):
        return {}

    body = event.get("body")
    if isinstance(body, str) and body.strip():
        try:
            body_payload = json.loads(body)
        except json.JSONDecodeError:
            return event
        if isinstance(body_payload, dict):
            return {**event, **body_payload}

    return event


def resolve_operation(event: dict) -> str:
    operation = event.get("operation") or event.get("action")
    if operation:
        return normalize_operation(operation)

    path = extract_request_path(event)
    if path.endswith("/ocr") or path.endswith("/ocr/"):
        return "ocr"
    if path.endswith("/verification") or path.endswith("/verification/"):
        return "verification"
    return "unsupported"


def normalize_operation(operation: object) -> str:
    value = str(operation).strip().lower()
    if value in {"ocr", "extract", "parse"}:
        return "ocr"
    if value in {"verification", "verify", "validate"}:
        return "verification"
    return "unsupported"


def extract_request_path(event: dict) -> str:
    request_context = event.get("requestContext") or {}
    http_context = request_context.get("http") or {}
    return str(event.get("rawPath") or event.get("path") or http_context.get("path") or "")


def parse_event_template_ids(event: dict) -> list[int]:
    template_ids = event.get("templateIds") or event.get("template_ids")
    if not template_ids:
        return []
    if isinstance(template_ids, list):
        return [int(template_id) for template_id in template_ids]
    return parse_template_ids(str(template_ids))


def parse_business_validation_mode(event: dict) -> str | None:
    mode = (
        event.get("businessRegistrationValidation")
        or event.get("business_registration_validation")
        or os.getenv("DATA_GO_KR_BUSINESS_VALIDATION", "")
    )
    if not mode:
        return None

    normalized = str(mode).strip().lower()
    if normalized in {"false", "0", "none", "off"}:
        return None
    if normalized in {"true", "1", "on"}:
        return "status"
    if normalized not in {"status", "authenticity"}:
        raise ValueError("businessRegistrationValidation must be 'status' or 'authenticity'")
    return normalized


def extract_business_fields(event: dict) -> dict:
    """검증에 쓰는 필드만 남긴다. 그 외 요청 값은 국세청 API로 넘기지 않는다."""
    business = event.get("business") if isinstance(event.get("business"), dict) else event
    return {
        key: business.get(key)
        for key in VERIFICATION_INPUT_FIELDS
        if business.get(key) is not None
    }
