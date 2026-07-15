"""검증된 Linux 의존성 ZIP에 현재 OCR 소스만 교체해 배포 ZIP을 만든다."""

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ocr_service.deployment import validate_lambda_package


PROJECT_FILES = ("main.py",)
PROJECT_DIRECTORY = Path("ocr_service")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="기존 Linux Lambda ZIP의 앱 소스를 최신으로 교체합니다.")
    parser.add_argument("--base-zip", type=Path, default=Path("dist/lambda-deploy.zip"))
    parser.add_argument("--output", type=Path, default=Path("dist/lambda-deploy-current.zip"))
    return parser.parse_args()


def should_copy_from_base(name: str) -> bool:
    """이전 ZIP에서는 의존성만 유지하고 프로젝트 소스는 제외한다."""
    return name != "main.py" and not name.startswith("ocr_service/")


def iter_project_files() -> list[Path]:
    """캐시를 제외한 현재 Python 소스만 ZIP 루트 기준으로 찾는다."""
    files = [Path(name) for name in PROJECT_FILES]
    files.extend(path for path in PROJECT_DIRECTORY.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def create_package(base_zip: Path, output: Path) -> None:
    if not base_zip.is_file():
        raise FileNotFoundError(f"Base Lambda ZIP not found: {base_zip}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as temp:
        temp_path = Path(temp.name)

    try:
        with zipfile.ZipFile(base_zip) as source, zipfile.ZipFile(
            temp_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for info in source.infolist():
                if should_copy_from_base(info.filename):
                    target.writestr(info, source.read(info.filename))
            for path in iter_project_files():
                target.write(path, path.as_posix())
        temp_path.replace(output)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def validate_package(output: Path) -> None:
    errors = validate_lambda_package(output)
    if errors:
        raise RuntimeError("; ".join(errors))


def main() -> None:
    args = parse_args()
    create_package(args.base_zip, args.output)
    validate_package(args.output)
    print(f"Created current-source Lambda ZIP: {args.output}")


if __name__ == "__main__":
    main()
