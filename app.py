from flask import Flask, request, jsonify, render_template, send_file, url_for
from agent_graph import graph
import ppt_utils
import json
import os
import time
import uuid
import shutil
import tempfile
from rag_engine import ingest_document
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# In-memory session store for uploaded PPT files (session_id -> session dict)
PPT_SESSIONS = {}

# --- Background Cleanup Task ---
def cleanup_old_files():
    """Deletes .pptx files older than 1 hour and expired PPT sessions."""
    now = time.time()
    cutoff = now - 3600  # 1 hour
    directory = os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(directory):
        if filename.endswith(".pptx") and (
            filename.startswith("presentation_") or filename.startswith("patched_")
        ):
            filepath = os.path.join(directory, filename)
            try:
                if os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    print(f"Deleted old file: {filename}")
            except Exception as e:
                print(f"Error checking/deleting {filename}: {e}")

    # Also clean up expired PPT sessions (temp files in system temp dir)
    expired = [
        sid for sid, sess in list(PPT_SESSIONS.items())
        if now - sess.get("created", now) > 3600
    ]
    for sid in expired:
        sess = PPT_SESSIONS.pop(sid, {})
        for key in ("path", "last_patched"):
            p = sess.get(key)
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        print(f"Cleaned up expired session: {sid}")

