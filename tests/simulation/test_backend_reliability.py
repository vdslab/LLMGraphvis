import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
# Add backend to path - INSERT at 0 to ensure it overrides any other 'app' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

# Mock dependencies BEFORE imports
sys.modules["common"] = MagicMock()
sys.modules["common.models"] = MagicMock()
sys.modules["app.core.database"] = MagicMock()
sys.modules["app.core.logging"] = MagicMock()
sys.modules["app.services.llm"] = MagicMock()
sys.modules["app.services.llm"].engine = MagicMock()
sys.modules["app.services.llm"].mcp_client = MagicMock()

# Now import the module to test
from app.api.v1.endpoints import chat
from common import models

# Configure ChatMessage to return an instance with a real ID
mock_msg_instance = MagicMock()
mock_msg_instance.id = 999
models.ChatMessage.return_value = mock_msg_instance

async def test_error_persistence():
    print("Testing Error Persistence in Background Task...")
    
    # Setup Mocks
    mock_db_session = MagicMock()
    chat.database.SessionLocal.return_value = mock_db_session
    
    # Mock LLM service to raise exception
    chat.llm_service.process_chat = AsyncMock(side_effect=ValueError("Simulated LLM Failure"))
    
    # Mock Event Queue
    mock_queue = AsyncMock()
    # Correctly setup async function mock
    chat.llm_service.get_event_queue = AsyncMock(return_value=mock_queue)

    # Execute
    await chat.handle_process_background(chat_id=123, user_message="test message")
    
    # Verification
    # 1. Verify Error was caught and DB session for error was created
    # Note: handle_process_background opens a session at start, puts it in 'db', then fails.
    # Then it opens a NEW session 'db_error' in the except block.
    # So SessionLocal should be called at least twice.
    assert chat.database.SessionLocal.call_count >= 2
    
    # 2. Verify we added a model message to the DB
    # We check if db_error.add was called with a ChatMessage model
    # Since we mocked common.models, we can check if the mocked class was instantiated
    # but exact argument matching on the instance might be tricky if we don't hold the reference.
    # However, we can check mock_db_session.add call args.
    
    # Get all calls to add
    add_calls = mock_db_session.add.call_args_list
    
    found_error_msg = False
    for call in add_calls:
        arg = call[0][0] # The object passed to add()
        # Check if it looks like our error message
        # Since models.ChatMessage is a Mock, we assume the code did: models.ChatMessage(...)
        # We can check if the role='model' was passed to the constructor of the mock
        if hasattr(arg, 'role') and arg.role == 'model': 
             # Wait, if we mocked models.ChatMessage, 'arg' is the instance returned by the constructor.
             # We need to configure the mock to store its init args or check the constructor call.
             pass

    # Alternative: Check models.ChatMessage constructor calls
    constructor_calls = models.ChatMessage.call_args_list
    error_msg_created = False
    for call in constructor_calls:
        kwargs = call[1]
        if kwargs.get('role') == 'model' and "Simulated LLM Failure" in kwargs.get('content', ''):
            error_msg_created = True
            break
            
    if error_msg_created:
        print("✅ SUCCESS: Error message model was created.")
    else:
        print("❌ FAILURE: Error message model was NOT created.")
        print(f"Constructor calls: {constructor_calls}")

    assert error_msg_created
    
    # 3. Verify 'message_complete' event was sent for the error message
    # We expect queue.put called with event: 'message_complete'
    # and event: 'error'
    
    put_calls = mock_queue.put.call_args_list
    events = [json.loads(str(c[0][0]).replace("'", '"')) if isinstance(c[0][0], str) else c[0][0] for c in put_calls]
    # Simplify: just check arguments
    
    found_completion_event = False
    found_error_event = False
    
    for call in put_calls:
        data = call[0][0] # dict
        if data.get('event') == 'message_complete':
            found_completion_event = True
        if data.get('event') == 'error':
            found_error_event = True
            
    if found_completion_event:
        print("✅ SUCCESS: 'message_complete' event emitted.")
    else:
        print("❌ FAILURE: 'message_complete' event NOT emitted.")
        
    if found_error_event:
        print("✅ SUCCESS: 'error' event emitted.")
    else:
        print("❌ FAILURE: 'error' event NOT emitted.")
        
    assert found_completion_event
    assert found_error_event
    
    print("Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_error_persistence())
