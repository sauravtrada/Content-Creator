from flask import Flask, request, jsonify, render_template, send_file, url_for
from agent_graph import graph
import ppt_utils
import json
import os
import time
import tempfile
from rag_engine import ingest_document
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# --- Background Cleanup Task ---
def cleanup_old_files():
    """Deletes .pptx files older than 1 hour."""
    now = time.time()
    cutoff = now - 3600  # 1 hour
    directory = os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(directory):
        if filename.endswith(".pptx") and filename.startswith("presentation_"):
            filepath = os.path.join(directory, filename)
            try:
                if os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    print(f"Deleted old file: {filename}")
            except Exception as e:
                print(f"Error checking/deleting {filename}: {e}")

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
            "outline": [],
            "slides": []
        }
        
        result = graph.invoke(initial_state)
        json_content = result.get("final_output")
        
        if not json_content:
             raise ValueError("Graph failed to produce output")

        ppt_data = json.loads(json_content)
        
        # 2. Create Presentation Locally
        filename = f"presentation_{os.urandom(4).hex()}.pptx"
        output_path = ppt_utils.create_ppt(ppt_data, filename=filename, image_mode=image_mode if include_images else None)

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
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    # Determine the path. 
    # Current implementation of create_ppt saves to current working directory or absolute path.
    # ppt_utils.create_ppt saves to os.path.abspath(filename) if we passed just filename.
    # So valid check if file exists in current dir.
    # SECURITY NOTE: In production, sanitize filename to prevent directory traversal.
    file_path = os.path.abspath(filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True)
