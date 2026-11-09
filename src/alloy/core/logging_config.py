import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

SENSITIVE_PATTERNS = re.compile(
    r'("?(?:password|password_confirm|new_password|token|refresh_token|reset_token|secret)"?\s*[:=]\s*)"?[^",\s\}]+("?)',
    re.IGNORECASE
)

def mask_sensitive_data(text: str) -> str:
    return SENSITIVE_PATTERNS.sub(r'\1"***REDACTED***"\2', text)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_sensitive_data(record.getMessage()),
        }

        extra_keys = (
            "event_type", "method", "path", "status_code",
            "duration_ms", "client_ip", "user_agent", "user_id", "recipient", "subject"
        )
        for key in extra_keys:
            if hasattr(record, key):
                log_record[key] = getattr(record, key)

        if record.exc_info:
            log_record["exception"] = mask_sensitive_data(
                "".join(traceback.format_exception(*record.exc_info))
            )

        return json.dumps(log_record, ensure_ascii=False)

def setup_centralized_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = JsonFormatter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "alloy.json.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger("alloy.audit")

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method

        is_security_event = (
            path.startswith("/api/v1/auth")
            or path.startswith("/api/v1/admin")
            or "moderation" in path
        )
        event_type = "security_audit" if is_security_event else "http_request"

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
            self.logger.log(
                log_level,
                f"{method} {path} -> {response.status_code} ({duration_ms} ms)",
                extra={
                    "event_type": event_type,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                    "user_agent": request.headers.get("user-agent", "unknown"),
                }
            )
            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.logger.error(
                f"UNHANDLED_EXCEPTION: {method} {path} failed after {duration_ms} ms",
                exc_info=True,
                extra={
                    "event_type": "unhandled_exception",
                    "method": method,
                    "path": path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                }
            )
            raise exc
