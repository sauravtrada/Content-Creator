import os
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load env from the project root
load_dotenv(r"e:\Nirma\SEM-2\gemini-content-generator\.env", override=True)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Try line 1 directly if env load failed
    api_key = "AIzaSyBtV6DgtsZvKQP9JZ1jTbKZCTBEFHBUFuY"

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", 
    google_api_key=api_key
)

def extract_json(text):
    import re
    match = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match: return json.loads(match.group(1))
    match = re.search(r"(\[.*\])", text, re.DOTALL)
    if match: return json.loads(match.group(1))
    return None

current_slides = [
    {
        "heading": "Intro to AI",
        "layout": "text_only",
        "content": [{"text": "AI is changing the world", "level": 0}]
    }
]

instruction = "Add a new slide about robots with an image of a humanoid robot"

prompt = f"""
You are a professional presentation editor. 
Current Slides (JSON list):
{json.dumps(current_slides, indent=2)}

User Instruction:
"{instruction}"

Update the presentation according to the instruction. 
- You can MODIFY existing slides, DELETE slides, or **ADD NEW SLIDES** (by appending them to the list).
- If the user asks for a **NEW SLIDE**, create a new slide object with a logical heading and content.
- **IMAGES**: If the user asks for an image (on a new or existing slide):
  1. You MUST include: "image_search_query": "a descriptive 3-5 word query for a high-quality photo"
  2. You MUST set "layout": "split".
- **VISUALS**: For any slide with a chart or table, set "layout": "split". Otherwise use "layout": "text_only".
- STRUCTURE: Ensure the "content" field is a list of objects: [{{ "text": "point", "level": 0 }}].
- Return ONLY the updated JSON list of slides. No preamble.

Updated JSON:
"""

print("--- Sending Request to AI ---")
response = llm.invoke(prompt)
print("--- Response Received ---")
print(response.content)

updated_slides = extract_json(response.content)

if updated_slides:
    print("\n--- Parsed JSON Success ---")
    print(json.dumps(updated_slides, indent=2))
    
    # Validation logic
    has_new_slide = len(updated_slides) > len(current_slides)
    has_image = any(s.get("image_search_query") for s in updated_slides)
    has_split = any(s.get("layout") == "split" for s in updated_slides if s.get("image_search_query"))
    
    print(f"\nResults:")
    print(f"- New slide added: {has_new_slide}")
    print(f"- Image query present: {has_image}")
    print(f"- Layout set to 'split': {has_split}")
    
    if has_new_slide and has_image and has_split:
        print("\nVERIFICATION PASSED!")
    else:
        print("\nVERIFICATION FAILED (checks not met)")
else:
    print("\n--- Failed to parse JSON ---")
