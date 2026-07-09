"""로그와 오류 응답에 비밀값이 섞여 나가지 않도록 마스킹한다.

requests 예외 메시지에는 요청 URL이 그대로 들어간다. 서비스 키를 쿼리
파라미터로 보내는 API는 예외 메시지만으로도 키가 노출되므로, 외부로 나가는
모든 문자열은 이 모듈을 거쳐야 한다.
"""

import os
import re
from urllib.parse import quote, quote_plus


REDACTED = "***REDACTED***"

# 값을 몰라도 이름만으로 가릴 수 있는 쿼리 파라미터이다.
SECRET_QUERY_PATTERN = re.compile(r"(?i)\b(servicekey)=[^&\s\"'<>]*")

# 환경 변수에 실제로 담기는 비밀값의 이름이다.
SECRET_ENV_NAMES = (
    "DATA_GO_KR_SERVICE_KEY",
    "NCLOUD_OCR_SECRET_KEY",
    "NCLOUD_BIZ_OCR_SECRET_KEY",
)

# 짧은 값은 무관한 문자열까지 지울 수 있어 마스킹 대상에서 제외한다.
MIN_SECRET_LENGTH = 8


def redact_secrets(value: object) -> str:
    """문자열에서 서비스 키와 시크릿 키를 지운 사본을 돌려준다."""
    if value is None:
        return ""

    redacted = SECRET_QUERY_PATTERN.sub(lambda match: f"{match.group(1)}={REDACTED}", str(value))
    for secret in collect_secret_values():
        redacted = redacted.replace(secret, REDACTED)
    return redacted


def collect_secret_values() -> list[str]:
    """환경 변수의 비밀값을 URL 인코딩 변형까지 포함해 모은다."""
    secrets: set[str] = set()
    for name in SECRET_ENV_NAMES:
        value = os.getenv(name)
        if not value or len(value) < MIN_SECRET_LENGTH:
            continue
        secrets.update({value, quote(value, safe=""), quote_plus(value)})

    # 긴 값을 먼저 지워야 짧은 값이 부분 치환으로 마스킹을 망가뜨리지 않는다.
    return sorted(secrets, key=len, reverse=True)
