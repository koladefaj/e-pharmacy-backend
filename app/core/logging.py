import logging
import sys
from contextvars import ContextVar

# --- CONTEXTUAL TRACING ---
request_id_var = ContextVar("request_id", default="system")

class RequestIdFilter(logging.Filter):
    """
    A filter that injects the current 'request_id' into every LogRecord.
    This makes 'request_id' available to the Formatter.
    """
    def filter(self, record):
        # If no request_id is set 
        # it defaults to "system" instead of "n/a" for better clarity.
        record.request_id = request_id_var.get()
        return True

def setup_logging():
    """
    Initializes the global logging system with a JSON formatter.

    """
    # Choose where logs go 
    handler = logging.StreamHandler(sys.stdout)
    
    # Attach our custom filter
    handler.addFilter(RequestIdFilter())
    
    # Define the Structured JSON Format

    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "file": "%(module)s.py:%(lineno)d", '
        '"message": "%(message)s", "request_id": "%(request_id)s"}'
    )
    handler.setFormatter(formatter)

    # Configure the Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clean up duplicate handlers 
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)

    # Silence noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)