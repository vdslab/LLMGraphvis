import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import get_logger

logger = get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        logger.info(
            f"Incoming request: method={request.method} path={request.url.path} "
            f"status_code={response.status_code} processing_time={process_time:.4f}s"
        )
        
        return response
