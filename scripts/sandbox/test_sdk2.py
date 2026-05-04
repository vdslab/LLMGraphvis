from google.genai import types

try:
    fc = types.FunctionCall(name="test", args={"a": 1})
    p = types.Part(function_call=fc)
    c = types.Content(role="model", parts=[p])
    print("function_call OK")
except Exception as e:
    print(f"function_call error: {e}")

