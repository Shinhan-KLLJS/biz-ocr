"""Lambda 운영 로그를 비밀값 노출 없이 남긴다."""

import logging
import traceback


MAX_TRACEBACK_LENGTH = 4_000


def get_request_id(context: object) -> str:
    """Lambda 컨텍스트가 없어도 테스트와 로컬 실행이 가능하도록 한다."""
    return str(getattr(context, "aws_request_id", None) or "local")


def log_invocation_started(logger: logging.Logger, context: object, event: dict) -> None:
    """객체 키나 문서 정보는 남기지 않고 호출 상관관계만 기록한다."""
    operation = event.get("operation") or event.get("action") or "missing"
    logger.info(
        "OCR invocation started: request_id=%s operation=%s",
        get_request_id(context),
        operation,
    )


def log_invocation_completed(logger: logging.Logger, context: object) -> None:
    """성공 호출도 request ID로 시작 로그와 연결한다."""
    logger.info("OCR invocation completed: request_id=%s", get_request_id(context))


def log_invocation_failed(
    logger: logging.Logger,
    context: object,
    exc: Exception,
    safe_message: str,
) -> None:
    """마스킹한 메시지와 예외 문구 없는 traceback만 CloudWatch에 남긴다.

    logger.exception()은 원본 예외 메시지 및 연쇄 예외를 다시 출력할 수 있어 사용하지 않는다.
    """
    traceback_text = format_safe_traceback(exc)
    logger.error(
        "OCR invocation failed: request_id=%s error_type=%s message=%s traceback=%s",
        get_request_id(context),
        type(exc).__name__,
        safe_message,
        traceback_text or "unavailable",
    )


def format_safe_traceback(exc: Exception) -> str:
    """소스 코드 줄과 예외 문구를 제외한 실행 위치만 남긴다."""
    frames = traceback.extract_tb(exc.__traceback__)
    locations = [f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames]
    return "\n".join(locations)[:MAX_TRACEBACK_LENGTH]
