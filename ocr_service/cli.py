"""로컬 파일을 OCR 처리하고 필요한 출력 형식으로 보여주는 CLI이다."""

import argparse
import json
import os
import sys
from pathlib import Path

from ocr_service.config import configure_stdio, load_dotenv
from ocr_service.extractors.template import extract_template_fields, extract_text
from ocr_service.ncloud_client import call_ocr, validate_file_size
from ocr_service.responses.business_registration import build_business_registration_response
from ocr_service.services.business_registration import analyze_business_registration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call Ncloud CLOVA OCR Template OCR.")
    parser.add_argument("file", help="Path to an image or PDF file.")
    parser.add_argument("--lang", default=os.getenv("NCLOUD_OCR_LANG", "ko"), help="OCR language. Default: ko")
    parser.add_argument("--table", action="store_true", help="Enable table detection if the OCR domain supports it.")
    parser.add_argument(
        "--template-id",
        action="append",
        type=int,
        default=[],
        help="Template OCR template ID. Repeat this option to pass multiple IDs.",
    )
    parser.add_argument("--timeout", type=int, default=int(os.getenv("NCLOUD_OCR_TIMEOUT", "60")))
    parser.add_argument("--text-only", action="store_true", help="Print only extracted text.")
    parser.add_argument("--template-fields", action="store_true", help="Print Template OCR field names and values.")
    parser.add_argument(
        "--business-registration",
        action="store_true",
        help="Parse the OCR result as a Korean business registration certificate.",
    )
    parser.add_argument(
        "--business-registration-validation",
        choices=("status", "authenticity"),
        help=(
            "Validate parsed business registration fields with data.go.kr NTS API. "
            "'status' checks registration status by number. "
            "'authenticity' checks number, opening date, representative name, and optional parsed fields."
        ),
    )
    parser.add_argument("--output", help="Write the raw OCR JSON response to this path.")
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    load_dotenv()
    args = parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 2
    if not file_path.is_file():
        print(f"Not a file: {file_path}", file=sys.stderr)
        return 2
    validate_file_size(file_path)

    result = call_ocr(file_path, args.lang, args.table, args.template_id, args.timeout)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    text = extract_text(result)

    if args.business_registration or args.business_registration_validation:
        parsed = analyze_business_registration(result, args.business_registration_validation)
        print(json.dumps(build_business_registration_response(parsed), ensure_ascii=False, indent=2))
    elif args.template_fields:
        print(json.dumps(extract_template_fields(result), ensure_ascii=False, indent=2))
    elif args.text_only:
        print(text)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0
