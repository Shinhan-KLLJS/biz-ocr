"""저장된 raw OCR output으로 OCR API 응답 계약을 점검한다.

Ncloud를 다시 호출하지 않고 outputs/document_raw/*.json만으로 파싱 결과를 확인한다.
진위 확인과 최종 판정은 서버가 하므로 이 스크립트는 OCR 응답까지만 만든다.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ocr_service.config import load_dotenv
from ocr_service.redaction import redact_secrets
from ocr_service.responses.business_registration import build_business_registration_ocr_response
from ocr_service.services.business_registration import parse_business_registration_with_fallback


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
            ocr_body = build_ocr_response(read_json(raw_path))
            print_case(source_path, raw_path, ocr_body)
        except Exception as exc:
            print_result(source_path.name, "FAIL", redact_secrets(f"{type(exc).__name__}: {exc}"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_ocr_response(raw: dict) -> dict:
    parsed = parse_business_registration_with_fallback(raw)
    return build_business_registration_ocr_response(parsed)


def print_case(source_path: Path, raw_path: Path, ocr_body: dict) -> None:
    print("=" * 80)
    print(f"DATA_FILE: {source_path}")
    print(f"RAW_OUTPUT: {raw_path}")
    print("OCR_RESPONSE")
    print(json.dumps(ocr_body, ensure_ascii=False, indent=2))


def print_result(file_name: str, status: str, message: str) -> None:
    print("=" * 80)
    print(f"{status}: {file_name}")
    print(message)


if __name__ == "__main__":
    main()
