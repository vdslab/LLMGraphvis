from google.genai import types

try:
    fc = types.FunctionCall(name="test", args={"a": 1})
    p_fc = types.Part(function_call=fc)
    c_model = types.Content(role="model", parts=[p_fc])
    
    p_fr = types.Part.from_function_response(name="test", response={"ok": 1})
    c_tool = types.Content(role="tool", parts=[p_fr])
    
    c_user = types.Content(role="user", parts=[types.Part.from_text(text="Please summarize")])
    
    # We don't have the API key to make an actual API call, but we can check if it's well-formed locally or we just know from Gemini docs.
    print("Parts constructed successfully.")
except Exception as e:
    print(f"Error: {e}")

