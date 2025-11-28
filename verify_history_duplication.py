import sys
import unittest
from unittest.mock import MagicMock
from google.genai import types

# Mocking the module imports since we are running this as a standalone script
# and don't want to load the entire app context if possible, 
# but we need to import the specific function.
# However, importing _build_history requires importing llm_service, which imports other things.
# Let's try to import it directly, assuming the python path is set correctly or we run it from root.

# Add backend to sys.path
sys.path.append("backend")

from app.services.llm_service import _build_history
from app import models

class TestHistoryDuplication(unittest.TestCase):
    def test_build_history_duplication(self):
        # Mock DB Session
        mock_db = MagicMock()
        
        # Mock Chat ID and User Message
        chat_id = 1
        user_message = "Hello, world!"
        
        # Mock DB Query Results
        # Scenario: The message has ALREADY been saved to the DB by chat.py
        mock_message = models.ChatMessage(
            chat_id=chat_id,
            role="user",
            content=user_message
        )
        
        # Mock the chain: db.query(...).filter(...).order_by(...).all()
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order_by = mock_filter.order_by.return_value
        mock_order_by.all.return_value = [mock_message]
        
        # Call the function
        history = _build_history(chat_id, user_message, mock_db)
        
        # Filter for user messages in the history (excluding few-shot if any, or just check the end)
        # The function returns a list of types.Content
        
        # Let's inspect the last few messages.
        # We expect the few-shot examples, then the history from DB, then the user_message appended.
        
        # If the bug exists:
        # History from DB: "Hello, world!"
        # Appended: "Hello, world!"
        # Total at end: "Hello, world!", "Hello, world!"
        
        print(f"Total history length: {len(history)}")
        
        last_message = history[-1]
        second_last_message = history[-2]
        
        print(f"Last message role: {last_message.role}")
        print(f"Last message content: {last_message.parts[0].text}")
        
        print(f"2nd Last message role: {second_last_message.role}")
        print(f"2nd Last message content: {second_last_message.parts[0].text}")
        
        # Check for duplication at the end
        is_duplicated = (
            last_message.role == "user" and 
            last_message.parts[0].text == user_message and
            second_last_message.role == "user" and
            second_last_message.parts[0].text == user_message
        )
        
        if is_duplicated:
            print("FAILURE: Duplicate user message detected!")
        else:
            print("SUCCESS: No duplication detected.")
            
        self.assertFalse(is_duplicated, "User message is duplicated in history!")

if __name__ == '__main__':
    unittest.main()
