"""업태와 종목 텍스트로 광고 관련 업종 여부를 분류한다."""

from ocr_service.extractors.business_registration.constants import (
    HIGH_CONFIDENCE_ADVERTISING_KEYWORDS,
    MEDIUM_CONFIDENCE_ADVERTISING_KEYWORDS,
)
from ocr_service.extractors.business_registration.normalization import compact_label


def classify_advertising_business(fields: dict) -> dict:
    source_fields = {
        key: fields.get(key)
        for key in ("businessType", "businessItem")
        if fields.get(key)
    }
    missing_fields = [
        key
        for key in ("businessType", "businessItem")
        if not fields.get(key)
    ]
    source_text = " ".join(source_fields.values())
    normalized_source = compact_label(source_text).lower()

    high_matches = match_keywords(normalized_source, HIGH_CONFIDENCE_ADVERTISING_KEYWORDS)
    medium_matches = match_keywords(normalized_source, MEDIUM_CONFIDENCE_ADVERTISING_KEYWORDS)
    matched_keywords = high_matches + [keyword for keyword in medium_matches if keyword not in high_matches]

    if high_matches:
        confidence = "high"
        classification_status = "matched"
        review_required = False
        reason = "matched high-confidence advertising keywords"
    elif medium_matches:
        confidence = "medium"
        classification_status = "matched"
        review_required = True
        reason = "matched broad advertising-related keywords"
    elif missing_fields:
        confidence = "unknown"
        classification_status = "unknown"
        review_required = True
        reason = f"missing required classification fields: {', '.join(missing_fields)}"
    else:
        confidence = "none"
        classification_status = "not_matched"
        review_required = False
        reason = "no advertising keywords matched in businessType or businessItem"

    return {
        "isAdvertisingRelated": bool(matched_keywords),
        "classificationStatus": classification_status,
        "confidence": confidence,
        "matchedKeywords": matched_keywords,
        "sourceFields": source_fields,
        "missingFields": missing_fields,
        "reviewRequired": review_required,
        "reason": reason,
    }


def match_keywords(normalized_source: str, keywords: tuple[str, ...]) -> list[str]:
    matches = []
    for keyword in keywords:
        normalized_keyword = compact_label(keyword).lower()
        if normalized_keyword in normalized_source and keyword not in matches:
            matches.append(keyword)
    return matches
