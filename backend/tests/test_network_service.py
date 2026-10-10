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


def _tree_with_chat_on_subgraph(db):
    """User 1's chat has switched into subgraph 11; 12 is a sibling of 11."""
    db.add_all(
        [
            models.User(id=1, username="owner", hashed_password="pw"),
            models.User(id=2, username="other", hashed_password="pw"),
            models.Network(id=10, name="Root"),
            models.Network(id=11, name="Sub A", parent_network_id=10),
            models.Network(id=12, name="Sub B", parent_network_id=10),
            models.Network(id=20, name="Other root"),
            models.Chat(id=100, user_id=1, network_id=11, name="Chat"),
            models.Chat(id=200, user_id=2, network_id=20, name="Other chat"),
        ]
    )
    db.commit()


def test_chat_on_subgraph_still_owns_root_and_siblings(db):
    _tree_with_chat_on_subgraph(db)
    assert NetworkService.verify_network_access(10, 1, db) is True
    assert NetworkService.verify_network_access(12, 1, db) is True


def test_chat_on_subgraph_does_not_grant_other_trees(db):
    _tree_with_chat_on_subgraph(db)
    assert NetworkService.verify_network_access(20, 1, db) is False
    assert NetworkService.verify_network_access(10, 2, db) is False


def test_missing_network_is_denied(db):
    _tree_with_chat_on_subgraph(db)
    assert NetworkService.verify_network_access(999, 1, db) is False


def test_parent_cycle_is_denied_not_looped(db):
    db.add_all(
        [
            models.User(id=1, username="owner", hashed_password="pw"),
            models.Network(id=30, name="A"),
            models.Network(id=31, name="B", parent_network_id=30),
        ]
    )
    db.commit()
    db.get(models.Network, 30).parent_network_id = 31
    db.add(models.Chat(id=100, user_id=1, network_id=30, name="Chat"))
    db.commit()
    assert NetworkService.root_network_id(31, db) is None
    assert NetworkService.verify_network_access(31, 1, db) is False