# Initialize Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_old_files, trigger="interval", minutes=60)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate_ppt", methods=["POST"])
def generate_ppt():
    topic = request.form.get("topic")
    include_images = request.form.get("include_images", "false").lower() == "true"
    image_mode = request.form.get("image_mode", "manual")
    num_slides = int(request.form.get("num_slides", 5))
    tone = request.form.get("tone", "Professional")
    audience = request.form.get("audience", "General Audience")
    additional_instructions = request.form.get("additional_instructions", "")
    source_type = request.form.get("source_type", "topic_only")
    template_choice = request.form.get("template", "default")
    title_font_size = int(request.form.get("title_font_size", 26))
    body_font_size = int(request.form.get("body_font_size", 22))
    font_style = request.form.get("font_style", "Calibri")
    title_font_color = request.form.get("title_font_color", "#000000")
    body_font_color = request.form.get("body_font_color", "#333333")

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        rag_store = None
        
        if source_type == 'pdf':
            if 'file' not in request.files:
                return jsonify({"error": "No PDF file uploaded"}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            # Save temp file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, os.urandom(8).hex() + "_" + file.filename)
            file.save(temp_path)
            
            try:
                rag_store = ingest_document(source=temp_path, source_type='pdf')
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        elif source_type == 'url':
            source_url = request.form.get("source_url")
            if not source_url:
                return jsonify({"error": "URL is required"}), 400
            rag_store = ingest_document(source=source_url, source_type='url')
            
        elif source_type == 'text':
            source_text = request.form.get("source_text")
            if not source_text:
                return jsonify({"error": "Raw text is required"}), 400
            rag_store = ingest_document(source=source_text, source_type='text')

        # 1. Invoke LangGraph Workflow
        initial_state_and_prefs = {
            "initial_state": {
                "topic": topic,
                "source_type": source_type,
                "rag_store": rag_store,
                "include_images": include_images,
                "image_mode": image_mode,
                "num_slides": num_slides,
                "tone": tone,
                "audience": audience,
                "additional_instructions": additional_instructions,
                "outline": [],
                "slides": []
            },
            "design_prefs": {
                "template": template_choice,
                "title_font_size": title_font_size,
                "body_font_size": body_font_size,
                "font_style": font_style,
                "title_font_color": title_font_color,
                "body_font_color": body_font_color
            }
        }
        
        # 1. Invoke LangGraph Workflow
        result = graph.invoke({
            **initial_state_and_prefs["initial_state"],
            "design_prefs": initial_state_and_prefs["design_prefs"]
        })
        json_content = result.get("final_output")
        
        if not json_content:
             raise ValueError("Graph failed to produce output")

        ppt_data = json.loads(json_content)
        
        # Inject design preferences into ppt_data for the util
        ppt_data["design_prefs"] = initial_state_and_prefs["design_prefs"]
        
        # 2. Create Presentation Locally
        filename = f"presentation_{os.urandom(4).hex()}.pptx"
        output_path = ppt_utils.create_ppt(
            ppt_data, 
            filename=filename, 
            image_mode=image_mode if include_images else None
        )

        # 3. Return the Download URL
        download_url = url_for('download_file', filename=filename)
        
        return jsonify({
            "message": "Presentation created successfully",
            "downloadUrl": download_url
        })

    except json.JSONDecodeError:
        return jsonify({"error": "Failed to generate valid JSON content from AI"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            return jsonify({"error": "Gemini API Quota Exceeded. Please try again later or use a different API key/model."}), 429
        return jsonify({"error": error_msg}), 500


@app.route("/generate_content_only", methods=["POST"])
def generate_content_only():
    """Generates the JSON slide content without creating the PPTX file yet."""
    topic = request.form.get("topic")
    source_type = request.form.get("source_type", "topic_only")
    num_slides = int(request.form.get("num_slides", 5))
    include_images = request.form.get("include_images", "false").lower() == "true"
    image_mode = request.form.get("image_mode", "manual")
    tone = request.form.get("tone", "Professional")
    audience = request.form.get("audience", "General Audience")
    additional_instructions = request.form.get("additional_instructions", "")

    try:
        rag_store = None
        # Handle PDF/URL/Text ingestion (same as in generate_ppt)
        if source_type == 'pdf':
            if 'file' not in request.files:
                return jsonify({"error": "No PDF file uploaded"}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            temp_path = os.path.join(tempfile.gettempdir(), os.urandom(8).hex() + "_" + file.filename)
            file.save(temp_path)
            try: 
                rag_store = ingest_document(source=temp_path, source_type='pdf')
            finally: 
                if os.path.exists(temp_path): os.remove(temp_path)
        elif source_type == 'url':
            source_url = request.form.get("source_url")
            if not source_url:
                return jsonify({"error": "URL is required"}), 400
            rag_store = ingest_document(source=source_url, source_type='url')
        elif source_type == 'text':
            source_text = request.form.get("source_text")
            if not source_text:
                return jsonify({"error": "Raw text is required"}), 400
            rag_store = ingest_document(source=source_text, source_type='text')

        initial_state = {
            "topic": topic,
            "source_type": source_type,
            "rag_store": rag_store,
            "include_images": include_images,
            "image_mode": image_mode,
            "num_slides": num_slides,
            "tone": tone,
            "audience": audience,
            "additional_instructions": additional_instructions,
            "outline": [], "slides": []
        }
        
        result = graph.invoke(initial_state)
        json_content = result.get("final_output")
        if not json_content: raise ValueError("Graph failed")
        
        return json_content # This is already a JSON string from aggregator_node
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/update_slides", methods=["POST"])
def update_slides():
    """Takes existing slides and a user instruction, uses AI to update them."""
    try:
        from agent_graph import llm, extract_json
        
        current_slides_json = request.form.get("slides")
        instruction = request.form.get("instruction")
        
        if not current_slides_json or not instruction:
            return jsonify({"error": "Slides and instruction are required"}), 400
            
        current_slides = json.loads(current_slides_json)
        
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
  1. You MUST include: `"image_search_query": "a descriptive 3-5 word query for a high-quality photo"`
  2. You MUST set `"layout": "split"`.
- **VISUALS**: For any slide with a chart or table, set `"layout": "split"`. Otherwise use `"layout": "text_only"`.
- CHARTS: `"chart": {{"type": "column/pie/line/bar", "title": "Title", "categories": ["A", "B"], "series": [{{"name": "S1", "values": [10, 20]}}]}}`
- TABLES: `"table": [["Header 1", "Header 2"], ["Val 1", "Val 2"]]`
- STRUCTURE: Ensure the "content" field is a list of objects: `[{{"text": "point", "level": 0}}]`.
- Return ONLY the updated JSON list of slides. No preamble.

Updated JSON:
"""
        response = llm.invoke(prompt)
        updated_slides = extract_json(response.content)
        
        if not updated_slides:
            raise ValueError("Failed to parse updated slides from AI")
            
        # If AI wrapped it in an object like {"slides": [...]}, unwrap it
        if isinstance(updated_slides, dict) and "slides" in updated_slides:
            updated_slides = updated_slides["slides"]
        
        # --- NEW: Agentic Image Discovery for Updated Slides ---
        from agent_graph import image_searcher_node
        # Mock a state object for the node
        mock_state = {
            "slides": updated_slides,
            "include_images": True, 
            "image_mode": "manual" # Default to manual for updates
        }
        image_result = image_searcher_node(mock_state)
        updated_slides = image_result.get("slides", updated_slides)
            
        return jsonify(updated_slides)
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            return jsonify({"error": "Gemini API Quota Exceeded. Please try again later or use a different API key/model."}), 429
        return jsonify({"error": error_msg}), 500


@app.route("/generate_final", methods=["POST"])
def generate_final():
    """Takes (edited) JSON content and creates the final PPTX."""
    try:
        full_data_json = request.form.get("full_data")
        ppt_data = json.loads(full_data_json)
        
        # Inject design prefs
        ppt_data["design_prefs"] = {
            "template": request.form.get("template", "default"),
            "title_font_size": int(request.form.get("title_font_size", 28)),
            "body_font_size": int(request.form.get("body_font_size", 24)),
            "font_style": request.form.get("font_style", "Calibri"),
            "title_font_color": request.form.get("title_font_color", "#000000"),
            "body_font_color": request.form.get("body_font_color", "#333333")
        }

        filename = f"presentation_{os.urandom(4).hex()}.pptx"
        output_path = ppt_utils.create_ppt(
            ppt_data, 
            filename=filename, 
            image_mode=request.form.get("image_mode", "manual")
        )
        download_url = url_for('download_file', filename=filename)
        
        return jsonify({"message": "Success", "downloadUrl": download_url})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/import_ppt", methods=["POST"])
def import_ppt():
    """Parses an uploaded PPTX, stores it for in-place editing, returns JSON slides + session_id."""
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    session_id = str(uuid.uuid4())
    temp_dir   = tempfile.gettempdir()
    temp_path  = os.path.join(temp_dir, f"ppt_session_{session_id}.pptx")
    file.save(temp_path)

    try:
        slides = ppt_utils.extract_slide_inventory(temp_path)

        PPT_SESSIONS[session_id] = {
            "path":         temp_path,
            "filename":     file.filename,
            "created":      time.time(),
            "last_patched": None,
            "last_patched_filename": None,
        }

        return jsonify({
            "title":       file.filename.replace(".pptx", "").replace(".PPTX", ""),
            "slides":      slides,
            "session_id":  session_id,
            "is_imported": True
        })
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    # SECURITY: only allow filenames without path separators
    safe_name = os.path.basename(filename)
    file_path = os.path.abspath(safe_name)
    if os.path.exists(file_path):
        return send_file(
            file_path,
            as_attachment=True,
            download_name=safe_name,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    # Also check temp dir for session patched files
    temp_path = os.path.join(tempfile.gettempdir(), safe_name)
    if os.path.exists(temp_path):
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=safe_name,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    return "File not found", 404


@app.route("/update_ppt_live", methods=["POST"])
def update_ppt_live():
    """AI-powered in-place PPTX editing. Uses session to preserve original design."""
    try:
        from agent_graph import llm, extract_json

        session_id          = request.form.get("session_id")
        instruction         = request.form.get("instruction")
        current_slides_json = request.form.get("current_slides")

        if not session_id or not instruction:
            return jsonify({"error": "session_id and instruction are required"}), 400

        if session_id not in PPT_SESSIONS:
            return jsonify({"error": "Session expired or not found. Please re-upload your file."}), 404

        sess = PPT_SESSIONS[session_id]
        original_path = sess["path"]

        if not os.path.exists(original_path):
            return jsonify({"error": "Session file missing. Please re-upload."}), 404

        current_slides = json.loads(current_slides_json) if current_slides_json else []
        slides_context = json.dumps(current_slides, indent=2)

        prompt = f"""You are a PowerPoint editor. Below is the current presentation state (0-indexed slides with text content and shape counts). Apply the user's instruction.

Current Slides:
{slides_context}

User Instruction: "{instruction}"

Return ONLY a JSON array of slide action objects. Each object:
- "slide_index": 0-based integer index of the slide to modify
- "actions": array of action objects

Available action types:
1. {{"type": "update_text", "heading": "New Title", "content": [{{"text": "bullet point", "level": 0}}]}}
   Change slide title and/or bullet points.

2. {{"type": "remove_image", "index": 0}}
   Remove the Nth image from the slide (0-indexed). Check the slide's shapes.images count first.

3. {{"type": "remove_chart", "index": 0}}
   Remove the Nth chart from the slide (0-indexed).

4. {{"type": "remove_table", "index": 0}}
   Remove the Nth table from the slide (0-indexed).

5. {{"type": "remove_smartart", "index": 0}}
   Remove the Nth SmartArt/diagram from the slide (0-indexed).

6. {{"type": "add_image", "query": "descriptive 3-5 word photo search query"}}
   Add a new relevant image fetched from the web.

7. {{"type": "add_chart", "chart": {{"type": "column", "title": "Chart Title", "categories": ["A","B"], "series": [{{"name": "Series1", "values": [10,20]}}]}}}}
   Add a new chart (type: column/pie/line/bar).

8. {{"type": "add_table", "table": [["Header1","Header2"],["Val1","Val2"]]}}
   Add a new data table.

Rules:
- Only include slides that need changes. Unchanged slides must NOT appear in the response.
- If a slide needs both text and visual changes, include all action types in a single slide object.
- Use shapes.images / shapes.charts etc. to know what currently exists before removing.
- When adding an image, write a descriptive, specific search query (e.g. "renewable solar energy farm" not just "energy").
- Do not include markdown or explanation. Return ONLY the JSON array.

Example:
[
  {{"slide_index": 1, "actions": [
    {{"type": "remove_image", "index": 0}},
    {{"type": "update_text", "heading": "Updated Title", "content": [{{"text": "Key point", "level": 0}}]}}
  ]}}
]"""

        response     = llm.invoke(prompt)
        slide_actions = extract_json(response.content)

        if not slide_actions:
            return jsonify({"error": "AI failed to generate valid actions. Try rephrasing your instruction."}), 500

        # If AI wrapped actions in an object, unwrap
        if isinstance(slide_actions, dict):
            slide_actions = slide_actions.get("actions", slide_actions.get("slides", []))

        if not isinstance(slide_actions, list):
            return jsonify({"error": "Unexpected AI response format"}), 500

        # Apply the patch to the current working file
        out_filename = f"patched_{session_id[:8]}_{os.urandom(3).hex()}.pptx"
        out_path     = ppt_utils.patch_ppt(original_path, slide_actions, out_filename)

        # The patched file becomes the new base for future patches (incremental)
        shutil.copy2(out_path, original_path)

        # Update session metadata
        if sess.get("last_patched") and os.path.exists(sess["last_patched"]):
            try:
                os.remove(sess["last_patched"])
            except Exception:
                pass
        sess["last_patched"]          = out_path
        sess["last_patched_filename"] = out_filename

        # Re-extract updated inventory from the patched file
        updated_slides = ppt_utils.extract_slide_inventory(out_path)
        download_url   = url_for('download_file', filename=out_filename)

        return jsonify({
            "slides":          updated_slides,
            "downloadUrl":     download_url,
            "actions_applied": len(slide_actions)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            return jsonify({"error": "Gemini API Quota Exceeded. Please try again later."}), 429
        return jsonify({"error": error_msg}), 500


@app.route("/clear_session", methods=["POST"])
def clear_session():
    """Deletes a PPT session and its associated temp files."""
    session_id = request.form.get("session_id")
    if session_id and session_id in PPT_SESSIONS:
        sess = PPT_SESSIONS.pop(session_id)
        for key in ("path", "last_patched"):
            p = sess.get(key)
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=False)
