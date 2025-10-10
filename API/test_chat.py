"""
Tests for chat endpoints.
"""

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock
import json

def test_create_conversation_success(client, auth_headers):
    """Test successful conversation creation."""
    conversation_data = {"title": "Test Conversation"}
    
    response = client.post(
        "/chat/conversations",
        headers=auth_headers,
        json=conversation_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == "Test Conversation"
    assert "id" in data
    assert data["user_id"] is not None
    assert data["network"] is not None  # Should create associated network

def test_create_conversation_with_default_title(client, auth_headers):
    """Test conversation creation with default title."""
    response = client.post(
        "/chat/conversations",
        headers=auth_headers,
        json={}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == "New Conversation"

def test_create_conversation_unauthorized(client):
    """Test conversation creation without authentication."""
    response = client.post("/chat/conversations", json={"title": "Test"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_get_conversations_success(client, auth_headers, test_conversation):
    """Test getting all conversations for user."""
    response = client.get("/chat/conversations", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(conv["id"] == test_conversation.id for conv in data)

def test_get_conversations_empty(client, auth_headers):
    """Test getting conversations when user has none."""
    response = client.get("/chat/conversations", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)

def test_get_conversation_by_id_success(client, auth_headers, test_conversation):
    """Test getting specific conversation by ID."""
    response = client.get(
        f"/chat/conversations/{test_conversation.id}",
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_conversation.id
    assert data["title"] == test_conversation.title

def test_get_conversation_by_id_not_found(client, auth_headers):
    """Test getting non-existent conversation."""
    response = client.get("/chat/conversations/99999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_get_conversation_different_user(client, db_session, test_conversation, test_user_data):
    """Test that users cannot access other users' conversations."""
    import auth
    import models
    
    # Create another user
    other_user_data = {"username": "otheruser", "password": "otherpass"}
    hashed_password = auth.get_password_hash(other_user_data["password"])
    other_user = models.User(
        username=other_user_data["username"],
        hashed_password=hashed_password
    )
    db_session.add(other_user)
    db_session.commit()
    
    # Get token for other user
    response = client.post("/auth/token", data=other_user_data)
    token = response.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access original user's conversation
    response = client.get(
        f"/chat/conversations/{test_conversation.id}",
        headers=other_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_get_messages_success(client, auth_headers, test_conversation, db_session, test_user):
    """Test getting messages from a conversation."""
    import models
    
    # Create some messages
    message1 = models.ChatMessage(
        content="Hello",
        role="user",
        user_id=test_user.id,
        conversation_id=test_conversation.id
    )
    message2 = models.ChatMessage(
        content="Hi there!",
        role="assistant",
        user_id=test_user.id,
        conversation_id=test_conversation.id
    )
    db_session.add_all([message1, message2])
    db_session.commit()
    
    response = client.get(
        f"/chat/conversations/{test_conversation.id}/messages",
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["content"] == "Hello"
    assert data[1]["content"] == "Hi there!"

def test_get_messages_empty_conversation(client, auth_headers, test_conversation):
    """Test getting messages from conversation with no messages."""
    response = client.get(
        f"/chat/conversations/{test_conversation.id}/messages",
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0

def test_get_messages_conversation_not_found(client, auth_headers):
    """Test getting messages from non-existent conversation."""
    response = client.get("/chat/conversations/99999/messages", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@patch('routers.chat.process_and_respond')
def test_create_message_success(mock_process, client, auth_headers, test_conversation):
    """Test creating a new message."""
    message_data = {"content": "Hello, how are you?", "role": "user"}
    
    response = client.post(
        f"/chat/conversations/{test_conversation.id}/messages",
        headers=auth_headers,
        json=message_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["content"] == "Hello, how are you?"
    assert data["role"] == "user"
    assert data["conversation_id"] == test_conversation.id
    
    # Verify background task was scheduled
    mock_process.assert_called_once()

def test_create_message_conversation_not_found(client, auth_headers):
    """Test creating message in non-existent conversation."""
    message_data = {"content": "Hello", "role": "user"}
    
    response = client.post(
        "/chat/conversations/99999/messages",
        headers=auth_headers,
        json=message_data
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_create_message_with_dict_content(client, auth_headers, test_conversation):
    """Test creating message with dictionary content."""
    message_data = {
        "content": {"type": "network_query", "query": "show centrality"},
        "role": "user"
    }
    
    response = client.post(
        f"/chat/conversations/{test_conversation.id}/messages",
        headers=auth_headers,
        json=message_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Content should be converted to JSON string
    assert isinstance(data["content"], str)

@patch('services.llm.process_chat_message')
@patch('httpx.AsyncClient')
def test_recommend_layout_success(mock_client_class, mock_llm, client, auth_headers):
    """Test layout recommendation endpoint."""
    # Mock LLM response
    mock_llm.return_value = {
        "content": '{"recommended_layout": "spring", "explanation": "Good for general networks", "recommended_parameters": {"iterations": 50}}'
    }
    
    request_data = {
        "description": "A social network with communities",
        "purpose": "Identify community structures"
    }
    
    response = client.post(
        "/chat/recommend-layout",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["recommended_layout"] == "spring"
    assert "explanation" in data
    assert "recommended_parameters" in data

def test_recommend_layout_missing_params(client, auth_headers):
    """Test layout recommendation with missing parameters."""
    response = client.post(
        "/chat/recommend-layout",
        headers=auth_headers,
        json={"description": "A network"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@patch('services.llm.process_chat_message')
def test_recommend_layout_llm_error(mock_llm, client, auth_headers):
    """Test layout recommendation when LLM returns invalid JSON."""
    # Mock LLM to return invalid JSON
    mock_llm.return_value = {"content": "This is not valid JSON"}
    
    request_data = {
        "description": "A network",
        "purpose": "General visualization"
    }
    
    response = client.post(
        "/chat/recommend-layout",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should fallback to default
    assert data["recommended_layout"] == "spring"

@patch('services.llm.process_chat_message')
@patch('httpx.AsyncClient')
def test_process_chat_with_tool_call(mock_client_class, mock_llm, client, auth_headers):
    """Test processing chat message that triggers a tool call."""
    # Mock LLM to return a tool call
    mock_llm.side_effect = [
        {
            "tool_calls": [{
                "function": {
                    "name": "change_layout",
                    "arguments": {"layout_type": "spring"}
                }
            }]
        },
        {
            "content": "I've applied the spring layout to your network."
        }
    ]
    
    # Mock NetworkX MCP response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "success": True,
            "layout_type": "spring",
            "positions": {"1": {"x": 0, "y": 0}}
        }
    }
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    request_data = {"message": "Apply spring layout to the network"}
    
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "content" in data
    assert "conversation_id" in data
    assert data["networkUpdate"] is not None

@patch('services.llm.process_chat_message')
def test_process_chat_without_tool_call(mock_llm, client, auth_headers):
    """Test processing chat message that doesn't trigger a tool call."""
    # Mock LLM to return direct response
    mock_llm.return_value = {
        "content": "Hello! How can I help you with your network analysis today?"
    }
    
    request_data = {"message": "Hello"}
    
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "Hello!" in data["content"]
    assert data["networkUpdate"] is None

def test_process_chat_missing_message(client, auth_headers):
    """Test processing chat with missing message."""
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json={}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@patch('services.llm.process_chat_message')
def test_process_chat_creates_conversation_if_none_exists(mock_llm, client, auth_headers):
    """Test that process chat creates a conversation if none exists."""
    mock_llm.return_value = {"content": "Hello!"}
    
    request_data = {"message": "Hello"}
    
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "conversation_id" in data

@patch('services.llm.process_chat_message')
def test_process_chat_with_specific_conversation(mock_llm, client, auth_headers, test_conversation):
    """Test processing chat with specific conversation ID."""
    mock_llm.return_value = {"content": "Response for specific conversation"}
    
    request_data = {
        "message": "Hello",
        "conversation_id": test_conversation.id
    }
    
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["conversation_id"] == test_conversation.id

def test_process_chat_invalid_conversation_id(client, auth_headers):
    """Test processing chat with invalid conversation ID."""
    request_data = {
        "message": "Hello",
        "conversation_id": 99999
    }
    
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json=request_data
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

@patch('services.llm.process_chat_message')
@patch('httpx.AsyncClient')
def test_process_chat_tool_call_error(mock_client_class, mock_llm, client, auth_headers):
    """Test processing chat when tool call fails."""
    # Mock LLM to return a tool call
    mock_llm.side_effect = [
        {
            "tool_calls": [{
                "function": {
                    "name": "change_layout",
                    "arguments": {"layout_type": "spring"}
                }
            }]
        },
        {
            "content": "I encountered an error while processing your request."
        }
    ]
    
    # Mock NetworkX MCP error response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    request_data = {"message": "Apply spring layout"}
    
    response = client.post(
        "/chat/process",
        headers=auth_headers,
        json=request_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    # Should still return content even if tool failed
    assert "content" in data

def test_create_empty_graphml():
    """Test the create_empty_graphml helper function."""
    from routers.chat import create_empty_graphml
    
    graphml_content = create_empty_graphml()
    assert isinstance(graphml_content, str)
    assert "<?xml" in graphml_content
    assert "graphml" in graphml_content

class TestMessagePersistence:
    """Test that messages are properly saved to database."""
    
    def test_user_message_saved(self, client, auth_headers, test_conversation, db_session):
        """Test that user messages are saved to database."""
        message_data = {"content": "Test message", "role": "user"}
        
        response = client.post(
            f"/chat/conversations/{test_conversation.id}/messages",
            headers=auth_headers,
            json=message_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check message was saved
        import models
        message = db_session.query(models.ChatMessage).filter(
            models.ChatMessage.content == "Test message"
        ).first()
        assert message is not None
        assert message.role == "user"
        assert message.conversation_id == test_conversation.id
    
    @patch('services.llm.process_chat_message')
    def test_assistant_message_saved_during_process(self, mock_llm, client, auth_headers, db_session):
        """Test that assistant messages are saved during processing."""
        mock_llm.return_value = {"content": "Assistant response"}
        
        request_data = {"message": "Hello"}
        
        response = client.post(
            "/chat/process",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check both user and assistant messages were saved
        import models
        messages = db_session.query(models.ChatMessage).all()
        
        user_msg = next((m for m in messages if m.role == "user"), None)
        assistant_msg = next((m for m in messages if m.role == "assistant"), None)
        
        assert user_msg is not None
        assert assistant_msg is not None
        assert assistant_msg.content == "Assistant response"