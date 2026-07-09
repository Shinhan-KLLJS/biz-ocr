"""요청/이벤트에서 S3 객체 위치를 찾아내고, 객체를 메모리로 읽는다."""

from urllib.parse import unquote_plus, urlparse


# Lambda warm start에서 재사용해 클라이언트 초기화 비용을 아낀다.
_s3_client = None


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
    global _s3_client
    if _s3_client is None:
        import boto3

        _s3_client = boto3.client("s3")
    return _s3_client


def head_s3_object_size(bucket: str, key: str, s3_client=None) -> int:
    """객체를 읽기 전에 크기만 조회한다. s3:GetObject 권한으로 호출할 수 있다."""
    client = s3_client or get_s3_client()
    return int(client.head_object(Bucket=bucket, Key=key)["ContentLength"])


def read_s3_object(bucket: str, key: str, s3_client=None) -> bytes:
    """객체 본문을 디스크를 거치지 않고 메모리로 읽는다."""
    client = s3_client or get_s3_client()
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()
