import os
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _resolve_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


api_key = _resolve_api_key()
if not api_key:
    raise SystemExit("Error: GEMINI_API_KEY not found.")

endpoint = "https://generativelanguage.googleapis.com/v1beta/models"

try:
    response = requests.get(
        endpoint,
        params={"key": api_key},
        timeout=10,
    )
    response.raise_for_status()
except requests.RequestException as exc:
    raise SystemExit(f"Error fetching models: {type(exc).__name__}") from exc

try:
    data = response.json()
except ValueError as exc:
    raise SystemExit("Error fetching models: invalid JSON response") from exc

models = data.get("models", [])
print(f"Found {len(models)} models. Available names:")
for model in models:
    print(f"- {model.get('name')}")
