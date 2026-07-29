from google.genai import types

try:
    p = types.Part.from_function_response(name="test", response={"ok": 1})
    c = types.Content(role="tool", parts=[p])
    print("tool OK")
except Exception as e:
    print(f"tool error: {e}")

try:
    c2 = types.Content(role="user", parts=[p])
    print("user OK")
except Exception as e:
    print(f"user error: {e}")
