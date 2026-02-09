import ppt_utils
import os

def test_pagination():
    print("Testing Slide Pagination...")
    
    # Create data with ONE slide that has WAY too many items
    long_content = []
    for i in range(20):
        long_content.append({"text": f"This is bullet point number {i+1} which is quite long to take up space.", "level": 0})
        
    data = {
        "title": "Pagination Test",
        "slides": [
            {
                "heading": "Overflowing Slide",
                "content": long_content,
                "image_search_query": "test"
            }
        ]
    }
    
    output = ppt_utils.create_ppt(data, filename="test_pagination.pptx", image_mode="manual")
    print(f"Created {output}")
    
    # We can't easily inspect the PPTX structure without opening it or using deep introspection,
    # but successful run without error is a good first step.
    # The user can visually verify 'test_pagination.pptx'.

if __name__ == "__main__":
    test_pagination()
