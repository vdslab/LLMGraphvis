import time

from starlette.types import ASGIApp, Receive, Scope, Send

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
        # When the last body chunk went out. BackgroundTasks run after that,
        # inside the same call, and are not part of the request's time.
        responded_at = [None]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            elif message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                responded_at[0] = time.time()
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            process_time = (responded_at[0] or time.time()) - start_time
            logger.info(
                f"Incoming request: method={method} path={path} "
                f"status_code={status_code[0]} processing_time={process_time:.4f}s"
            )
