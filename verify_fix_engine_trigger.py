
import asyncio
import json
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Mock mcp_client before importing engine
sys.modules["app.services.llm.mcp_client"] = MagicMock()
from app.services.llm import engine
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
# Force engine logger to INFO
logging.getLogger("app.services.llm.engine").setLevel(logging.INFO)
print(f"Loaded engine from: {engine.__file__}")

async def verify_fix():
    print("Verifying context switch visualization trigger...")
    
    # Mock queue
    queue = AsyncMock()
    
    # Mock mcp_client.execute_tool
    engine.mcp_client.execute_tool = AsyncMock()
    engine.mcp_client.get_tools_as_gemini_functions = AsyncMock(return_value=[])
    engine.local_tools.get_local_tools = MagicMock(return_value=[])
    
    # Setup scenario: Tool returns new_network_id (context switch)
    # We want to ensure generate_visualization is CALLED for the new ID
    
    initial_network_id = 1
    new_network_id = 999
    
    # Simulate a tool execution result that causes context switch
    # We are testing the logic INSIDE the loop, but we can't easily run the loop because it depends on GenAI client.
    # However, the logic we changed is inside the `try...except` block where `function_result` is processed.
    
    # Actually, running the full `execute_tool_loop` is hard because of the GenAI client dependency.
    # But I can check if the code I wrote is valid by importing it (which I did).
    
    # To truly test the logic, I might need to mock the GenAI client too.
    
    # Let's try to mock the GenAI client response.
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = None
    mock_part.function_call = MagicMock()
    mock_part.function_call.name = "create_largest_component_subgraph"
    mock_part.function_call.args = {"network_id": initial_network_id}
    
    mock_candidate.content.parts = [mock_part]
    mock_response.candidates = [mock_candidate]
    
    # Mock client
    engine.client = MagicMock()
    engine.client.aio.models.generate_content = AsyncMock()
    
    # IMPORTANT: The loop runs until candidates are exhausted or max_iterations.
    # We need the second call to generate_content to return something without function call to stop the loop.
    mock_response_2 = MagicMock()
    mock_response_2.candidates = [] # End loop
    mock_response_2.text = "Done"
    
    engine.client.aio.models.generate_content.side_effect = [mock_response_2]
    
    # Mock MCP tool execution to return new network ID
    engine.mcp_client.execute_tool.side_effect = [
        {"new_network_id": new_network_id}, # First call: create_subgraph
        {"nodes": [], "edges": []}          # Second call: auto-generate visualization (The one we added!)
    ]
    
    # Run the loop
    # We pass the FIRST response (mock_response) as initial_response
    await engine.execute_tool_loop(
        initial_response=mock_response,
        network_id=initial_network_id,
        history=[],
        queue=queue,
        tool_config={},
        chat_id=1,
        db=MagicMock()
    )
    
    # Verify generate_visualization was called with new_network_id
    calls = engine.mcp_client.execute_tool.call_args_list
    print(f"MCP Calls: {calls}")
    
    found_vis_call = False
    for call in calls:
        if call[0][0] == "generate_visualization" and call[0][1].get("network_id") == new_network_id:
            found_vis_call = True
            break
            
    if found_vis_call:
        print("SUCCESS: generate_visualization was triggered for the new network ID.")
    else:
        print("FAILURE: generate_visualization was NOT triggered for the new network ID.")

if __name__ == "__main__":
    asyncio.run(verify_fix())
