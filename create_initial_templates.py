import os
from pptx import Presentation
from pptx.util import Inches

# --- Global Constants ---
SLIDE_WIDTH = Inches(13.333)  # 16:9 aspect ratio
SLIDE_HEIGHT = Inches(7.5)
TEMPLATE_DIR = "slide_templates"

THEMES = [
    {"file": "professional_blue.pptx", "bg": "#FFFFFF", "surface": "#F8FAFC", "accent": "#1565C0", "text": "#1A202C"},
    {"file": "executive_dark.pptx",    "bg": "#0F172A", "surface": "#1E293B", "accent": "#E53E3E", "text": "#F1F5F9"},
    {"file": "teal_modern.pptx",      "bg": "#F0FFF4", "surface": "#E6FFFA", "accent": "#319795", "text": "#234E52"},
    {"file": "sunset_coral.pptx",     "bg": "#FFF5F5", "surface": "#FED7D7", "accent": "#E53E3E", "text": "#2D3748"},
    {"file": "ocean_blue.pptx",       "bg": "#EBF8FF", "surface": "#BEE3F8", "accent": "#3182CE", "text": "#2A4365"},
    {"file": "forest_green.pptx",     "bg": "#F0FFF4", "surface": "#C6F6D5", "accent": "#2F855A", "text": "#22543D"},
    {"file": "royal_purple.pptx",     "bg": "#1A1B26", "surface": "#24283B", "accent": "#BB9AF7", "text": "#A9B1D6"},
    {"file": "golden_amber.pptx",     "bg": "#FFFDF0", "surface": "#FEF3C7", "accent": "#D97706", "text": "#451A03"},
    {"file": "charcoal_mono.pptx",    "bg": "#121212", "surface": "#1E1E1E", "accent": "#D1D5DB", "text": "#F9FAFB"},
    {"file": "rose_blush.pptx",       "bg": "#FFF5F7", "surface": "#FFE4E6", "accent": "#E11D48", "text": "#4C0519"},
    {"file": "navy_slate.pptx",       "bg": "#0D1117", "surface": "#161B22", "accent": "#58A6FF", "text": "#C9D1D9"},
    {"file": "olive_sage.pptx",       "bg": "#FCFCFA", "surface": "#F1F1E6", "accent": "#6B705C", "text": "#333333"},
]

def create_template(filename):
    """
    Creates a clean, 0-slide PPTX template.
    All design/colors are applied programmatically in ppt_utils.py.
    """
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR)
        
    prs = Presentation()
    
    # Set Slide Size (16:9)
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    
    # Save empty file (0 slides)
    path = os.path.join(TEMPLATE_DIR, filename)
    prs.save(path)
    print(f"  ✓ Created Clean Template: {path}")

if __name__ == "__main__":
    print("\nGenerating 12 Clean (0-slide) PPTX Templates...")
    for theme in THEMES:
        create_template(theme['file'])
    print("\nDone! All templates saved to ./slide_templates/\n")
