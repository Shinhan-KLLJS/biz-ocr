import os
from pathlib import Path
from urllib.parse import unquote_plus, urlparse


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 URI: {uri}")

    return parsed.netloc, parsed.path.lstrip("/")


def parse_s3_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.split("@")[-1].split(":")[0]
    path = parsed.path.lstrip("/")

    if parsed.scheme == "s3":
        return parse_s3_uri(url)

    if parsed.scheme not in {"http", "https"} or not host or not path:
        raise ValueError(f"Invalid S3 URL: {url}")

    if host.startswith("s3.") or host.startswith("s3-"):
        bucket, _, key = path.partition("/")
        if bucket and key:
            return bucket, key

    marker_index = host.find(".s3.")
    if marker_index == -1:
        marker_index = host.find(".s3-")
    if marker_index > 0:
        return host[:marker_index], path

    raise ValueError(f"Unsupported S3 URL format: {url}")


def extract_s3_location(event: dict) -> tuple[str, str]:
    if "Records" in event and event["Records"]:
        record = event["Records"][0]
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name")
        key = s3_info.get("object", {}).get("key")
        if bucket and key:
            return bucket, unquote_plus(key)

    if event.get("bucket") and event.get("key"):
        return event["bucket"], event["key"]

    s3_payload = event.get("s3")
    if isinstance(s3_payload, dict) and s3_payload.get("bucket") and s3_payload.get("key"):
        return s3_payload["bucket"], s3_payload["key"]

    for key_name in ("s3Uri", "s3_uri", "s3Url", "s3_url"):
        value = event.get(key_name)
        if not value:
            continue
        value = str(value)
        if value.startswith("s3://"):
            return parse_s3_uri(value)
        if value.startswith(("https://", "http://")):
            return parse_s3_url(value)

    raise ValueError("Missing S3 object location. Provide bucket/key, s3.bucket/s3.key, s3Uri, or an S3 event.")


def get_s3_client():
    import boto3

    return boto3.client("s3")


def download_s3_object(bucket: str, key: str, download_dir: Path | None = None, s3_client=None) -> Path:
    if download_dir is None:
        download_dir = Path(os.getenv("OCR_DOWNLOAD_DIR", "/tmp"))

    download_dir.mkdir(parents=True, exist_ok=True)
    file_name = Path(key).name or "document"
    destination = download_dir / file_name
    client = s3_client or get_s3_client()
    client.download_file(bucket, key, str(destination))
    return destination
