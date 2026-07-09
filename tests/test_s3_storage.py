import io
import unittest

from ocr_service.storage.s3 import (
    extract_s3_location,
    head_s3_object_size,
    parse_s3_url,
    read_s3_object,
)


class FakeS3Client:
    def __init__(self, content: bytes = b"downloaded"):
        self.content = content
        self.get_calls = []
        self.head_calls = []

    def get_object(self, Bucket, Key):  # noqa: N803 - boto3 인자 이름을 따른다.
        self.get_calls.append((Bucket, Key))
        return {"Body": io.BytesIO(self.content)}

    def head_object(self, Bucket, Key):  # noqa: N803 - boto3 인자 이름을 따른다.
        self.head_calls.append((Bucket, Key))
        return {"ContentLength": len(self.content)}


class S3StorageTests(unittest.TestCase):
    def test_extract_s3_event_location(self):
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "ocr-bucket"},
                        "object": {"key": "incoming/business+registration.png"},
                    }
                }
            ]
        }

        self.assertEqual(extract_s3_location(event), ("ocr-bucket", "incoming/business registration.png"))

    def test_extract_direct_bucket_key(self):
        self.assertEqual(
            extract_s3_location({"bucket": "ocr-bucket", "key": "incoming/file.png"}),
            ("ocr-bucket", "incoming/file.png"),
        )

    def test_parse_s3_url(self):
        self.assertEqual(
            parse_s3_url("https://ocr-bucket.s3.ap-northeast-2.amazonaws.com/incoming/file.png?x=y"),
            ("ocr-bucket", "incoming/file.png"),
        )
        self.assertEqual(
            parse_s3_url("https://s3.ap-northeast-2.amazonaws.com/ocr-bucket/incoming/file.png"),
            ("ocr-bucket", "incoming/file.png"),
        )

    def test_read_s3_object_returns_bytes_without_touching_disk(self):
        fake_client = FakeS3Client(b"image-bytes")

        content = read_s3_object("ocr-bucket", "incoming/file.png", s3_client=fake_client)

        self.assertEqual(content, b"image-bytes")
        self.assertEqual(fake_client.get_calls, [("ocr-bucket", "incoming/file.png")])

    def test_head_s3_object_size_reports_content_length(self):
        fake_client = FakeS3Client(b"12345")

        size = head_s3_object_size("ocr-bucket", "incoming/file.png", s3_client=fake_client)

        self.assertEqual(size, 5)
        self.assertEqual(fake_client.head_calls, [("ocr-bucket", "incoming/file.png")])


if __name__ == "__main__":
    unittest.main()
