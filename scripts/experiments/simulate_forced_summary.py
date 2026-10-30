import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

# MOCK DEPENDENCIES
from unittest.mock import MagicMock
sys.modules["common"] = MagicMock()
sys.modules["common.models"] = MagicMock()
sys.modules["app.core.logging"] = MagicMock()
# Mock get_logger to avoid errors
mock_logger = MagicMock()
sys.modules["app.core.logging"].get_logger.return_value = mock_logger

# Also mock genai because engine imports it at top level
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()

# Now we can import
from app.services.llm.engine import GraphVisAgent
from google.genai import types # This will use our mock, but we need to setup types properly for our test usage


# Mock Types since we mocked the module
# engine.py uses types.Content, types.Part, types.GenerateContentConfig, types.Tool, types.ToolConfig
# We need to make sure types is populated
types = sys.modules["google.genai.types"]

class RealMockPart:
    def __init__(self, text=None, function_call=None):
        self.text = text
        self.function_call = function_call
    @classmethod
    def from_text(cls, text):
        return cls(text=text)
    @classmethod
    def from_function_response(cls, name, response):
        return cls()

class RealMockContent:
    def __init__(self, role, parts):
        self.role = role
        self.parts = parts

types.Content = RealMockContent
types.Part = RealMockPart
types.GenerateContentConfig = MagicMock()
types.Tool = MagicMock()
types.ToolConfig = MagicMock()

# Mock Event
class MockEvent:
    def __init__(self, text=None, function_call=None):
        self.text = text
        self.function_call = function_call

class MockCandidate:
    def __init__(self, parts):
        self.content = MagicMock()
        self.content.parts = parts

class MockChunk:
    def __init__(self, parts):
        self.candidates = [MockCandidate(parts)]

async def mock_stream(parts_list):
    # parts_list is a list of RealMockPart
    chunk = MockChunk(parts_list)
    yield chunk


class TestGraphVisAgent(GraphVisAgent):
    def __init__(self):
        self.db = None
        self.model_name = "test-model"
        # Mock client
        self.client = MagicMock()
        self.client.aio = MagicMock()
        self.client.aio.models = MagicMock()
        self.client.aio.models.generate_content_stream = AsyncMock()
        
        # We will set side_effects for generate_content_stream
        self.generation_responses = [] # FIFO queue of responses to yield

    async def _gemini_generate(self, history, tools, tool_config):
        print(f"DEBUG: _gemini_generate called. History len: {len(history)}")
        if history and history[-1].role == 'user':
            print(f"DEBUG: Last user message: {history[-1].parts[0].text}")
            
        if not self.generation_responses:
            raise Exception("No more mocked responses")
        
        response_parts = self.generation_responses.pop(0)
        return mock_stream(response_parts)

    async def _get_all_tools(self):
        return []

    async def _run_tool(self, function_name, args, chat_id, network_id):
        print(f"DEBUG: Executing tool {function_name}")
        return {"status": "ok"}, "completed", None

    async def _emit_message_chunk(self, queue, text):
        pass
    
    async def _emit_tool_event(self, queue, tool, status, args_or_error):
        pass

    async def _handle_side_effects(self, *args):
        pass

async def test_forced_summary():
    agent = TestGraphVisAgent()
    
    # Queue mock
    queue = AsyncMock()
    
    # Scenario:
    # 1. Initial generation: Calls 'dummy_tool'
    # 2. Tool finishes.
    # 3. Next generation: Returns empty text. (Should trigger forced summary)
    # 4. Forced generation: Returns "Summary text".
    
    # Response 1: Tool Call
    fc = MagicMock()
    fc.name = "dummy_tool"
    fc.args = {"param": "value"}
    resp1 = [RealMockPart(function_call=fc)]
    
    # Response 2: Empty text
    resp2 = [RealMockPart(text="")] 
    
    # Response 3: Summary
    resp3 = [RealMockPart(text="Summary: Tool executed successfully.")]
    
    agent.generation_responses = [resp2, resp3]
    
    # We call _execute_tool_loop manually to skip the initial generation call in process_turn
    # mimic the initial response being passed in
    initial_stream = mock_stream(resp1)
    
    history = []
    
    print("Starting Loop...")
    final_text = await agent._execute_tool_loop(
        initial_response=initial_stream,
        history=history,
        all_tools=[],
        tool_config=None,
        queue=queue,
        chat_id=1,
        network_id=1
    )
    
    print(f"Final Text: {final_text}")
    
    assert "Summary: Tool executed successfully." in final_text
    print("TEST PASSED!")

if __name__ == "__main__":
    asyncio.run(test_forced_summary())
