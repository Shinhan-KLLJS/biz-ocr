"""General OCR처럼 라벨과 값이 흩어진 텍스트에서 필드를 찾는다."""

import re

from ocr_service.extractors.business_registration.constants import LABEL_ALIASES
from ocr_service.extractors.business_registration.normalization import (
    compact_label,
    normalize_business_field_value,
)


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None

    label, value = line.split(":", 1)
    key = LABEL_ALIASES.get(compact_label(label))
    if not key:
        return None
    return key, normalize_business_field_value(key, value.strip())


def extract_split_text_business_fields(text: str) -> dict:
    fields = {}
    patterns = {
        "businessRegistrationNumber": r"(?:사업자\s*)?등록번호\s*:\s*(\d{3}-\d{2}-\d{5})",
        "companyName": (
            r"(?:상\s*호|법\s*인\s*명\s*\(\s*단체명\s*\))\s*:\s*(.*?)"
            r"(?=\s*(?:대표\s*자|성\s*[명영]|개\s*업\s*연\s*월\s*일|법인등록번호|사업장))"
        ),
        "representativeName": (
            r"(?:대표\s*자|성\s*[명영])\s*:\s*(.*?)"
            r"(?=\s*(?:개\s*업\s*연\s*월\s*일|법인등록번호|사업장|생년월일))"
        ),
        "openingDate": (
            r"개\s*업\s*연\s*월\s*일\s*:\s*"
            r"(\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일)"
        ),
        "businessAddress": (
            r"사\s*업\s*장\s*(?:소\s*재\s*지|장소재지|주소)\s*:\s*(.*?)"
            r"(?=\s*(?:본\s*점|생년월일|사\s*업\s*의\s*종\s*류|종목|발\s*급))"
        ),
        "businessType": (
            r"사\s*업\s*의\s*종\s*류\s*:\s*업태\s*(.*?)"
            r"(?=\s*(?:종목|발\s*급|법\s*인\s*명|상\s*호|대표\s*자))"
        ),
        "businessItem": (
            r"(?:종\s*목|중\s*목)\s*:?\s*(.*?)"
            r"(?=\s*(?:발\s*급|사업자\s*단위|전자세금계산서|송\s*파\s*세\s*무\s*서|$))"
        ),
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            continue

        value = normalize_business_field_value(key, match.group(1))
        if key in {"businessType", "businessItem"} and is_noisy_business_kind(value):
            continue
        fields[key] = value

    return fields


def is_noisy_business_kind(value: str) -> bool:
    compacted = compact_label(value)
    # 업태/종목 구간에 다른 라벨이 섞이면 과감히 버리고 줄 기반 보정에 맡긴다.
    blocked_labels = ("법인명", "상호", "대표자", "개업연월일", "사업장소재지", "발급사유")
    return not value or ":" in value or any(label in compacted for label in blocked_labels)
