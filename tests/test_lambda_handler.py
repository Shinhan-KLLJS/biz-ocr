"""Lambda 핸들러의 이벤트 정규화와 S3 문서 로딩을 검증한다."""

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
    def test_normalize_event_keeps_the_sdk_payload_as_is(self):
        # 백엔드가 SDK로 직접 invoke하므로 이벤트가 곧 페이로드다.
        # API Gateway의 body 문자열을 풀어주던 처리는 없앴다 (더 이상 API GW를 거치지 않는다).
        event = {"action": "ocr", "bucket": "ocr-bucket", "key": "incoming/file.png"}

        self.assertEqual(normalize_event(event), event)
        self.assertEqual(normalize_event(None), {})
        self.assertEqual(normalize_event("not a dict"), {})

    def test_parse_event_template_ids(self):
        self.assertEqual(parse_event_template_ids({"templateIds": "1, 2"}), [1, 2])
        self.assertEqual(parse_event_template_ids({"template_ids": [3, "4"]}), [3, 4])

    @patch("ocr_service.lambda_handler.load_s3_document")
    def test_handler_rejects_request_without_an_operation(self, mock_load_document):
        response = handler({"bucket": "ocr-bucket", "key": "incoming/file.png"}, None)

        self.assertEqual(response["error"], "ValueError")
        self.assertIn("operation must be 'ocr'", response["message"])
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
        # S3 이벤트에는 operation이 없어 OCR 결과를 돌려줄 호출자가 없다.
        event = {"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": "k.png"}}}]}

        response = handler(event, None)

        self.assertIn("S3 event triggers are not supported", response["message"])
        mock_load_document.assert_not_called()


if __name__ == "__main__":
    unittest.main()
