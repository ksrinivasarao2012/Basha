import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# ContextVar to store the current request ID across async tasks/threads
REQUEST_ID_VAR: ContextVar[str] = ContextVar("request_id", default="")

class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as single-line JSON.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        # Include request ID if present in the contextvar
        request_id = REQUEST_ID_VAR.get()
        if request_id:
            log_data["request_id"] = request_id
            
        # Include extra attributes if any
        if hasattr(record, "extra_info") and isinstance(record.extra_info, dict):
            log_data.update(record.extra_info)
            
        # Exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

def setup_logging(level: str = "INFO") -> None:
    """
    Configures the root logger to output JSON to stdout.
    """
    root_logger = logging.getLogger()
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance.
    """
    return logging.getLogger(name)

# Context manager for tracking duration/performance metrics
class LogContext:
    """
    A helper context manager to log start, success, or failure of an action
    along with duration metrics.
    """
    def __init__(self, name: str, action: str, extra: Dict[str, Any] = None):
        self.logger = get_logger(name)
        self.action = action
        self.extra = extra or {}
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        self.logger.info(
            f"Starting: {self.action}",
            extra={"extra_info": {**self.extra, "state": "started"}}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        extra_info = {**self.extra, "duration_seconds": round(duration, 4)}
        
        if exc_type:
            extra_info["state"] = "failed"
            extra_info["error"] = str(exc_val)
            self.logger.error(
                f"Failed: {self.action} (after {extra_info['duration_seconds']}s)",
                exc_info=True,
                extra={"extra_info": extra_info}
            )
        else:
            extra_info["state"] = "completed"
            self.logger.info(
                f"Completed: {self.action} (after {extra_info['duration_seconds']}s)",
                extra={"extra_info": extra_info}
            )

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to intercept requests, assign a request ID,
    log the incoming/outgoing endpoints, and track request latency.
    """
    async def dispatch(self, request: Request, call_next):
        # Retrieve existing or generate a new request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = REQUEST_ID_VAR.set(request_id)
        
        logger = get_logger("basha.api")
        start_time = time.perf_counter()
        
        logger.info(
            f"Incoming request {request.method} {request.url.path}",
            extra={"extra_info": {"method": request.method, "path": request.url.path}}
        )
        
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            response.headers["X-Request-ID"] = request_id
            
            logger.info(
                f"Finished request {request.method} {request.url.path} - {response.status_code}",
                extra={"extra_info": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_seconds": round(duration, 4)
                }}
            )
            return response
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                f"Request failed {request.method} {request.url.path} - {str(e)}",
                exc_info=True,
                extra={"extra_info": {
                    "method": request.method,
                    "path": request.url.path,
                    "duration_seconds": round(duration, 4)
                }}
            )
            raise e
        finally:
            REQUEST_ID_VAR.reset(token)
