from google.genai import types

try:
    p = types.Part.from_function_response(name="test", response="just a string")
    print("string response OK")
except Exception as e:
    print(f"string response error: {e}")

