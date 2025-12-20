import time

from app.core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Wrapper to capture status code
        status_code = [500]  # Default to 500 if start no called

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # If an exception occurs, we might not have sent the response start yet.
            # But the main app or exception handlers should handle it.
            # We just log it if needed or let it propagate.
            raise e
        finally:
            process_time = time.time() - start_time
            logger.info(
                f"Incoming request: method={scope['method']} path={scope['path']} "
                f"status_code={status_code[0]} processing_time={process_time:.4f}s"
            )
