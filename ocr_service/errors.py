"""서비스 전반에서 쓰는 예외 타입을 정의한다."""


class ExternalServiceError(RuntimeError):
    """외부 API 호출이 실패했음을 알린다.

    원본 예외에는 요청 URL과 비밀값이 들어 있으므로 그대로 전파하지 않는다.
    이 예외에는 마스킹을 마친 메시지만 담는다.
    """
