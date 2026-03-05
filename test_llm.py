import os
import sys
import logging

# Enable logging to see the retries
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# Ensure we can import applypilot
sys.path.insert(0, os.path.abspath("src"))

from applypilot.config import load_env

def test_gemini():
    # Load ~/.applypilot/.env first so provider detection sees fresh env vars.
    load_env()
    # Faster failure during debugging when provider is slow/unreachable.
    os.environ.setdefault("LLM_TIMEOUT", "15")
    os.environ.setdefault("LLM_MAX_RETRIES", "2")
    from applypilot.llm import get_client
    client = get_client()
    
    # Check the configured provider and model
    print(f"Provider: {client.provider}")
    print(f"Model: {client.model}")
    print("Testing connection to Gemini API...")
    
    try:
        response = client.ask("Hi! Please reply with exactly: 'Gemini API is online and working.'")
        print("\n--- RESPONSE SUCCESS ---")
        print(f"Gemini replied: {response}")
    except Exception as e:
        print("\n--- RESPONSE ERROR ---")
        print(f"Failed to get a response: {e}")

if __name__ == "__main__":
    test_gemini()
