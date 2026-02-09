import ppt_utils
import os

data = {
    "title": "IEEE Style Test",
    "slides": [
        {
            "heading": "Introduction",
            "content": [
                {"text": "Main Point (Should be 32pt)", "level": 0},
                {"text": "Sub Point (Should be 28pt)", "level": 1},
                {"text": "Detail Point (Should be 24pt)", "level": 2}
            ]
        }
    ]
}

try:
    output_path = ppt_utils.create_ppt(data, filename="ieee_test.pptx", image_mode="manual")
    print(f"Successfully created: {output_path}")
except Exception as e:
    print(f"Error: {e}")
