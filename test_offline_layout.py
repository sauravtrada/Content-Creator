from ppt_utils import create_ppt
import json

ppt_data = {
  "title": "Quantum Futures: Unlocking Tomorrow's Tech",
  "theme": {
    "font": "Inter",
    "color_primary": "00C0FF",
    "color_accent": "C060FF",
    "color_background": "0D1117",
    "color_text_main": "F0F2F5",
    "color_text_light": "B0B8C4"
  },
  "slides": [
    {
      "heading": "Slide 1 Title",
      "content": [
        { "text": "This is a main point with a lot of text that might wrap to a second line. We need to make sure the font size is appropriate.", "level": 0 },
        { "text": "This is a sub point that should be colored with COLOR_TEXT_MAIN.", "level": 1 },
        { "text": "Another sub point.", "level": 1 },
        { "text": "And a level 2 point.", "level": 2 }
      ],
      "image_search_query": "Quantum Computer"
    },
    {
      "heading": "Slide 2 Content",
      "content": [
        { "text": "Point 1 that is long enough to demonstrate wrapping.", "level": 0 },
        { "text": "Point 2 that is also long.", "level": 0 }
      ]
    }
  ]
}

filename = "test_layout_theme.pptx"
create_ppt(ppt_data, filename=filename, image_mode="auto")
print(f"Created {filename}")
