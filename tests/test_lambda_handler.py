import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ocr_service.lambda_handler import normalize_event, parse_event_template_ids, handler


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

    @patch("ocr_service.lambda_handler.parse_business_registration_result")
    @patch("ocr_service.lambda_handler.call_ocr")
    @patch("ocr_service.lambda_handler.validate_file_size")
    @patch("ocr_service.lambda_handler.download_s3_object")
    def test_handler_downloads_s3_and_returns_parsed_payload(
        self,
        mock_download,
        mock_validate,
        mock_call_ocr,
        mock_parse,
    ):
        mock_download.return_value = Path("/tmp/file.png")
        mock_call_ocr.return_value = {"images": []}
        mock_parse.return_value = {
            "documentType": "businessRegistrationCertificate",
            "fields": {"businessRegistrationNumber": "368-88-03013"},
            "warnings": [],
        }

        response = handler({"bucket": "ocr-bucket", "key": "incoming/file.png"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["source"], {"bucket": "ocr-bucket", "key": "incoming/file.png"})
        mock_download.assert_called_once_with("ocr-bucket", "incoming/file.png")
        mock_validate.assert_called_once_with(Path("/tmp/file.png"))
        mock_call_ocr.assert_called_once()


if __name__ == "__main__":
    unittest.main()
