import os
import json
from typing import TypedDict, List, Dict, Any, Annotated, cast
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import time

load_dotenv(override=True)


def list_reducer(a: List, b: List) -> List:
    if a is None:
        a = []
    if b is None:
        b = []
    return a + b


# ---------------- STATE ---------------- #

class AgentState(TypedDict):
    topic: str
    source_type: str
    rag_store: Any
    include_images: bool
    image_mode: str
    presentation_title: str
    num_slides: int
    tone: str
    audience: str
    additional_instructions: str
    outline: Annotated[List[str], list_reducer]
    theme: Dict[str, Any]
    slides: Annotated[List[Dict[str, Any]], list_reducer]
    final_output: str
    retry_count: int


# ---------------- LLM ---------------- #

if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY not found")

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,
    max_retries=3
)


# ---------------- JSON PARSER ---------------- #

def extract_json(text):
    import re

    if not text:
        return None

    if isinstance(text, list):
        parts = []
        for part in text:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        text = "".join(parts)

    try:

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        return json.loads(text.strip())

    except Exception:
        return None


# ---------------- PLANNER ---------------- #

def planner_node(state: AgentState):

    print("\n[PLANNER AGENT] Generating outline")

    num_slides = state["num_slides"]
    if not isinstance(num_slides, int):
        num_slides = 5

    rag_context = ""

    if state.get("rag_store"):
        retriever = state["rag_store"].as_retriever(search_kwargs={"k": 4})
        docs = retriever.invoke(state["topic"])

        doc_texts = "\n\n".join(d.page_content for d in docs)
        rag_context = f"\nUse this context:\n{doc_texts}\n"

    prompt = f"""
You are a presentation planner.

Topic: {state['topic']}

{rag_context}

Create {num_slides} slide titles.

Return JSON:

{{
"title":"Presentation title",
"outline":["title1","title2"]
}}
"""

    response = llm.invoke(prompt)

    data = extract_json(response.content)

    if data:
        return {
            "presentation_title": data.get("title", state["topic"]),
            "outline": data.get("outline", [])
        }

    return {
        "presentation_title": state["topic"],
        "outline": [f"Slide {i+1}" for i in range(num_slides)]
    }


# ---------------- DESIGNER ---------------- #

def designer_node(state: AgentState):

    print("[DESIGNER AGENT] Generating theme")

    prompt = f"""
Design a presentation theme for topic:

{state['topic']}

Return JSON:

{{
"font":"Calibri",
"color_primary":"0E2A47",
"color_accent":"009688",
"color_background":"FAFAFA",
"color_text_main":"404040",
"color_text_light":"757575"
}}
"""

    response = llm.invoke(prompt)

    data = extract_json(response.content)

    if data:
        return {"theme": data}

    return {
        "theme": {
            "font": "Calibri",
            "color_primary": "0E2A47",
            "color_accent": "009688",
            "color_background": "FAFAFA",
            "color_text_main": "404040",
            "color_text_light": "757575",
        }
    }


# ---------------- CONTENT WRITER ---------------- #

def content_node(state: AgentState):

    outline = cast(List[str], state.get("outline", []))

    print(f"[WRITER AGENT] Writing {len(outline)} slides")

    outline_str = "\n".join(f"- {x}" for x in outline)

    rag_context = ""   # ✅ FIX 1: always defined

    if state.get("rag_store"):

        print("[Writer] Using RAG")

        retriever = state["rag_store"].as_retriever(search_kwargs={"k": 3})

        docs = retriever.invoke(state["topic"])

        doc_texts = "\n".join(d.page_content for d in docs)

        rag_context = f"\nContext:\n{doc_texts}\n"

    image_instruction = ""

    if state.get("include_images"):

        image_instruction = """
Include:
"image_search_query":"2-3 words"
"""

    prompt = f"""
You are a presentation writer.

Title: {state['presentation_title']}

Audience: {state.get('audience','general')}

Tone: {state.get('tone','professional')}

{rag_context}

Slides:

{outline_str}

Return JSON list:

[
{{
"heading":"slide title",
"content":[
{{"text":"point","level":0}}
],
"image_search_query":"query",
"chart": {{
    "type": "column/pie/line/bar",
    "title": "Chart Title",
    "categories": ["A", "B"],
    "series": [{{"name": "Series 1", "values": [10, 20]}}]
}},
"table": [
    ["Header 1", "Header 2"],
    ["Value 1", "Value 2"]
]
}}
]

- ONLY include "chart" if there is numerical data or trends to visualize.
- ONLY include "table" if there is structured comparative data or a list of specifications.
- Do not include both chart and table on the same slide.
- Choose "pie" for proportions, "column/bar" for comparisons, and "line" for trends.

{image_instruction}
"""

    response = llm.invoke(prompt)

    slides = extract_json(response.content)

    if slides:
        return {"slides": slides}

    fallback = []

    for title in outline:

        fallback.append({
            "heading": title,
            "content": [
                {"text": "Overview", "level": 0},
                {"text": "Key ideas", "level": 1},
                {"text": "Future outlook", "level": 1}
            ],
            "image_search_query": title
        })

    return {"slides": fallback}


# ---------------- AGGREGATOR ---------------- #

def aggregator_node(state: AgentState):

    print("[AGGREGATOR] Building final output")

    final_structure = {
        "title": state["presentation_title"],
        "theme": state.get("theme", {}),
        "slides": state.get("slides", [])
    }

    return {"final_output": json.dumps(final_structure)}


# ---------------- REFINER ---------------- #

def refine_node(state: AgentState):

    slides = state["slides"]

    for slide in slides:

        text = ""

        for item in slide["content"]:
            text += item["text"]

        if len(text) > 500:

            for item in slide["content"]:
                item["text"] = item["text"][:80]

    return {"slides": slides}


# ---------------- CHECK LENGTH ---------------- #

def check_length(state: AgentState):

    slides = state["slides"]

    for slide in slides:

        text = ""

        for item in slide["content"]:
            text += item["text"]

        if len(text) > 500:
            return "refine"

    return "aggregator"


# ---------------- GRAPH ---------------- #

builder = StateGraph(AgentState)

builder.add_node("planner", planner_node)
builder.add_node("designer", designer_node)
builder.add_node("content", content_node)
builder.add_node("refiner", refine_node)
builder.add_node("aggregator", aggregator_node)

builder.set_entry_point("planner")

builder.add_edge("planner", "designer")
builder.add_edge("designer", "content")

builder.add_conditional_edges(
    "content",
    check_length,
    {
        "refine": "refiner",
        "aggregator": "aggregator"
    }
)

builder.add_conditional_edges(
    "refiner",
    check_length,
    {
        "refine": "refiner",
        "aggregator": "aggregator"
    }
)

builder.add_edge("aggregator", END)

graph = builder.compile()