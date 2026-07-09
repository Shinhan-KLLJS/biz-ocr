"""OCR에 넘길 문서를 메모리 위에서 다룬다.

Lambda의 /tmp는 warm 컨테이너에서 재사용되므로 파일을 남기면 디스크가 찬다.
requests의 multipart 본문은 어차피 메모리에 통째로 만들어지기 때문에,
S3 객체를 디스크에 내려받지 않고 바이트로 바로 들고 다닌다.
"""

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


SUPPORTED_FORMATS = {
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".png": "png",
    ".pdf": "pdf",
    ".tif": "tiff",
    ".tiff": "tiff",
}

DEFAULT_MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def infer_format(file_name: object) -> str:
    """파일 이름의 확장자로 OCR API에 보낼 format 값을 정한다."""
    suffix = Path(str(file_name)).suffix.lower()
    try:
        return SUPPORTED_FORMATS[suffix]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise ValueError(f"Unsupported file format: {suffix or file_name}. Supported: {supported}") from exc


def max_document_bytes() -> int:
    return int(os.getenv("NCLOUD_OCR_MAX_FILE_BYTES", str(DEFAULT_MAX_DOCUMENT_BYTES)))


def validate_document_size(size_bytes: int, file_name: str = "document") -> None:
    """내려받기 전에 크기를 확인해 큰 파일을 메모리에 올리지 않는다."""
    limit = max_document_bytes()
    if size_bytes > limit:
        raise ValueError(f"File is too large for OCR request: {file_name} > {limit} bytes")


def object_key_to_file_name(key: str) -> str:
    """S3 key는 항상 '/' 구분자이므로 OS별 경로 해석에 맡기지 않는다."""
    return PurePosixPath(key).name or "document"


@dataclass(frozen=True)
class DocumentSource:
    """OCR API에 그대로 전달할 파일 이름과 내용이다."""

    name: str
    content: bytes

    @classmethod
    def from_path(cls, path: Path) -> "DocumentSource":
        return cls(name=path.name, content=path.read_bytes())

    @property
    def format(self) -> str:
        return infer_format(self.name)

    @property
    def stem(self) -> str:
        return Path(self.name).stem or "document"

    @property
    def size(self) -> int:
        return len(self.content)
