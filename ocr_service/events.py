"""Lambda 이벤트를 해석해 동작을 고르고, API Gateway 형식 응답을 만든다."""

import json

from ocr_service.ncloud_client import parse_template_ids


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
    """이 Lambda는 OCR만 수행한다. 그 외 입력은 모두 unsupported로 돌린다."""
    operation = event.get("operation") or event.get("action")
    if operation:
        return normalize_operation(operation)

    path = extract_request_path(event)
    if path.endswith("/ocr") or path.endswith("/ocr/"):
        return "ocr"
    return "unsupported"


def normalize_operation(operation: object) -> str:
    value = str(operation).strip().lower()
    if value in {"ocr", "extract", "parse"}:
        return "ocr"
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
