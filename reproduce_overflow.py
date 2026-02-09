import ppt_utils
import os

def reproduce_overflow():
    print(" reproducing overflow...")
    
    # 9 items of Level 0 text (should fit according to logic, but overflow visually)
    # Each item roughly 1 line
    content = []
    for i in range(9):
        content.append({"text": f"Level 0 Item {i+1}: This is a standard length bullet point to test spacing.", "level": 0})
        
    data = {
        "title": "Overflow Reproduction",
        "slides": [
            {
                "heading": "9 Items (Should Overflow)",
                "content": content
            }
        ]
    }
    
    output = ppt_utils.create_ppt(data, filename="reproduce_overflow.pptx", image_mode="manual")
    print(f"Created {output}. Please open it and check if the last item is off-slide.")

if __name__ == "__main__":
    reproduce_overflow()
