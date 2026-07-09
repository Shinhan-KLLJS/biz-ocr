"""OCR 원문에서 흔히 발생하는 공백, 날짜, 괄호 흔들림을 정리한다."""

import re


def compact_label(label: str) -> str:
    return re.sub(r"\s+", "", label).strip()


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", "", label).strip()


def normalize_date(value: str) -> str | None:
    match = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", value)
    if not match:
        match = re.search(r"(\d{4})\D*(\d{1,2})\D*(\d{1,2})\s*일?", value)
    if not match:
        return None

    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def normalize_business_field_value(key: str, value: str) -> str:
    value = normalize_captured_value(value, preserve_spaces=(key == "businessAddress"))

    if key == "businessRegistrationNumber":
        match = re.search(r"\d{3}-\d{2}-\d{5}", value)
        return match.group(0) if match else value

    if key == "openingDate":
        return normalize_date(value) or value

    return value


def normalize_captured_value(value: str, preserve_spaces: bool = False) -> str:
    tokens = [line.strip() for line in value.splitlines() if line.strip()]
    normalized = " ".join(tokens).strip()
    normalized = re.sub(r"\s*,\s*", ",", normalized)
    normalized = re.sub(r"\s*\(\s*", "(", normalized)
    normalized = re.sub(r"\s*\)\s*", ")", normalized)
    normalized = re.sub(r"(\d)\s+명\b", r"\1명", normalized)
    if not preserve_spaces:
        normalized = re.sub(r"\s+", " ", normalized)
    return normalized
