"""S3에 올라온 사업자등록증을 OCR 처리해 파싱된 필드를 돌려준다.

진위 확인과 최종 승인 판정은 이 Lambda가 하지 않는다.
서버가 수행하며 규칙은 docs/server-verification-spec.md에 있다.

백엔드가 SDK로 직접 invoke한다. API Gateway proxy 봉투({statusCode, body})를 만들지 않고
결과 dict를 그대로 반환한다 - 이유는 events.py 참고.
"""

import logging
import os

from ocr_service.config import load_dotenv
from ocr_service.documents import (
    DocumentSource,
    infer_format,
    object_key_to_file_name,
    validate_document_size,
)
from ocr_service.events import (
    normalize_event,
    parse_event_template_ids,
    resolve_operation,
)
from ocr_service.ncloud_client import call_business_license_ocr, call_ocr
from ocr_service.redaction import redact_secrets
from ocr_service.responses.business_registration import build_business_registration_ocr_response
from ocr_service.services.business_registration import (
    has_missing_required_business_fields,
    parse_business_registration_with_fallback,
)
from ocr_service.storage.s3 import (
    assert_allowed_bucket,
    extract_s3_location,
    head_s3_object_size,
    read_s3_object,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


UNSUPPORTED_OPERATION_MESSAGE = (
    "operation must be 'ocr'. "
    "S3 event triggers are not supported because the OCR result has no caller to return to."
)


def handler(event, context):
    """성공하면 응답 계약 6개 필드를, 실패하면 {"error", "message"}를 돌려준다.

    <b>실패해도 예외를 던지지 않는다.</b> 백엔드는 OCR 실패를 업로드 실패로 취급하지 않고
    모든 필드를 null로 채워 사용자가 직접 입력하게 한다 (team-creation-api-spec.md 8절).
    즉 여기서의 실패는 사용자 흐름을 막지 않으므로, 호출자가 파싱하기 쉬운 형태로 돌려주고
    원인은 CloudWatch에 남긴다.
    """
    load_dotenv()
    event = normalize_event(event)

    try:
        if resolve_operation(event) != "ocr":
            raise ValueError(UNSUPPORTED_OPERATION_MESSAGE)
        return handle_business_registration_ocr(event)
    except Exception as exc:
        # 외부 API 예외 메시지에는 시크릿 키가 실린 요청 URL이 들어올 수 있다.
        # 응답과 로그 어느 쪽으로도 새어 나가지 않게 가린 뒤에만 내보낸다.
        message = redact_secrets(exc)
        logger.error("OCR failed: %s: %s", type(exc).__name__, message)
        return {"error": type(exc).__name__, "message": message}


lambda_handler = handler


def handle_business_registration_ocr(event: dict) -> dict:
    parsed = run_business_registration_ocr(event)
    log_parse_warnings(parsed)
    return build_business_registration_ocr_response(parsed)


def log_parse_warnings(parsed: dict) -> None:
    """파서 경고는 응답에 넣지 않는다 (계약은 6개 필드로 고정이다). 대신 CloudWatch에 남긴다.

    어떤 필드를 왜 못 읽었는지는 운영에서 OCR 품질을 볼 때 필요한데, 백엔드는 이 값을
    쓰지 않으므로 응답 계약을 늘릴 이유가 없다.
    """
    key = (parsed.get("source") or {}).get("key")
    for warning in parsed.get("warnings") or []:
        logger.warning("OCR parse warning (key=%s): %s", key, warning)


def load_s3_document(bucket: str, key: str) -> DocumentSource:
    """S3 객체를 디스크를 거치지 않고 메모리로 읽는다."""
    file_name = object_key_to_file_name(key)
    # 지원하지 않는 형식과 너무 큰 파일은 본문을 읽기 전에 걸러낸다.
    infer_format(file_name)
    validate_document_size(head_s3_object_size(bucket, key), file_name)
    return DocumentSource(name=file_name, content=read_s3_object(bucket, key))


def run_business_registration_ocr(event: dict) -> dict:
    bucket, key = extract_s3_location(event or {})
    assert_allowed_bucket(bucket)
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
