from google.genai import types

try:
    p = types.Part.from_function_call(name="test", args={"a": 1})
    print("from_function_call OK")
except Exception as e:
    print(f"from_function_call error: {e}")

