import tempfile
import unittest
from pathlib import Path

from ocr_service.storage.s3 import download_s3_object, extract_s3_location, parse_s3_url


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def download_file(self, bucket, key, destination):
        self.calls.append((bucket, key, destination))
        Path(destination).write_bytes(b"downloaded")


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

    def test_download_s3_object(self):
        fake_client = FakeS3Client()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = download_s3_object(
                "ocr-bucket",
                "incoming/file.png",
                download_dir=Path(temp_dir),
                s3_client=fake_client,
            )

        self.assertEqual(fake_client.calls[0][0], "ocr-bucket")
        self.assertEqual(fake_client.calls[0][1], "incoming/file.png")
        self.assertEqual(path.name, "file.png")


if __name__ == "__main__":
    unittest.main()
