from flask import Flask, request, jsonify, render_template, send_file, url_for
from gemini_client import generate_content
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

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        # 1. Get structured content from Gemini
        json_content = generate_content(topic)
        ppt_data = json.loads(json_content)
        
        # 2. Create Presentation Locally
        # Use simple filename sanitization or uuid usually, keeping it simple for now
        filename = f"presentation_{os.urandom(4).hex()}.pptx"
        output_path = ppt_utils.create_ppt(ppt_data, filename=filename)

        # 3. Return the Download URL
        # We need a route to serve this file.
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
