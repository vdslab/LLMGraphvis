import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def main():
    project_id = os.getenv("VERTEX_PROJECT_ID")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    api_key = os.getenv("GOOGLE_API_KEY")

    if project_id:
        print(f"Using Vertex AI (Project: {project_id}, Location: {location})")
        client = genai.Client(vertexai=True, project=project_id, location=location)
    else:
        print("Using AI Studio (API Key)")
        client = genai.Client(api_key=api_key)
    
    # Use 2.5 flash
    model = "gemini-2.0-flash-thinking-exp-01-21"
    
    print(f"Testing {model} with thinking_budget=2048...")
    
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=2048)
    )
    
    prompt = "Solve this logic puzzle: Three gods A, B, and C are called True, False, and Random. True always speaks truly, False always speaks falsely, but whether Random speaks truly or falsely is a completely random matter. Your task is to determine the identities of A, B, and C by asking three yes-no questions; each question must be put to exactly one god. The gods understand English, but will answer all questions in their own language, in which the words for yes and no are da and ja, in some order. You do not know which word means which. Explain your reasoning step by step."

    try:
        response = await client.aio.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=config
        )
        
        has_thought = False
        async for chunk in response:
            if chunk.candidates:
                cand = chunk.candidates[0]
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        # Inspect Raw Part
                        # print(f"Part keys: {dir(part)}")
                        
                        th = getattr(part, "thought", None)
                        val_str = "None"
                        if th is not None:
                            val_str = f"{type(th)} val={th}"
                        
                        txt = getattr(part, "text", "")
                        
                        print(f"Chunk Part: thought={val_str}, textlen={len(txt)}")
                        if hasattr(part, "thought") and part.thought:
                            has_thought = True
                            print(f"!!! FOUND THOUGHT: {part.thought} !!!")
                            
        if not has_thought:
            print("No thought detected in stream.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
