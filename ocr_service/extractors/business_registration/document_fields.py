"""Ncloud Document OCR 사업자등록증 응답을 내부 필드로 변환한다."""

from ocr_service.extractors.business_registration.normalization import normalize_business_field_value


DOCUMENT_FIELD_MAPPINGS = (
    ("registerNumber", "businessRegistrationNumber"),
    ("companyName", "companyName"),
    ("corpName", "companyName"),
    ("repName", "representativeName"),
    ("openDate", "openingDate"),
    ("bisAddress", "businessAddress"),
    ("headAddress", "businessAddress"),
    ("bisType", "businessType"),
    ("bisItem", "businessItem"),
)


def extract_document_business_fields(result: dict) -> dict:
    fields = {}
    for image in result.get("images", []):
        document_result = image.get("bizLicense", {}).get("result", {})
        if not isinstance(document_result, dict):
            continue

        # 공식 Document OCR 필드는 배열로 오므로 텍스트만 모아 내부 표준 필드로 맞춘다.
        for source_key, target_key in DOCUMENT_FIELD_MAPPINGS:
            if target_key in fields:
                continue
            text = collect_document_text(document_result.get(source_key))
            if text:
                fields[target_key] = normalize_business_field_value(target_key, text)
    return fields


def collect_document_text(items) -> str | None:
    if not isinstance(items, list):
        return None

    texts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = get_document_item_text(item)
        if text:
            texts.append(text)
    return " ".join(texts).strip() or None


def get_document_item_text(item: dict) -> str | None:
    formatted = item.get("formatted")
    if isinstance(formatted, dict) and formatted.get("value"):
        return str(formatted["value"]).strip()
    text = item.get("text")
    return str(text).strip() if text else None
