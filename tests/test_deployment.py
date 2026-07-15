"""Lambda 배포 사전검사 규칙을 검증한다."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from ocr_service.deployment import validate_lambda_environment, validate_lambda_package


class DeploymentEnvironmentTests(unittest.TestCase):
    def test_accepts_the_minimum_production_configuration(self):
        environment = {
            "NCLOUD_OCR_BIZ_LICENSE_API_URL": "https://ocr.example.com/biz-license",
            "NCLOUD_OCR_SECRET_KEY": "secret",
            "OCR_INPUT_BUCKET": "loovi-ocr-input",
            "NCLOUD_OCR_TIMEOUT": "60",
            "NCLOUD_OCR_MAX_FILE_BYTES": "52428800",
        }

        self.assertEqual(validate_lambda_environment(environment, production=True), [])

    def test_rejects_missing_secret_invalid_url_and_invalid_number(self):
        environment = {
            "NCLOUD_OCR_BIZ_LICENSE_API_URL": "http://ocr.example.com/biz-license",
            "NCLOUD_OCR_TIMEOUT": "zero",
        }

        errors = validate_lambda_environment(environment, production=True)

        self.assertIn("OCR API URL은 https URL이어야 합니다.", errors)
        self.assertIn("OCR Secret Key가 없습니다.", errors)
        self.assertIn("운영 배포에는 OCR_INPUT_BUCKET이 필요합니다.", errors)
        self.assertIn("NCLOUD_OCR_TIMEOUT은 0보다 큰 정수여야 합니다.", errors)


class DeploymentPackageTests(unittest.TestCase):
    def test_accepts_a_package_with_required_entries(self):
        with temporary_package(
            {
                "main.py": "",
                "ocr_service/lambda_handler.py": "",
                "requests/__init__.py": "",
                "boto3/__init__.py": "",
            }
        ) as package:
            self.assertEqual(validate_lambda_package(package), [])

    def test_rejects_missing_entries_and_windows_binaries(self):
        with temporary_package({"main.py": "", "native.pyd": ""}) as package:
            errors = validate_lambda_package(package)

        self.assertIn("ZIP 필수 파일 누락: ocr_service/lambda_handler.py", errors)
        self.assertIn("Windows 네이티브 바이너리가 포함되었습니다: native.pyd", errors)


def temporary_package(entries: dict[str, str]):
    directory = tempfile.TemporaryDirectory()
    package = Path(directory.name) / "lambda.zip"
    with zipfile.ZipFile(package, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return TemporaryPackage(directory, package)


class TemporaryPackage:
    def __init__(self, directory: tempfile.TemporaryDirectory, package: Path):
        self.directory = directory
        self.package = package

    def __enter__(self) -> Path:
        return self.package

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.directory.cleanup()
