import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests

from ocr_service.config import get_required_env


SUPPORTED_FORMATS = {
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".png": "png",
    ".pdf": "pdf",
    ".tif": "tiff",
    ".tiff": "tiff",
}


def infer_format(file_path: Path) -> str:
    try:
        return SUPPORTED_FORMATS[file_path.suffix.lower()]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise ValueError(f"Unsupported file format: {file_path.suffix}. Supported: {supported}") from exc


def validate_file_size(file_path: Path) -> None:
    max_bytes = int(os.getenv("NCLOUD_OCR_MAX_FILE_BYTES", str(50 * 1024 * 1024)))
    if file_path.stat().st_size > max_bytes:
        raise ValueError(f"File is too large for OCR request: {file_path} > {max_bytes} bytes")


def parse_template_ids(raw_value: str) -> list[int]:
    if not raw_value.strip():
        return []

    template_ids = []
    for raw_id in raw_value.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        template_ids.append(int(raw_id))
    return template_ids


def build_message(file_path: Path, language: str, enable_table_detection: bool) -> dict:
    image = {
        "format": infer_format(file_path),
        "name": file_path.stem or "document",
    }
    template_ids = parse_template_ids(os.getenv("NCLOUD_OCR_TEMPLATE_IDS", ""))
    if template_ids:
        image["templateIds"] = template_ids

    message = {
        "version": os.getenv("NCLOUD_OCR_VERSION", "V2"),
        "requestId": str(uuid.uuid4()),
        "timestamp": int(round(time.time() * 1000)),
        "lang": language,
        "images": [image],
    }

    if enable_table_detection:
        message["enableTableDetection"] = True

    return message


def add_template_ids(message: dict, template_ids: list[int]) -> None:
    if not template_ids:
        return
    message["images"][0]["templateIds"] = template_ids


def call_ocr(
    file_path: Path,
    language: str,
    enable_table_detection: bool,
    template_ids: list[int],
    timeout: int,
) -> dict:
    api_url = get_required_env("NCLOUD_OCR_API_URL")
    secret_key = get_required_env("NCLOUD_OCR_SECRET_KEY")
    message = build_message(file_path, language, enable_table_detection)
    add_template_ids(message, template_ids)

    with file_path.open("rb") as image_file:
        response = requests.post(
            api_url,
            headers={"X-OCR-SECRET": secret_key},
            data={"message": json.dumps(message, ensure_ascii=False)},
            files={"file": (file_path.name, image_file)},
            timeout=timeout,
        )

    if not response.ok:
        print(response.text, file=sys.stderr)
        response.raise_for_status()

    return response.json()
