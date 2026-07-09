"""업태와 종목처럼 OCR 줄 순서가 흔들리는 영역을 해석한다."""

from ocr_service.extractors.business_registration.normalization import (
    compact_label,
    normalize_captured_value,
    normalize_date,
)


def collect_business_items(lines: list[str]) -> list[str]:
    try:
        start = next(index for index, line in enumerate(lines) if compact_label(line) in {"종목", "중목"})
    except StopIteration:
        return []

    items = []
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if is_business_item_stop_at(lines, index):
            break
        if normalize_date(line):
            break
        # OCR이 마지막 글자만 다음 줄로 밀어내는 경우를 복원한다.
        if items and line in {"업", "스업"}:
            items[-1] = f"{items[-1]}{line}"
        else:
            items.append(line)

    return items


def is_business_item_stop_at(lines: list[str], index: int) -> bool:
    compacted_line = compact_label(lines[index])
    if not compacted_line:
        return False

    # "발", "급", "사유"처럼 끊긴 라벨도 잡기 위해 다음 몇 줄을 붙여서 본다.
    compacted_window = "".join(compact_label(line) for line in lines[index : index + 5])
    stop_phrases = (
        "발급사유",
        "사업자단위과세",
        "전자세금계산서",
        "공동사업자",
        "주류판매신고번호",
        "사업범위",
        "판매할주류의종류",
        "지정조건",
    )
    return any(compacted_window.startswith(phrase) for phrase in stop_phrases)


def collect_business_type_candidates_from_lines(lines: list[str], business_items: list[str]) -> list[str]:
    # 종목 라벨 바로 앞의 업태 후보가 가장 신뢰도가 높다.
    before_subject_candidates = collect_business_type_candidates_before_subject(lines)
    if before_subject_candidates:
        return before_subject_candidates
    return collect_leading_business_type_candidates(business_items)


def collect_business_item(lines: list[str], business_items: list[str]) -> str | None:
    normalized_items = [normalize_captured_value(item) for item in business_items]
    normalized_items = [item for item in normalized_items if item]
    if not normalized_items:
        return None

    if collect_business_type_candidates_before_subject(lines):
        return " ".join(normalized_items)

    item_start = 0
    while item_start < len(normalized_items) and is_business_type_candidate(normalized_items[item_start]):
        item_start += 1

    business_item_values = normalized_items[item_start:] or normalized_items
    return " ".join(business_item_values)


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


def is_business_type_candidate(value: str) -> bool:
    if not value.endswith("업"):
        return False
    if len(value) < 2:
        return False
    if len(value.split()) > 1:
        return False
    return True
