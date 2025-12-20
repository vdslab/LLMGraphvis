import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
# Add backend to path (backend/tests/manual -> backend)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.services.llm import engine
from google.genai import types


async def run_verification():
    print("Starting verification of engine streaming logic...")

    # Mock Queue
    mock_queue = AsyncMock()

    # --- Simulate Initial Response (Text Plan) ---
    # "I plan to check metadata."
    chunk1 = MagicMock()
    chunk1.candidates = [MagicMock()]
    chunk1.candidates[0].content.parts = [
        types.Part(text="[Phase 1] I will check the metadata.")
    ]

    # Chunk 2: Tool Call
    # Note: In real stream, tool call might come in separate chunk or same.
    # Let's verify subsequent chunk.
    chunk2 = MagicMock()
    chunk2.candidates = [MagicMock()]
    func_call = types.FunctionCall(
        name="read_resource", args={"uri": "network://1/metadata"}
    )
    chunk2.candidates[0].content.parts = [types.Part(function_call=func_call)]

    # Async iterator for initial response
    async def initial_stream_iterator():
        yield chunk1
        yield chunk2

    start_response = initial_stream_iterator()

    # --- Simulate Second Response (After Tool Execution) ---
    # "Report: Done."
    chunk3 = MagicMock()
    chunk3.candidates = [MagicMock()]
    chunk3.candidates[0].content.parts = [
        types.Part(text="[Phase 3] I have checked the metadata.")
    ]

    async def second_stream_iterator():
        yield chunk3

    # Mock Dependencies
    with patch(
        "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
    ) as mock_tool:
        mock_tool.return_value = {"name": "Test Network", "node_count": 10}

        # Mock client for next iteration
        with patch(
            "app.services.llm.engine.client.aio.models.generate_content_stream",
            return_value=second_stream_iterator(),
        ) as mock_client_call:
            # Mock local_tools
            with patch(
                "app.services.llm.local_tools.execute_local_tool",
                new_callable=AsyncMock,
            ):
                print("Executing tool loop...")
                await engine.execute_tool_loop(
                    initial_response=start_response,
                    network_id=1,
                    history=[],
                    queue=mock_queue,
                    tool_config=None,
                    chat_id=1,
                    db=MagicMock(),
                )

    # --- Verification ---
    print("\n--- Verifying Queue Events ---")
    events = []
    for call in mock_queue.put.call_args_list:
        event = call.args[0]
        events.append(event)
        print(f"Event: {event['event']} | Data: {event['data'][:50]}...")

    # Check for sequencing
    has_text_1 = any(
        e["event"] == "message_chunk" and "Phase 1" in e["data"] for e in events
    )
    has_tool_start = any(
        e["event"] == "tool_execution" and "started" in e["data"] for e in events
    )
    has_tool_end = any(
        e["event"] == "tool_execution" and "completed" in e["data"] for e in events
    )
    has_text_2 = any(
        e["event"] == "message_chunk" and "Phase 3" in e["data"] for e in events
    )

    if has_text_1 and has_tool_start and has_tool_end and has_text_2:
        print("\nSUCCESS: Sequence verified (Text -> Tool -> Text)")
    else:
        print("\nFAILURE: Sequence missing elements.")
        print(f"Has Start Text: {has_text_1}")
        print(f"Has Tool Start: {has_tool_start}")
        print(f"Has Tool End: {has_tool_end}")
        print(f"Has Final Text: {has_text_2}")


if __name__ == "__main__":
    asyncio.run(run_verification())
