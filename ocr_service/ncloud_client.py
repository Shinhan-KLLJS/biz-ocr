"""Ncloud CLOVA OCR 호출과 요청 메시지 구성을 담당한다."""

import json
import logging
import os
import time
import uuid

import requests

from ocr_service.config import get_required_env
from ocr_service.documents import DocumentSource
from ocr_service.errors import ExternalServiceError
from ocr_service.redaction import redact_secrets


logger = logging.getLogger(__name__)


def parse_template_ids(raw_value: str) -> list[int]:
    if not raw_value.strip():
        return []

    template_ids = []
    for raw_id in raw_value.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        template_ids.append(int(raw_id))
    return template_ids


def build_message(document: DocumentSource, language: str, enable_table_detection: bool) -> dict:
    image = {
        "format": document.format,
        "name": document.stem,
    }
    template_ids = parse_template_ids(os.getenv("NCLOUD_OCR_TEMPLATE_IDS", ""))
    if template_ids:
        image["templateIds"] = template_ids

    message = {
        "version": os.getenv("NCLOUD_OCR_VERSION", "V2"),
        "requestId": str(uuid.uuid4()),
        "timestamp": int(round(time.time() * 1000)),
        "lang": language,
        "images": [image],
    }

    if enable_table_detection:
        message["enableTableDetection"] = True

    return message


def build_document_message(document: DocumentSource) -> dict:
    # Document OCR은 문서 유형별 엔진이므로 General OCR 전용 옵션을 보내지 않는다.
    return {
        "version": os.getenv("NCLOUD_OCR_VERSION", "V2"),
        "requestId": str(uuid.uuid4()),
        "timestamp": int(round(time.time() * 1000)),
        "images": [
            {
                "format": document.format,
                "name": document.stem,
            }
        ],
    }


def add_template_ids(message: dict, template_ids: list[int]) -> None:
    if not template_ids:
        return
    message["images"][0]["templateIds"] = template_ids


def post_multipart_ocr(
    api_url: str,
    secret_key: str,
    message: dict,
    document: DocumentSource,
    timeout: int,
) -> dict:
    try:
        response = requests.post(
            api_url,
            headers={"X-OCR-SECRET": secret_key},
            data={"message": json.dumps(message, ensure_ascii=False)},
            files={"file": (document.name, document.content)},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        # 원본 예외에는 요청 URL이 들어 있어 연쇄(chaining) 없이 새 예외만 올린다.
        raise ExternalServiceError(f"Ncloud OCR request failed: {redact_secrets(exc)}") from None

    if not response.ok:
        logger.error("Ncloud OCR responded %s: %s", response.status_code, redact_secrets(response.text))
        raise ExternalServiceError(f"Ncloud OCR responded with HTTP {response.status_code}")

    return response.json()


def call_ocr(
    document: DocumentSource,
    language: str,
    enable_table_detection: bool,
    template_ids: list[int],
    timeout: int,
) -> dict:
    api_url = get_required_env("NCLOUD_OCR_API_URL")
    secret_key = get_required_env("NCLOUD_OCR_SECRET_KEY")
    message = build_message(document, language, enable_table_detection)
    add_template_ids(message, template_ids)

    return post_multipart_ocr(api_url, secret_key, message, document, timeout)


def call_business_license_ocr(document: DocumentSource, timeout: int) -> dict:
    api_url = (
        os.getenv("NCLOUD_OCR_BIZ_LICENSE_API_URL")
        or os.getenv("NCLOUD_BIZ_OCR_API_URL")
        or get_required_env("NCLOUD_OCR_API_URL")
    )
    secret_key = os.getenv("NCLOUD_BIZ_OCR_SECRET_KEY") or get_required_env("NCLOUD_OCR_SECRET_KEY")
    return post_multipart_ocr(api_url, secret_key, build_document_message(document), document, timeout)
