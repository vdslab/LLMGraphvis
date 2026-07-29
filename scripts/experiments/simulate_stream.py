
import asyncio
from typing import List, Any

# Mock classes to simulate Gemini response parts
class Part:
    def __init__(self, text=None, thought=None):
        self.text = text
        self.thought = thought
        self.function_call = None

class Candidate:
    def __init__(self, parts):
        self.content = type('Content', (), {'parts': parts})()

class Chunk:
    def __init__(self, parts):
        self.candidates = [Candidate(parts)]

# Extracted logic from _consume_stream for testing
async def consume_stream_simulation(chunks):
    text_content = ""
    thought_content = ""
    in_simulated_thought = False
    
    print("--- Starting Stream Simulation ---")

    for chunk in chunks:
        if chunk.candidates:
            cand = chunk.candidates[0]
            if cand.content and cand.content.parts:
                for part in cand.content.parts:
                    is_thought = False
                    current_thought_text = ""

                    # Check for native thought
                    if hasattr(part, "thought") and isinstance(part.thought, str) and part.thought:
                        is_thought = True
                        current_thought_text = part.thought
                    elif hasattr(part, "thought") and isinstance(part.thought, bool) and part.thought:
                        is_thought = True
                        if part.text:
                            current_thought_text = part.text

                    if is_thought:
                        thought_content += current_thought_text
                        print(f"[EVENT: thinking_stream] {current_thought_text}")
                    elif part.text:
                        txt = part.text
                        
                        # Logic from engine.py
                        if not in_simulated_thought:
                            if "<thought>" in txt:
                                valid_text, rest = txt.split("<thought>", 1)
                                if valid_text:
                                    text_content += valid_text
                                    print(f"[EVENT: message_chunk] {valid_text}")
                                in_simulated_thought = True
                                txt = rest # Continue processing as thought
                            else:
                                text_content += txt
                                print(f"[EVENT: message_chunk] {txt}")
                                continue
                        
                        if in_simulated_thought:
                            if "</thought>" in txt:
                                t_content, rest_text = txt.split("</thought>", 1)
                                thought_content += t_content
                                print(f"[EVENT: thinking_stream] {t_content}")
                                in_simulated_thought = False
                                
                                if rest_text:
                                    text_content += rest_text
                                    print(f"[EVENT: message_chunk] {rest_text}")
                            else:
                                thought_content += txt
                                print(f"[EVENT: thinking_stream] {txt}")

    print("--- Final Result ---")
    print(f"Text Content: {text_content}")
    print(f"Thought Content: {thought_content}")

# Test Case 1: Standard Thinking Block at start
chunks1 = [
    Chunk([Part(text="<thought>I need to ch")]),
    Chunk([Part(text="eck the data.")]),
    Chunk([Part(text="</thought>OK, I will process it.")])
]

# Test Case 2: Thinking split across <thought> tag
chunks2 = [
    Chunk([Part(text="<thou")]),
    Chunk([Part(text="ght>Thinking...")]),
]

async def run_tests():
    print("\nTest Case 1: Standard Start")
    await consume_stream_simulation(chunks1)
    
    # print("\nTest Case 2: Split Tag (Known limitation check)")
    # await consume_stream_simulation(chunks2)

if __name__ == "__main__":
    asyncio.run(run_tests())
