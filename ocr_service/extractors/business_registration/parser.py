"""사업자등록증 OCR 결과를 최종 응답 구조로 조립한다."""

import re

from ocr_service.extractors.business_registration.business_items import (
    collect_business_item,
    collect_business_items,
    collect_business_type_candidates_from_lines,
)
from ocr_service.extractors.business_registration.classification import classify_advertising_business
from ocr_service.extractors.business_registration.constants import REQUIRED_BUSINESS_FIELDS
from ocr_service.extractors.business_registration.document_fields import extract_document_business_fields
from ocr_service.extractors.business_registration.normalization import compact_label, normalize_date
from ocr_service.extractors.business_registration.template_fields import extract_template_business_fields
from ocr_service.extractors.business_registration.text_fields import (
    extract_split_text_business_fields,
    parse_key_value_line,
)
from ocr_service.extractors.template import extract_text


def parse_business_registration_text(text: str) -> dict:
    fields = {}
    warnings = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 먼저 명시적인 "라벨: 값" 형태를 읽고, 깨진 줄 기반 보정은 뒤에서 덮어쓴다.
    for line in lines:
        parsed = parse_key_value_line(line)
        if not parsed:
            continue

        key, value = parsed
        if key == "businessType" and compact_label(value) == "업태":
            continue
        fields[key] = value

    fields.update(extract_split_text_business_fields(text))
    warnings.extend(validate_number_fields(fields))
    add_document_metadata(fields, lines)
    add_business_item_fields(fields, lines, warnings)

    # 외부 응답에는 승인 판단에 필요한 필드와 검토용 후보만 노출한다.
    required_fields = select_required_business_fields(fields)
    missing = [key for key in REQUIRED_BUSINESS_FIELDS if not required_fields.get(key)]
    if missing:
        warnings.append(f"missing required fields: {', '.join(missing)}")

    return {
        "documentType": "businessRegistrationCertificate",
        "fields": required_fields,
        "advertisingClassification": classify_advertising_business(required_fields),
        "rawText": text,
        "warnings": warnings,
    }


def parse_business_registration_result(result: dict) -> dict:
    text = extract_text(result)
    parsed = parse_business_registration_text(text)
    # Template OCR 명명 필드는 사용자가 직접 정의한 값이므로 일반 텍스트 추출보다 우선한다.
    # Document OCR 특화 필드는 가장 구조화된 응답이므로 최종 우선순위로 병합한다.
    fields = {
        **parsed["fields"],
        **extract_template_business_fields(result),
        **extract_document_business_fields(result),
    }

    fields = select_required_business_fields(fields)
    missing = [key for key in REQUIRED_BUSINESS_FIELDS if not fields.get(key)]
    warnings = [
        warning for warning in parsed["warnings"] if not warning.startswith("missing required fields:")
    ]
    if missing:
        warnings.append(f"missing required fields: {', '.join(missing)}")

    return {
        "documentType": "businessRegistrationCertificate",
        "fields": fields,
        "fieldLabels": REQUIRED_BUSINESS_FIELDS,
        "advertisingClassification": classify_advertising_business(fields),
        "rawText": text,
        "warnings": warnings,
    }


def validate_number_fields(fields: dict) -> list[str]:
    warnings = []
    registration_number = fields.get("businessRegistrationNumber")
    if registration_number:
        match = re.search(r"\d{3}-\d{2}-\d{5}", registration_number)
        if match:
            fields["businessRegistrationNumber"] = match.group(0)
        else:
            warnings.append("businessRegistrationNumber format was not recognized")

    corporate_number = fields.get("corporateRegistrationNumber")
    if corporate_number:
        match = re.search(r"\d{6}-\d{7}", corporate_number)
        if match:
            fields["corporateRegistrationNumber"] = match.group(0)
        else:
            warnings.append("corporateRegistrationNumber format was not recognized")
    return warnings


def add_document_metadata(fields: dict, lines: list[str]) -> None:
    all_dates = [normalized for normalized in (normalize_date(line) for line in lines) if normalized]
    if all_dates:
        fields["issueDate"] = all_dates[-1]

    # 세무서명은 필수 승인 필드는 아니지만 원문 검토에 도움이 되는 부가 정보다.
    for line in lines:
        if "세" in line and "무" in line and "서" in line and line.endswith("장"):
            fields["taxOfficeRaw"] = line
            fields["taxOffice"] = re.sub(r"\s+", "", line).removesuffix("장")
            break

    for line in lines:
        if "사업자 단위 과세 적용사업자 여부" in line:
            compacted = compact_label(line).lower()
            if "부(v)" in compacted:
                fields["isBusinessUnitTaxpayer"] = False
            elif "여(v)" in compacted:
                fields["isBusinessUnitTaxpayer"] = True
            break


def add_business_item_fields(fields: dict, lines: list[str], warnings: list[str]) -> None:
    business_items = collect_business_items(lines)
    if not business_items:
        return

    # 종목 영역은 OCR 줄 순서가 자주 흔들려 원문 후보도 함께 보존한다.
    fields["businessItemsRaw"] = business_items
    business_item = collect_business_item(lines, business_items)
    if business_item:
        fields["businessItem"] = business_item
    if "businessType" not in fields:
        business_type_candidates = collect_business_type_candidates_from_lines(lines, business_items)
        if business_type_candidates:
            fields["businessTypeCandidates"] = business_type_candidates
            fields["businessType"] = " ".join(business_type_candidates)
    warnings.append("businessItemsRaw may need review because OCR line order is often unstable in this section")


def select_required_business_fields(fields: dict) -> dict:
    selected = {
        key: fields.get(key)
        for key in REQUIRED_BUSINESS_FIELDS
        if fields.get(key) not in (None, "")
    }
    if fields.get("businessTypeCandidates"):
        selected["businessTypeCandidates"] = fields["businessTypeCandidates"]
    if fields.get("businessItemsRaw"):
        selected["businessItemsRaw"] = fields["businessItemsRaw"]
    return selected
