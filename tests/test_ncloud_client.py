import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from ocr_service.documents import DocumentSource, infer_format, validate_document_size
from ocr_service.errors import ExternalServiceError
from ocr_service.ncloud_client import call_business_license_ocr, parse_template_ids


NCLOUD_ENV = {
    "NCLOUD_OCR_BIZ_LICENSE_API_URL": "https://example.com/document/biz-license",
    "NCLOUD_OCR_API_URL": "https://example.com/general",
    "NCLOUD_OCR_SECRET_KEY": "secret-key-value",
}


def make_document(name: str = "sample.png") -> DocumentSource:
    return DocumentSource(name=name, content=b"image")


class DocumentTests(unittest.TestCase):
    def test_parse_template_ids(self):
        self.assertEqual(parse_template_ids("1, 2,3"), [1, 2, 3])

    def test_infer_format(self):
        self.assertEqual(infer_format(Path("sample.jpg")), "jpg")
        self.assertEqual(infer_format("sample.jpeg"), "jpg")
        self.assertEqual(infer_format("sample.png"), "png")
        self.assertEqual(infer_format("sample.pdf"), "pdf")
        self.assertEqual(infer_format("sample.tif"), "tiff")
        self.assertEqual(infer_format("sample.tiff"), "tiff")

    def test_infer_format_rejects_unsupported_extension(self):
        with self.assertRaises(ValueError):
            infer_format("sample.gif")

    def test_validate_document_size_allows_small_document(self):
        validate_document_size(5, "sample.png")

    def test_validate_document_size_rejects_large_document(self):
        with patch.dict(os.environ, {"NCLOUD_OCR_MAX_FILE_BYTES": "10"}, clear=False):
            with self.assertRaises(ValueError):
                validate_document_size(11, "sample.png")


class NcloudClientTests(unittest.TestCase):
    @patch("ocr_service.ncloud_client.requests.post")
    def test_call_business_license_ocr_uses_document_endpoint(self, mock_post):
        mock_post.return_value = Mock(ok=True, json=Mock(return_value={"images": []}))

        with patch.dict(os.environ, NCLOUD_ENV, clear=False):
            result = call_business_license_ocr(make_document(), 10)

        self.assertEqual(result, {"images": []})
        self.assertEqual(mock_post.call_args.args[0], "https://example.com/document/biz-license")
        message = mock_post.call_args.kwargs["data"]["message"]
        self.assertNotIn("lang", message)
        self.assertIn('"format": "png"', message)

    @patch("ocr_service.ncloud_client.requests.post")
    def test_call_business_license_ocr_sends_bytes_not_a_file_path(self, mock_post):
        mock_post.return_value = Mock(ok=True, json=Mock(return_value={"images": []}))

        with patch.dict(os.environ, NCLOUD_ENV, clear=False):
            call_business_license_ocr(make_document(), 10)

        file_name, content = mock_post.call_args.kwargs["files"]["file"]
        self.assertEqual(file_name, "sample.png")
        self.assertEqual(content, b"image")

    @patch("ocr_service.ncloud_client.requests.post")
    def test_request_failure_is_wrapped_without_the_secret_key(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("failed while sending secret-key-value")

        with patch.dict(os.environ, NCLOUD_ENV, clear=False):
            with self.assertRaises(ExternalServiceError) as raised:
                call_business_license_ocr(make_document(), 10)

        self.assertNotIn("secret-key-value", str(raised.exception))

    @patch("ocr_service.ncloud_client.requests.post")
    def test_http_error_masks_the_secret_in_both_the_exception_and_the_log(self, mock_post):
        mock_post.return_value = Mock(ok=False, status_code=401, text="secret-key-value is invalid")

        with patch.dict(os.environ, NCLOUD_ENV, clear=False):
            with self.assertLogs("ocr_service.ncloud_client", level="ERROR") as captured:
                with self.assertRaises(ExternalServiceError) as raised:
                    call_business_license_ocr(make_document(), 10)

        self.assertNotIn("secret-key-value", str(raised.exception))
        self.assertIn("401", str(raised.exception))
        self.assertNotIn("secret-key-value", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
