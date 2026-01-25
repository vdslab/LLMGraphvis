
import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def main():
    project_id = os.getenv("VERTEX_PROJECT_ID")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    api_key = os.getenv("GOOGLE_API_KEY")

    client = None
    if project_id:
        print(f"Using Vertex AI: {project_id}")
        client = genai.Client(vertexai=True, project=project_id, location=location)
    else:
        print("Using Google AI Studio")
        client = genai.Client(api_key=api_key)

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    print(f"Model: {model}")

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=1024),
    )

    try:
        response = await client.aio.models.generate_content_stream(
            model=model,
            contents="Why is the sky blue? Explain with thoughts.",
            config=config
        )

        async for chunk in response:
            if chunk.candidates:
                cand = chunk.candidates[0]
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        print("-" * 20)
                        print(f"Part keys: {dir(part)}")
                        
                        thought_val = getattr(part, "thought", "MISSING")
                        text_val = getattr(part, "text", "MISSING")
                        
                        print(f"part.thought type: {type(thought_val)}")
                        print(f"part.thought value: {thought_val}")
                        print(f"part.text type: {type(text_val)}")
                        # Print text/thought content (truncated)
                        if isinstance(thought_val, str):
                            print(f"Review thought: {thought_val[:50]}...")
                        if isinstance(text_val, str):
                            print(f"Review text: {text_val[:50]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
