"""Lambda 이벤트를 해석해 동작을 고른다.

이 Lambda는 백엔드가 SDK로 직접 invoke한다 (API Gateway를 거치지 않는다).
API Gateway를 쓰면 동기 호출에 29초 제한이 걸리고, 인증(JWT authorizer)과 CORS를 따로
관리해야 하며, 인증 없이 열려 있으면 OCR 비용이 남용될 수 있기 때문이다.
그래서 proxy 응답 봉투({statusCode, body})도 만들지 않고 결과 dict를 그대로 반환한다.
"""

from ocr_service.ncloud_client import parse_template_ids


def normalize_event(event) -> dict:
    return event if isinstance(event, dict) else {}


def resolve_operation(event: dict) -> str:
    """이 Lambda는 OCR만 수행한다. 그 외 입력은 모두 unsupported로 돌린다.

    <b>operation/action을 반드시 요구한다.</b> bucket/key만 있는 입력을 OCR로 받아주면
    S3 업로드 이벤트로 Lambda가 트리거되도록 잘못 설정했을 때 그대로 실행돼 버린다 -
    OCR 결과를 돌려받을 호출자가 없어 비용만 쓰고 결과는 버려진다.
    """
    operation = event.get("operation") or event.get("action")
    if not operation:
        return "unsupported"
    return normalize_operation(operation)


def normalize_operation(operation: object) -> str:
    value = str(operation).strip().lower()
    if value in {"ocr", "extract", "parse"}:
        return "ocr"
    return "unsupported"


def parse_event_template_ids(event: dict) -> list[int]:
    template_ids = event.get("templateIds") or event.get("template_ids")
    if not template_ids:
        return []
    if isinstance(template_ids, list):
        return [int(template_id) for template_id in template_ids]
    return parse_template_ids(str(template_ids))
