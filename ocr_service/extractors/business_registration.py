import re

from ocr_service.extractors.template import extract_text, get_field_text


REQUIRED_BUSINESS_FIELDS = {
    "businessRegistrationNumber": "사업자등록번호",
    "companyName": "상호(단체명 등)",
    "representativeName": "대표자명",
    "openingDate": "개업연월일",
    "businessAddress": "사업장주소",
    "businessType": "업태",
}


LABEL_ALIASES = {
    "등록번호": "businessRegistrationNumber",
    "사업자등록번호": "businessRegistrationNumber",
    "상호": "companyName",
    "상호(단체명등)": "companyName",
    "상호(단체명)": "companyName",
    "법인명": "companyName",
    "법인명(단체명)": "companyName",
    "대표자": "representativeName",
    "대표자명": "representativeName",
    "개업연월일": "openingDate",
    "개업일": "openingDate",
    "법인등록번호": "corporateRegistrationNumber",
    "사업장주소": "businessAddress",
    "사업장소재지": "businessAddress",
    "본점소재지": "headOfficeAddress",
    "업태": "businessType",
}


def compact_label(label: str) -> str:
    return re.sub(r"\s+", "", label).strip()


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", "", label).strip()


def normalize_date(value: str) -> str | None:
    match = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", value)
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


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None

    label, value = line.split(":", 1)
    normalized_label = compact_label(label)
    return normalized_label, value.strip()


def parse_business_registration_text(text: str) -> dict:
    fields = {}
    warnings = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        parsed = parse_key_value_line(line)
        if not parsed:
            continue

        label, value = parsed
        key = LABEL_ALIASES.get(label)
        if not key:
            continue

        if key == "businessType" and normalize_label(value) == "업태":
            continue

        fields[key] = normalize_business_field_value(key, value)

    fields.update(extract_split_text_business_fields(text))

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

    all_dates = [normalized for normalized in (normalize_date(line) for line in lines) if normalized]
    if all_dates:
        fields["issueDate"] = all_dates[-1]

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

    business_items = collect_business_items(lines)
    if business_items:
        fields["businessItemsRaw"] = business_items
        if "businessType" not in fields:
            business_type_candidates = collect_business_type_candidates_from_lines(lines, business_items)
            if business_type_candidates:
                fields["businessTypeCandidates"] = business_type_candidates
                fields["businessType"] = " ".join(business_type_candidates)
        warnings.append("businessItemsRaw may need review because OCR line order is often unstable in this section")

    required_fields = select_required_business_fields(fields)
    missing = [key for key in REQUIRED_BUSINESS_FIELDS if not required_fields.get(key)]
    if missing:
        warnings.append(f"missing required fields: {', '.join(missing)}")

    return {
        "documentType": "businessRegistrationCertificate",
        "fields": required_fields,
        "rawText": text,
        "warnings": warnings,
    }


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
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            continue

        value = normalize_business_field_value(key, match.group(1))
        if key == "businessType":
            compacted = compact_label(value)
            if (
                not value
                or ":" in value
                or any(label in compacted for label in ("법인명", "상호", "대표자", "개업연월일", "사업장소재지"))
            ):
                continue
        fields[key] = value

    return select_required_business_fields(fields)


def parse_business_registration_result(result: dict) -> dict:
    text = extract_text(result)
    parsed = parse_business_registration_text(text)
    fields = {
        **parsed["fields"],
        **extract_template_business_fields(result),
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
        "rawText": text,
        "warnings": warnings,
    }


def select_required_business_fields(fields: dict) -> dict:
    selected = {
        key: fields.get(key)
        for key in REQUIRED_BUSINESS_FIELDS
        if fields.get(key) not in (None, "")
    }
    if fields.get("businessTypeCandidates"):
        selected["businessTypeCandidates"] = fields["businessTypeCandidates"]
    return selected


def collect_business_items(lines: list[str]) -> list[str]:
    try:
        start = next(index for index, line in enumerate(lines) if compact_label(line) in {"종목", "중목"})
    except StopIteration:
        return []

    stop_markers = ("발 급 사유", "발급사유", "사업자 단위 과세", "전자세금계산서")
    items = []
    for line in lines[start + 1:]:
        if any(marker in line for marker in stop_markers):
            break
        if normalize_date(line):
            break
        if items and line in {"업", "스업"}:
            items[-1] = f"{items[-1]}{line}"
        else:
            items.append(line)

    return items


def collect_business_type_candidates_from_lines(lines: list[str], business_items: list[str]) -> list[str]:
    before_subject_candidates = collect_business_type_candidates_before_subject(lines)
    if before_subject_candidates:
        return before_subject_candidates
    return collect_leading_business_type_candidates(business_items)


def collect_business_type_candidates_before_subject(lines: list[str]) -> list[str]:
    candidates = []
    subject_indexes = [
        index
        for index, line in enumerate(lines)
        if compact_label(line) in {"종목", "중목"}
    ]
    for subject_index in subject_indexes:
        current = []
        cursor = subject_index - 1
        while cursor >= 0 and is_business_type_candidate(normalize_captured_value(lines[cursor])):
            current.insert(0, normalize_captured_value(lines[cursor]))
            cursor -= 1
        if current:
            for candidate in current:
                if candidate not in candidates:
                    candidates.append(candidate)
            break

    return candidates


def collect_leading_business_type_candidates(items: list[str]) -> list[str]:
    leading = []
    for item in items:
        normalized = normalize_captured_value(item)
        if is_business_type_candidate(normalized):
            if normalized not in leading:
                leading.append(normalized)
            continue
        break

    return leading


def collect_business_type_candidates(items: list[str]) -> list[str]:
    candidates = []
    for item in items:
        normalized = normalize_captured_value(item)
        if not normalized:
            continue

        if is_business_type_candidate(normalized) and normalized not in candidates:
            candidates.append(normalized)

    return candidates[:5]


def is_business_type_candidate(value: str) -> bool:
    if not value.endswith("업"):
        return False
    if len(value) < 2:
        return False
    if len(value.split()) > 1:
        return False
    return True
