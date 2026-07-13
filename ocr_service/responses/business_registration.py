"""OCR 파싱 결과를 백엔드가 의존하는 응답 계약으로 줄인다."""

import re


# 백엔드와 고정한 응답 계약 (backend/docs/team-creation-api-spec.md 8절).
# 왼쪽은 파서 내부 필드명, 오른쪽은 응답 필드명이다.
#
# 이 6개 키는 인식에 실패해도 null로 항상 존재한다. 백엔드가 키 유무를 확인하지 않고
# 값만 보면 되도록 하기 위해서다.
#
# 사업장주소는 넣지 않는다. DB에 저장하지도 진위확인에 쓰지도 않는 개인정보다.
PARSED_FIELD_TO_RESPONSE_FIELD = {
    "companyName": "companyName",
    "representativeName": "representativeName",
    "businessRegistrationNumber": "businessNumber",
    "openingDate": "businessOpeningDate",
    "businessType": "businessType",
    "businessItem": "businessItem",
}


def build_business_registration_ocr_response(parsed: dict) -> dict:
    """사용자가 화면에서 검토·수정할 추정값. 판정 결과는 넣지 않는다 (서버 몫이다)."""
    fields = parsed.get("fields") or {}
    return {
        response_key: normalize_response_field(response_key, fields.get(parsed_key))
        for parsed_key, response_key in PARSED_FIELD_TO_RESPONSE_FIELD.items()
    }


def normalize_response_field(key: str, value: object) -> object:
    if key == "businessNumber":
        return normalize_digits(value, 10)
    if key == "businessOpeningDate":
        return format_opening_date(value)
    # 빈 문자열은 "인식 실패"와 같은 뜻이므로 null로 통일한다.
    return value or None


def format_opening_date(value: object) -> str | None:
    """개업일을 yyyy-MM-dd로 맞춘다.

    OCR 원문은 '2024. 6. 24.', '2024년 6월 24일'처럼 제각각이라 숫자만 남겨 8자리인지 본다.
    8자리가 아니면 서버가 진위확인에 쓸 수 없으므로 null로 내려 사용자가 직접 입력하게 한다.
    """
    digits = normalize_digits(value, 8)
    if not digits:
        return None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def normalize_digits(value: object, expected_length: int) -> str | None:
    """구분자를 제거해 서버가 그대로 국세청에 보낼 수 있는 형태로 만든다."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == expected_length else None
