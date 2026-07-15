"""Lambda 배포 직전에 환경 변수와 ZIP 산출물을 점검한다."""

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ocr_service.config import configure_stdio, load_dotenv
from ocr_service.deployment import validate_lambda_environment, validate_lambda_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lambda 배포 환경과 ZIP을 안전하게 점검합니다.")
    parser.add_argument("--package", type=Path, help="검사할 Lambda ZIP 경로")
    parser.add_argument("--production", action="store_true", help="OCR_INPUT_BUCKET도 필수로 검사")
    parser.add_argument("--skip-env", action="store_true", help="환경 변수 검사를 건너뜀")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_stdio()
    load_dotenv(ROOT_DIR / ".env")
    errors: list[str] = []
    if not args.skip_env:
        errors.extend(validate_lambda_environment(production=args.production))
    if args.package:
        errors.extend(validate_lambda_package(args.package))

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("PASS: Lambda deployment preflight completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
