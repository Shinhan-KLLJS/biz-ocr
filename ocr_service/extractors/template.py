def extract_text(result: dict) -> str:
    lines = []
    for image in result.get("images", []):
        combine_text = image.get("combineResult", {}).get("text")
        if combine_text:
            lines.append(combine_text)
        for field in image.get("fields", []):
            text = field.get("inferText")
            if text:
                lines.append(text)
    return "\n".join(lines)


def get_field_text(field: dict) -> str | None:
    for key in ("inferText", "text", "value"):
        value = field.get(key)
        if value is not None:
            return str(value).strip()
    return None


def extract_template_fields(result: dict) -> dict:
    extracted = {}
    for image in result.get("images", []):
        for field in image.get("fields", []):
            name = field.get("name") or field.get("fieldName")
            text = field.get("inferText")
            if name and text is not None:
                extracted[name] = {
                    "text": text,
                    "confidence": field.get("inferConfidence"),
                    "type": field.get("type"),
                    "valueType": field.get("valueType"),
                }
    return extracted
