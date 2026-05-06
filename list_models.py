import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in .env")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

print(f"Fetching models from {url[:60]}...[REDACTED]")
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    models = data.get("models", [])
    print(f"\nFound {len(models)} models. Available names:")
    for m in models:
        print(f"- {m.get('name')}")
else:
    print(f"Error {response.status_code}: {response.text}")
