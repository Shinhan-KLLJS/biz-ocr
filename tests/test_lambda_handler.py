"""Lambda 핸들러의 이벤트 정규화와 S3 문서 로딩을 검증한다."""

import json
import os
import unittest
from unittest.mock import patch

from ocr_service.lambda_handler import (
    handler,
    load_s3_document,
    normalize_event,
    parse_event_template_ids,
)


class LambdaHandlerTests(unittest.TestCase):
    def test_normalize_api_gateway_body(self):
        event = {"body": json.dumps({"bucket": "ocr-bucket", "key": "incoming/file.png"})}

        self.assertEqual(
            normalize_event(event),
            {"body": event["body"], "bucket": "ocr-bucket", "key": "incoming/file.png"},
        )

    def test_parse_event_template_ids(self):
        self.assertEqual(parse_event_template_ids({"templateIds": "1, 2"}), [1, 2])
        self.assertEqual(parse_event_template_ids({"template_ids": [3, "4"]}), [3, 4])

    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_handler_rejects_request_without_split_operation(self, mock_load_document):
        response = handler({"bucket": "ocr-bucket", "key": "incoming/file.png"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["error"], "UnsupportedOperation")
        mock_load_document.assert_not_called()

    @patch("ocr_service.lambda_handler.read_s3_object")
    @patch("ocr_service.lambda_handler.head_s3_object_size")
    def test_load_s3_document_rejects_large_object_before_reading_it(self, mock_head, mock_read):
        mock_head.return_value = 400 * 1024 * 1024

        with patch.dict(os.environ, {"NCLOUD_OCR_MAX_FILE_BYTES": str(50 * 1024 * 1024)}, clear=False):
            with self.assertRaises(ValueError):
                load_s3_document("ocr-bucket", "incoming/huge.pdf")

        mock_read.assert_not_called()

    @patch("ocr_service.lambda_handler.read_s3_object")
    @patch("ocr_service.lambda_handler.head_s3_object_size")
    def test_load_s3_document_rejects_unsupported_format_before_any_s3_call(self, mock_head, mock_read):
        with self.assertRaises(ValueError):
            load_s3_document("ocr-bucket", "incoming/file.gif")

        mock_head.assert_not_called()
        mock_read.assert_not_called()

    @patch("ocr_service.lambda_handler.read_s3_object")
    @patch("ocr_service.lambda_handler.head_s3_object_size")
    def test_load_s3_document_uses_posix_key_basename(self, mock_head, mock_read):
        mock_head.return_value = 10
        mock_read.return_value = b"image"

        document = load_s3_document("ocr-bucket", "incoming/nested/business registration.png")

        self.assertEqual(document.name, "business registration.png")
        self.assertEqual(document.content, b"image")

    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_handler_rejects_s3_event_trigger_with_a_clear_reason(self, mock_load_document):
        # S3 이벤트에는 operation도 경로도 없어 OCR 결과를 돌려줄 호출자가 없다.
        event = {"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": "k.png"}}}]}

        response = handler(event, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertIn("S3 event triggers are not supported", body["message"])
        mock_load_document.assert_not_called()


if __name__ == "__main__":
    unittest.main()
