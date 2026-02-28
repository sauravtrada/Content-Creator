from agent_graph import graph
from ppt_utils import create_ppt
import json

initial_state = {
    "topic": "The Future of Quantum Computing",
    "include_images": False,
    "image_mode": "manual",
    "num_slides": 3,
    "tone": "futuristic",
    "audience": "Tech Enthusiasts",
    "additional_instructions": "",
    "outline": [],
    "slides": []
}

result = graph.invoke(initial_state)
json_content = result.get("final_output")

if json_content:
    ppt_data = json.loads(json_content)
    # print theme chosen
    print("Theme generated:", json.dumps(ppt_data.get("theme", {}), indent=2))
    
    filename = "test_quantum_theme.pptx"
    create_ppt(ppt_data, filename=filename, image_mode="manual")
    print(f"Created {filename}")
else:
    print("Failed to generate")
