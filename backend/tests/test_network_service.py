import pytest
from common import models
from app.services.network_service import NetworkService

def test_verify_network_access_direct_ownership(db):
    # Setup
    user = models.User(id=1, username="testuser", hashed_password="pw")
    network = models.Network(id=10, name="Test Network")
    chat = models.Chat(id=100, user_id=1, network_id=10, name="Test Chat")
    
    db.add(user)
    db.add(network)
    db.add(chat)
    db.commit()

    # Test
    allowed = NetworkService.verify_network_access(network.id, user.id, db)
    assert allowed is True

def test_verify_network_access_denied(db):
    # Setup
    user = models.User(id=1, username="testuser", hashed_password="pw")
    user2 = models.User(id=2, username="other", hashed_password="pw")
    network = models.Network(id=10, name="Test Network")
    chat = models.Chat(id=100, user_id=2, network_id=10, name="Test Chat")
    
    db.add(user)
    db.add(user2)
    db.add(network)
    db.add(chat)
    db.commit()

    # Test
    allowed = NetworkService.verify_network_access(network.id, user.id, db)
    assert allowed is False

def test_verify_network_access_subgraph(db):
    # Setup
    user = models.User(id=1, username="testuser", hashed_password="pw")
    
    # Parent Network
    parent_net = models.Network(id=10, name="Parent Network")
    parent_chat = models.Chat(id=100, user_id=1, network_id=10, name="Parent Chat")
    
    # Subgraph (child of 10)
    child_net = models.Network(id=11, name="Child Network", parent_network_id=10)
    # Subgraph has no direct chat for this user yet, but user owns parent
    
    db.add(user)
    db.add(parent_net)
    db.add(parent_chat)
    db.add(child_net)
    db.commit()

    # Test
    # Access to child should be allowed because user has access to parent (via chat 100)
    allowed = NetworkService.verify_network_access(child_net.id, user.id, db)
    assert allowed is True

def test_verify_network_access_subgraph_nested(db):
    # Setup
    user = models.User(id=1, username="testuser", hashed_password="pw")
    
    # Grandparent
    g_net = models.Network(id=10, name="Grandparent")
    g_chat = models.Chat(id=100, user_id=1, network_id=10, name="G Chat")
    
    # Parent (child of 10)
    p_net = models.Network(id=11, name="Parent", parent_network_id=10)
    
    # Child (child of 11)
    c_net = models.Network(id=12, name="Child", parent_network_id=11)
    
    db.add(user)
    db.add(g_net)
    db.add(g_chat)
    db.add(p_net)
    db.add(c_net)
    db.commit()

    # Test
    allowed = NetworkService.verify_network_access(c_net.id, user.id, db)
    assert allowed is True

def test_verify_network_access_subgraph_denied(db):
    # Setup
    user = models.User(id=1, username="testuser", hashed_password="pw")
    other_user = models.User(id=2, username="other", hashed_password="pw")
    
    # Parent owned by other
    parent_net = models.Network(id=10, name="Parent")
    parent_chat = models.Chat(id=100, user_id=2, network_id=10, name="P Chat")
    
    # Child
    child_net = models.Network(id=11, name="Child", parent_network_id=10)
    
    db.add(user)
    db.add(other_user)
    db.add(parent_net)
    db.add(parent_chat)
    db.add(child_net)
    db.commit()

    # Test
    allowed = NetworkService.verify_network_access(child_net.id, user.id, db)
    assert allowed is False
