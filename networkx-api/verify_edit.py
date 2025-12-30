import asyncio
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(__file__))

# Handle imports depending on run location
try:
    from app.mcp_server import mcp
    from app.core import database
    from common import models
except ImportError:
    from backend.app.mcp_server import mcp
    from backend.app.core import database
    from common import models

def get_db():
    return database.SessionLocal()

async def verify_edit_tool():
    print("=== Verifying Edit Tool ===")
    db = get_db()
    test_net = None
    try:
        # 1. Create Test Network
        test_net = models.Network(name="Edit Verification Network")
        db.add(test_net)
        db.commit()
        db.refresh(test_net)
        print(f"Created network: {test_net.id}")

        # 2. Add Test Node
        node = models.Node(network_id=test_net.id, node_id="test_node_1", label="Original Label")
        db.add(node)
        db.commit()
        print(f"Created node: {node.node_id} with label '{node.label}'")

        # 3. Call Tool to Update Label
        print("Calling update_node_label...")
        result = await mcp.call_tool("update_node_label", {
            "network_id": test_net.id,
            "node_id": "test_node_1",
            "new_label": "New Updated Label"
        })
        print(f"Tool Result: {result}")

        # 4. Verify in DB
        db.refresh(node)
        print(f"Node label in DB: '{node.label}'")

        if node.label == "New Updated Label":
            print("✅ PASS: Node label updated successfully.")
        else:
            print(f"❌ FAIL: Node label mismatch. Expected 'New Updated Label', got '{node.label}'")

    except Exception as e:
        print(f"❌ FAIL: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if test_net:
            # Cleanup
            db.delete(test_net) # Cascades to node
            db.commit()
            print("Cleaned up test network.")
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_edit_tool())
