import os
import tempfile
import unittest
from pathlib import Path

from ocr_service.ncloud_client import infer_format, parse_template_ids, validate_file_size


class NcloudClientTests(unittest.TestCase):
    def test_parse_template_ids(self):
        self.assertEqual(parse_template_ids("1, 2,3"), [1, 2, 3])

    def test_infer_format(self):
        self.assertEqual(infer_format(Path("sample.jpg")), "jpg")
        self.assertEqual(infer_format(Path("sample.jpeg")), "jpg")
        self.assertEqual(infer_format(Path("sample.png")), "png")
        self.assertEqual(infer_format(Path("sample.pdf")), "pdf")
        self.assertEqual(infer_format(Path("sample.tif")), "tiff")
        self.assertEqual(infer_format(Path("sample.tiff")), "tiff")

    def test_validate_file_size_allows_small_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"small")
            temp_path = Path(temp_file.name)

        try:
            validate_file_size(temp_path)
        finally:
            os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
