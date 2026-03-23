import ppt_utils
import json
import os

# Test data for Nebula Glow
nebula_data = {
    "title": "Nebula Glow Test",
    "design_prefs": {
        "template": "nebula_glow.pptx",
        "title_font_size": 40,
        "body_font_size": 24,
    },
    "slides": [
        {
            "heading": "Introduction to Nebula",
            "content": [
                {"text": "Modern glassmorphism effects", "level": 0},
                {"text": "Dynamic glowing accents", "level": 1},
                {"text": "Deep space color palette", "level": 0}
            ]
        },
        {
            "heading": "Visual Features",
            "content": [
                {"text": "Central floating cards", "level": 0},
                {"text": "Corner glow shapes", "level": 0}
            ],
            "image_search_query": "galaxy nebula"
        }
    ]
}

# Test data for Retrowave Neon
retrowave_data = {
    "title": "Retrowave Neon Test",
    "design_prefs": {
        "template": "retrowave_neon.pptx",
        "title_font_size": 40,
        "body_font_size": 24,
    },
    "slides": [
        {
            "heading": "80s Retro Aesthetic",
            "content": [
                {"text": "Vibrant synthwave colors", "level": 0},
                {"text": "Grid floors and neon horizons", "level": 0},
                {"text": "High energy design", "level": 1}
            ]
        },
        {
            "heading": "Cyberpunk Elements",
            "content": [
                {"text": "Sidebar accents", "level": 0},
                {"text": "Header block containers", "level": 0}
            ]
        }
    ]
}

def run_test():
    print("Generating Nebula Glow test...")
    nebula_path = ppt_utils.create_ppt(nebula_data, "test_nebula.pptx")
    print(f"  ✓ Saved to: {nebula_path}")

    print("\nGenerating Retrowave Neon test...")
    retrowave_path = ppt_utils.create_ppt(retrowave_data, "test_retrowave.pptx")
    print(f"  ✓ Saved to: {retrowave_path}")

if __name__ == "__main__":
    run_test()
