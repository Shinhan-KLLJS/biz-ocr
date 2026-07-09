"""Ncloud Template OCR이 준 명명 필드를 사업자등록증 필드로 변환한다."""

from ocr_service.extractors.business_registration.constants import LABEL_ALIASES, REQUIRED_BUSINESS_FIELDS
from ocr_service.extractors.business_registration.normalization import (
    normalize_business_field_value,
    normalize_label,
)
from ocr_service.extractors.template import get_field_text


def extract_template_business_fields(result: dict) -> dict:
    fields = {}
    for image in result.get("images", []):
        for field in image.get("fields", []):
            raw_name = field.get("name") or field.get("fieldName")
            text = get_field_text(field)
            if not raw_name or text is None:
                continue

            key = LABEL_ALIASES.get(normalize_label(raw_name))
            if key in REQUIRED_BUSINESS_FIELDS:
                fields[key] = normalize_business_field_value(key, text)

    return fields
