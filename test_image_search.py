import sys
import os
from io import BytesIO

# Add current directory to path so we can import ppt_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ppt_utils

def test_image_fetching():
    queries = ["Satoro Gojo", "modern office building", "artificial intelligence concept"]
    
    for query in queries:
        print(f"\nTesting query: '{query}'")
        stream = ppt_utils.fetch_image(query)
        
        if stream:
            print(f"SUCCESS: Fetched image for '{query}'")
            print(f"Stream size: {len(stream.getvalue())} bytes")
            # Basic check if it's a valid image (e.g., check first few bytes)
            header = stream.getvalue()[:10]
            print(f"Header bytes: {header}")
        else:
            print(f"FAILED: Could not fetch image for '{query}'")

if __name__ == "__main__":
    test_image_fetching()
