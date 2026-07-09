"""data 파일 목록과 저장된 OCR output으로 OCR/Verification API 계약을 점검한다."""

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ocr_service.config import load_dotenv
from ocr_service.responses.business_registration import (
    build_business_registration_ocr_response,
    build_business_registration_verification_response,
)
from ocr_service.services.business_registration import (
    parse_business_registration_with_fallback,
    verify_business_registration_submission,
)


DATA_DIR = ROOT_DIR / "data"
RAW_OUTPUT_DIR = ROOT_DIR / "outputs" / "document_raw"
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".pdf", ".tif", ".tiff"}


def main() -> None:
    load_dotenv()

    for source_path in sorted(DATA_DIR.iterdir()):
        if source_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        raw_path = RAW_OUTPUT_DIR / f"{source_path.stem}.json"
        if not raw_path.exists():
            print_result(source_path.name, "SKIP", f"raw output 없음: {raw_path}")
            continue

        try:
            raw = read_json(raw_path)
            ocr_body = build_ocr_response(raw)
            verification_request = build_verification_request(ocr_body)
            verification_body = try_build_verification_response(verification_request)

            print_case(source_path, raw_path, ocr_body, verification_request, verification_body)
        except Exception as exc:
            print_result(source_path.name, "FAIL", sanitize_error(exc))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_ocr_response(raw: dict) -> dict:
    parsed = parse_business_registration_with_fallback(raw)
    return build_business_registration_ocr_response(parsed)


def build_verification_request(ocr_body: dict) -> dict:
    business = ocr_body.get("business", {})
    return {
        "business": {
            "businessRegistrationNumber": business.get("businessRegistrationNumber"),
            "representativeName": business.get("representativeName"),
            "openingDate": business.get("openingDate"),
            "businessType": business.get("businessType"),
            "businessItem": business.get("businessItem"),
        },
        "businessRegistrationValidation": "authenticity",
    }


def build_verification_response(request_body: dict) -> dict:
    parsed = verify_business_registration_submission(request_body["business"])
    return build_business_registration_verification_response(parsed)


def try_build_verification_response(request_body: dict) -> dict:
    try:
        return build_verification_response(request_body)
    except Exception as exc:
        return {
            "status": "verification_call_failed",
            "error": sanitize_error(exc),
        }


def sanitize_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    return re.sub(r"serviceKey=[^&\s)]+", "serviceKey=***", message)


def print_case(
    source_path: Path,
    raw_path: Path,
    ocr_body: dict,
    verification_request: dict,
    verification_body: dict,
) -> None:
    print("=" * 80)
    print(f"DATA_FILE: {source_path}")
    print(f"RAW_OUTPUT: {raw_path}")
    print("OCR_RESPONSE")
    print(json.dumps(ocr_body, ensure_ascii=False, indent=2))
    print("VERIFICATION_REQUEST")
    print(json.dumps(verification_request, ensure_ascii=False, indent=2))
    print("VERIFICATION_RESPONSE")
    print(json.dumps(verification_body, ensure_ascii=False, indent=2))


def print_result(file_name: str, status: str, message: str) -> None:
    print("=" * 80)
    print(f"{status}: {file_name}")
    print(message)


if __name__ == "__main__":
    main()
