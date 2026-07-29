import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()

async def verify_model():
    project_id = os.getenv("VERTEX_PROJECT_ID")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    api_key = os.getenv("GOOGLE_API_KEY")

    if project_id:
        print(f"Using Vertex AI with Project ID: {project_id}")
        client = genai.Client(vertexai=True, project=project_id, location=location)
    else:
        print("Using Google AI Studio with API Key")
        client = genai.Client(api_key=api_key)

    model_name = "gemini-2.5-flash"
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents="Hello, are you working?"
        )
        print(f"Model {model_name} is working. Response: {response.text}")
    except Exception as e:
        print(f"Model {model_name} failed: {e}")
        
    # Also try the preview version if the above fails or just to check
    model_name_preview = "gemini-2.5-flash-preview-09-2025"
    try:
        response = await client.aio.models.generate_content(
            model=model_name_preview,
            contents="Hello, are you working?"
        )
        print(f"Model {model_name_preview} is working. Response: {response.text}")
    except Exception as e:
        print(f"Model {model_name_preview} failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_model())
