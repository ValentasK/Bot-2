import os

from dotenv import load_dotenv
from openai import OpenAI


def greet(name):
    return f"Hello, {name}!"


def ask_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Call OpenAI's Responses API with the provided prompt."""
    load_dotenv()  # ensures values from a local .env file are available
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set the OPENAI_API_KEY environment variable before calling OpenAI.")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(model=model, input=prompt)
    return response.output_text



for i in range(5):
    print(greet(i + 1))

    try:
        message = ask_openai("Give me a friendly greeting for a programmer.")
        print(message)
    except Exception as exc:
        print(f"OpenAI call failed: {exc}")

