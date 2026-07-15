"""저장된 Document OCR 결과가 백엔드 6필드 계약을 계속 만족하는지 검증한다."""

import json
import unittest
from pathlib import Path

from ocr_service.responses.business_registration import build_business_registration_ocr_response
from ocr_service.services.business_registration import parse_business_registration_with_fallback


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_OUTPUT_DIR = ROOT_DIR / "outputs" / "document_raw"
REQUIRED_KEYS = {
    "companyName",
    "representativeName",
    "businessNumber",
    "businessOpeningDate",
    "businessType",
    "businessItem",
}


class SavedDocumentOutputTests(unittest.TestCase):
    def test_all_saved_documents_produce_complete_backend_contracts(self):
        raw_paths = sorted(RAW_OUTPUT_DIR.glob("*.json"))
        self.assertEqual(len(raw_paths), 6, "저장된 Document OCR fixture 수가 바뀌었습니다.")

        for raw_path in raw_paths:
            with self.subTest(raw_path=raw_path.name):
                response = build_response(raw_path)
                self.assertEqual(set(response), REQUIRED_KEYS)
                self.assertTrue(all(response.values()), f"필수 OCR 필드 누락: {response}")
                self.assertRegex(response["businessNumber"], r"^\d{10}$")
                self.assertRegex(response["businessOpeningDate"], r"^\d{4}-\d{2}-\d{2}$")


def build_response(raw_path: Path) -> dict:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    return build_business_registration_ocr_response(parse_business_registration_with_fallback(raw))
