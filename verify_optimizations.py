import ppt_utils
import os
import time
import json
from agent_graph import extract_json

def test_extract_json():
    print("Testing JSON Extraction...")
    
    cases = [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"b": 2}\n```', {"b": 2}),
        ('Some text\n```\n[{"c": 3}]\n```\nMore text', [{"c": 3}]),
        ('Just text', None)
    ]
    
    for input_str, expected in cases:
        result = extract_json(input_str)
        if result == expected:
            print(f"PASS: {input_str[:20]}...")
        else:
            print(f"FAIL: {input_str[:20]}... Expected {expected}, got {result}")

def test_image_parallel_fetch():
    print("\nTesting Parallel Image Fetching...")
    
    data = {
        "title": "Test Presentation",
        "slides": [
            {"heading": "Slide 1", "content": [], "image_search_query": "cat"},
            {"heading": "Slide 2", "content": [], "image_search_query": "dog"},
            {"heading": "Slide 3", "content": [], "image_search_query": "bird"},
            {"heading": "Slide 4", "content": [], "image_search_query": "fish"},
            {"heading": "Slide 5", "content": [], "image_search_query": "tree"},
        ]
    }
    
    start = time.time()
    # Mocking create_ppt logic implicitly by running it. 
    # Note: This will create a file locally.
    output = ppt_utils.create_ppt(data, filename="test_parallel.pptx", image_mode="auto")
    duration = time.time() - start
    
    print(f"Created PPT in {duration:.2f} seconds.")
    if os.path.exists(output):
        print("PASS: File created.")
        os.remove(output) # Cleanup
    else:
        print("FAIL: File not created.")

if __name__ == "__main__":
    test_extract_json()
    test_image_parallel_fetch()
