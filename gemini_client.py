import os
from dotenv import load_dotenv
from google import genai
import json

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_content(topic):
    prompt = f"""
    You are an expert presentation creator.
    Create a structured presentation on the topic: "{topic}".

    Output must be a valid JSON object with the following structure:
    {{
        "title": "Presentation Title",
        "slides": [
            {{
                "heading": "Slide 1 Heading",
                "bullet_points": [
                    "Point 1",
                    "Point 2",
                    "Point 3"
                ]
            }},
            ...
        ]
    }}

    Rules:
    - Create 4-5 slides.
    - Each slide should have 3-5 concise bullet points.
    - Content must be professional and informative.
    - Return ONLY the JSON. No Markdown formatting used.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config={
                'response_mime_type': 'application/json'
            }
        )
        
        # The new SDK handles JSON response types better if configured, 
        # but let's be safe and get text
        text = response.text.strip()
        
        # Cleanup code blocks just in case, though response_mime_type might handle it
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        return text.strip()
    except Exception as e:
        print(f"Error generating content: {e}")
        raise e
