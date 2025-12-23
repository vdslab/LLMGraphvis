
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath("backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.v1.endpoints.chat import create_chat
from app import models, schemas
from app.core.database import Base
from app.services.llm.history import build_history

# Setup in-memory DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def test_history_isolation():
    db = TestingSessionLocal()
    try:
        # Create User
        user = models.User(username="testuser", hashed_password="pw")
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create Network 1
        net1 = models.Network(name="Network 1")
        db.add(net1)
        db.commit()
        
        # Create Chat 1
        chat1 = models.Chat(name="Chat 1", user_id=user.id, network_id=net1.id)
        db.add(chat1)
        db.commit()
        
        # Add messages to Chat 1
        msg1 = models.ChatMessage(chat_id=chat1.id, role="user", content="User Msg 1")
        msg2 = models.ChatMessage(chat_id=chat1.id, role="model", content="Model Msg 1")
        db.add(msg1)
        db.add(msg2)
        db.commit()
        
        # Create Network 2
        net2 = models.Network(name="Network 2")
        db.add(net2)
        db.commit()
        
        # Create Chat 2
        chat2 = models.Chat(name="Chat 2", user_id=user.id, network_id=net2.id)
        db.add(chat2)
        db.commit()
        
        # Add messages to Chat 2
        msg3 = models.ChatMessage(chat_id=chat2.id, role="user", content="User Msg 2")
        db.add(msg3)
        db.commit()
        
        print(f"Chat 1 ID: {chat1.id}")
        print(f"Chat 2 ID: {chat2.id}")
        
        # Get History for Chat 2
        history_2 = build_history(chat2.id, "User Msg 2", db)
        
        print("\n--- History for Chat 2 ---")
        leak_found = False
        for content in history_2:
             # Check if any part contains "User Msg 1" or "Model Msg 1"
             for part in content.parts:
                 if hasattr(part, 'text') and part.text:
                     print(f"[{content.role}] {part.text}")
                     if "User Msg 1" in part.text or "Model Msg 1" in part.text:
                         leak_found = True
        
        if len(history_2) != 1:
             print(f"\n[FAIL] Expected history length 1, got {len(history_2)}")
             for content in history_2:
                 print(f"[{content.role}] {content.parts[0].text if content.parts else 'Empty'}")
        elif leak_found:
            print("\n[FAIL] Leakage detected! Messages from Chat 1 found in Chat 2 history.")
        else:
            print("\n[PASS] No leakage detected. History length strictly correct.")

    finally:
        db.close()

if __name__ == "__main__":
    test_history_isolation()
