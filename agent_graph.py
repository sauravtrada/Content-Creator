import os
import json
import concurrent.futures
from typing import TypedDict, List, Dict, Any, Annotated, cast
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

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
    outline: List[str]
    theme: Dict[str, Any]
    slides: List[Dict[str, Any]]
    final_output: str
    retry_count: int
    design_prefs: Dict[str, Any]   # passed through from app.py to ppt_utils


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


# ---------------- VALIDATION LAYER ---------------- #

_FALLBACK_CONTENT = [
    {"text": "Key concepts and overview", "level": 0},
    {"text": "Important considerations", "level": 1},
    {"text": "Summary and next steps", "level": 1},
]


def validate_and_repair_slides(slides: Any) -> List[Dict[str, Any]]:
    """
    Validates and repairs a list of slide dicts from the LLM.
    - Removes slides that are not dicts
    - Ensures required fields: heading, content, layout
    - Enforces hard content limits: max 5 level-0 bullets, 15 words per bullet
    - Applies deterministic layout rule (backend, not LLM)
    """
    if not isinstance(slides, list):
        return []

    repaired = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue

        # Ensure heading
        if not slide.get("heading"):
            slide["heading"] = "Slide"

        # Ensure content is a list of dicts with 'text'
        raw_content = slide.get("content", [])
        if not isinstance(raw_content, list):
            raw_content = []

        cleaned_content = []
        for item in raw_content:
            if isinstance(item, str):
                item = {"text": item, "level": 0}
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            # Hard constraint: max 15 words per bullet
            words = text.split()
            if len(words) > 15:
                text = " ".join(words[:15]) + "..."
            cleaned_content.append({"text": text, "level": int(item.get("level", 0))})

        # Hard constraint: max 5 level-0 bullets per slide
        level0_count = 0
        final_content = []
        for item in cleaned_content:
            if item["level"] == 0:
                if level0_count >= 5:
                    continue
                level0_count += 1
            final_content.append(item)

        slide["content"] = final_content if final_content else list(_FALLBACK_CONTENT)

        # Deterministic layout rule (backend enforces, not LLM)
        has_image_query = bool(slide.get("image_search_query"))
        has_image_url   = bool(slide.get("image_url"))
        has_chart       = bool(slide.get("chart"))
        has_table       = bool(slide.get("table"))

        if has_image_query or has_image_url or has_chart or has_table:
            slide["layout"] = "split"
        else:
            slide["layout"] = "text_only"

        repaired.append(slide)

    return repaired


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
- For slides that would benefit from a visual (concept overviews, complex processes):
  Include "image_search_query": "2-4 descriptive words for a photo search"
- For purely informational/list-based slides: OMIT "image_search_query" entirely.
- NOTE: layout (split/text_only) will be assigned automatically by the backend.
  You do NOT need to set "layout" — it will be overridden.
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
"layout":"text_only/split",
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

- Use "layout": "text_only" for slides that are primarily text and should use the full width. This is the preferred default.
- Use "layout": "split" ONLY if you are including a "chart" or "table". 
- Do not include both chart and table on the same slide.
- Choose "pie" for proportions, "column/bar" for comparisons, and "line" for trends.
- If a slide is purely descriptive, ALWAYS use "layout": "text_only" and OMIT "image_search_query", "chart", and "table".

{image_instruction}
"""

    response = llm.invoke(prompt)

    slides = extract_json(response.content)

    # Always validate + repair LLM output before using it
    slides = validate_and_repair_slides(slides)

    if slides:
        return {"slides": slides}

    # Fallback: generate safe default slides
    fallback = []
    for title in outline:
        fallback.append({
            "heading": title,
            "layout": "text_only",
            "content": list(_FALLBACK_CONTENT),
        })

    return {"slides": fallback}


# ---------------- AGGREGATOR ---------------- #

def aggregator_node(state: AgentState):

    print("[AGGREGATOR] Building final output")

    final_structure = {
        "title": state.get("presentation_title", "Untitled"),
        "theme": state.get("theme", {}),
        "slides": state.get("slides", []),
        "design_prefs": state.get("design_prefs", {})  # pass through to ppt_utils
    }

    return {"final_output": json.dumps(final_structure)}


# ---------------- IMAGE SEARCHER ---------------- #

def image_searcher_node(state: AgentState):
    """
    Finds real image URLs for slides using the tiered image service.
    Runs image fetches in PARALLEL — no sleep(), no blocking.
    Priority: Unsplash API → Pexels API → DuckDuckGo → None
    """
    slides = state.get("slides", [])
    if not state.get("include_images") or not slides:
        return {"slides": slides}

    from services.image_service import fetch_image_for_query

    print(f"[IMAGE AGENT] Searching images for {len(slides)} slides (parallel)...")

    # Collect queries
    queries: Dict[int, str] = {}
    for i, slide in enumerate(slides):
        query = slide.get("image_search_query")
        url   = slide.get("image_url")

        if url:
            queries[i] = url  # Already have a URL — just verify/download
        elif query:
            queries[i] = query
        elif state.get("image_mode") == "auto":
            # Auto mode: use heading as fallback query
            heading = slide.get("heading", "")
            if heading:
                queries[i] = heading

    if not queries:
        return {"slides": slides}

    # Parallel fetch — no time.sleep()
    results: Dict[int, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {
            executor.submit(fetch_image_for_query, q): idx
            for idx, q in queries.items()
        }
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                stream = future.result()
                if stream:
                    # Store the query/url so ppt_utils can fetch it again
                    results[idx] = queries[idx]
            except Exception as e:
                print(f"[IMAGE AGENT] Error fetching slide {idx}: {e}")

    # Attach confirmed image sources back to slides
    updated_slides = []
    for i, slide in enumerate(slides):
        if i in results:
            slide = dict(slide)
            if results[i].startswith(("http://", "https://")):
                slide["image_url"] = results[i]
            else:
                slide["image_search_query"] = results[i]
            # Re-enforce layout after image confirmation
            slide["layout"] = "split"
        updated_slides.append(slide)

    return {"slides": updated_slides}


# ---------------- REFINER ---------------- #

def refine_node(state: AgentState):
    """Trim any remaining over-long content as a safety net."""
    slides = state.get("slides", [])

    for slide in slides:
        content = slide.get("content", [])
        for item in content:
            text = item.get("text", "")
            words = text.split()
            if len(words) > 15:
                item["text"] = " ".join(words[:15]) + "..."

    return {"slides": slides}


# ---------------- CHECK LENGTH ---------------- #

def check_length(state: AgentState):
    slides = state.get("slides", [])

    for slide in slides:
        for item in slide.get("content", []):
            text = item.get("text", "")
            if len(text.split()) > 15:
                return "refine"

    return "aggregator"


# ---------------- GRAPH ---------------- #

builder = StateGraph(AgentState)

builder.add_node("planner", planner_node)
builder.add_node("designer", designer_node)
builder.add_node("content", content_node)
builder.add_node("refiner", refine_node)
builder.add_node("image_searcher", image_searcher_node)
builder.add_node("aggregator", aggregator_node)

builder.set_entry_point("planner")

builder.add_edge("planner", "designer")
builder.add_edge("designer", "content")

builder.add_conditional_edges(
    "content",
    check_length,
    {
        "refine": "refiner",
        "aggregator": "image_searcher"
    }
)

builder.add_conditional_edges(
    "refiner",
    check_length,
    {
        "refine": "refiner",
        "aggregator": "image_searcher"
    }
)

builder.add_edge("image_searcher", "aggregator")

builder.add_edge("aggregator", END)

graph = builder.compile()