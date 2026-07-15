"""Lambda 배포 전 환경과 ZIP 산출물을 점검한다."""

import os
import zipfile
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_PACKAGE_ENTRIES = (
    "main.py",
    "ocr_service/lambda_handler.py",
    "requests/__init__.py",
    "boto3/__init__.py",
)


def validate_lambda_package(package_path: Path) -> list[str]:
    """Lambda가 풀 수 있는 ZIP인지 최소 구성과 Windows 바이너리 유입을 검사한다."""
    if not package_path.is_file():
        return [f"배포 ZIP이 없습니다: {package_path}"]

    try:
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return [f"유효한 ZIP 파일이 아닙니다: {package_path}"]

    errors = [f"ZIP 필수 파일 누락: {name}" for name in REQUIRED_PACKAGE_ENTRIES if name not in names]
    windows_native = [name for name in names if name.lower().endswith((".pyd", ".dll"))]
    if windows_native:
        errors.append(f"Windows 네이티브 바이너리가 포함되었습니다: {windows_native[0]}")
    return errors


def validate_lambda_environment(
    environment: dict[str, str] | None = None,
    production: bool = False,
) -> list[str]:
    """시크릿 값은 출력하지 않고 Lambda 실행에 필요한 설정만 확인한다."""
    environment = environment or os.environ
    errors: list[str] = []
    endpoint = first_value(
        environment,
        "NCLOUD_OCR_BIZ_LICENSE_API_URL",
        "NCLOUD_BIZ_OCR_API_URL",
        "NCLOUD_OCR_API_URL",
    )
    if not endpoint:
        errors.append("OCR API URL이 없습니다.")
    elif not is_https_url(endpoint):
        errors.append("OCR API URL은 https URL이어야 합니다.")

    if not first_value(environment, "NCLOUD_BIZ_OCR_SECRET_KEY", "NCLOUD_OCR_SECRET_KEY"):
        errors.append("OCR Secret Key가 없습니다.")
    if production and not environment.get("OCR_INPUT_BUCKET"):
        errors.append("운영 배포에는 OCR_INPUT_BUCKET이 필요합니다.")

    for name in ("NCLOUD_OCR_TIMEOUT", "NCLOUD_OCR_MAX_FILE_BYTES"):
        value = environment.get(name)
        if value and not is_positive_integer(value):
            errors.append(f"{name}은 0보다 큰 정수여야 합니다.")
    return errors


def first_value(environment: dict[str, str], *names: str) -> str | None:
    return next((environment[name] for name in names if environment.get(name)), None)


def is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def is_positive_integer(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False
