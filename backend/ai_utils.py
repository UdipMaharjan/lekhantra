import os
from pathlib import Path

_client = None
_environment_loaded = False


def _load_environment() -> None:
    """Load the local environment file on first use, not at app startup."""
    global _environment_loaded
    if not _environment_loaded:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))
        _environment_loaded = True


def get_openai_client():
    """Create the OpenAI client only when an AI endpoint is used."""
    global _client
    if _client is None:
        from openai import OpenAI

        _load_environment()
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def generate_ai_response(prompt: str) -> str:
    """
    Sends a prompt to the AI model and returns the answer.
    """

    _load_environment()

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_api_key_here":
        return "OpenAI API key is missing. Please add your real API key in backend/.env."

    try:
        response = get_openai_client().responses.create(
            model="gpt-4o-mini",
            input=prompt
        )

        return response.output_text

    except Exception as e:
        return f"AI error: {str(e)}"
