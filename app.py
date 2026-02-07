from flask import Flask, request, jsonify, render_template, send_file, url_for
from agent_graph import graph
import ppt_utils
import json
import os

app = Flask(__name__)
app.secret_key = os.urandom(24) 

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate_ppt", methods=["POST"])
def generate_ppt():
    data = request.get_json()
    topic = data.get("topic")
    include_images = data.get("include_images", False)
    image_mode = data.get("image_mode", "manual")

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        # 1. Invoke LangGraph Workflow
        initial_state = {
            "topic": topic,
            "include_images": include_images,
            "image_mode": image_mode,
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
