import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def generate_ai_response(prompt: str) -> str:
    """
    Sends a prompt to the AI model and returns the answer.
    """

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_api_key_here":
        return "OpenAI API key is missing. Please add your real API key in backend/.env."

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )

        return response.output_text

    except Exception as e:
        return f"AI error: {str(e)}"