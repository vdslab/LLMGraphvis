import time
import logging
from starlette.types import ASGIApp, Scope, Receive, Send
from app.core.logging import get_logger

logger = get_logger(__name__)

class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope["method"]
        path = scope["path"]
        
        # We need to capture the status code. 
        # But for streaming responses, the status is sent early.
        # This wrapper captures the initial response start message.
        status_code = [500] 

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            process_time = time.time() - start_time
            logger.info(
                f"Incoming request: method={method} path={path} "
                f"status_code={status_code[0]} processing_time={process_time:.4f}s"
            )

