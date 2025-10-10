"""
Test basic import functionality and structure validation.
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("validation_test")


def test_core_modules():
    """Test core module imports."""
    try:
        from core.context import ServerContext
        logger.info("✓ Core context module imported successfully")

        context = ServerContext()
        stats = context.get_cache_stats()
        logger.info(f"✓ ServerContext created and working: {stats}")

        return True
    except Exception as e:
        logger.error(f"✗ Core module test failed: {e}")
        return False


def test_tool_modules():
    """Test tool module structure."""
    tools_to_test = [
        "network_operations",
        "layout_algorithms",
        "centrality_metrics",
        "graph_io",
        "visualization"
    ]

    success_count = 0
    for tool_name in tools_to_test:
        try:
            module = __import__(f"tools.{tool_name}", fromlist=[
                                f"register_{tool_name.replace('_', '_')}_tools"])
            logger.info(f"✓ Tool module {tool_name} imported successfully")
            success_count += 1
        except Exception as e:
            logger.warning(f"⚠ Tool module {tool_name} import failed: {e}")

    logger.info(
        f"Tool modules: {success_count}/{len(tools_to_test)} imported successfully")
    return success_count > 0


def test_resource_modules():
    """Test resource module structure."""
    try:
        from resources.graph_resources import register_graph_resources
        from resources.cache_resources import register_cache_resources
        logger.info("✓ Resource modules imported successfully")
        return True
    except Exception as e:
        logger.warning(f"⚠ Resource modules import failed: {e}")
        return False


def test_server_structure():
    """Test server module structure."""
    try:
        # Test if server module can be imported
        import server
        logger.info("✓ Server module imported successfully")

        # Test if main tools are accessible
        if hasattr(server, 'mcp'):
            logger.info("✓ MCP server instance found")
        else:
            logger.warning("⚠ MCP server instance not found")

        return True
    except Exception as e:
        logger.warning(f"⚠ Server module test failed: {e}")
        return False


def main():
    """Run all validation tests."""
    logger.info("Starting NetworkX MCP structure validation...")
    logger.info("=" * 50)

    tests = [
        ("Core Modules", test_core_modules),
        ("Tool Modules", test_tool_modules),
        ("Resource Modules", test_resource_modules),
        ("Server Structure", test_server_structure)
    ]

    results = {}
    for test_name, test_func in tests:
        logger.info(f"\nTesting {test_name}...")
        results[test_name] = test_func()

    logger.info("\n" + "=" * 50)
    logger.info("VALIDATION SUMMARY:")

    success_count = 0
    for test_name, success in results.items():
        status = "PASS" if success else "FAIL"
        logger.info(f"{test_name}: {status}")
        if success:
            success_count += 1

    logger.info(f"\nOverall: {success_count}/{len(tests)} tests passed")

    if success_count == len(tests):
        logger.info("🎉 All tests passed! MCP structure is valid.")
        return 0
    elif success_count > 0:
        logger.warning("⚠ Some tests passed. Structure is partially working.")
        return 1
    else:
        logger.error("❌ All tests failed. Structure needs work.")
        return 2


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
