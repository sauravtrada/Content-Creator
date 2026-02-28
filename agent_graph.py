import os
import json
from typing import TypedDict, List, Dict, Any, Annotated
import operator
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

# Force load Env
load_dotenv(override=True)

# --- 1. State Definition ---
class AgentState(TypedDict):
    topic: str
    include_images: bool
    image_mode: str
    presentation_title: str
    num_slides: int
    tone: str
    audience: str
    additional_instructions: str
    outline: List[str]      # List of Slide Headers
    theme: Dict[str, Any]   # Theme colors and fonts
    slides: List[Dict[str, Any]] # List of slide objects
    final_output: str       # The final JSON string for the app

# --- 2. LLM Setup ---
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY not found in environment variables")

llm = ChatGoogleGenerativeAI(
    #model="gemini-2.0-flash", 
    model="gemini-2.5-flash", 
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7,
    max_retries=3
)

# --- Helper: Robust JSON Extraction ---
def extract_json(text):
    """
    Extracts JSON from a string, handling markdown code blocks and extra text.
    """
    import re
    try:
        # 1. Try to find JSON within ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # 2. Try to find the first '{' and the last '}'
        # This is a fallback if no markdown blocks are found
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
             return json.loads(match.group(1))
        
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
             return json.loads(match.group(1))

        # 3. Try raw parsing
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError):
        return None

# --- 3. Node Functions ---

def planner_node(state: AgentState):
    """
    Agent 1: Planner
    Breaks the topic into a structured outline (titles).
    """
    print(f"--- [Planner] Planning topic: {state['topic']} ---")
    
    num_slides = state.get('num_slides', 5)
    tone = state.get('tone', 'professional')
    audience = state.get('audience', 'general audience')
    instructions = state.get('additional_instructions', '')
    
    prompt = f"""
    You are an expert presentation planner.
    Topic: "{state['topic']}"
    Target Audience: "{audience}"
    Tone: "{tone}"
    Additional Instructions: "{instructions}"
    
    Task: Generate a {num_slides}-slide outline for this topic.
    Return ONLY a JSON object with this structure:
    {{
        "title": "Main Presentation Title",
        "outline": ["Slide 1 Title", "Slide 2 Title", ... "Slide {num_slides} Title"]
    }}
    
    CRITICAL RULE: Slide Titles in the `outline` array MUST be short and punchy. Maximum 3 to 5 words per title. DO NOT write long sentences for slide titles.
    """
    
    response = llm.invoke(prompt)
    data = extract_json(response.content)
    
    if data:
        return {
            "presentation_title": data.get("title", state['topic']),
            "outline": data.get("outline", [])
        }
    else:
        # Fallback if JSON fails
        return {
            "presentation_title": state['topic'],
            "outline": [f"Slide {i+1} for {state['topic']}" for i in range(state.get('num_slides', 5))]
        }

def designer_node(state: AgentState):
    """
    Agent 1.5: Designer
    Generates a color palette and font pairing based on the topic.
    """
    print(f"--- [Designer] Designing theme for: {state['topic']} ---")
    
    tone = state.get('tone', 'professional')
    
    prompt = f"""
    You are an expert presentation designer.
    Topic: "{state['topic']}"
    Tone: "{tone}"
    
    Task: Design a modern, beautiful color palette and font pairing for this presentation.
    
    Output Format:
    Return ONLY a JSON object with this structure:
    {{
        "font": "Font Name (e.g. Arial, Calibri, Tahoma, Verdana, Trebuchet MS)", 
        "color_primary": "HEX_CODE (e.g. 0E2A47)",
        "color_accent": "HEX_CODE",
        "color_background": "HEX_CODE",
        "color_text_main": "HEX_CODE",
        "color_text_light": "HEX_CODE"
    }}
    
    Rules:
    - Omit the '#' in hex codes.
    - Ensure high contrast: if background is dark, text must be light, and vice versa.
    """
    
    response = llm.invoke(prompt)
    data = extract_json(response.content)
    
    if data:
        return {"theme": data}
    else:
        # Fallback theme
        return {"theme": {
            "font": "Calibri",
            "color_primary": "0E2A47",
            "color_accent": "009688",
            "color_background": "FAFAFA",
            "color_text_main": "404040",
            "color_text_light": "757575"
        }}

def content_node(state: AgentState):
    """
    Agent 2: Content Writer
    Takes the outline and generates detailed content + image prompts for each slide.
    """
    print(f"--- [Writer] Writing content for {len(state['outline'])} slides ---")
    
    outline_str = "\\n".join(f"- {title}" for title in state['outline'])
    
    image_instruction = ""
    if state['include_images']:
        image_instruction = """
        - For each slide, include an "image_search_query" (2-4 words) to find a relevant image.
        """
        
    prompt = f"""
    You are a professional presentation content writer.
    Presentation Title: "{state['presentation_title']}"
    Target Audience: "{state.get('audience', 'general audience')}"
    Tone: "{state.get('tone', 'professional')}"
    
    Outline:
    {outline_str}
    
    Task: Write the detailed content for EXACTLY these slides. You MUST create one slide object for each title in the Outline above.
    The "heading" of each slide MUST EXACTLY match the title from the Outline. DO NOT use the same heading for every slide.
    
    Output Format:
    Return ONLY a detailed JSON list of slide objects.
    Example:
    [
        {{
            "heading": "Slide 1 Title From Outline",
            "content": [
                {{ "text": "Main point 1", "level": 0 }},
                {{ "text": "Sub-point details", "level": 1 }},
                {{ "text": "Another main point", "level": 0 }}
            ],
            "image_search_query": "search query"
        }},
        {{
            "heading": "Slide 2 Title From Outline",
            "content": [ ... ]
        }}
    ]
    
    Rules:
    - You MUST use the exact headings from the provided Outline.
    - Write rich, detailed content (up to 7 or 8 bullet points per slide).
    - Content must be concise but informative, matching the requested tone and audience.
    - Use "level": 0 for main points, "level": 1 for sub-points.
    {image_instruction}
    """
    
    response = llm.invoke(prompt)
    slides = extract_json(response.content)
    
    if slides:
        return {"slides": slides}
    else:
        print(f"Writer Error: Failed to parse JSON")
        return {"slides": []}

def aggregator_node(state: AgentState):
    """
    Agent 3: Aggregator
    Compiles everything into the final format expected by app.py/ppt_utils.
    """
    print("--- [Aggregator] Formatting final JSON ---")
    
    final_structure = {
        "title": state['presentation_title'],
        "theme": state.get('theme', {}),
        "slides": state['slides']
    }
    
    return {"final_output": json.dumps(final_structure)}

# --- 4. Graph Construction ---

builder = StateGraph(AgentState)

builder.add_node("planner", planner_node)
builder.add_node("designer", designer_node)
builder.add_node("writer", content_node)
builder.add_node("aggregator", aggregator_node)

builder.set_entry_point("planner")

builder.add_edge("planner", "designer")
builder.add_edge("designer", "writer")
builder.add_edge("writer", "aggregator")
builder.add_edge("aggregator", END)

graph = builder.compile()
