"""로컬 파일을 OCR 처리하고 필요한 출력 형식으로 보여주는 CLI이다."""

import argparse
import json
import os
import sys
from pathlib import Path

from ocr_service.config import configure_stdio, load_dotenv
from ocr_service.documents import DocumentSource, validate_document_size
from ocr_service.extractors.template import extract_template_fields, extract_text
from ocr_service.ncloud_client import call_business_license_ocr, call_ocr
from ocr_service.responses.business_registration import build_business_registration_ocr_response
from ocr_service.services.business_registration import (
    has_missing_required_business_fields,
    parse_business_registration_with_fallback,
)


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
    parser.add_argument("--output", help="Write the raw OCR JSON response to this path.")
    parser.add_argument("--parsed-output", help="Write the parsed business registration JSON to this path.")
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
    validate_document_size(file_path.stat().st_size, file_path.name)
    document = DocumentSource.from_path(file_path)

    if args.business_registration:
        result = call_business_license_ocr(document, args.timeout)
    else:
        result = call_ocr(document, args.lang, args.table, args.template_id, args.timeout)

    if args.output:
        write_json_file(Path(args.output), result)

    text = extract_text(result)

    if args.business_registration:
        fallback_result = load_business_registration_fallback(document, args, result)
        parsed = parse_business_registration_with_fallback(result, fallback_result)
        if args.parsed_output:
            write_json_file(Path(args.parsed_output), parsed)
        print(json.dumps(build_business_registration_ocr_response(parsed), ensure_ascii=False, indent=2))
    elif args.template_fields:
        print(json.dumps(extract_template_fields(result), ensure_ascii=False, indent=2))
    elif args.text_only:
        print(text)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


def write_json_file(output_path: Path, payload: dict) -> None:
    # raw와 parsed 저장 모두 같은 인코딩/디렉터리 생성 규칙을 사용한다.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_business_registration_fallback(
    document: DocumentSource,
    args: argparse.Namespace,
    result: dict,
) -> dict | None:
    parsed = parse_business_registration_with_fallback(result)
    if not has_missing_required_business_fields(parsed):
        return None

    # Document OCR 필드가 부족할 때만 기존 General/Template OCR 파서를 보조로 사용한다.
    return call_ocr(document, args.lang, args.table, args.template_id, args.timeout)
