import ppt_utils
import os
from pptx.util import Pt

# Mock data
data = {
    "title": "Verification Test",
    "design_prefs": {
        "template": "professional_blue.pptx",
        "title_font_size": 28,
        "body_font_size": 24,
        "font_style": "Arial"
    },
    "slides": [
        {
            "heading": "Test Slide 1",
            "content": [{"text": "This is a test with Arial font and 28pt header.", "level": 0}]
        }
    ]
}

output_file = "test_font_verification.pptx"
try:
    path = ppt_utils.create_ppt(data, filename=output_file)
    print(f"Presentation created at: {path}")
    
    # Check if the file exists
    if os.path.exists(path):
        print("SUCCESS: File generated successfully.")
    else:
        print("FAILURE: File not found.")
except Exception as e:
    print(f"FAILURE: An error occurred: {e}")
