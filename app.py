from flask import Flask, request, jsonify, render_template, send_file, url_for
from agent_graph import graph
import ppt_utils
import json
import os
import time
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
    
    # print("Running cleanup task...") 
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
    data = request.get_json()
    topic = data.get("topic")
    include_images = data.get("include_images", False)
    image_mode = data.get("image_mode", "manual")
    num_slides = int(data.get("num_slides", 5))
    tone = data.get("tone", "Professional")
    audience = data.get("audience", "General Audience")
    additional_instructions = data.get("additional_instructions", "")

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        # 1. Invoke LangGraph Workflow
        initial_state = {
            "topic": topic,
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
