import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)

try:
    print("Listing models...")
    # The SDK might have a different way to list models. 
    # Checking documentation or guessing common method.
    # Usually client.models.list() or similar.
    # Based on the error message "Call ListModels", it might be client.models.list()
    
    for model in client.models.list():
        print(f"Model: {model.name}")
        # print(f"  DisplayName: {model.display_name}")
        # print(f"  SupportedGenerationMethods: {model.supported_generation_methods}")
        print("-" * 20)
        
except Exception as e:
    print(f"Error listing models: {e}")
    # Try alternative method if SDK differs
    try:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GOOGLE_API_KEY)
        for m in genai_old.list_models():
            print(f"Old SDK Model: {m.name}")
            print(f"  Methods: {m.supported_generation_methods}")
    except Exception as e2:
        print(f"Error with old SDK: {e2}")
