"""S3 입력 이벤트를 OCR 처리해 API Gateway 형식 응답으로 반환한다."""

import json
import os

from ocr_service.config import load_dotenv
from ocr_service.ncloud_client import call_ocr, parse_template_ids, validate_file_size
from ocr_service.responses.business_registration import build_business_registration_response
from ocr_service.services.business_registration import analyze_business_registration
from ocr_service.storage.s3 import download_s3_object, extract_s3_location


def make_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


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


def handler(event, context):
    load_dotenv()
    event = normalize_event(event)

    try:
        bucket, key = extract_s3_location(event or {})
        local_path = download_s3_object(bucket, key)
        validate_file_size(local_path)

        result = call_ocr(
            file_path=local_path,
            language=event.get("lang") or os.getenv("NCLOUD_OCR_LANG", "ko"),
            enable_table_detection=bool(event.get("table", False)),
            template_ids=parse_event_template_ids(event),
            timeout=int(event.get("timeout") or os.getenv("NCLOUD_OCR_TIMEOUT", "60")),
        )
        validation_mode = parse_business_validation_mode(event)
        parsed = analyze_business_registration(result, validation_mode)
        parsed["source"] = {"bucket": bucket, "key": key}
        return make_response(200, build_business_registration_response(parsed))
    except Exception as exc:
        return make_response(
            500,
            {
                "error": type(exc).__name__,
                "message": str(exc),
            },
        )


lambda_handler = handler
