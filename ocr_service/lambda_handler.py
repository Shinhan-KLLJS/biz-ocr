"""S3에 올라온 사업자등록증을 OCR 처리하거나, 확정된 값을 검증해 응답한다."""

import os

from ocr_service.config import load_dotenv
from ocr_service.documents import (
    DocumentSource,
    infer_format,
    object_key_to_file_name,
    validate_document_size,
)
from ocr_service.events import (
    extract_business_fields,
    make_response,
    normalize_event,
    parse_business_validation_mode,
    parse_event_template_ids,
    resolve_operation,
)
from ocr_service.ncloud_client import call_business_license_ocr, call_ocr
from ocr_service.redaction import redact_secrets
from ocr_service.responses.business_registration import (
    build_business_registration_ocr_response,
    build_business_registration_verification_response,
)
from ocr_service.services.business_registration import (
    has_missing_required_business_fields,
    parse_business_registration_with_fallback,
    verify_business_registration_submission,
)
from ocr_service.storage.s3 import extract_s3_location, head_s3_object_size, read_s3_object


UNSUPPORTED_OPERATION_MESSAGE = (
    "operation must be 'ocr' or 'verification'. "
    "S3 event triggers are not supported because the OCR result has no caller to return to."
)


def handler(event, context):
    load_dotenv()
    event = normalize_event(event)

    try:
        operation = resolve_operation(event)
        if operation == "verification":
            return handle_business_registration_verification(event)
        if operation == "ocr":
            return handle_business_registration_ocr(event)
        # S3 업로드 이벤트에는 operation도 경로도 없어 여기로 온다.
        return make_response(400, {"error": "UnsupportedOperation", "message": UNSUPPORTED_OPERATION_MESSAGE})
    except Exception as exc:
        # 외부 API 예외 메시지에는 서비스 키가 실린 요청 URL이 들어올 수 있다.
        return make_response(500, {"error": type(exc).__name__, "message": redact_secrets(exc)})


lambda_handler = handler


def handle_business_registration_ocr(event: dict) -> dict:
    parsed = run_business_registration_ocr(event)
    return make_response(200, build_business_registration_ocr_response(parsed))


def handle_business_registration_verification(event: dict) -> dict:
    fields = extract_business_fields(event)
    validation_mode = parse_business_validation_mode(event) or "authenticity"
    parsed = verify_business_registration_submission(fields, validation_mode)
    return make_response(200, build_business_registration_verification_response(parsed))


def load_s3_document(bucket: str, key: str) -> DocumentSource:
    """S3 객체를 디스크를 거치지 않고 메모리로 읽는다."""
    file_name = object_key_to_file_name(key)
    # 지원하지 않는 형식과 너무 큰 파일은 본문을 읽기 전에 걸러낸다.
    infer_format(file_name)
    validate_document_size(head_s3_object_size(bucket, key), file_name)
    return DocumentSource(name=file_name, content=read_s3_object(bucket, key))


def run_business_registration_ocr(event: dict) -> dict:
    bucket, key = extract_s3_location(event or {})
    document = load_s3_document(bucket, key)

    language = event.get("lang") or os.getenv("NCLOUD_OCR_LANG", "ko")
    timeout = int(event.get("timeout") or os.getenv("NCLOUD_OCR_TIMEOUT", "60"))
    table = bool(event.get("table", False))
    template_ids = parse_event_template_ids(event)

    result = call_business_license_ocr(document, timeout)
    fallback_result = load_business_registration_fallback(
        document,
        language,
        table,
        template_ids,
        timeout,
        result,
    )
    parsed = parse_business_registration_with_fallback(result, fallback_result)
    parsed["source"] = {"bucket": bucket, "key": key}
    return parsed


def load_business_registration_fallback(
    document: DocumentSource,
    language: str,
    table: bool,
    template_ids: list[int],
    timeout: int,
    result: dict,
) -> dict | None:
    parsed = parse_business_registration_with_fallback(result)
    if not has_missing_required_business_fields(parsed):
        return None

    # Document OCR이 충분하지 않은 경우에만 기존 OCR 도메인을 한 번 더 호출한다.
    return call_ocr(document, language, table, template_ids, timeout)
