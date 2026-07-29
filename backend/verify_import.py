import sys
import os

# Add backend path to sys.path
sys.path.append("/Users/takuma/develop/vdslab/master/GraphVisAgent/backend")

try:
    from app.services.llm import mcp_client
    print("Successfully imported mcp_client")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
