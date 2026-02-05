from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in environment.")
    exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("Client initialized.")
    
    # Try with gemini-2.0-flash first
    model_name = "gemini-2.0-flash"
    print(f"Testing model: {model_name}")
    response = client.models.generate_content(
        model=model_name,
        contents="Say hello"
    )
    print(f"Success! Response: {response.text}")

except Exception as e:
    print(f"Error testing model: {e}")
