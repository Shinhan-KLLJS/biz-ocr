import io
import os
import unittest
from unittest.mock import patch

from ocr_service.storage.s3 import (
    assert_allowed_bucket,
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


class AllowedBucketTests(unittest.TestCase):
    @patch.dict(os.environ, {"OCR_INPUT_BUCKET": "loovi-ocr-input"}, clear=False)
    def test_configured_bucket_is_allowed(self):
        assert_allowed_bucket("loovi-ocr-input")

    @patch.dict(os.environ, {"OCR_INPUT_BUCKET": "loovi-ocr-input"}, clear=False)
    def test_other_buckets_are_rejected(self):
        # 호출자가 준 버킷을 그대로 믿으면 Lambda role이 읽을 수 있는 모든 객체가 노출된다.
        with self.assertRaises(ValueError):
            assert_allowed_bucket("someone-elses-bucket")

    def test_any_bucket_is_allowed_when_the_allowlist_is_not_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OCR_INPUT_BUCKET", None)
            assert_allowed_bucket("any-bucket")


if __name__ == "__main__":
    unittest.main()
