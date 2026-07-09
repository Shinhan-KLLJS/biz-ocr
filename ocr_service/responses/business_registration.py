"""내부 OCR/검증 결과를 클라이언트용 최소 응답으로 줄인다."""


def build_business_registration_response(parsed: dict) -> dict:
    fields = parsed.get("fields") or {}
    validation = parsed.get("validation") or {}
    classification = parsed.get("advertisingClassification") or {}
    decision = parsed.get("decision") or {}

    return {
        "status": decision.get("status", "review_required"),
        "business": {
            "companyName": fields.get("companyName"),
            "representativeName": fields.get("representativeName"),
            "businessRegistrationNumber": fields.get("businessRegistrationNumber"),
        },
        "eligibility": {
            "isEligible": decision.get("status") == "accepted",
            "isCertificateValid": validation.get("isValid"),
            "isActive": validation.get("isActive"),
            "isAdvertisingRelated": classification.get("isAdvertisingRelated"),
            "reasonCode": decision.get("reasonCode"),
            "message": decision.get("message"),
        },
    }
