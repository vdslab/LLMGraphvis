from google import genai
from google.genai import types

try:
    print(types.Content(role="user", parts=[types.Part.from_function_response(name="test", response={"result": "ok"})]))
    print(types.Content(role="tool", parts=[types.Part.from_function_response(name="test", response={"result": "ok"})]))
except Exception as e:
    print("Error:", e)
