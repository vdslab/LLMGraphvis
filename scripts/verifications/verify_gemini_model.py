import asyncio
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

async def verify_model():
    project_id = os.getenv("VERTEX_PROJECT_ID")
    location = os.getenv("VERTEX_LOCATION") or "global"
    api_key = os.getenv("GOOGLE_API_KEY")

    if project_id:
        print(f"Using Vertex AI with Project ID: {project_id}")
        client = genai.Client(vertexai=True, project=project_id, location=location)
    else:
        print("Using Google AI Studio with API Key")
        client = genai.Client(api_key=api_key)

    model_name = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
    thinking_level = os.getenv("GEMINI_THINKING_LEVEL") or "medium"
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents="Hello, are you working?",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=thinking_level,
                )
            ),
        )
        print(f"Model {model_name} is working. Response: {response.text}")
    except Exception as e:
        print(f"Model {model_name} failed: {e}")


if __name__ == "__main__":
    asyncio.run(verify_model())
