"""Keep request queries, SQL details and exception payloads out of service logs."""
import logging
import re


class PrivacyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, target, version, status = record.args
            record.args = (client, method, str(target).split("?", 1)[0], version, status)
        elif record.name.startswith("sqlalchemy"):
            record.msg = "Database diagnostic omitted for privacy"
            record.args = ()
        else:
            # HTTP client diagnostics can contain full OAuth URLs. Never log query values.
            record.msg = re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[redacted]', record.getMessage())
            record.args = ()
        if record.exc_info:
            exception_type = record.exc_info[0].__name__
            record.msg = record.getMessage() + f" ({exception_type})"
            record.args = ()
            record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def configure_private_logging() -> None:
    # Uvicorn configures its handlers before importing app.main. Attach at handlers
    # so propagated records from child loggers are filtered as well.
    root = logging.getLogger()
    if not root.handlers:
        # Uvicorn normally leaves root without handlers. Otherwise pool errors
        # would use logging.lastResort and bypass all handler filters.
        root.addHandler(logging.StreamHandler())
    loggers = [root, logging.getLogger("uvicorn"),
               logging.getLogger("uvicorn.error"), logging.getLogger("uvicorn.access"),
               logging.getLogger("sqlalchemy"), logging.getLogger("sqlalchemy.engine")]
    for logger in loggers:
        for handler in logger.handlers:
            if not any(isinstance(item, PrivacyFilter) for item in handler.filters):
                handler.addFilter(PrivacyFilter())
    for name in ("httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
