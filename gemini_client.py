import os
from dotenv import load_dotenv
from google import genai
import json

load_dotenv(override=True)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_content(topic, include_images=False):
    
    image_instruction = ""
    if include_images:
        image_instruction = """
        - For each slide, also include a field "image_search_query" which is a concise 2-4 word string to find a relevant image for that slide.
        """

    prompt = f"""
    You are an expert presentation creator.
    Create a structured presentation on the topic: "{topic}".

    Output must be a valid JSON object with the following structure:
    {{
        "title": "Presentation Title",
        "slides": [
            {{
                "heading": "Slide 1 Heading",
                "content": [
                    {{ "text": "Main Point 1", "level": 0 }},
                    {{ "text": "Sub-point detail", "level": 1 }},
                    {{ "text": "Main Point 2", "level": 0 }}
                ],
                "image_search_query": "relevant search terms" 
            }},
            ...
        ]
    }}

    Rules:
    - Create 4-5 slides.
    - MAXIMUM 5 lines of content per slide to prevent overflow.
    - "text" must be extremely concise (max 10 words).
    - Use "level": 0 for main points, "level": 1 for sub-points.
    - Content must be professional and informative.
    - Return ONLY the JSON. No Markdown formatting used.
    {image_instruction}
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
